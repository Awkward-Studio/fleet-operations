import datetime
from django.db import models, transaction
from django.core.exceptions import ValidationError


class LegalEntity(models.Model):
    legal_name = models.CharField(max_length=150)
    trade_name = models.CharField(max_length=150, blank=True)
    pan = models.CharField(max_length=20, blank=True)
    gstin = models.CharField(max_length=20, blank=True)
    state_code = models.CharField(max_length=5, blank=True)
    registered_address = models.TextField(blank=True)
    billing_email = models.EmailField(blank=True)
    billing_phone = models.CharField(max_length=30, blank=True)
    bank_name = models.CharField(max_length=100, blank=True)
    bank_account_number = models.CharField(max_length=40, blank=True)
    ifsc_code = models.CharField(max_length=20, blank=True)
    bank_branch = models.CharField(max_length=100, blank=True)
    invoice_notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["legal_name"]

    def __str__(self):
        return f"{self.legal_name} ({self.gstin or 'No GSTIN'})"


class FinancialYear(models.Model):
    name = models.CharField(max_length=50, unique=True)  # e.g. "FY 2025-26"
    start_date = models.DateField()
    end_date = models.DateField()
    is_closed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        status = "Closed" if self.is_closed else "Open"
        return f"{self.name} ({status})"

    def clean(self):
        super().clean()
        if self.end_date <= self.start_date:
            raise ValidationError({"end_date": "Financial year end date must be after start date."})


class FiscalPeriod(models.Model):
    financial_year = models.ForeignKey(FinancialYear, related_name="periods", on_delete=models.CASCADE)
    period_number = models.PositiveIntegerField()  # 1 to 12
    name = models.CharField(max_length=50)  # e.g. "Apr 2025"
    start_date = models.DateField()
    end_date = models.DateField()
    is_locked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["financial_year", "period_number"]
        constraints = [
            models.UniqueConstraint(fields=["financial_year", "period_number"], name="unique_period_per_fy")
        ]

    def __str__(self):
        locked = "Locked" if self.is_locked else "Open"
        return f"{self.name} - Period {self.period_number} ({locked})"


class DocumentType(models.TextChoices):
    INVOICE = "INVOICE", "Tax Invoice"
    CREDIT_NOTE = "CREDIT_NOTE", "Credit Note"
    DEBIT_NOTE = "DEBIT_NOTE", "Debit Note"
    RECEIPT = "RECEIPT", "Payment Receipt"
    EXPENSE = "EXPENSE", "Trip / Vendor Expense"
    JOURNAL = "JOURNAL", "Journal Entry"


class DocumentSequence(models.Model):
    legal_entity = models.ForeignKey(LegalEntity, related_name="sequences", on_delete=models.CASCADE)
    financial_year = models.ForeignKey(FinancialYear, related_name="sequences", on_delete=models.CASCADE)
    document_type = models.CharField(max_length=30, choices=DocumentType.choices)
    prefix = models.CharField(max_length=20, default="INV/")
    current_number = models.PositiveIntegerField(default=0)
    padding_digits = models.PositiveIntegerField(default=5)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["legal_entity", "financial_year", "document_type"],
                name="unique_sequence_per_entity_fy_type",
            )
        ]

    def __str__(self):
        return f"{self.prefix}{str(self.current_number).zfill(self.padding_digits)} ({self.document_type})"

    @classmethod
    def get_next_number(cls, legal_entity, financial_year, document_type, prefix="INV/"):
        with transaction.atomic():
            seq, created = cls.objects.select_for_update().get_or_create(
                legal_entity=legal_entity,
                financial_year=financial_year,
                document_type=document_type,
                defaults={
                    "prefix": prefix,
                    "current_number": 0,
                    "padding_digits": 5,
                },
            )
            seq.current_number += 1
            seq.save(update_fields=["current_number", "updated_at"])
            number_str = str(seq.current_number).zfill(seq.padding_digits)
            return f"{seq.prefix}{number_str}"


