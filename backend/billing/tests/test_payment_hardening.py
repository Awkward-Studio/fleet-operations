from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status

from billing.models import LegalEntity, Invoice, InvoiceStatus, FinancialYear, PaymentReceipt, PaymentAllocation
from fleet.models import CorporateCustomer
from billing.services import PaymentService
from accounts.models import UserRole

User = get_user_model()

class PaymentHardeningTests(TestCase):
    def setUp(self):
        self.entity = LegalEntity.objects.create(
            legal_name="Test Logistics",
            trade_name="TestLog",
            gstin="27AAAAA1111A1Z1",
            state_code="MH"
        )
        self.entity2 = LegalEntity.objects.create(
            legal_name="Test Logistics 2",
            trade_name="TestLog2",
            gstin="27AAAAA1111A1Z2",
            state_code="MH"
        )
        self.customer = CorporateCustomer.objects.create(
            code="CUST_1",
            legal_name="Test Corp Client",
            display_name="Test Corp"
        )
        self.customer2 = CorporateCustomer.objects.create(
            code="CUST_2",
            legal_name="Test Corp Client 2",
            display_name="Test Corp 2"
        )
        self.year = FinancialYear.objects.create(
            name="FY 2026-27",
            start_date="2026-04-01",
            end_date="2027-03-31",
            is_closed=False
        )
        self.invoice = Invoice.objects.create(
            legal_entity=self.entity,
            customer=self.customer,
            status=InvoiceStatus.ISSUED,
            total_amount=Decimal("1000.00"),
            balance_amount=Decimal("1000.00"),
            currency="INR",
            financial_year=self.year
        )
        self.user = User.objects.create_user(
            username="billing_op",
            email="billing@test.com",
            password="pass"
        )

    def test_record_receipt_invalid_amount(self):
        with self.assertRaises(ValidationError):
            PaymentService.record_receipt(
                legal_entity=self.entity,
                customer=self.customer,
                amount=Decimal("-100.00"),
                currency="INR",
                created_by=self.user
            )

        with self.assertRaises(ValidationError):
            PaymentService.record_receipt(
                legal_entity=self.entity,
                customer=self.customer,
                amount=Decimal("0.00"),
                currency="INR",
                created_by=self.user
            )

    def test_record_receipt_idempotency(self):
        key = "idemp-key-123"
        receipt1 = PaymentService.record_receipt(
            legal_entity=self.entity,
            customer=self.customer,
            amount=Decimal("500.00"),
            currency="INR",
            idempotency_key=key,
            created_by=self.user
        )
        receipt2 = PaymentService.record_receipt(
            legal_entity=self.entity,
            customer=self.customer,
            amount=Decimal("500.00"),
            currency="INR",
            idempotency_key=key,
            created_by=self.user
        )
        self.assertEqual(receipt1.id, receipt2.id)

    def test_allocate_payment_entity_mismatch(self):
        receipt = PaymentService.record_receipt(
            legal_entity=self.entity2,  # Different legal entity
            customer=self.customer,
            amount=Decimal("500.00"),
            currency="INR",
            created_by=self.user
        )
        with self.assertRaisesMessage(ValidationError, "same legal entity"):
            PaymentService.allocate_payment(receipt, self.invoice, Decimal("100.00"))

    def test_allocate_payment_customer_mismatch(self):
        receipt = PaymentService.record_receipt(
            legal_entity=self.entity,
            customer=self.customer2,  # Different customer
            amount=Decimal("500.00"),
            currency="INR",
            created_by=self.user
        )
        with self.assertRaisesMessage(ValidationError, "same customer"):
            PaymentService.allocate_payment(receipt, self.invoice, Decimal("100.00"))

    def test_allocate_payment_currency_mismatch(self):
        receipt = PaymentService.record_receipt(
            legal_entity=self.entity,
            customer=self.customer,
            amount=Decimal("500.00"),
            currency="USD",  # Mismatching currency
            created_by=self.user
        )
        with self.assertRaisesMessage(ValidationError, "currency must match"):
            PaymentService.allocate_payment(receipt, self.invoice, Decimal("100.00"))

    def test_allocate_payment_negative_amounts(self):
        receipt = PaymentService.record_receipt(
            legal_entity=self.entity,
            customer=self.customer,
            amount=Decimal("500.00"),
            currency="INR",
            created_by=self.user
        )
        with self.assertRaisesMessage(ValidationError, "cannot be negative"):
            PaymentService.allocate_payment(receipt, self.invoice, Decimal("-100.00"))

        with self.assertRaisesMessage(ValidationError, "cannot be negative"):
            PaymentService.allocate_payment(receipt, self.invoice, Decimal("100.00"), tds_amount=Decimal("-10.00"))

    def test_allocate_payment_both_zero(self):
        receipt = PaymentService.record_receipt(
            legal_entity=self.entity,
            customer=self.customer,
            amount=Decimal("500.00"),
            currency="INR",
            created_by=self.user
        )
        with self.assertRaisesMessage(ValidationError, "allocate a positive amount"):
            PaymentService.allocate_payment(receipt, self.invoice, Decimal("0.00"), tds_amount=Decimal("0.00"))

    def test_allocate_payment_exceed_receipt_unapplied(self):
        receipt = PaymentService.record_receipt(
            legal_entity=self.entity,
            customer=self.customer,
            amount=Decimal("100.00"),
            currency="INR",
            created_by=self.user
        )
        with self.assertRaisesMessage(ValidationError, "unapplied balance"):
            PaymentService.allocate_payment(receipt, self.invoice, Decimal("150.00"))

    def test_allocate_payment_exceed_invoice_balance(self):
        receipt = PaymentService.record_receipt(
            legal_entity=self.entity,
            customer=self.customer,
            amount=Decimal("2000.00"),
            currency="INR",
            created_by=self.user
        )
        with self.assertRaisesMessage(ValidationError, "remaining balance"):
            PaymentService.allocate_payment(receipt, self.invoice, Decimal("1200.00"))
            
        with self.assertRaisesMessage(ValidationError, "remaining balance"):
            PaymentService.allocate_payment(receipt, self.invoice, Decimal("900.00"), tds_amount=Decimal("150.00"))

    def test_journal_entry_posting(self):
        from billing.models import JournalEntry, JournalLine
        
        # Test receipt posting
        receipt = PaymentService.record_receipt(
            legal_entity=self.entity,
            customer=self.customer,
            amount=Decimal("500.00"),
            currency="INR",
            created_by=self.user
        )
        jv_rec = JournalEntry.objects.filter(source_type="PAYMENT_RECEIPT", source_id=str(receipt.id)).first()
        self.assertIsNotNone(jv_rec)
        lines = list(jv_rec.lines.all())
        self.assertEqual(len(lines), 2)
        dr_line = next(l for l in lines if l.debit_amount > 0)
        cr_line = next(l for l in lines if l.credit_amount > 0)
        self.assertEqual(dr_line.account.code, "1000")
        self.assertEqual(dr_line.debit_amount, Decimal("500.00"))
        self.assertEqual(cr_line.account.code, "2360")
        self.assertEqual(cr_line.credit_amount, Decimal("500.00"))

        # Test allocation posting (with TDS)
        allocation = PaymentService.allocate_payment(receipt, self.invoice, Decimal("200.00"), tds_amount=Decimal("20.00"))
        jv_alloc = JournalEntry.objects.filter(source_type="PAYMENT_ALLOCATION", source_id=str(allocation.id)).first()
        self.assertIsNotNone(jv_alloc)
        alloc_lines = list(jv_alloc.lines.all())
        self.assertEqual(len(alloc_lines), 4)
        
        # Dr Unapplied Cash (200), Cr AR (200)
        # Dr TDS (20), Cr AR (20)
        dr_clearing = next(l for l in alloc_lines if l.account.code == "2360" and l.debit_amount > 0)
        self.assertEqual(dr_clearing.debit_amount, Decimal("200.00"))
        
        dr_tds = next(l for l in alloc_lines if l.account.code == "1300" and l.debit_amount > 0)
        self.assertEqual(dr_tds.debit_amount, Decimal("20.00"))
        
        cr_ar_total = sum(l.credit_amount for l in alloc_lines if l.account.code == "1100" and l.credit_amount > 0)
        self.assertEqual(cr_ar_total, Decimal("220.00"))

    def test_reversal_flow(self):
        from billing.models import JournalEntry
        
        receipt = PaymentService.record_receipt(
            legal_entity=self.entity,
            customer=self.customer,
            amount=Decimal("500.00"),
            currency="INR",
            created_by=self.user
        )
        allocation = PaymentService.allocate_payment(receipt, self.invoice, Decimal("200.00"), tds_amount=Decimal("20.00"))
        
        # Test reverse single allocation
        PaymentService.reverse_allocation(allocation)
        allocation.refresh_from_db()
        receipt.refresh_from_db()
        self.invoice.refresh_from_db()
        
        self.assertTrue(allocation.is_reversed)
        self.assertEqual(receipt.unapplied_amount, Decimal("500.00")) # Restored
        self.assertEqual(self.invoice.paid_amount, Decimal("0.00"))
        self.assertEqual(self.invoice.status, InvoiceStatus.ISSUED)
        
        # Verify reversal journal was created
        rev_jv = JournalEntry.objects.filter(source_type="PAYMENT_ALLOCATION_REVERSAL", source_id=str(allocation.id)).first()
        self.assertIsNotNone(rev_jv)
        
        # Test reverse receipt
        # Re-allocate
        allocation2 = PaymentService.allocate_payment(receipt, self.invoice, Decimal("200.00"))
        PaymentService.reverse_receipt(receipt, reason="Double payment entry")
        
        receipt.refresh_from_db()
        allocation2.refresh_from_db()
        self.invoice.refresh_from_db()
        
        self.assertTrue(receipt.is_reversed)
        self.assertEqual(receipt.unapplied_amount, Decimal("0.00"))
        self.assertTrue(allocation2.is_reversed) # Associated allocations also reversed automatically!
        self.assertEqual(self.invoice.paid_amount, Decimal("0.00"))
        
        # Verify receipt reversal journal
        rev_rec_jv = JournalEntry.objects.filter(source_type="PAYMENT_RECEIPT_REVERSAL", source_id=str(receipt.id)).first()
        self.assertIsNotNone(rev_rec_jv)


