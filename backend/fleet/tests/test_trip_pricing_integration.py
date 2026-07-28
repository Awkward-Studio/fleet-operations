import datetime
from decimal import Decimal
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from fleet.models import (
    CorporateCustomer,
    CorporateContract,
    ContractRate,
    CustomerStatus,
    DutyType,
    Trip,
    BookingType,
    PricingAmountStatus,
    RateBook,
    RateBookStatus,
    RateBookType,
    RatePackage,
)
from django.utils import timezone

User = get_user_model()


class TripPricingIntegrationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="tripuser",
            email="trip@test.com",
            password="password123",
            role="dispatcher",
        )
        self.customer = CorporateCustomer.objects.create(
            code="CUST_TRIP_01",
            legal_name="Delta Enterprises Pvt Ltd",
            display_name="Delta Corp",
            status=CustomerStatus.ACTIVE,
        )
        self.contract = CorporateContract.objects.create(
            customer=self.customer,
            title="Delta Contract 2026",
            version_name="v1.0",
            effective_start=datetime.date(2026, 1, 1),
            status="ACTIVE",
            cgst_rate=Decimal("2.50"),
            sgst_rate=Decimal("2.50"),
        )
        self.rate = ContractRate.objects.create(
            contract=self.contract,
            city="mumbai",
            vehicle_category="sedan",
            duty_type=DutyType.LOCAL_8HR_80KM,
            included_hours=8,
            included_km=80,
            base_rate=Decimal("2500.00"),
            extra_hour_rate=Decimal("200.00"),
            extra_km_rate=Decimal("18.00"),
        )
        approved_at = timezone.now()
        corporate_book = RateBook.objects.create(
            code="DELTA-2026",
            name="Delta 2026",
            version=1,
            book_type=RateBookType.CORPORATE,
            status=RateBookStatus.ACTIVE,
            effective_start=datetime.date(2026, 1, 1),
            contract=self.contract,
            approved_at=approved_at,
        )
        public_book = RateBook.objects.create(
            code="PUBLIC-2026",
            name="Public 2026",
            version=1,
            book_type=RateBookType.PUBLIC,
            status=RateBookStatus.ACTIVE,
            effective_start=datetime.date(2026, 1, 1),
            approved_at=approved_at,
        )
        for book, code in ((corporate_book, "DELTA-LOCAL"), (public_book, "PUBLIC-LOCAL")):
            RatePackage.objects.create(
                rate_book=book,
                code=code,
                name="Local 8h / 80km",
                city="mumbai",
                vehicle_category="sedan",
                duty_type=DutyType.LOCAL_8HR_80KM,
                included_hours=8,
                included_km=80,
                base_rate=Decimal("2500.00"),
                extra_hour_rate=Decimal("200.00"),
                extra_km_rate=Decimal("18.00"),
            )

    def test_create_corporate_trip_recalculates_fare_and_stores_snapshot(self):
        self.client.force_authenticate(user=self.user)
        payload = {
            "booking_type": "CORPORATE",
            "customer_id": self.customer.id,
            "duty_type": DutyType.LOCAL_8HR_80KM,
            "vehicle_category_requested": "Sedan",
            "pickup_city": "Mumbai",
            "drop_city": "Mumbai",
            "pickup_at": "2026-07-25T10:00:00Z",
            "estimated_drop_at": "2026-07-25T18:00:00Z",
            "distance_km": 70,
            "fare_amount": "1.00",  # Forged fare in payload
        }
        res = self.client.post("/api/trips/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        
        trip = Trip.objects.get(id=res.data["id"])
        # Total base 2500 + 5% tax (125) = 2625.00 (Forged fare 1.00 rejected!)
        self.assertEqual(trip.fare_amount, Decimal("2625.00"))
        self.assertEqual(trip.pricing_amount_status, PricingAmountStatus.QUOTED)
        self.assertEqual(trip.quoted_taxable_amount, Decimal("2500.00"))
        self.assertEqual(trip.quoted_tax_amount, Decimal("125.00"))
        self.assertEqual(trip.quoted_total_amount, Decimal("2625.00"))
        self.assertEqual(res.data["quoted_taxable_amount"], "2500.00")
        self.assertEqual(trip.customer_display_name_snapshot, "Delta Corp")
        self.assertEqual(trip.pricing_snapshot["rate_book"]["type"], "CORPORATE")
        self.assertIsNotNone(trip.rate_package_id)
        self.assertEqual(trip.calculation_version, "unified-rate-card-v1")

    def test_adhoc_trip_is_server_priced(self):
        self.client.force_authenticate(user=self.user)
        payload = {
            "booking_type": "ADHOC",
            "customer_name": "Direct Guest",
            "pickup_city": "Mumbai",
            "drop_city": "Pune",
            "pickup_at": "2026-07-25T10:00:00Z",
            "estimated_drop_at": "2026-07-25T14:00:00Z",
            "duty_type": DutyType.LOCAL_8HR_80KM,
            "vehicle_category_requested": "Sedan",
            "distance_km": 70,
            "fare_amount": "3000.00",
        }
        res = self.client.post("/api/trips/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["fare_amount"], "2625.00")
        self.assertEqual(
            res.data["pricing_amount_status"],
            PricingAmountStatus.QUOTED,
        )

    def test_immutability_of_trip_snapshot_on_customer_change(self):
        self.client.force_authenticate(user=self.user)
        payload = {
            "booking_type": "CORPORATE",
            "customer_id": self.customer.id,
            "duty_type": DutyType.LOCAL_8HR_80KM,
            "vehicle_category_requested": "Sedan",
            "pickup_city": "Mumbai",
            "drop_city": "Mumbai",
            "pickup_at": "2026-07-25T10:00:00Z",
            "estimated_drop_at": "2026-07-25T18:00:00Z",
        }
        res = self.client.post("/api/trips/", payload, format="json")
        trip_id = res.data["id"]

        # Rename and deactivate customer
        self.customer.display_name = "Delta Corp Renamed"
        self.customer.status = CustomerStatus.INACTIVE
        self.customer.save()

        # Check existing trip snapshot remains unchanged
        trip = Trip.objects.get(id=trip_id)
        self.assertEqual(trip.customer_display_name_snapshot, "Delta Corp")
        self.assertEqual(trip.fare_amount, Decimal("2625.00"))

    def test_explicit_quote_amounts_must_reconcile(self):
        trip = Trip(
            pickup_city="Mumbai",
            drop_city="Pune",
            pickup_at=datetime.datetime(2026, 7, 25, 10, tzinfo=datetime.timezone.utc),
            estimated_drop_at=datetime.datetime(2026, 7, 25, 14, tzinfo=datetime.timezone.utc),
            pricing_amount_status=PricingAmountStatus.QUOTED,
            quoted_taxable_amount=Decimal("2500.00"),
            quoted_tax_amount=Decimal("125.00"),
            quoted_total_amount=Decimal("2750.00"),
        )

        with self.assertRaises(ValidationError):
            trip.full_clean()

    def test_legacy_fare_remains_explicitly_unclassified(self):
        trip = Trip.objects.create(
            pickup_city="Mumbai",
            drop_city="Pune",
            pickup_at=datetime.datetime(2026, 7, 25, 10, tzinfo=datetime.timezone.utc),
            estimated_drop_at=datetime.datetime(2026, 7, 25, 14, tzinfo=datetime.timezone.utc),
            fare_amount=Decimal("3000.00"),
        )

        self.assertEqual(
            trip.pricing_amount_status,
            PricingAmountStatus.LEGACY_UNCLASSIFIED,
        )
        self.assertIsNone(trip.quoted_taxable_amount)