class CloseoutStatus(models.TextChoices):
    INCOMPLETE = "INCOMPLETE", "Incomplete"
    SUBMITTED = "SUBMITTED", "Submitted for Review"
    EXCEPTION_REVIEW = "EXCEPTION_REVIEW", "Exception Review"
    APPROVED = "APPROVED", "Approved"
    BILLING_READY = "BILLING_READY", "Billing Ready"
    REOPENED = "REOPENED", "Reopened"


class ChargeCategory(models.TextChoices):
    TOLL = "TOLL", "Toll Charges"
    PARKING = "PARKING", "Parking Fee"
    STATE_PERMIT_TAX = "STATE_PERMIT_TAX", "State / Permit Tax"
    WAITING_CHARGE = "WAITING_CHARGE", "Waiting Charges"
    NIGHT_ALLOWANCE = "NIGHT_ALLOWANCE", "Night Halt Allowance"
    DRIVER_ALLOWANCE = "DRIVER_ALLOWANCE", "Driver Allowance"
    DISCOUNT = "DISCOUNT", "Discount"
    OTHER_EXTRA = "OTHER_EXTRA", "Other Extra Charge"


class TripCloseout(models.Model):
    trip = models.OneToOneField("fleet.Trip", related_name="closeout", on_delete=models.CASCADE)
    status = models.CharField(max_length=30, choices=CloseoutStatus.choices, default=CloseoutStatus.INCOMPLETE)
    actual_pickup_at = models.DateTimeField(null=True, blank=True)
    actual_drop_at = models.DateTimeField(null=True, blank=True)
    start_odometer_km = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    end_odometer_km = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    actual_km = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    waiting_minutes = models.PositiveIntegerField(default=0)
    overtime_minutes = models.PositiveIntegerField(default=0)
    completion_notes = models.TextField(blank=True)
    approved_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL)
    approved_at = models.DateTimeField(null=True, blank=True)
    billing_ready = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        if self.end_odometer_km < self.start_odometer_km:
            raise ValidationError({"end_odometer_km": "End odometer reading cannot be less than start odometer reading."})

    def save(self, *args, **kwargs):
        if self.end_odometer_km >= self.start_odometer_km:
            self.actual_km = self.end_odometer_km - self.start_odometer_km
        if self.status in [CloseoutStatus.APPROVED, CloseoutStatus.BILLING_READY]:
            self.billing_ready = True
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Closeout Trip #{self.trip_id} ({self.status})"


class TripCharge(models.Model):
    closeout = models.ForeignKey(TripCloseout, related_name="extra_charges", on_delete=models.CASCADE)
    category = models.CharField(max_length=30, choices=ChargeCategory.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=200, blank=True)
    receipt_attachment_url = models.URLField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.category}: ₹{self.amount} for Closeout #{self.closeout_id}"


class InvoiceStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    REVIEW = "REVIEW", "In Review"
    APPROVED = "APPROVED", "Approved"
    ISSUED = "ISSUED", "Issued"
    SENT = "SENT", "Sent to Customer"
    PARTIALLY_PAID = "PARTIALLY_PAID", "Partially Paid"
    PAID = "PAID", "Paid"
    OVERDUE = "OVERDUE", "Overdue"
    VOID = "VOID", "Void"
    CREDITED = "CREDITED", "Credited / Refunded"


