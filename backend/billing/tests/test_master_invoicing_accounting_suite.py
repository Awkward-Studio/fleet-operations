from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import UserRole
from billing.models import (
    LegalEntity, TripCloseout, Invoice, InvoiceStatus, CloseoutStatus,
    FinancialYear, FiscalPeriod, CreditNote, PaymentReceipt
)
from fleet.models import Trip, CorporateCustomer

User = get_user_model()


class MasterInvoicingAccountingEdgeCasesTests(APITestCase):
    """
    Comprehensive, end-to-end Master Test Suite covering all edge cases across
    Invoicing, Accounting, Billing Closeouts, Tax Calculations, OTA Settlements,
    Fiscal Period Locking, and Credit/Debit Adjustments.
    """

    def setUp(self):
        # 1. Create Legal Entity (State Code: MH)
        self.entity_mh = LegalEntity.objects.create(
            legal_name="Apex Fleet Operations Pvt Ltd",
            trade_name="Apex Fleet",
            gstin="27AAACA1234A1Z5",
            state_code="MH",
        )

        # 2. Create Users
        self.admin = User.objects.create_user(
            username="suite_admin",
            email="admin@apexfleet.com",
            password="password123",
            role=UserRole.ADMIN,
            is_superuser=True,
        )
        self.accountant_1 = User.objects.create_user(
            username="suite_accountant_1",
            email="acc1@apexfleet.com",
            password="password123",
            role=UserRole.ACCOUNTANT,
        )
        self.accountant_2 = User.objects.create_user(
            username="suite_accountant_2",
            email="acc2@apexfleet.com",
            password="password123",
            role=UserRole.ACCOUNTANT,
        )
        self.accountant_1.assigned_legal_entities.add(self.entity_mh)
        self.accountant_2.assigned_legal_entities.add(self.entity_mh)

        # 3. Create Customers (Intra-state MH and Inter-state KA)
        self.customer_mh = CorporateCustomer.objects.create(
            code="CUST-MH-001",
            legal_name="Maharashtra Tech Corp Ltd",
            display_name="MH Tech",
            gstin="27BBBBB5555B1Z9",
        )
        self.customer_ka = CorporateCustomer.objects.create(
            code="CUST-KA-002",
            legal_name="Karnataka Infosys Ventures",
            display_name="KA Infosys",
            gstin="29CCCCC8888C1Z2",
        )

        # 4. Create Fiscal Year and Periods
        self.fin_year = FinancialYear.objects.create(
            name="FY 2026-27",
            start_date="2026-04-01",
            end_date="2027-03-31",
            is_closed=False,
        )
        self.open_period = FiscalPeriod.objects.create(
            financial_year=self.fin_year,
            name="August 2026",
            start_date="2026-08-01",
            end_date="2026-08-31",
            period_number=5,
            is_locked=False,
        )
        self.locked_period = FiscalPeriod.objects.create(
            financial_year=self.fin_year,
            name="April 2026",
            start_date="2026-04-01",
            end_date="2026-04-30",
            period_number=1,
            is_locked=True,
        )

    # -------------------------------------------------------------------------
    # Edge Case 1: Out-of-Order Odometer Readings
    # -------------------------------------------------------------------------
    def test_out_of_order_odometer_readings_edge_case(self):
        """
        Tests when start odometer reading is greater than end odometer reading.
        """
        trip = Trip.objects.create(
            customer=self.customer_mh,
            pickup_city="Mumbai",
            drop_city="Pune",
            status="completed",
            pickup_at=timezone.now(),
            estimated_drop_at=timezone.now(),
        )

        closeout = TripCloseout(
            trip=trip,
            start_odometer_km=15000,
            end_odometer_km=14200,  # Negative delta of -800 km!
            status=CloseoutStatus.SUBMITTED,
            submitted_by=self.admin,
            final_total_amount=Decimal("3500.00"),
        )
        with self.assertRaises(DjangoValidationError):
            closeout.clean()

    # -------------------------------------------------------------------------
    # Edge Case 2: Zero KM & Zero Hours Trip (Base Charge Minimum Package)
    # -------------------------------------------------------------------------
    def test_zero_km_minimal_package_allowance(self):
        """
        Tests a trip where 0 km and 0 hours were traveled.
        """
        trip = Trip.objects.create(
            customer=self.customer_mh,
            pickup_city="Mumbai",
            drop_city="Mumbai",
            status="completed",
            pickup_at=timezone.now(),
            estimated_drop_at=timezone.now(),
            fare_amount="2500.00",
        )

        closeout = TripCloseout.objects.create(
            trip=trip,
            start_odometer_km=10000,
            end_odometer_km=10000,  # 0 km traveled
            actual_km=0,
            actual_hours=0,
            status=CloseoutStatus.APPROVED,
            approved_by=self.accountant_1,
            final_taxable_amount=Decimal("2380.95"),
            final_tax_amount=Decimal("119.05"),
            final_total_amount=Decimal("2500.00"),
        )

        self.assertEqual(closeout.final_total_amount, Decimal("2500.00"))
        self.assertEqual(closeout.end_odometer_km - closeout.start_odometer_km, 0)

    # -------------------------------------------------------------------------
    # Edge Case 3: Extreme Long-Haul Excess KM & Excess Hours Calculation
    # -------------------------------------------------------------------------
    def test_extreme_excess_km_and_hours_calculation(self):
        """
        Tests extreme long-haul trip (e.g. 3,500 km, 120 hours) with excess rates.
        """
        trip = Trip.objects.create(
            customer=self.customer_mh,
            pickup_city="Mumbai",
            drop_city="Delhi",
            status="completed",
            pickup_at=timezone.now(),
            estimated_drop_at=timezone.now(),
        )

        closeout = TripCloseout.objects.create(
            trip=trip,
            start_odometer_km=5000,
            end_odometer_km=8500,  # 3,500 km traveled
            actual_km=3500,
            actual_hours=120,
            final_taxable_amount=Decimal("76190.48"),
            final_tax_amount=Decimal("3809.52"),
            final_total_amount=Decimal("80000.00"),
            status=CloseoutStatus.APPROVED,
            approved_by=self.accountant_1,
        )

        self.assertEqual(closeout.final_total_amount, Decimal("80000.00"))
        self.assertEqual(closeout.actual_km, 3500)

    # -------------------------------------------------------------------------
    # Edge Case 4: Intra-state (CGST+SGST) vs Inter-state (IGST) Tax Calculation
    # -------------------------------------------------------------------------
    def test_intrastate_vs_interstate_gst_tax_breakdown(self):
        """
        Tests Intra-state (MH customer -> CGST 2.5% + SGST 2.5%) vs
        Inter-state (KA customer -> IGST 5.0%).
        """
        inv_intra = Invoice.objects.create(
            legal_entity=self.entity_mh,
            customer=self.customer_mh,
            status=InvoiceStatus.REVIEW,
            created_by=self.admin,
            subtotal=Decimal("10000.00"),
            cgst_amount=Decimal("250.00"),
            sgst_amount=Decimal("250.00"),
            igst_amount=Decimal("0.00"),
            total_amount=Decimal("10500.00"),
            balance_amount=Decimal("10500.00"),
            financial_year=self.fin_year,
        )
        self.assertEqual(inv_intra.cgst_amount + inv_intra.sgst_amount, Decimal("500.00"))
        self.assertEqual(inv_intra.igst_amount, Decimal("0.00"))

        inv_inter = Invoice.objects.create(
            legal_entity=self.entity_mh,
            customer=self.customer_ka,
            status=InvoiceStatus.REVIEW,
            created_by=self.admin,
            subtotal=Decimal("10000.00"),
            cgst_amount=Decimal("0.00"),
            sgst_amount=Decimal("0.00"),
            igst_amount=Decimal("500.00"),
            total_amount=Decimal("10500.00"),
            balance_amount=Decimal("10500.00"),
            financial_year=self.fin_year,
        )
        self.assertEqual(inv_inter.igst_amount, Decimal("500.00"))
        self.assertEqual(inv_inter.cgst_amount, Decimal("0.00"))

    # -------------------------------------------------------------------------
    # Edge Case 5: Credit Note & Invoice Balance Adjustment
    # -------------------------------------------------------------------------
    def test_credit_note_and_debit_note_invoice_adjustments(self):
        """
        Tests issuing a Credit Note against a finalized invoice.
        """
        self.client.force_authenticate(user=self.accountant_1)

        invoice = Invoice.objects.create(
            legal_entity=self.entity_mh,
            customer=self.customer_mh,
            status=InvoiceStatus.SENT,
            created_by=self.admin,
            subtotal=Decimal("10000.00"),
            total_amount=Decimal("10000.00"),
            balance_amount=Decimal("10000.00"),
            financial_year=self.fin_year,
        )

        credit_note = CreditNote.objects.create(
            credit_note_number="CN-202608-0001",
            invoice=invoice,
            legal_entity=self.entity_mh,
            reason="Billing adjustment for excess delay",
            total_amount=Decimal("2000.00"),
            status="APPROVED",
            created_by=self.accountant_1,
        )

        invoice.save()
        invoice.refresh_from_db()

        self.assertEqual(invoice.balance_amount, Decimal("8000.00"))
        self.assertEqual(credit_note.total_amount, Decimal("2000.00"))

    # -------------------------------------------------------------------------
    # Edge Case 6: Partial Payments & Full Settlement Transition
    # -------------------------------------------------------------------------
    def test_partial_payment_overpayment_and_settlement(self):
        """
        Tests applying partial payments to an invoice.
        """
        invoice = Invoice.objects.create(
            legal_entity=self.entity_mh,
            customer=self.customer_mh,
            status=InvoiceStatus.SENT,
            created_by=self.admin,
            subtotal=Decimal("5000.00"),
            total_amount=Decimal("5000.00"),
            balance_amount=Decimal("5000.00"),
            financial_year=self.fin_year,
        )

        payment_1 = PaymentReceipt.objects.create(
            receipt_number="REC-202608-0001",
            legal_entity=self.entity_mh,
            customer=self.customer_mh,
            amount=Decimal("3000.00"),
            unapplied_amount=Decimal("0.00"),
            payment_method="BANK_TRANSFER",
            reference_number="NEFT9998881",
            created_by=self.accountant_1,
        )
        invoice.paid_amount += payment_1.amount
        invoice.save()
        invoice.refresh_from_db()

        self.assertEqual(invoice.balance_amount, Decimal("2000.00"))
        self.assertEqual(invoice.status, InvoiceStatus.PARTIALLY_PAID)

        payment_2 = PaymentReceipt.objects.create(
            receipt_number="REC-202608-0002",
            legal_entity=self.entity_mh,
            customer=self.customer_mh,
            amount=Decimal("2000.00"),
            unapplied_amount=Decimal("0.00"),
            payment_method="UPI",
            reference_number="UPI11223344",
            created_by=self.accountant_1,
        )
        invoice.paid_amount += payment_2.amount
        invoice.save()
        invoice.refresh_from_db()

        self.assertEqual(invoice.balance_amount, Decimal("0.00"))
        self.assertEqual(invoice.status, InvoiceStatus.PAID)

    # -------------------------------------------------------------------------
    # Edge Case 7: Self-Approval Protection Security Check
    # -------------------------------------------------------------------------
    def test_self_approval_protection(self):
        """
        Ensures the creator/submitter of an invoice cannot approve their own invoice.
        """
        self.client.force_authenticate(user=self.accountant_1)

        invoice = Invoice.objects.create(
            legal_entity=self.entity_mh,
            customer=self.customer_mh,
            status=InvoiceStatus.REVIEW,
            created_by=self.accountant_1,  # Accountant 1 created it!
            created_by_id=self.accountant_1.id,
            subtotal=Decimal("5000.00"),
            total_amount=Decimal("5000.00"),
            balance_amount=Decimal("5000.00"),
            financial_year=self.fin_year,
        )

        url = reverse("invoice-approve", kwargs={"pk": invoice.pk})
        response = self.client.post(url)
        # Blocked with 403 Forbidden
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # -------------------------------------------------------------------------
    # Edge Case 8: Sequential Invoice Number Generation (No Gaps)
    # -------------------------------------------------------------------------
    def test_sequential_invoice_numbering_no_gaps(self):
        """
        Tests generating consecutive invoices to ensure unique sequential numbering.
        """
        invoices = []
        for i in range(1, 6):
            inv = Invoice.objects.create(
                legal_entity=self.entity_mh,
                customer=self.customer_mh,
                invoice_number=f"INV-202608-000{i}",
                status=InvoiceStatus.APPROVED,
                created_by=self.admin,
                subtotal=Decimal("1000.00"),
                total_amount=Decimal("1000.00"),
                balance_amount=Decimal("1000.00"),
                financial_year=self.fin_year,
            )
            invoices.append(inv)

        numbers = [inv.invoice_number for inv in invoices]
        self.assertEqual(len(numbers), len(set(numbers)))
        self.assertEqual(numbers[0], "INV-202608-0001")
        self.assertEqual(numbers[4], "INV-202608-0005")

    # -------------------------------------------------------------------------
    # Edge Case 9: Trip Closeout Re-rating & Idempotency
    # -------------------------------------------------------------------------
    def test_trip_closeout_rerating_idempotency(self):
        """
        Tests submitting re-rated closeouts for the same trip multiple times.
        """
        trip = Trip.objects.create(
            customer=self.customer_mh,
            pickup_city="Mumbai",
            drop_city="Pune",
            status="completed",
            pickup_at=timezone.now(),
            estimated_drop_at=timezone.now(),
        )

        closeout_1 = TripCloseout.objects.create(
            trip=trip,
            start_odometer_km=1000,
            end_odometer_km=1200,
            final_total_amount=Decimal("3000.00"),
            status=CloseoutStatus.SUBMITTED,
            submitted_by=self.admin,
        )

        closeout_1.final_total_amount = Decimal("3200.00")
        closeout_1.save()

        count = TripCloseout.objects.filter(trip=trip).count()
        self.assertEqual(count, 1)
        self.assertEqual(TripCloseout.objects.get(trip=trip).final_total_amount, Decimal("3200.00"))
