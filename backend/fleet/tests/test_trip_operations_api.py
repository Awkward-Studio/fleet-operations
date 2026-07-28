from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APITestCase

from fleet.models import (
    Driver,
    DriverStatus,
    DutyType,
    RateBook,
    RateBookStatus,
    RateBookType,
    RatePackage,
    Trip,
    TripLocationLog,
    TripStatus,
    Vehicle,
    VehicleStatus,
)
from media_store.models import UploadedAsset


class TripOperationsAPITest(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="driver-api",
            email="driver-api@example.com",
            password="driver123",
        )
        license_asset = UploadedAsset.objects.create(
            kind=UploadedAsset.KIND_IMAGE,
            file_url="/media/test/license.jpg",
            original_name="license.jpg",
            content_type="image/jpeg",
        )
        self.driver = Driver.objects.create(
            user=self.user,
            name="Driver API",
            phone="+91 90000 10001",
            license_number="DRV-API-001",
            home_base="Delhi",
            status=DriverStatus.ASSIGNED,
            driving_license=license_asset,
            driving_license_expiry_date=timezone.localdate() + timedelta(days=365),
        )
        self.vehicle = Vehicle.objects.create(
            registration_number="DLAPI0001",
            make="Toyota",
            model="Etios",
            category="Sedan",
            current_city="Delhi",
            status=VehicleStatus.IDLE,
            assigned_driver=self.driver,
            permit_expires_on=timezone.localdate() + timedelta(days=90),
            insurance_expires_on=timezone.localdate() + timedelta(days=90),
            pollution_expires_on=timezone.localdate() + timedelta(days=90),
            fitness_expires_on=timezone.localdate() + timedelta(days=90),
            odometer_km=1000,
        )
        self.trip = Trip.objects.create(
            customer_name="Passenger API",
            pickup_city="Delhi",
            drop_city="Noida",
            pickup_at=timezone.now() + timedelta(minutes=30),
            estimated_drop_at=timezone.now() + timedelta(hours=2),
            status=TripStatus.ASSIGNED,
            vehicle=self.vehicle,
            driver=self.driver,
            fare_amount=1500,
        )
        book = RateBook.objects.create(
            code="OPS-PUBLIC",
            name="Operations public",
            version=1,
            book_type=RateBookType.PUBLIC,
            status=RateBookStatus.ACTIVE,
            effective_start=timezone.localdate(),
            approved_at=timezone.now(),
        )
        RatePackage.objects.create(
            rate_book=book,
            code="OPS-LOCAL",
            name="Operations local",
            city="delhi",
            vehicle_category="sedan",
            duty_type=DutyType.LOCAL_8HR_80KM,
            included_hours=8,
            included_km=80,
            base_rate=Decimal("1200"),
        )
        self.client.force_authenticate(self.user)

    def test_otp_generation_and_verification(self):
        response = self.client.post(
            f"/api/fleet/trips/{self.trip.id}/generate-otp/",
            {"digits": 4, "idempotency_key": "otp-test-key"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        code = response.data["code"]

        retry = self.client.post(
            f"/api/fleet/trips/{self.trip.id}/generate-otp/",
            {"digits": 4, "idempotency_key": "otp-test-key"},
            format="json",
        )
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(retry.data["code"], code)

        invalid = self.client.post(
            f"/api/fleet/trips/{self.trip.id}/verify-otp/",
            {"code": "0000"},
            format="json",
        )
        self.assertEqual(invalid.status_code, 400)

        valid = self.client.post(
            f"/api/fleet/trips/{self.trip.id}/verify-otp/",
            {"code": code},
            format="json",
        )
        self.assertEqual(valid.status_code, 200)
        self.assertTrue(valid.data["is_verified"])

    def test_current_driver_trip_endpoint_returns_active_assignment(self):
        response = self.client.get("/api/fleet/driver/my-trips/current/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.trip.id)
        self.assertEqual(response.data["customer_name"], "Passenger API")

    def test_current_driver_trip_endpoint_returns_null_without_assignment(self):
        self.trip.status = TripStatus.COMPLETED
        self.trip.save(update_fields=["status"])

        response = self.client.get("/api/fleet/driver/my-trips/current/")

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data)

    def test_checklist_location_and_completion_flow(self):
        checklist = self.client.post(
            f"/api/fleet/trips/{self.trip.id}/checklist/",
            {
                "start_odometer_km": 1005,
                "start_odometer_photo": SimpleUploadedFile(
                    "start.jpg",
                    b"start-photo",
                    content_type="image/jpeg",
                ),
                "cleanliness_ok": True,
                "fuel_level_percent": 85,
                "tire_pressure_ok": True,
                "idempotency_key": "checklist-test-key",
            },
            format="multipart",
        )
        self.assertEqual(checklist.status_code, 201)
        self.trip.refresh_from_db()
        self.assertEqual(self.trip.status, TripStatus.EN_ROUTE_PICKUP)

        location_payload = {
            "latitude": "28.48968000",
            "longitude": "77.09224000",
            "speed_kmh": 45.2,
            "heading": 180.0,
            "idempotency_key": "location-test-key",
        }
        first_location = self.client.post(
            f"/api/fleet/trips/{self.trip.id}/location/",
            location_payload,
            format="json",
        )
        retry_location = self.client.post(
            f"/api/fleet/trips/{self.trip.id}/location/",
            location_payload,
            format="json",
        )
        self.assertEqual(first_location.status_code, 201)
        self.assertEqual(retry_location.status_code, 200)
        self.assertEqual(TripLocationLog.objects.filter(trip=self.trip).count(), 1)

        complete = self.client.post(
            f"/api/fleet/trips/{self.trip.id}/complete/",
            {
                "end_odometer_km": 1042,
                "end_odometer_photo": SimpleUploadedFile(
                    "end.jpg",
                    b"end-photo",
                    content_type="image/jpeg",
                ),
                "idempotency_key": "complete-test-key",
            },
            format="multipart",
        )
        self.assertEqual(complete.status_code, 200)
        self.trip.refresh_from_db()
        self.vehicle.refresh_from_db()
        self.driver.refresh_from_db()
        self.assertEqual(self.trip.status, TripStatus.COMPLETED)
        self.assertEqual(str(self.trip.distance_km), "37.00")
        self.assertEqual(self.vehicle.odometer_km, 1042)
        self.assertEqual(self.driver.status, DriverStatus.AVAILABLE)
        self.assertEqual(self.trip.closeout.status, "SUBMITTED")
        self.assertEqual(str(self.trip.closeout.actual_km), "37.00")
        self.assertEqual(
            self.trip.closeout.source_event_key,
            "complete-test-key",
        )
        self.assertEqual(self.trip.closeout.blockers, [])

        retry_complete = self.client.post(
            f"/api/fleet/trips/{self.trip.id}/complete/",
            {
                "end_odometer_km": 1042,
                "idempotency_key": "complete-test-key",
            },
            format="json",
        )
        self.assertEqual(retry_complete.status_code, 200)
        from billing.models import TripCloseout
        self.assertEqual(TripCloseout.objects.filter(trip=self.trip).count(), 1)

    def test_create_driver_with_email_and_password_creates_user(self):
        payload = {
            "name": "New Driver User",
            "phone": "+91 91111 22222",
            "license_number": "DL-DRV-NEW999",
            "home_base": "Jaipur",
            "email": "newdriver@example.com",
            "password": "driverpassword123",
        }
        response = self.client.post("/api/fleet/drivers/", payload, format="json")
        self.assertEqual(response.status_code, 201)
        
        # Verify Driver is created and links to a user
        driver = Driver.objects.get(license_number="DL-DRV-NEW999")
        self.assertIsNotNone(driver.user)
        self.assertEqual(driver.user.email, "newdriver@example.com")
        self.assertEqual(driver.user.role, "driver")
        
        # Verify the user can authenticate
        from django.contrib.auth import authenticate
        authenticated_user = authenticate(username="newdriver@example.com", password="driverpassword123")
        self.assertEqual(authenticated_user, driver.user)

    def test_create_trip_with_direct_driver_and_vehicle_assignment(self):
        # Create a new available driver and vehicle
        available_driver = Driver.objects.create(
            name="Free Driver",
            phone="+91 92222 33333",
            license_number="DL-DRV-FREE1",
            home_base="Delhi",
            status=DriverStatus.AVAILABLE,
        )
        idle_vehicle = Vehicle.objects.create(
            registration_number="DLFREE001",
            make="Maruti",
            model="Swift",
            category="Sedan",
            current_city="Delhi",
            status=VehicleStatus.IDLE,
            permit_expires_on=timezone.localdate() + timedelta(days=90),
            insurance_expires_on=timezone.localdate() + timedelta(days=90),
            pollution_expires_on=timezone.localdate() + timedelta(days=90),
            fitness_expires_on=timezone.localdate() + timedelta(days=90),
            odometer_km=5000,
        )
        
        trip_payload = {
            "booking_type": "ADHOC",
            "customer_name": "Direct Passenger",
            "pickup_city": "Delhi",
            "drop_city": "Gurgaon",
            "pickup_at": (timezone.now() + timedelta(hours=5)).isoformat(),
            "estimated_drop_at": (timezone.now() + timedelta(hours=7)).isoformat(),
            "driver_id": available_driver.id,
            "vehicle_id": idle_vehicle.id,
            "fare_amount": "1200.00",
            "duty_type": DutyType.LOCAL_8HR_80KM,
            "vehicle_category_requested": "Sedan",
        }
        
        response = self.client.post("/api/fleet/trips/", trip_payload, format="json")
        self.assertEqual(response.status_code, 201)
        
        # Check trip status and side effects
        trip = Trip.objects.get(id=response.data["id"])
        self.assertEqual(trip.status, TripStatus.ASSIGNED)
        self.assertEqual(trip.driver, available_driver)
        self.assertEqual(trip.vehicle, idle_vehicle)
        
        available_driver.refresh_from_db()
        idle_vehicle.refresh_from_db()
        self.assertEqual(available_driver.status, DriverStatus.ASSIGNED)
        self.assertEqual(idle_vehicle.assigned_driver, available_driver)

    def test_create_trip_with_conflict_driver_assignment_fails(self):
        # Create another trip payload with the same driver in the same time window
        available_driver = Driver.objects.create(
            name="Conflicting Driver",
            phone="+91 92222 44444",
            license_number="DL-DRV-CONFLICT",
            home_base="Delhi",
            status=DriverStatus.AVAILABLE,
        )
        
        trip_payload1 = {
            "booking_type": "ADHOC",
            "customer_name": "Passenger 1",
            "pickup_city": "Delhi",
            "drop_city": "Gurgaon",
            "pickup_at": (timezone.now() + timedelta(hours=5)).isoformat(),
            "estimated_drop_at": (timezone.now() + timedelta(hours=7)).isoformat(),
            "driver_id": available_driver.id,
            "fare_amount": "1000.00",
            "duty_type": DutyType.LOCAL_8HR_80KM,
            "vehicle_category_requested": "Sedan",
        }
        
        # Create first trip successfully (which marks the driver status as ASSIGNED)
        response1 = self.client.post("/api/fleet/trips/", trip_payload1, format="json")
        self.assertEqual(response1.status_code, 201)
        
        # Now try to create second trip with same driver in overlapping window
        trip_payload2 = {
            "booking_type": "ADHOC",
            "customer_name": "Passenger 2",
            "pickup_city": "Delhi",
            "drop_city": "Gurgaon",
            "pickup_at": (timezone.now() + timedelta(hours=6)).isoformat(),
            "estimated_drop_at": (timezone.now() + timedelta(hours=8)).isoformat(),
            "driver_id": available_driver.id,
            "fare_amount": "1000.00",
            "duty_type": DutyType.LOCAL_8HR_80KM,
            "vehicle_category_requested": "Sedan",
        }
        
        response2 = self.client.post("/api/fleet/trips/", trip_payload2, format="json")
        # Should fail validation due to overlapping window and driver not being AVAILABLE
        self.assertEqual(response2.status_code, 400)
