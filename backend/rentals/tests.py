from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone
from .models import (
    CorporateCustomer, GuestProfile, CorporateApprovalPolicy,
    RentalPackage, BookingRequest, BookingRequestStatus, BookingRequestAmendment,
    RentalBooking, RentalStatus
)

from rentals.views import handoff_booking_request_to_rental_booking, send_rental_notification
from rentals.models import RentalNotification

User = get_user_model()

class PortalModelTests(TestCase):
    def setUp(self):
        self.company = CorporateCustomer.objects.create(
            name="Alpha Corp",
            billing_address="Avenue 1",
            email="alpha@example.com",
            contact_person="Alpha Manager",
            phone="99999999"
        )
        self.user = User.objects.create_user(
            username="portal_user",
            email="user@alpha.com",
            password="password123"
        )
        self.package = RentalPackage.objects.create(
            name="8hr/80km Sedan",
            included_hours=8,
            included_km=80,
            default_base_price=1500.00,
            extra_hour_rate=150.00,
            extra_km_rate=15.00
        )

    def test_guest_profile_creation_and_uniqueness(self):
        guest = GuestProfile.objects.create(
            company=self.company,
            name="Alice Guest",
            phone="9876543210",
            email="alice@example.com",
            employee_id="EMP101"
        )
        self.assertEqual(guest.name, "Alice Guest")
        
        # Test phone uniqueness per company
        with self.assertRaises(IntegrityError):
            GuestProfile.objects.create(
                company=self.company,
                name="Another Alice",
                phone="9876543210"
            )

    def test_corporate_approval_policy(self):
        policy = CorporateApprovalPolicy.objects.create(
            company=self.company,
            require_po=True,
            require_cost_centre=True,
            approval_threshold_amount=5000.00
        )
        self.assertEqual(policy.company, self.company)
        self.assertTrue(policy.require_po)

    def test_booking_request_creation(self):
        guest = GuestProfile.objects.create(
            company=self.company,
            name="Bob Guest",
            phone="1122334455"
        )
        
        req = BookingRequest.objects.create(
            booking_number="PQ-2026-0001",
            company=self.company,
            requester=self.user,
            guest=guest,
            passenger_name="Bob Guest",
            passenger_phone="1122334455",
            pickup_address="Hotel Central",
            pickup_city="Mumbai",
            pickup_at=timezone.now(),
            expected_return_at=timezone.now() + timezone.timedelta(hours=8),
            package=self.package,
            vehicle_category="Sedan",
            status=BookingRequestStatus.SUBMITTED,
            quote_base_price=1500.00
        )
        
        self.assertEqual(req.booking_number, "PQ-2026-0001")
        self.assertEqual(req.status, BookingRequestStatus.SUBMITTED)

    def test_booking_request_amendment(self):
        req = BookingRequest.objects.create(
            booking_number="PQ-2026-0002",
            company=self.company,
            requester=self.user,
            passenger_name="Charlie Guest",
            passenger_phone="5566778899",
            pickup_address="Terminal 2",
            pickup_city="Mumbai",
            pickup_at=timezone.now(),
            expected_return_at=timezone.now() + timezone.timedelta(hours=4),
            package=self.package,
            quote_base_price=1500.00
        )
        
        amendment = BookingRequestAmendment.objects.create(
            booking_request=req,
            amended_by=self.user,
            changes={"pickup_address": "Terminal 1"},
            reason="Change of pickup point"
        )
        
        self.assertEqual(amendment.booking_request, req)
        self.assertEqual(amendment.reason, "Change of pickup point")


from django.urls import reverse
from rest_framework.test import APITestCase
from accounts.models import CorporateMembership, CorporateRole
from .models import RentalPricingRule

