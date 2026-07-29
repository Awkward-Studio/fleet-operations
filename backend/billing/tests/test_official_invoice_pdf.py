"""
End-to-end validation tests for the Official Tax Invoice Layout
and Duty Slip Annexure Engine.

Covers:
- amount_in_words(): Indian rupee number-to-words formatter
- InvoiceReportService.render_official_tax_invoice(): HTML output assertions
- InvoiceReportService.render_duty_slip_annexure(): HTML output assertions
- InvoiceReportService.render_pdf_from_html(): PDF byte output
- GET /api/billing/invoices/{id}/official-pdf/   → 200 application/pdf
- GET /api/billing/invoices/{id}/duty-slip-pdf/  → 200 application/pdf
"""

import datetime
from decimal import Decimal

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from billing.models import (
    CloseoutStatus,
    FinancialYear,
    Invoice,
    InvoiceStatus,
    LegalEntity,
    TripCloseout,
)
from billing.reports import InvoiceReportService, amount_in_words
from fleet.models import BookingType, CorporateCustomer, Driver, PricingAmountStatus, Trip, Vehicle


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests for amount_in_words()
# ─────────────────────────────────────────────────────────────────────────────

class AmountInWordsTests(TestCase):
    def test_zero(self):
        self.assertEqual(amount_in_words(Decimal("0.00")), "Zero Rupees Only")

    def test_round_hundreds(self):
        self.assertEqual(amount_in_words(Decimal("100.00")), "One Hundred Rupees Only")

    def test_thousands(self):
        self.assertEqual(amount_in_words(Decimal("3388.00")), "Three Thousand Three Hundred And Eighty Eight Rupees Only")

    def test_lakh(self):
        self.assertIn("Lakh", amount_in_words(Decimal("100000.00")))

    def test_crore(self):
        self.assertIn("Crore", amount_in_words(Decimal("10000000.00")))

    def test_with_paise(self):
        result = amount_in_words(Decimal("1001.50"))
        self.assertIn("Paise", result)
        self.assertIn("Fifty", result)

    def test_ends_only(self):
        self.assertTrue(amount_in_words(Decimal("500.00")).endswith("Only"))


# ─────────────────────────────────────────────────────────────────────────────
# Shared test fixture builder
# ─────────────────────────────────────────────────────────────────────────────

def _build_invoice_fixtures():
    """Create and return (entity, fy, customer, vehicle, driver, trip, closeout)."""
    entity = LegalEntity.objects.create(
        legal_name="Index Leasing and Fleet Services Pvt Ltd",
        trade_name="Index Fleet",
        gstin="27AAACI1234A1Z5",
        state_code="27",
        registered_address="Ground Floor, XYZ Tower, Mumbai – 400001",
        bank_name="HDFC Bank",
        bank_account_number="50200012345678",
        ifsc_code="HDFC0001234",
        bank_branch="Andheri West",
    )
    fy = FinancialYear.objects.create(
        name="FY 2025-26",
        start_date=datetime.date(2025, 4, 1),
        end_date=datetime.date(2026, 3, 31),
    )
    customer = CorporateCustomer.objects.create(
        code="CIPLA_TEST",
        legal_name="Cipla Limited",
        display_name="Cipla",
        gstin="27AAACI0000A1Z9",
        payment_terms_days=30,
    )
    vehicle = Vehicle.objects.create(
        registration_number="MH01AB9999",
        make="Toyota",
        model="Innova",
        category="suv",
        current_city="Mumbai",
        permit_expires_on=datetime.date(2027, 1, 1),
        insurance_expires_on=datetime.date(2027, 1, 1),
        pollution_expires_on=datetime.date(2027, 1, 1),
        fitness_expires_on=datetime.date(2027, 1, 1),
    )
    driver = Driver.objects.create(
        name="Ravi Kumar",
        phone="+919876543210",
        license_number="MH20240001",
    )
    trip = Trip.objects.create(
        customer=customer,
        booking_type=BookingType.CORPORATE,
        pickup_city="Mumbai",
        drop_city="Pune",
        pickup_at=datetime.datetime(2026, 7, 21, 9, 0, tzinfo=datetime.timezone.utc),
        estimated_drop_at=datetime.datetime(2026, 7, 21, 13, 0, tzinfo=datetime.timezone.utc),
        status="completed",
        vehicle=vehicle,
        driver=driver,
        fare_amount=Decimal("3228.00"),
        pricing_amount_status=PricingAmountStatus.QUOTED,
        quoted_taxable_amount=Decimal("3228.00"),
        quoted_tax_amount=Decimal("161.40"),
        quoted_total_amount=Decimal("3389.40"),
        pricing_snapshot={
            "calculation_version": "contract-quote-v1",
            "itemized_charges": {"cgst_rate": "2.50", "sgst_rate": "2.50"},
        },
    )
    closeout = TripCloseout.objects.create(
        trip=trip,
        start_odometer_km=Decimal("12000"),
        end_odometer_km=Decimal("12160"),
        actual_km=Decimal("160"),
        actual_hours=Decimal("4.00"),
        status=CloseoutStatus.BILLING_READY,
        milestone_snapshot={
            "garage_departure": {
                "timestamp": "2026-07-21T08:00:00Z",
                "odometer_km": "12000",
            },
            "pickup": {
                "timestamp": "2026-07-21T09:10:00Z",
                "odometer_km": "12010",
            },
            "drop": {
                "timestamp": "2026-07-21T13:05:00Z",
                "odometer_km": "12160",
            },
        },
    )
    return entity, fy, customer, vehicle, driver, trip, closeout


