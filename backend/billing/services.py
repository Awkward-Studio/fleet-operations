import datetime
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from .models import (
    LegalEntity,
    FinancialYear,
    FiscalPeriod,
    DocumentSequence,
    DocumentType,
    Invoice,
    InvoiceLine,
    InvoiceTrip,
    InvoiceStatus,
    TripCloseout,
    CloseoutStatus,
)
from .tax_service import TaxService, money
from fleet.models import PricingAmountStatus, Trip


class InvoiceService:
    @staticmethod
    def generate_invoice_draft(legal_entity: LegalEntity, trip_ids: list, created_by=None) -> Invoice:
        if not trip_ids:
            raise ValidationError("At least one trip must be provided to generate an invoice draft.")

        trips = list(
            Trip.objects.filter(id__in=trip_ids).select_related(
                "customer", "closeout", "contract"
            )
        )
        if len(trips) != len(trip_ids):
            raise ValidationError("One or more specified trips could not be found.")

        # Ensure all trips belong to the same customer (if corporate)
        customer = trips[0].customer
        for t in trips:
            if t.customer != customer:
                raise ValidationError("Consolidated invoice trips must belong to the same customer.")

            if InvoiceTrip.objects.filter(trip=t).exists():
                raise ValidationError(f"Trip #{t.id} has already been invoiced.")

            if t.pricing_amount_status not in (
                PricingAmountStatus.QUOTED,
                PricingAmountStatus.FINALIZED,
            ):
                raise ValidationError(
                    f"Trip #{t.id} has legacy or unclassified pricing. Reprice and approve "
                    "the trip before generating an invoice."
                )

            amount_prefix = (
                "final"
                if t.pricing_amount_status == PricingAmountStatus.FINALIZED
                else "quoted"
            )
            values = [
                getattr(t, f"{amount_prefix}_taxable_amount"),
                getattr(t, f"{amount_prefix}_tax_amount"),
                getattr(t, f"{amount_prefix}_total_amount"),
            ]
            if any(value is None for value in values) or money(values[0] + values[1]) != money(values[2]):
                raise ValidationError(
                    f"Trip #{t.id} pricing components are incomplete or unreconciled."
                )

            if (
                hasattr(t, "closeout")
                and t.closeout
                and t.closeout.extra_charges.exists()
                and t.closeout.status != CloseoutStatus.APPROVED
            ):
                raise ValidationError(
                    f"Trip #{t.id} has extra charges that must be approved before invoicing."
                )

        today = datetime.date.today()
        # Find active financial year & period
        fy = FinancialYear.objects.filter(start_date__lte=today, end_date__gte=today, is_closed=False).first()
        if not fy:
            # Fallback to latest open financial year
            fy = FinancialYear.objects.filter(is_closed=False).order_by("-start_date").first()
            if not fy:
                fy = FinancialYear.objects.create(
                    name=f"FY {today.year}-{str(today.year+1)[-2:]}",
                    start_date=datetime.date(today.year, 4, 1),
                    end_date=datetime.date(today.year + 1, 3, 31),
                )

        period = FiscalPeriod.objects.filter(financial_year=fy, start_date__lte=today, end_date__gte=today).first()
        if not period:
            period = fy.periods.first()
            if not period:
                period = FiscalPeriod.objects.create(
                    financial_year=fy,
                    period_number=1,
                    name=f"{today:%b %Y}",
                    start_date=datetime.date(today.year, today.month, 1),
                    end_date=datetime.date(today.year, today.month, 28),
                )

        with transaction.atomic():
            context = TaxService.determine_context(
                legal_entity=legal_entity,
                customer_gstin=customer.gstin if customer else "",
                place_of_supply="Maharashtra (27)",
            )
            invoice = Invoice.objects.create(
                legal_entity=legal_entity,
                customer=customer,
                status=InvoiceStatus.DRAFT,
                financial_year=fy,
                fiscal_period=period,
                issue_date=today,
                due_date=today + datetime.timedelta(days=customer.payment_terms_days if customer else 30),
                billing_name_snapshot=customer.display_name if customer else (trips[0].customer_name or "Retail Cash Customer"),
                billing_address_snapshot=customer.billing_address if customer else "",
                gstin_snapshot=customer.gstin if customer else "",
                supplier_state_code_snapshot=context.supplier_state_code,
                customer_state_code_snapshot=context.customer_state_code,
                tax_regime=context.regime,
                created_by=created_by,
            )

            total_taxable = Decimal("0.00")
            total_cgst = Decimal("0.00")
            total_sgst = Decimal("0.00")
            total_igst = Decimal("0.00")

            for t in trips:
                InvoiceTrip.objects.create(invoice=invoice, trip=t)

                amount_prefix = (
                    "final"
                    if t.pricing_amount_status == PricingAmountStatus.FINALIZED
                    else "quoted"
                )
                taxable = getattr(t, f"{amount_prefix}_taxable_amount")
                snapshot = t.pricing_snapshot or {}
                itemized = snapshot.get("itemized_charges", {})
                contract = t.contract
                cgst_rate = (
                    contract.cgst_rate if contract else itemized.get("cgst_rate", 0)
                )
                sgst_rate = (
                    contract.sgst_rate if contract else itemized.get("sgst_rate", 0)
                )
                tax = TaxService.calculate_line(
                    taxable_value=taxable,
                    cgst_rate=cgst_rate,
                    sgst_rate=sgst_rate,
                    context=context,
                )

                InvoiceLine.objects.create(
                    invoice=invoice,
                    description=f"Trip #{t.id}: {t.pickup_city} to {t.drop_city} ({t.duty_type or 'Local/Outstation'})",
                    quantity=Decimal("1.00"),
                    unit_rate=tax.taxable_value,
                    taxable_value=tax.taxable_value,
                    cgst_rate=tax.cgst_rate,
                    cgst_amount=tax.cgst_amount,
                    sgst_rate=tax.sgst_rate,
                    sgst_amount=tax.sgst_amount,
                    igst_rate=tax.igst_rate,
                    igst_amount=tax.igst_amount,
                    tax_regime=tax.regime,
                    source_type="TRIP_PRICING",
                    source_id=str(t.id),
                    calculation_version=snapshot.get("calculation_version", ""),
                    pricing_snapshot=snapshot,
                    line_total=tax.line_total,
                )

                total_taxable += tax.taxable_value
                total_cgst += tax.cgst_amount
                total_sgst += tax.sgst_amount
                total_igst += tax.igst_amount

                if (
                    hasattr(t, "closeout")
                    and t.closeout
                    and t.closeout.status == CloseoutStatus.APPROVED
                ):
                    for charge in t.closeout.extra_charges.all():
                        charge_tax = TaxService.calculate_line(
                            taxable_value=charge.amount,
                            cgst_rate=cgst_rate,
                            sgst_rate=sgst_rate,
                            context=context,
                        )

                        InvoiceLine.objects.create(
                            invoice=invoice,
                            description=f"Trip #{t.id} Extra: {charge.get_category_display()} - {charge.description or ''}".strip(),
                            quantity=Decimal("1.00"),
                            unit_rate=charge_tax.taxable_value,
                            taxable_value=charge_tax.taxable_value,
                            cgst_rate=charge_tax.cgst_rate,
                            cgst_amount=charge_tax.cgst_amount,
                            sgst_rate=charge_tax.sgst_rate,
                            sgst_amount=charge_tax.sgst_amount,
                            igst_rate=charge_tax.igst_rate,
                            igst_amount=charge_tax.igst_amount,
                            tax_regime=charge_tax.regime,
                            source_type="TRIP_CHARGE",
                            source_id=str(charge.id),
                            calculation_version=snapshot.get("calculation_version", ""),
                            pricing_snapshot={
                                "trip_id": t.id,
                                "charge_category": charge.category,
                                "approved_closeout_id": t.closeout.id,
                            },
                            line_total=charge_tax.line_total,
                        )
                        total_taxable += charge_tax.taxable_value
                        total_cgst += charge_tax.cgst_amount
                        total_sgst += charge_tax.sgst_amount
                        total_igst += charge_tax.igst_amount

            subtotal = total_taxable
            grand_total = subtotal + total_cgst + total_sgst + total_igst

            invoice.subtotal = subtotal
            invoice.taxable_amount = total_taxable
            invoice.cgst_amount = total_cgst
            invoice.sgst_amount = total_sgst
            invoice.igst_amount = total_igst
            invoice.total_amount = grand_total
            invoice.balance_amount = grand_total
            invoice.save()

            return invoice

    @staticmethod
    def issue_invoice(invoice: Invoice, created_by=None) -> Invoice:
        if invoice.status in [InvoiceStatus.ISSUED, InvoiceStatus.SENT, InvoiceStatus.PAID]:
            return invoice

        with transaction.atomic():
            prefix = f"INV/{invoice.financial_year.name.replace(' ', '')}/"
            inv_number = DocumentSequence.get_next_number(
                legal_entity=invoice.legal_entity,
                financial_year=invoice.financial_year,
                document_type=DocumentType.INVOICE,
                prefix=prefix,
            )
            invoice.invoice_number = inv_number
            invoice.status = InvoiceStatus.ISSUED
            invoice.issue_date = datetime.date.today()
            invoice.save()

            PostingEngine.post_invoice_journal(invoice)
            return invoice


