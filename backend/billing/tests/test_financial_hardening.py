from decimal import Decimal
import uuid
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError

from accounts.models import UserRole
from billing.models import (
    LegalEntity, TripCloseout, Invoice, InvoiceStatus, CloseoutStatus,
    FinancialYear, FiscalPeriod, FinancialAuditEvent, IdempotencyRegistry,
    PaymentReceipt, PaymentAllocation, CreditNote
)
from fleet.models import Trip, TripStatus, CorporateCustomer, PricingAmountStatus

User = get_user_model()

class FinancialHardeningTests(APITestCase):
    def setUp(self):
        # Create legal entity
        self.entity = LegalEntity.objects.create(
            legal_name="Hardened Logistics Ltd",
            trade_name="Hardened",
            gstin="27AAAAA1111A1Z1",
            state_code="MH",
        )
        
        # Create users
        self.admin = User.objects.create_user(
            username="admin_user",
            email="admin@test.com",
            password="pass",
            role=UserRole.ADMIN,
            is_superuser=True
        )
        self.accountant = User.objects.create_user(
            username="accountant_user",
            email="acc@test.com",
            password="pass",
            role=UserRole.ACCOUNTANT
        )
        self.accountant.assigned_legal_entities.add(self.entity)

        self.operations = User.objects.create_user(
            username="ops_user",
            email="ops@test.com",
            password="pass",
            role=UserRole.OPERATIONS_APPROVER
        )
        
        # Create Customer
        self.customer = CorporateCustomer.objects.create(
            legal_name="E2E Corp Client",
            display_name="E2E Corp",
        )
        
        # Create Fiscal period / year
        self.year = FinancialYear.objects.create(
            name="FY 2026-27",
            start_date="2026-04-01",
            end_date="2027-03-31",
            is_closed=False
        )
        self.period = FiscalPeriod.objects.create(
            financial_year=self.year,
            name="April 2026",
            start_date="2026-04-01",
            end_date="2026-04-30",
            period_number=1,
            is_locked=True  # LOCKED PERIOD
        )
        
        # Active open period
        self.open_period = FiscalPeriod.objects.create(
            financial_year=self.year,
            name="July 2026",
            start_date="2026-07-01",
            end_date="2026-07-31",
            period_number=4,
            is_locked=False # OPEN PERIOD
        )

    def test_role_based_permissions(self):
        # Operations user shouldn't be allowed to approve invoices
        self.client.force_authenticate(user=self.operations)
        trip = Trip.objects.create(
            customer=self.customer,
            pickup_city="Mumbai",
            drop_city="Pune",
            status="completed",
            pickup_at=timezone.now(),
            estimated_drop_at=timezone.now(),
        )
        closeout = TripCloseout.objects.create(
            trip=trip,
            status=CloseoutStatus.SUBMITTED,
            submitted_by=self.admin,
            final_total_amount=Decimal("5000.00")
        )
        
        invoice = Invoice.objects.create(
            legal_entity=self.entity,
            customer=self.customer,
            status=InvoiceStatus.REVIEW,
            created_by=self.admin,
            total_amount=Decimal("5000.00"),
            balance_amount=Decimal("5000.00"),
            financial_year=self.year,
        )
        
        url = reverse("invoice-approve", kwargs={"pk": invoice.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_self_approval_protection(self):
        # Creator/Submitter cannot approve their own invoice
        invoice = Invoice.objects.create(
            legal_entity=self.entity,
            customer=self.customer,
            status=InvoiceStatus.REVIEW,
            created_by=self.accountant,
            total_amount=Decimal("1000.00"),
            balance_amount=Decimal("1000.00"),
            financial_year=self.year,
        )
        
        self.client.force_authenticate(user=self.accountant)
        url = reverse("invoice-approve", kwargs={"pk": invoice.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_period_lock_enforcement(self):
        self.client.force_authenticate(user=self.admin)
        from billing.services import check_period_lock
        with self.assertRaises(DjangoValidationError):
            check_period_lock(timezone.datetime(2026, 4, 15).date())

    def test_idempotency_compliance(self):
        self.client.force_authenticate(user=self.accountant)
        url = reverse("invoice-list") + "generate_draft/"
        
        trip = Trip.objects.create(
            customer=self.customer,
            pickup_city="Mumbai",
            drop_city="Pune",
            status="completed",
            pickup_at=timezone.now(),
            estimated_drop_at=timezone.now(),
            pricing_amount_status=PricingAmountStatus.FINALIZED,
            final_taxable_amount=Decimal("4761.90"),
            final_tax_amount=Decimal("238.10"),
            final_total_amount=Decimal("5000.00"),
            fare_amount=Decimal("5000.00"),
        )
        closeout = TripCloseout.objects.create(
            trip=trip,
            status=CloseoutStatus.BILLING_READY,
            start_odometer_km=Decimal("100.0"),
            end_odometer_km=Decimal("150.0"),
            actual_km=Decimal("50.0"),
            final_total_amount=Decimal("5000.00"),
            final_taxable_amount=Decimal("4761.90"),
            final_tax_amount=Decimal("238.10")
        )
        
        data = {
            "legal_entity_id": self.entity.id,
            "trip_ids": [trip.id]
        }
        
        headers = {"HTTP_X_IDEMPOTENCY_KEY": "test-key-1"}
        response1 = self.client.post(url, data, format="json", **headers)
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        first_id = response1.data["id"]
        
        response2 = self.client.post(url, data, format="json", **headers)
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response2.data["id"], first_id)
        
        different_data = {
            "legal_entity_id": self.entity.id,
            "trip_ids": []
        }
        response3 = self.client.post(url, different_data, format="json", **headers)
        self.assertEqual(response3.status_code, status.HTTP_409_CONFLICT)

    def test_audit_logging(self):
        self.client.force_authenticate(user=self.admin)
        
        trip = Trip.objects.create(
            customer=self.customer,
            pickup_city="Mumbai",
            drop_city="Pune",
            status="completed",
            pickup_at=timezone.now(),
            estimated_drop_at=timezone.now(),
        )
        closeout = TripCloseout.objects.create(
            trip=trip,
            status=CloseoutStatus.INCOMPLETE,
            final_total_amount=Decimal("1500.00")
        )
        
        url = reverse("closeout-submit", kwargs={"pk": closeout.pk})
        response = self.client.post(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_409_CONFLICT])
        
        audit = FinancialAuditEvent.objects.filter(entity_id=str(closeout.id)).first()
        self.assertIsNotNone(audit)
        self.assertIn(audit.action, ["CLOSEOUT_SUBMIT", "CLOSEOUT_SUBMIT_FAIL"])
        self.assertIsNotNone(audit.after_snapshot_hash)

    def test_reconciliation_service(self):
        Trip.objects.create(
            customer=self.customer,
            pickup_city="Mumbai",
            drop_city="Pune",
            status="completed",
            pickup_at=timezone.now(),
            estimated_drop_at=timezone.now(),
        )
        from billing.reports import ReconciliationService
        data = ReconciliationService.reconcile()
        self.assertIn("trips_missing_closeout", data)
        self.assertTrue(len(data["trips_missing_closeout"]) > 0)