class Invoice(models.Model):
    legal_entity = models.ForeignKey(LegalEntity, related_name="invoices", on_delete=models.PROTECT)
    customer = models.ForeignKey("fleet.CorporateCustomer", related_name="invoices", null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=30, choices=InvoiceStatus.choices, default=InvoiceStatus.DRAFT)
    invoice_number = models.CharField(max_length=50, unique=True, null=True, blank=True)
    financial_year = models.ForeignKey(FinancialYear, related_name="invoices", on_delete=models.PROTECT)
    fiscal_period = models.ForeignKey(FiscalPeriod, related_name="invoices", null=True, blank=True, on_delete=models.PROTECT)
    issue_date = models.DateField(default=datetime.date.today)
    due_date = models.DateField(default=datetime.date.today)
    currency = models.CharField(max_length=10, default="INR")
    place_of_supply = models.CharField(max_length=100, default="Maharashtra (27)")
    po_number = models.CharField(max_length=80, blank=True)
    billing_name_snapshot = models.CharField(max_length=150, blank=True)
    billing_address_snapshot = models.TextField(blank=True)
    gstin_snapshot = models.CharField(max_length=20, blank=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    taxable_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    igst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    rounding_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        super().clean()
        if self.status in [InvoiceStatus.ISSUED, InvoiceStatus.SENT, InvoiceStatus.PAID]:
            if self.pk:
                original = Invoice.objects.get(pk=self.pk)
                if original.status in [InvoiceStatus.ISSUED, InvoiceStatus.SENT, InvoiceStatus.PAID]:
                    if self.total_amount != original.total_amount:
                        raise ValidationError("Monetary total on an issued invoice cannot be modified.")

    def save(self, *args, **kwargs):
        self.balance_amount = self.total_amount - self.paid_amount
        super().save(*args, **kwargs)

    def __str__(self):
        number = self.invoice_number or f"DRAFT-{self.id}"
        return f"Invoice {number} - ₹{self.total_amount} ({self.status})"


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, related_name="lines", on_delete=models.CASCADE)
    description = models.CharField(max_length=250)
    sac_hsn_code = models.CharField(max_length=20, default="996601")
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_rate = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    taxable_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cgst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=2.50)
    cgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sgst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=2.50)
    sgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.description}: ₹{self.line_total}"


class InvoiceTrip(models.Model):
    invoice = models.ForeignKey(Invoice, related_name="invoice_trips", on_delete=models.CASCADE)
    trip = models.OneToOneField("fleet.Trip", related_name="invoice_link", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Invoice #{self.invoice_id} -> Trip #{self.trip_id}"


class CreditNote(models.Model):
    credit_note_number = models.CharField(max_length=50, unique=True)
    invoice = models.ForeignKey(Invoice, related_name="credit_notes", on_delete=models.PROTECT)
    legal_entity = models.ForeignKey(LegalEntity, related_name="credit_notes", on_delete=models.PROTECT)
    reason = models.CharField(max_length=250)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Credit Note {self.credit_note_number}: ₹{self.total_amount}"


class AccountType(models.TextChoices):
    ASSET = "ASSET", "Asset"
    LIABILITY = "LIABILITY", "Liability"
    EQUITY = "EQUITY", "Equity"
    REVENUE = "REVENUE", "Revenue"
    EXPENSE = "EXPENSE", "Expense"


class LedgerAccount(models.Model):
    code = models.CharField(max_length=30, unique=True)  # e.g. "1100"
    name = models.CharField(max_length=120)  # e.g. "Accounts Receivable"
    account_type = models.CharField(max_length=30, choices=AccountType.choices)
    external_mapping_code = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name} ({self.account_type})"