def _create_draft_invoice(entity, fy, customer, trip):
    """Create an issued Invoice with one line item linked to trip."""
    from billing.services import InvoiceService
    return InvoiceService.generate_invoice_draft(entity, [trip.id])


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests for InvoiceReportService
# ─────────────────────────────────────────────────────────────────────────────

class InvoiceReportServiceTests(TestCase):
    def setUp(self):
        fixtures = _build_invoice_fixtures()
        self.entity, self.fy, self.customer, self.vehicle, self.driver, self.trip, self.closeout = fixtures
        self.invoice = _create_draft_invoice(self.entity, self.fy, self.customer, self.trip)

    def test_render_official_tax_invoice_returns_html(self):
        html = InvoiceReportService.render_official_tax_invoice(self.invoice)
        self.assertIsInstance(html, str)
        self.assertIn("<!DOCTYPE html>", html)

    def test_official_invoice_contains_company_name(self):
        html = InvoiceReportService.render_official_tax_invoice(self.invoice)
        self.assertIn("Index Leasing and Fleet Services Pvt Ltd", html)

    def test_official_invoice_contains_customer_name(self):
        html = InvoiceReportService.render_official_tax_invoice(self.invoice)
        self.assertIn("Cipla", html)

    def test_official_invoice_contains_amount_in_words(self):
        html = InvoiceReportService.render_official_tax_invoice(self.invoice)
        # The total is 3389.40 – words should appear
        self.assertIn("Rupees", html)

    def test_official_invoice_draft_flag(self):
        html = InvoiceReportService.render_official_tax_invoice(self.invoice)
        # Draft invoices should carry the watermark indicator
        self.assertIn("DRAFT", html)

    def test_render_duty_slip_annexure_returns_html(self):
        html = InvoiceReportService.render_duty_slip_annexure(self.invoice)
        self.assertIsInstance(html, str)
        self.assertIn("<!DOCTYPE html>", html)

    def test_duty_slip_contains_company_name(self):
        html = InvoiceReportService.render_duty_slip_annexure(self.invoice)
        self.assertIn("Index Leasing and Fleet Services Pvt Ltd", html)

    def test_duty_slip_contains_milestone_labels(self):
        html = InvoiceReportService.render_duty_slip_annexure(self.invoice)
        self.assertIn("Garage Start", html)
        self.assertIn("Reporting", html)
        self.assertIn("Release", html)

    def test_duty_slip_contains_signature_block(self):
        html = InvoiceReportService.render_duty_slip_annexure(self.invoice)
        self.assertIn("Customer Signature", html)

    def test_render_pdf_from_html_returns_bytes(self):
        html = "<html><body><p>Test Invoice PDF</p></body></html>"
        pdf = InvoiceReportService.render_pdf_from_html(html)
        self.assertIsInstance(pdf, bytes)
        self.assertGreater(len(pdf), 100)

    def test_official_invoice_pdf_is_valid_pdf(self):
        html = InvoiceReportService.render_official_tax_invoice(self.invoice)
        pdf = InvoiceReportService.render_pdf_from_html(html)
        self.assertIsInstance(pdf, bytes)
        # PDF files start with %PDF
        self.assertTrue(pdf.startswith(b"%PDF"), "PDF output does not start with %PDF magic bytes")


# ─────────────────────────────────────────────────────────────────────────────
# API endpoint tests
# ─────────────────────────────────────────────────────────────────────────────

class OfficialPdfEndpointTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="pdf_tester",
            email="pdftester@indexfleet.com",
            password="password123",
            role="accountant",
        )
        self.client.force_authenticate(user=self.user)
        fixtures = _build_invoice_fixtures()
        self.entity, self.fy, self.customer, self.vehicle, self.driver, self.trip, self.closeout = fixtures
        self.invoice = _create_draft_invoice(self.entity, self.fy, self.customer, self.trip)

    def test_official_pdf_endpoint_returns_200(self):
        res = self.client.get(f"/api/billing/invoices/{self.invoice.id}/official-pdf/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res["Content-Type"], "application/pdf")

    def test_official_pdf_response_has_content_disposition(self):
        res = self.client.get(f"/api/billing/invoices/{self.invoice.id}/official-pdf/")
        self.assertIn("Content-Disposition", res)
        self.assertIn("tax-invoice", res["Content-Disposition"])

    def test_official_pdf_body_is_pdf_bytes(self):
        res = self.client.get(f"/api/billing/invoices/{self.invoice.id}/official-pdf/")
        self.assertTrue(res.content.startswith(b"%PDF"), "Response body is not a valid PDF")

    def test_duty_slip_endpoint_returns_200(self):
        res = self.client.get(f"/api/billing/invoices/{self.invoice.id}/duty-slip-pdf/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res["Content-Type"], "application/pdf")

    def test_duty_slip_response_has_content_disposition(self):
        res = self.client.get(f"/api/billing/invoices/{self.invoice.id}/duty-slip-pdf/")
        self.assertIn("Content-Disposition", res)
        self.assertIn("duty-slip", res["Content-Disposition"])

    def test_duty_slip_body_is_pdf_bytes(self):
        res = self.client.get(f"/api/billing/invoices/{self.invoice.id}/duty-slip-pdf/")
        self.assertTrue(res.content.startswith(b"%PDF"), "Duty slip response body is not a valid PDF")

    def test_pdf_endpoint_requires_authentication(self):
        self.client.force_authenticate(user=None)
        res = self.client.get(f"/api/billing/invoices/{self.invoice.id}/official-pdf/")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_duty_slip_endpoint_requires_authentication(self):
        self.client.force_authenticate(user=None)
        res = self.client.get(f"/api/billing/invoices/{self.invoice.id}/duty-slip-pdf/")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