class PortalAPITests(APITestCase):
    def setUp(self):
        self.packages_url = reverse("portal_packages")
        self.quote_url = reverse("portal_quote")
        self.company = CorporateCustomer.objects.create(
            name="Acme Corp",
            billing_address="Avenue 1",
            email="acme@example.com",
            contact_person="Acme Manager",
            phone="88888888"
        )
        self.user = User.objects.create_user(
            username="acme_user",
            email="user@acme.com",
            password="password123"
        )
        CorporateMembership.objects.create(
            user=self.user,
            company=self.company,
            role=CorporateRole.REQUESTER
        )
        self.package = RentalPackage.objects.create(
            name="Mumbai 8hr/80km",
            included_hours=8,
            included_km=80,
            default_base_price=1200.00
        )
        self.pricing_rule = RentalPricingRule.objects.create(
            company=self.company,
            city="Mumbai",
            package=self.package,
            base_price=1600.00,
            extra_hour_rate=150.00,
            extra_km_rate=15.00,
            driver_allowance=250.00
        )
        self.other_user = User.objects.create_user(
            username="other_user",
            email="other@corp.com",
            password="password123"
        )

    def test_portal_packages_success(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.packages_url, {"city": "Mumbai"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], "Mumbai 8hr/80km")

    def test_portal_quote_success(self):
        self.client.force_authenticate(user=self.user)
        data = {
            "company_id": self.company.id,
            "pickup_city": "Mumbai",
            "package_id": self.package.id,
            "vehicle_category": "Sedan"
        }
        response = self.client.post(self.quote_url, data, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(float(response.data["base_price"]), 1600.00)
        self.assertEqual(float(response.data["driver_allowance"]), 250.00)
        self.assertIn("signature", response.data)

    def test_portal_quote_forbidden(self):
        self.client.force_authenticate(user=self.other_user)
        data = {
            "company_id": self.company.id,
            "pickup_city": "Mumbai",
            "package_id": self.package.id
        }
        response = self.client.post(self.quote_url, data, format="json")
        self.assertEqual(response.status_code, 403)


class BookingWorkflowTests(APITestCase):
    def setUp(self):
        self.booking_requests_url = "/api/rentals/portal/booking-requests/"
        self.company = CorporateCustomer.objects.create(
            name="Acme Corp",
            billing_address="Avenue 1",
            email="acme@example.com",
            contact_person="Acme Manager",
            phone="88888888"
        )
        self.package = RentalPackage.objects.create(
            name="Mumbai 8hr/80km",
            included_hours=8,
            included_km=80,
            default_base_price=1200.00
        )
        self.pricing_rule = RentalPricingRule.objects.create(
            company=self.company,
            city="Mumbai",
            package=self.package,
            base_price=1600.00,
            extra_hour_rate=150.00,
            extra_km_rate=15.00
        )
        
        self.policy = CorporateApprovalPolicy.objects.create(
            company=self.company,
            require_cost_centre=True,
            approval_threshold_amount=1000.00
        )
        
        self.requester_user = User.objects.create_user(
            username="requester",
            email="req@acme.com",
            password="password123"
        )
        CorporateMembership.objects.create(
            user=self.requester_user,
            company=self.company,
            role=CorporateRole.REQUESTER
        )
        
        self.approver_user = User.objects.create_user(
            username="approver",
            email="app@acme.com",
            password="password123"
        )
        CorporateMembership.objects.create(
            user=self.approver_user,
            company=self.company,
            role=CorporateRole.APPROVER
        )

    def test_booking_request_policy_validation_and_approval_required(self):
        self.client.force_authenticate(user=self.requester_user)
        
        data = {
            "company": self.company.id,
            "passenger_name": "John Doe",
            "passenger_phone": "1234567890",
            "pickup_address": "Airport T2",
            "pickup_city": "Mumbai",
            "pickup_at": timezone.now().isoformat(),
            "expected_return_at": (timezone.now() + timezone.timedelta(hours=8)).isoformat(),
            "package": self.package.id
        }
        response = self.client.post(self.booking_requests_url, data, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("cost_centre", response.data)
        
        data["cost_centre"] = "CC-HR-01"
        response = self.client.post(self.booking_requests_url, data, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "approval_required")
        
        self.assertFalse(RentalBooking.objects.filter(booking_number=response.data["booking_number"]).exists())

    def test_booking_request_approver_action(self):
        req = BookingRequest.objects.create(
            booking_number="PQ-TEST-01",
            company=self.company,
            requester=self.requester_user,
            passenger_name="John Doe",
            passenger_phone="1234567890",
            pickup_address="Airport T2",
            pickup_city="Mumbai",
            pickup_at=timezone.now(),
            expected_return_at=timezone.now() + timezone.timedelta(hours=8),
            package=self.package,
            status=BookingRequestStatus.APPROVAL_REQUIRED,
            quote_base_price=1600.00
        )
        
        approve_url = f"{self.booking_requests_url}{req.id}/approve/"
        
        self.client.force_authenticate(user=self.requester_user)
        response = self.client.post(approve_url, {}, format="json")
        self.assertEqual(response.status_code, 403)
        
        self.client.force_authenticate(user=self.approver_user)
        response = self.client.post(approve_url, {}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "approved")
        
        self.assertTrue(RentalBooking.objects.filter(booking_number="PQ-TEST-01").exists())

    def test_booking_status_timeline_and_precision_live_location(self):
        from fleet.models import Driver, Vehicle
        from rentals.models import RentalBookingLocationLog
        req = BookingRequest.objects.create(
            booking_number="PQ-TEST-TRACK",
            company=self.company,
            requester=self.requester_user,
            passenger_name="John Tracker",
            passenger_phone="1234567890",
            pickup_address="Airport T2",
            pickup_city="Mumbai",
            pickup_at=timezone.now(),
            expected_return_at=timezone.now() + timezone.timedelta(hours=8),
            package=self.package,
            status=BookingRequestStatus.APPROVED,
            quote_base_price=1600.00
        )
        booking = handoff_booking_request_to_rental_booking(req)
        
        self.client.force_authenticate(user=self.requester_user)
        status_url = f"{self.booking_requests_url}{req.id}/status/"
        
        response = self.client.get(status_url, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "pending")
        self.assertIsNone(response.data["driver"])
        self.assertIsNone(response.data["vehicle"])
        self.assertIsNone(response.data["live_location"])
        
        driver = Driver.objects.create(name="Driver Dave", phone="99999999", license_number="LIC-100", home_base="Mumbai")
        vehicle = Vehicle.objects.create(registration_number="MH-12-XX-1234", make="Tata", model="Nexon", category="SUV", current_city="Mumbai", permit_expires_on="2030-01-01", insurance_expires_on="2030-01-01", pollution_expires_on="2030-01-01", fitness_expires_on="2030-01-01")
        
        booking.driver = driver
        booking.vehicle = vehicle
        booking.status = RentalStatus.READY
        booking.save()
        
        response = self.client.get(status_url, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["driver"]["first_name"], "Driver")
        self.assertEqual(response.data["vehicle"]["registration_number"], "MH-12-XX-1234")
        self.assertIsNone(response.data["live_location"])
        
        booking.status = RentalStatus.STARTED
        booking.save()
        
        self.policy.location_precision_digits = 3
        self.policy.save()
        
        RentalBookingLocationLog.objects.create(
            booking=booking,
            latitude=19.123456,
            longitude=72.987654
        )
        
        response = self.client.get(status_url, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.data["live_location"])
        self.assertEqual(float(response.data["live_location"]["latitude"]), 19.123)
        self.assertEqual(float(response.data["live_location"]["longitude"]), 72.988)

    def test_notification_idempotency(self):
        req = BookingRequest.objects.create(
            booking_number="PQ-TEST-NOTIF",
            company=self.company,
            requester=self.requester_user,
            passenger_name="Notification Guy",
            passenger_phone="1234567890",
            passenger_email="passenger@acme.com",
            pickup_address="Airport T2",
            pickup_city="Mumbai",
            pickup_at=timezone.now(),
            expected_return_at=timezone.now() + timezone.timedelta(hours=8),
            package=self.package,
            status=BookingRequestStatus.SUBMITTED,
            quote_base_price=1600.00
        )
        
        notif1 = send_rental_notification(req, "submitted")
        notif2 = send_rental_notification(req, "submitted")
        
        self.assertIsNotNone(notif1)
        self.assertIsNotNone(notif2)
        self.assertEqual(notif1.id, notif2.id)
        self.assertEqual(RentalNotification.objects.filter(booking_number="PQ-TEST-NOTIF").count(), 1)

    def test_portal_invoices_and_statements(self):
        from billing.models import Invoice as BillingInvoice, InvoiceStatus as BillingInvoiceStatus, LegalEntity, FinancialYear
        from fleet.models import CorporateCustomer as FleetCorporateCustomer
        
        company = FleetCorporateCustomer.objects.create(
            code="ACME",
            legal_name="Acme Corp",
            display_name="Acme Corp",
            billing_address="Avenue 1",
            billing_email="acme@example.com",
            billing_phone="88888888"
        )
        
        entity = LegalEntity.objects.create(
            legal_name="Fleet Operations Ltd",
            trade_name="FleetOps",
            gstin="27AAAAA1111A1Z1",
            pan="AAAAA1111A",
            registered_address="Mumbai"
        )
        
        fy = FinancialYear.objects.create(
            name="FY 2026-27",
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timezone.timedelta(days=365)
        )
        
        inv1 = BillingInvoice.objects.create(
            invoice_number="INV-2026-001",
            legal_entity=entity,
            financial_year=fy,
            customer=company,
            billing_name_snapshot="Acme Corp",
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timezone.timedelta(days=30),
            total_amount=5000.00,
            cgst_amount=125.00,
            sgst_amount=125.00,
            taxable_amount=4750.00,
            paid_amount=0.00,
            balance_amount=5000.00,
            status=BillingInvoiceStatus.ISSUED,
            po_number="PO-999"
        )
        
        inv2 = BillingInvoice.objects.create(
            invoice_number="INV-2026-DRAFT",
            legal_entity=entity,
            financial_year=fy,
            customer=company,
            billing_name_snapshot="Acme Corp",
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timezone.timedelta(days=30),
            total_amount=2000.00,
            cgst_amount=50.00,
            sgst_amount=50.00,
            taxable_amount=1900.00,
            paid_amount=0.00,
            balance_amount=2000.00,
            status=BillingInvoiceStatus.DRAFT,
            po_number="PO-999"
        )
        
        self.client.force_authenticate(user=self.requester_user)
        
        url = "/api/rentals/portal/invoices/"
        response = self.client.get(url, format="json")
        self.assertEqual(response.status_code, 200)
        invoice_numbers = [item["invoice_number"] for item in response.data]
        self.assertIn("INV-2026-001", invoice_numbers)
        self.assertNotIn("INV-2026-DRAFT", invoice_numbers)
        
        download_url = f"/api/rentals/portal/invoices/{inv1.id}/download/"
        response = self.client.get(download_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response["Content-Type"])
        self.assertIn("INV-2026-001", response.content.decode("utf-8"))
        
        statements_url = "/api/rentals/portal/statements/"
        response = self.client.get(statements_url, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["closing_balance"], 5000.00)

    def test_portal_audit_support_and_impersonate(self):
        from accounts.models import UserRole
        from rentals.models import PortalAuditEvent, PortalSupportCase
        
        self.client.force_authenticate(user=self.requester_user)
        
        support_url = "/api/rentals/portal/support-cases/"
        data = {
            "company": self.company.id,
            "subject": "Need help with booking",
            "description": "Please assign a larger SUV."
        }
        response = self.client.post(support_url, data, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["subject"], "Need help with booking")
        
        self.assertEqual(PortalAuditEvent.objects.filter(action_type="support_ticket").count(), 1)
        
        audit_url = "/api/rentals/portal/audit-logs/"
        response = self.client.get(audit_url, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)
        
        from accounts.models import CorporateMembership, CorporateRole
        membership = CorporateMembership.objects.get(user=self.approver_user)
        membership.role = CorporateRole.ADMIN
        membership.save()
        
        self.client.force_authenticate(user=self.approver_user)
        response = self.client.get(audit_url, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.data), 1)
        
        support_agent = User.objects.create_user(
            username="support_agent",
            email="agent@fleetops.com",
            password="password123",
            role=UserRole.ADMIN
        )
        self.client.force_authenticate(user=support_agent)
        
        impersonate_url = "/api/rentals/portal/support/impersonate/"
        impersonate_data = {
            "user_id": self.requester_user.id,
            "company_id": self.company.id
        }
        response = self.client.post(impersonate_url, impersonate_data, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["impersonation_active"])
        self.assertEqual(response.data["impersonated_user"], "requester")
        
        self.assertEqual(PortalAuditEvent.objects.filter(action_type="impersonation").count(), 1)
        
        health_url = "/api/rentals/portal/health/"
        response = self.client.get(health_url, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "healthy")

    def test_tenant_isolation_and_cross_access_rejection(self):
        from accounts.models import CorporateMembership, CorporateRole
        
        company2 = CorporateCustomer.objects.create(
            name="Beta Corp",
            billing_address="Avenue 2",
            email="beta@example.com",
            contact_person="Beta Manager",
            phone="77777777"
        )
        
        user2 = User.objects.create_user(
            username="beta_user",
            email="user@beta.com",
            password="password123"
        )
        CorporateMembership.objects.create(
            user=user2,
            company=company2,
            role=CorporateRole.ADMIN
        )
        
        req1 = BookingRequest.objects.create(
            booking_number="PQ-COMP1-01",
            company=self.company,
            requester=self.requester_user,
            passenger_name="John Doe",
            passenger_phone="1234567890",
            pickup_address="Airport T2",
            pickup_city="Mumbai",
            pickup_at=timezone.now(),
            expected_return_at=timezone.now() + timezone.timedelta(hours=8),
            package=self.package,
            status=BookingRequestStatus.SUBMITTED,
            quote_base_price=1600.00
        )
        
        self.client.force_authenticate(user=user2)
        
        detail_url = f"{self.booking_requests_url}{req1.id}/"
        response = self.client.get(detail_url, format="json")
        self.assertEqual(response.status_code, 404)
        
        approve_url = f"{self.booking_requests_url}{req1.id}/approve/"
        response = self.client.post(approve_url, {}, format="json")
        self.assertEqual(response.status_code, 404)
        
        amend_url = f"{self.booking_requests_url}{req1.id}/amend/"
        response = self.client.post(amend_url, {"passenger_name": "Hack"}, format="json")
        self.assertEqual(response.status_code, 404)