class PaymentAPITests(APITestCase):
    def setUp(self):
        self.entity = LegalEntity.objects.create(
            legal_name="Test Logistics API",
            trade_name="TestLogAPI",
            gstin="27AAAAA1111A1Z1",
            state_code="MH"
        )
        self.customer = CorporateCustomer.objects.create(
            code="API_CUST",
            legal_name="API Corp Client",
            display_name="API Corp"
        )
        self.year = FinancialYear.objects.create(
            name="FY 2026-27",
            start_date="2026-04-01",
            end_date="2027-03-31",
            is_closed=False
        )
        self.invoice = Invoice.objects.create(
            legal_entity=self.entity,
            customer=self.customer,
            status=InvoiceStatus.ISSUED,
            total_amount=Decimal("1000.00"),
            balance_amount=Decimal("1000.00"),
            currency="INR",
            financial_year=self.year
        )
        
        self.accountant = User.objects.create_user(
            username="acc_api",
            email="acc_api@test.com",
            password="pass",
            role=UserRole.ACCOUNTANT
        )
        self.accountant.assigned_legal_entities.add(self.entity)
        
        self.auditor = User.objects.create_user(
            username="auditor_api",
            email="auditor_api@test.com",
            password="pass",
            role=UserRole.AUDITOR
        )
        
        self.client.force_authenticate(user=self.accountant)

    def test_receipt_lifecycle_api(self):
        # Create receipt
        url = reverse("receipt-list")
        data = {
            "legal_entity": self.entity.id,
            "customer": self.customer.id,
            "amount": "600.00",
            "currency": "INR",
            "payment_method": "BANK_TRANSFER"
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        receipt_id = response.data["id"]
        self.assertEqual(response.data["unapplied_amount"], "600.00")
        self.assertIsNotNone(response.data["journal_entry_number"])
        self.assertEqual(response.data["allocations"], [])

        # Allocate
        alloc_url = reverse("allocation-list")
        alloc_data = {
            "receipt": receipt_id,
            "invoice": self.invoice.id,
            "allocated_amount": "400.00",
            "tds_amount": "0.00"
        }
        alloc_res = self.client.post(alloc_url, alloc_data, format="json")
        self.assertEqual(alloc_res.status_code, status.HTTP_201_CREATED)
        alloc_id = alloc_res.data["id"]
        self.assertIsNotNone(alloc_res.data["journal_entry_number"])

        # Fetch receipt and check allocation history nested
        receipt_res = self.client.get(reverse("receipt-detail", kwargs={"pk": receipt_id}))
        self.assertEqual(receipt_res.status_code, status.HTTP_200_OK)
        self.assertEqual(receipt_res.data["unapplied_amount"], "200.00")
        self.assertEqual(len(receipt_res.data["allocations"]), 1)
        self.assertEqual(receipt_res.data["allocations"][0]["allocated_amount"], "400.00")

        # Test Auditor permission restriction (cannot reverse)
        self.client.force_authenticate(user=self.auditor)
        rev_url = reverse("receipt-reverse", kwargs={"pk": receipt_id})
        self.assertEqual(self.client.post(rev_url, {"reason": "Test"}).status_code, status.HTTP_403_FORBIDDEN)

        # Authenticate back as accountant
        self.client.force_authenticate(user=self.accountant)
        
        # Test reverse allocation
        alloc_rev_url = reverse("allocation-reverse", kwargs={"pk": alloc_id})
        alloc_rev_res = self.client.post(alloc_rev_url)
        self.assertEqual(alloc_rev_res.status_code, status.HTTP_200_OK)
        self.assertTrue(alloc_rev_res.data["is_reversed"])

        # Test reverse receipt
        rev_res = self.client.post(rev_url, {"reason": "Duplicate Entry"}, format="json")
        self.assertEqual(rev_res.status_code, status.HTTP_200_OK)
        self.assertTrue(rev_res.data["is_reversed"])

