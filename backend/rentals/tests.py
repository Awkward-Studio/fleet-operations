from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone
from .models import (
    CorporateCustomer, GuestProfile, CorporateApprovalPolicy,
    RentalPackage, BookingRequest, BookingRequestStatus, BookingRequestAmendment,
    RentalBooking, RentalStatus
)

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


