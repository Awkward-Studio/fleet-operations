import datetime
from decimal import Decimal
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model

from billing.models import (
    LegalEntity, FinancialYear, Invoice, InvoiceLine, InvoiceStatus,
    CreditNote, CreditNoteLine, CreditNoteStatus,
    DebitNote, DebitNoteLine, DebitNoteStatus, JournalEntry
)
from fleet.models import CorporateCustomer
from accounts.models import UserRole
from billing.services import CreditNoteService, DebitNoteService

User = get_user_model()


class NotesHardeningTests(APITestCase):
    def setUp(self):
        self.entity = LegalEntity.objects.create(
            legal_name="Notes Test Logistics",
            trade_name="NotesLog",
            gstin="27BBBBB2222B2Z2",
            state_code="MH"
        )
        self.customer = CorporateCustomer.objects.create(
            code="NOTE_CUST",
            legal_name="Notes Corp Client",
            display_name="Notes Corp"
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
            total_amount=Decimal("1100.00"),
            taxable_amount=Decimal("1000.00"),
            cgst_amount=Decimal("50.00"),
            sgst_amount=Decimal("50.00"),
            balance_amount=Decimal("1100.00"),
            currency="INR",
            financial_year=self.year
        )
        self.inv_line = InvoiceLine.objects.create(
            invoice=self.invoice,
            description="Premium Ride Service",
            quantity=Decimal("2.00"),
            unit_rate=Decimal("500.00"),
            taxable_value=Decimal("1000.00"),
            cgst_rate=Decimal("5.00"),
            cgst_amount=Decimal("50.00"),
            sgst_rate=Decimal("5.00"),
            sgst_amount=Decimal("50.00"),
            line_total=Decimal("1100.00")
        )
        
        self.accountant = User.objects.create_user(
            username="acc_notes",
            email="acc_notes@test.com",
            password="pass",
            role=UserRole.ACCOUNTANT
        )
        self.accountant.assigned_legal_entities.add(self.entity)
        
        self.auditor = User.objects.create_user(
            username="auditor_notes",
            email="auditor_notes@test.com",
            password="pass",
            role=UserRole.AUDITOR
        )
        
        self.client.force_authenticate(user=self.accountant)

    def test_credit_note_lifecycle_service(self):
        # Create CreditNote (Draft)
        lines_data = [
            {
                "invoice_line_id": self.inv_line.id,
                "quantity": 1,
                "unit_rate": 500
            }
        ]
        cn = CreditNoteService.create_credit_note(
            invoice=self.invoice,
            reason="Partial credit request",
            lines_data=lines_data,
            created_by=self.accountant
        )
        self.assertEqual(cn.status, CreditNoteStatus.DRAFT)
        self.assertEqual(cn.total_amount, Decimal("550.00"))
        self.assertEqual(cn.taxable_amount, Decimal("500.00"))
        self.assertEqual(cn.cgst_amount, Decimal("25.00"))
        self.assertEqual(cn.sgst_amount, Decimal("25.00"))
        self.assertEqual(cn.invoice.balance_amount, Decimal("1100.00"))  # Balance shouldn't change in DRAFT

        # Approve CreditNote
        cn_approved = CreditNoteService.approve_credit_note(cn, approved_by=self.accountant)
        self.assertEqual(cn_approved.status, CreditNoteStatus.APPROVED)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.balance_amount, Decimal("550.00"))
        self.assertEqual(self.invoice.status, InvoiceStatus.PARTIALLY_PAID)

        # Check Credit Note Journal
        cn_jv = JournalEntry.objects.filter(source_type="CREDIT_NOTE", source_id=str(cn.id)).first()
        self.assertIsNotNone(cn_jv)
        # Dr Revenue 500, Dr CGST 25, Dr SGST 25, Cr AR 550
        debits = sum(line.debit_amount for line in cn_jv.lines.all())
        credits = sum(line.credit_amount for line in cn_jv.lines.all())
        self.assertEqual(debits, Decimal("550.00"))
        self.assertEqual(credits, Decimal("550.00"))

        # Void CreditNote
        cn_voided = CreditNoteService.void_credit_note(cn_approved, voided_by=self.accountant)
        self.assertEqual(cn_voided.status, CreditNoteStatus.VOID)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.balance_amount, Decimal("1100.00"))
        self.assertEqual(self.invoice.status, InvoiceStatus.ISSUED)

        # Check Reversal Journal
        rev_jv = JournalEntry.objects.filter(source_type="CREDIT_NOTE_REVERSAL", source_id=str(cn.id)).first()
        self.assertIsNotNone(rev_jv)

    def test_credit_note_over_credit_validation(self):
        # Quantity validation
        lines_data = [
            {
                "invoice_line_id": self.inv_line.id,
                "quantity": 3,  # Invoiced is 2
                "unit_rate": 500
            }
        ]
        with self.assertRaises(Exception):
            CreditNoteService.create_credit_note(
                invoice=self.invoice,
                reason="Over credit quantity test",
                lines_data=lines_data,
                created_by=self.accountant
            )

        # Amount validation
        lines_data_ok = [
            {
                "invoice_line_id": self.inv_line.id,
                "quantity": 2,
                "unit_rate": 500
            }
        ]
        cn = CreditNoteService.create_credit_note(
            invoice=self.invoice,
            reason="Full credit",
            lines_data=lines_data_ok,
            created_by=self.accountant
        )
        CreditNoteService.approve_credit_note(cn, approved_by=self.accountant)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.balance_amount, Decimal("0.00"))

        # Try to credit again
        with self.assertRaises(Exception):
            CreditNoteService.create_credit_note(
                invoice=self.invoice,
                reason="Second credit on zero balance",
                lines_data=lines_data_ok,
                created_by=self.accountant
            )

    def test_debit_note_lifecycle_service(self):
        # Create DebitNote (Draft)
        lines_data = [
            {
                "invoice_line_id": self.inv_line.id,
                "quantity": 1,
                "unit_rate": 200
            }
        ]
        dn = DebitNoteService.create_debit_note(
            invoice=self.invoice,
            reason="Additional fuel surcharge",
            lines_data=lines_data,
            created_by=self.accountant
        )
        self.assertEqual(dn.status, DebitNoteStatus.DRAFT)
        self.assertEqual(dn.total_amount, Decimal("220.00"))
        self.assertEqual(dn.taxable_amount, Decimal("200.00"))
        self.assertEqual(dn.cgst_amount, Decimal("10.00"))
        self.assertEqual(dn.sgst_amount, Decimal("10.00"))
        
        # Approve DebitNote
        dn_approved = DebitNoteService.approve_debit_note(dn, approved_by=self.accountant)
        self.assertEqual(dn_approved.status, DebitNoteStatus.APPROVED)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.total_amount, Decimal("1320.00"))
        self.assertEqual(self.invoice.balance_amount, Decimal("1320.00"))

        # Check Debit Note Journal
        dn_jv = JournalEntry.objects.filter(source_type="DEBIT_NOTE", source_id=str(dn.id)).first()
        self.assertIsNotNone(dn_jv)
        # Dr AR 220, Cr Revenue 200, Cr CGST 10, Cr SGST 10
        debits = sum(line.debit_amount for line in dn_jv.lines.all())
        credits = sum(line.credit_amount for line in dn_jv.lines.all())
        self.assertEqual(debits, Decimal("220.00"))
        self.assertEqual(credits, Decimal("220.00"))

        # Void DebitNote
        dn_voided = DebitNoteService.void_debit_note(dn_approved, voided_by=self.accountant)
        self.assertEqual(dn_voided.status, DebitNoteStatus.VOID)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.total_amount, Decimal("1100.00"))
        self.assertEqual(self.invoice.balance_amount, Decimal("1100.00"))

        # Check Reversal Journal
        rev_jv = JournalEntry.objects.filter(source_type="DEBIT_NOTE_REVERSAL", source_id=str(dn.id)).first()
        self.assertIsNotNone(rev_jv)

    def test_notes_api_endpoints_and_permissions(self):
        # Create credit note draft
        url = reverse("credit-note-list")
        payload = {
            "invoice": self.invoice.id,
            "reason": "API credit request",
            "lines": [
                {
                    "invoice_line_id": self.inv_line.id,
                    "quantity": "1.00",
                    "unit_rate": "300.00"
                }
            ]
        }
        res = self.client.post(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        cn_id = res.data["id"]
        self.assertEqual(res.data["status"], "DRAFT")
        self.assertEqual(res.data["total_amount"], "330.00")
        self.assertEqual(len(res.data["lines"]), 1)

        # Create debit note draft
        dn_url = reverse("debit-note-list")
        dn_payload = {
            "invoice": self.invoice.id,
            "reason": "API debit request",
            "lines": [
                {
                    "invoice_line_id": self.inv_line.id,
                    "quantity": "1.00",
                    "unit_rate": "150.00"
                }
            ]
        }
        dn_res = self.client.post(dn_url, dn_payload, format="json")
        self.assertEqual(dn_res.status_code, status.HTTP_201_CREATED)
        dn_id = dn_res.data["id"]
        self.assertEqual(dn_res.data["status"], "DRAFT")
        self.assertEqual(dn_res.data["total_amount"], "165.00")

        # Test read-only auditor gets 403 on approval
        self.client.force_authenticate(user=self.auditor)
        approve_url = reverse("credit-note-approve", kwargs={"pk": cn_id})
        res_auditor = self.client.post(approve_url)
        self.assertEqual(res_auditor.status_code, status.HTTP_403_FORBIDDEN)

        # Authenticate back as accountant
        self.client.force_authenticate(user=self.accountant)
        
        # Approve credit note
        res_approve = self.client.post(approve_url)
        self.assertEqual(res_approve.status_code, status.HTTP_200_OK)
        self.assertEqual(res_approve.data["status"], "APPROVED")
        self.assertIsNotNone(res_approve.data["journal_entry_number"])

        # Approve debit note
        dn_approve_url = reverse("debit-note-approve", kwargs={"pk": dn_id})
        res_dn_approve = self.client.post(dn_approve_url)
        self.assertEqual(res_dn_approve.status_code, status.HTTP_200_OK)
        self.assertEqual(res_dn_approve.data["status"], "APPROVED")
        self.assertIsNotNone(res_dn_approve.data["journal_entry_number"])

        # Void credit note
        void_url = reverse("credit-note-void", kwargs={"pk": cn_id})
        res_void = self.client.post(void_url)
        self.assertEqual(res_void.status_code, status.HTTP_200_OK)
        self.assertEqual(res_void.data["status"], "VOID")

        # Void debit note
        dn_void_url = reverse("debit-note-void", kwargs={"pk": dn_id})
        res_dn_void = self.client.post(dn_void_url)
        self.assertEqual(res_dn_void.status_code, status.HTTP_200_OK)
        self.assertEqual(res_dn_void.data["status"], "VOID")

    def test_ar_aging_report_service_and_api(self):
        # Trigger the aging report API
        url = reverse("invoice-aging")
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("grand_totals", res.data)
        self.assertIn("customers", res.data)
        
        # Verify the totals match outstanding invoice amount
        self.assertEqual(res.data["grand_totals"]["current"], "1100.00")
        self.assertEqual(res.data["grand_totals"]["net_outstanding"], "1100.00")

    def test_customer_statement_report_service_and_api(self):
        # Trigger the customer statement API
        url = reverse("invoice-statement")
        params = {
            "customer": self.customer.id,
            "start_date": "2026-04-01",
            "end_date": "2026-08-31"
        }
        res = self.client.get(url, params)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["opening_balance"], "0.00")
        self.assertEqual(res.data["closing_balance"], "1100.00")
        self.assertEqual(len(res.data["lines"]), 1)
        self.assertEqual(res.data["lines"][0]["type"], "INVOICE")
        self.assertEqual(res.data["lines"][0]["debit"], "1100.00")

