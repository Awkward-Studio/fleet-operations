import datetime
from decimal import Decimal
from rest_framework.test import APITestCase
from rest_framework import status
from billing.models import LegalEntity, FinancialYear, FiscalPeriod, Invoice, InvoiceStatus
from fleet.models import Trip, Vehicle, Driver, CorporateCustomer
from accounts.models import User


class BillingAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="billing_admin",
            email="billing@indexfleet.com",
            password="password123",
            role="admin",
        )
        self.client.force_authenticate(user=self.user)

        self.entity = LegalEntity.objects.create(
            legal_name="Awkward Fleet Operations Pvt Ltd",
            gstin="27AAACA9876A1Z4",
            state_code="27",
        )
        self.fy = FinancialYear.objects.create(
            name="FY 2025-26",
            start_date=datetime.date(2025, 4, 1),
            end_date=datetime.date(2026, 3, 31),
        )
        self.customer = CorporateCustomer.objects.create(
            code="ACME_API_TEST",
            legal_name="ACME Logistics Pvt Ltd",
            display_name="ACME Corp",
            gstin="27AAACA1234A1Z5",
            payment_terms_days=30,
        )
        self.vehicle = Vehicle.objects.create(
            registration_number="MH01XY1111",
            make="Toyota",
            model="Camry",
            category="sedan",
            current_city="Mumbai",
            permit_expires_on=datetime.date(2027, 1, 1),
            insurance_expires_on=datetime.date(2027, 1, 1),
            pollution_expires_on=datetime.date(2027, 1, 1),
            fitness_expires_on=datetime.date(2027, 1, 1),
        )
        self.driver = Driver.objects.create(name="Deepak", phone="+919000011122", license_number="DL11223344")

        self.trip = Trip.objects.create(
            customer=self.customer,
            pickup_city="Mumbai",
            drop_city="Mumbai",
            pickup_at=datetime.datetime(2026, 7, 23, 10, 0, tzinfo=datetime.timezone.utc),
            estimated_drop_at=datetime.datetime(2026, 7, 23, 18, 0, tzinfo=datetime.timezone.utc),
            status="COMPLETED",
            vehicle=self.vehicle,
            driver=self.driver,
            fare_amount=Decimal("2400.00"),
        )

    def test_generate_invoice_draft_api(self):
        res = self.client.post(
            "/api/billing/invoices/generate_draft/",
            {
                "legal_entity_id": self.entity.id,
                "trip_ids": [self.trip.id],
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["status"], "DRAFT")
        self.assertEqual(res.data["subtotal"], "2400.00")

    def test_issue_invoice_api(self):
        draft_res = self.client.post(
            "/api/billing/invoices/generate_draft/",
            {
                "legal_entity_id": self.entity.id,
                "trip_ids": [self.trip.id],
            },
            format="json",
        )
        inv_id = draft_res.data["id"]

        issue_res = self.client.post(f"/api/billing/invoices/{inv_id}/issue/")
        self.assertEqual(issue_res.status_code, status.HTTP_200_OK)
        self.assertEqual(issue_res.data["status"], "ISSUED")
        self.assertTrue(issue_res.data["invoice_number"].startswith("INV/"))