class JournalEntry(models.Model):
    entry_number = models.CharField(max_length=50, unique=True)
    legal_entity = models.ForeignKey(LegalEntity, related_name="journals", on_delete=models.PROTECT)
    financial_year = models.ForeignKey(FinancialYear, related_name="journals", on_delete=models.PROTECT)
    fiscal_period = models.ForeignKey(FiscalPeriod, related_name="journals", null=True, blank=True, on_delete=models.PROTECT)
    entry_date = models.DateField(default=datetime.date.today)
    source_type = models.CharField(max_length=50)  # e.g. "INVOICE", "RECEIPT", "EXPENSE"
    source_id = models.CharField(max_length=50)
    narration = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Journal {self.entry_number} ({self.source_type} #{self.source_id})"


class JournalLine(models.Model):
    journal_entry = models.ForeignKey(JournalEntry, related_name="lines", on_delete=models.CASCADE)
    account = models.ForeignKey(LedgerAccount, related_name="journal_lines", on_delete=models.PROTECT)
    debit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    credit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    narration = models.CharField(max_length=250, blank=True)

    def __str__(self):
        return f"{self.account.code}: Dr ₹{self.debit_amount} | Cr ₹{self.credit_amount}"


class PaymentMethod(models.TextChoices):
    BANK_TRANSFER = "BANK_TRANSFER", "Bank Transfer / NEFT / RTGS"
    UPI = "UPI", "UPI Payment"
    CHEQUE = "CHEQUE", "Cheque"
    CASH = "CASH", "Cash"
    CREDIT_CARD = "CREDIT_CARD", "Credit / Debit Card"


class PaymentReceipt(models.Model):
    receipt_number = models.CharField(max_length=50, unique=True)
    legal_entity = models.ForeignKey(LegalEntity, related_name="receipts", on_delete=models.PROTECT)
    customer = models.ForeignKey("fleet.CorporateCustomer", related_name="receipts", null=True, blank=True, on_delete=models.SET_NULL)
    receipt_date = models.DateField(default=datetime.date.today)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    unapplied_amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=30, choices=PaymentMethod.choices, default=PaymentMethod.BANK_TRANSFER)
    reference_number = models.CharField(max_length=100, blank=True)
    created_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.pk and self.unapplied_amount is None:
            self.unapplied_amount = self.amount
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Receipt {self.receipt_number}: ₹{self.amount} ({self.payment_method})"


class PaymentAllocation(models.Model):
    receipt = models.ForeignKey(PaymentReceipt, related_name="allocations", on_delete=models.CASCADE)
    invoice = models.ForeignKey(Invoice, related_name="allocations", on_delete=models.CASCADE)
    allocated_amount = models.DecimalField(max_digits=12, decimal_places=2)
    tds_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Allocated ₹{self.allocated_amount} from {self.receipt.receipt_number} to {self.invoice.invoice_number}"


class ExpenseCategory(models.TextChoices):
    FUEL = "FUEL", "Fuel Charges"
    TOLL = "TOLL", "Toll & Fastag"
    PARKING = "PARKING", "Parking Fee"
    STATE_TAX = "STATE_TAX", "State / Entry Permit Tax"
    MAINTENANCE = "MAINTENANCE", "Vehicle Maintenance"
    DRIVER_ALLOWANCE = "DRIVER_ALLOWANCE", "Driver Allowance"
    VENDOR_CHARGE = "VENDOR_CHARGE", "Outsourced Vendor Charge"
    MISC = "MISC", "Miscellaneous Expense"


class ExpenseStatus(models.TextChoices):
    SUBMITTED = "SUBMITTED", "Submitted"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"
    SETTLED = "SETTLED", "Settled"


class SupplierProfile(models.Model):
    name = models.CharField(max_length=150)
    pan = models.CharField(max_length=20, blank=True)
    gstin = models.CharField(max_length=20, blank=True)
    bank_account = models.CharField(max_length=40, blank=True)
    ifsc = models.CharField(max_length=20, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.gstin or 'Vendor'})"


class TripExpense(models.Model):
    trip = models.ForeignKey("fleet.Trip", related_name="expenses", null=True, blank=True, on_delete=models.SET_NULL)
    supplier = models.ForeignKey(SupplierProfile, related_name="expenses", null=True, blank=True, on_delete=models.SET_NULL)
    category = models.CharField(max_length=30, choices=ExpenseCategory.choices, default=ExpenseCategory.FUEL)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=24, choices=ExpenseStatus.choices, default=ExpenseStatus.SUBMITTED)
    evidence_url = models.URLField(max_length=500, blank=True)
    description = models.CharField(max_length=250, blank=True)
    approved_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.category}: ₹{self.amount} ({self.status})"