class PostingEngine:
    @staticmethod
    def post_invoice_journal(invoice: Invoice) -> "JournalEntry":
        from .models import LedgerAccount, AccountType, JournalEntry, JournalLine

        with transaction.atomic():
            ar_account, _ = LedgerAccount.objects.get_or_create(
                code="1100",
                defaults={"name": "Accounts Receivable", "account_type": AccountType.ASSET, "external_mapping_code": "AR_1100"},
            )
            rev_account, _ = LedgerAccount.objects.get_or_create(
                code="4000",
                defaults={"name": "Passenger Transport Revenue", "account_type": AccountType.REVENUE, "external_mapping_code": "REV_4000"},
            )
            cgst_account, _ = LedgerAccount.objects.get_or_create(
                code="2100",
                defaults={"name": "Output CGST Payable", "account_type": AccountType.LIABILITY, "external_mapping_code": "TAX_2100"},
            )
            sgst_account, _ = LedgerAccount.objects.get_or_create(
                code="2200",
                defaults={"name": "Output SGST Payable", "account_type": AccountType.LIABILITY, "external_mapping_code": "TAX_2200"},
            )
            igst_account, _ = LedgerAccount.objects.get_or_create(
                code="2250",
                defaults={
                    "name": "Output IGST Payable",
                    "account_type": AccountType.LIABILITY,
                    "external_mapping_code": "TAX_2250",
                },
            )

            entry_number = f"JV/INV/{invoice.id}"
            journal, _ = JournalEntry.objects.get_or_create(
                entry_number=entry_number,
                defaults={
                    "legal_entity": invoice.legal_entity,
                    "financial_year": invoice.financial_year,
                    "fiscal_period": invoice.fiscal_period,
                    "entry_date": invoice.issue_date,
                    "source_type": "INVOICE",
                    "source_id": str(invoice.id),
                    "narration": f"Journal entry for Invoice #{invoice.invoice_number or invoice.id}",
                },
            )

            # Clear old lines if re-posting
            journal.lines.all().delete()

            # Dr Accounts Receivable
            JournalLine.objects.create(
                journal_entry=journal,
                account=ar_account,
                debit_amount=invoice.total_amount,
                credit_amount=Decimal("0.00"),
                narration=f"Arising from Invoice #{invoice.invoice_number}",
            )

            # Cr Revenue
            JournalLine.objects.create(
                journal_entry=journal,
                account=rev_account,
                debit_amount=Decimal("0.00"),
                credit_amount=invoice.taxable_amount,
                narration="Taxable revenue",
            )

            # Cr CGST
            if invoice.cgst_amount > Decimal("0.00"):
                JournalLine.objects.create(
                    journal_entry=journal,
                    account=cgst_account,
                    debit_amount=Decimal("0.00"),
                    credit_amount=invoice.cgst_amount,
                    narration="Output CGST",
                )

            # Cr SGST
            if invoice.sgst_amount > Decimal("0.00"):
                JournalLine.objects.create(
                    journal_entry=journal,
                    account=sgst_account,
                    debit_amount=Decimal("0.00"),
                    credit_amount=invoice.sgst_amount,
                    narration="Output SGST",
                )

            if invoice.igst_amount > Decimal("0.00"):
                JournalLine.objects.create(
                    journal_entry=journal,
                    account=igst_account,
                    debit_amount=Decimal("0.00"),
                    credit_amount=invoice.igst_amount,
                    narration="Output IGST",
                )

            total_debits = sum(line.debit_amount for line in journal.lines.all())
            total_credits = sum(line.credit_amount for line in journal.lines.all())
            if total_debits != total_credits:
                raise ValidationError(f"Journal entry #{entry_number} is unbalanced: Dr ₹{total_debits} vs Cr ₹{total_credits}")

            return journal

    @staticmethod
    def post_fuel_journal(fuel_transaction, trip_expense) -> "JournalEntry":
        from .models import LedgerAccount, AccountType, JournalEntry, JournalLine
        with transaction.atomic():
            fuel_exp_acc, _ = LedgerAccount.objects.get_or_create(
                code="5100",
                defaults={"name": "Fuel Expense", "account_type": AccountType.EXPENSE, "external_mapping_code": "EXP_5100"}
            )
            gst_in_acc, _ = LedgerAccount.objects.get_or_create(
                code="1200",
                defaults={"name": "Input GST Receivable", "account_type": AccountType.ASSET, "external_mapping_code": "TAX_1200"}
            )
            payable_acc, _ = LedgerAccount.objects.get_or_create(
                code="2300",
                defaults={"name": "Fuel Payables / Cash", "account_type": AccountType.LIABILITY, "external_mapping_code": "PAY_2300"}
            )

            today = datetime.date.today()
            fy = FinancialYear.objects.filter(start_date__lte=today, end_date__gte=today, is_closed=False).first()
            if not fy:
                fy = FinancialYear.objects.filter(is_closed=False).order_by("-start_date").first()
            if not fy:
                fy = FinancialYear.objects.create(
                    name=f"FY {today.year}-{str(today.year+1)[-2:]}",
                    start_date=datetime.date(today.year, 4, 1),
                    end_date=datetime.date(today.year+1, 3, 31),
                )
            period = FiscalPeriod.objects.filter(financial_year=fy, start_date__lte=today, end_date__gte=today).first()
            if not period:
                period = fy.periods.first()

            legal_entity = LegalEntity.objects.filter(is_active=True).first()
            if not legal_entity:
                legal_entity = LegalEntity.objects.create(
                    legal_name="Primary Fleet Entity",
                    is_active=True,
                )

            entry_number = f"JV/FUEL/{fuel_transaction.id}"
            journal, _ = JournalEntry.objects.get_or_create(
                entry_number=entry_number,
                defaults={
                    "legal_entity": legal_entity,
                    "financial_year": fy,
                    "fiscal_period": period,
                    "entry_date": today,
                    "source_type": "FUEL",
                    "source_id": str(fuel_transaction.id),
                    "narration": f"Journal entry for Fuel purchase for {fuel_transaction.vehicle.registration_number} @ {fuel_transaction.vendor}",
                },
            )

            journal.lines.all().delete()

            taxable_amt = fuel_transaction.total_amount - fuel_transaction.tax_amount
            JournalLine.objects.create(
                journal_entry=journal,
                account=fuel_exp_acc,
                debit_amount=taxable_amt,
                credit_amount=Decimal("0.00"),
                narration=f"Fuel cost excl tax",
            )
            if fuel_transaction.tax_amount > Decimal("0.00"):
                JournalLine.objects.create(
                    journal_entry=journal,
                    account=gst_in_acc,
                    debit_amount=fuel_transaction.tax_amount,
                    credit_amount=Decimal("0.00"),
                    narration="Input GST on fuel purchase",
                )

            JournalLine.objects.create(
                journal_entry=journal,
                account=payable_acc,
                debit_amount=Decimal("0.00"),
                credit_amount=fuel_transaction.total_amount,
                narration=f"Amount payable to {fuel_transaction.vendor}",
            )

            total_debits = sum(line.debit_amount for line in journal.lines.all())
            total_credits = sum(line.credit_amount for line in journal.lines.all())
            if total_debits != total_credits:
                raise ValidationError(f"Journal entry #{entry_number} is unbalanced: Dr ₹{total_debits} vs Cr ₹{total_credits}")

            return journal

    @staticmethod
    def post_fuel_reversal_journal(fuel_transaction) -> "JournalEntry":
        from .models import LedgerAccount, AccountType, JournalEntry, JournalLine
        with transaction.atomic():
            fuel_exp_acc, _ = LedgerAccount.objects.get_or_create(
                code="5100",
                defaults={"name": "Fuel Expense", "account_type": AccountType.EXPENSE, "external_mapping_code": "EXP_5100"}
            )
            gst_in_acc, _ = LedgerAccount.objects.get_or_create(
                code="1200",
                defaults={"name": "Input GST Receivable", "account_type": AccountType.ASSET, "external_mapping_code": "TAX_1200"}
            )
            payable_acc, _ = LedgerAccount.objects.get_or_create(
                code="2300",
                defaults={"name": "Fuel Payables / Cash", "account_type": AccountType.LIABILITY, "external_mapping_code": "PAY_2300"}
            )

            today = datetime.date.today()
            fy = FinancialYear.objects.filter(start_date__lte=today, end_date__gte=today, is_closed=False).first()
            if not fy:
                fy = FinancialYear.objects.filter(is_closed=False).order_by("-start_date").first()
            if not fy:
                fy = FinancialYear.objects.create(
                    name=f"FY {today.year}-{str(today.year+1)[-2:]}",
                    start_date=datetime.date(today.year, 4, 1),
                    end_date=datetime.date(today.year+1, 3, 31),
                )
            period = FiscalPeriod.objects.filter(financial_year=fy, start_date__lte=today, end_date__gte=today).first()
            if not period:
                period = fy.periods.first()

            legal_entity = LegalEntity.objects.filter(is_active=True).first()
            if not legal_entity:
                legal_entity = LegalEntity.objects.create(
                    legal_name="Primary Fleet Entity",
                    is_active=True,
                )

            entry_number = f"JV/FUEL/REV/{fuel_transaction.id}"
            journal, _ = JournalEntry.objects.get_or_create(
                entry_number=entry_number,
                defaults={
                    "legal_entity": legal_entity,
                    "financial_year": fy,
                    "fiscal_period": period,
                    "entry_date": today,
                    "source_type": "FUEL_REVERSAL",
                    "source_id": str(fuel_transaction.id),
                    "narration": f"Reversal of Fuel purchase for {fuel_transaction.vehicle.registration_number} @ {fuel_transaction.vendor} (Orig JV/FUEL/{fuel_transaction.id})",
                },
            )

            journal.lines.all().delete()

            JournalLine.objects.create(
                journal_entry=journal,
                account=payable_acc,
                debit_amount=fuel_transaction.total_amount,
                credit_amount=Decimal("0.00"),
                narration=f"Reversal of payable for {fuel_transaction.vendor}",
            )

            taxable_amt = fuel_transaction.total_amount - fuel_transaction.tax_amount
            JournalLine.objects.create(
                journal_entry=journal,
                account=fuel_exp_acc,
                debit_amount=Decimal("0.00"),
                credit_amount=taxable_amt,
                narration=f"Reversal of fuel cost",
            )

            if fuel_transaction.tax_amount > Decimal("0.00"):
                JournalLine.objects.create(
                    journal_entry=journal,
                    account=gst_in_acc,
                    debit_amount=Decimal("0.00"),
                    credit_amount=fuel_transaction.tax_amount,
                    narration="Reversal of Input GST on fuel",
                )

            total_debits = sum(line.debit_amount for line in journal.lines.all())
            total_credits = sum(line.credit_amount for line in journal.lines.all())
            if total_debits != total_credits:
                raise ValidationError(f"Journal entry #{entry_number} is unbalanced: Dr ₹{total_debits} vs Cr ₹{total_credits}")

            return journal


class PaymentService:
    @staticmethod
    def record_receipt(legal_entity, customer, amount, payment_method="BANK_TRANSFER", reference_number="", created_by=None):
        from .models import PaymentReceipt
        with transaction.atomic():
            fy = FinancialYear.objects.filter(is_closed=False).first()
            prefix = f"REC/{fy.name.replace(' ', '')}/" if fy else "REC/2026/"
            rec_num = DocumentSequence.get_next_number(
                legal_entity=legal_entity,
                financial_year=fy,
                document_type=DocumentType.RECEIPT,
                prefix=prefix,
            )
            receipt = PaymentReceipt.objects.create(
                receipt_number=rec_num,
                legal_entity=legal_entity,
                customer=customer,
                amount=amount,
                unapplied_amount=amount,
                payment_method=payment_method,
                reference_number=reference_number,
                created_by=created_by,
            )
            return receipt

    @staticmethod
    def allocate_payment(receipt, invoice, amount, tds_amount=Decimal("0.00")):
        from .models import PaymentAllocation
        if amount > receipt.unapplied_amount:
            raise ValidationError("Allocation amount cannot exceed receipt unapplied balance.")
        if (amount + tds_amount) > invoice.balance_amount:
            raise ValidationError("Allocation amount cannot exceed invoice remaining balance.")

        with transaction.atomic():
            allocation = PaymentAllocation.objects.create(
                receipt=receipt,
                invoice=invoice,
                allocated_amount=amount,
                tds_amount=tds_amount,
            )

            receipt.unapplied_amount -= amount
            receipt.save()

            total_credit = amount + tds_amount
            invoice.paid_amount += total_credit
            if invoice.paid_amount >= invoice.total_amount:
                invoice.status = InvoiceStatus.PAID
            elif invoice.paid_amount > Decimal("0.00"):
                invoice.status = InvoiceStatus.PARTIALLY_PAID
            invoice.save()

            return allocation
