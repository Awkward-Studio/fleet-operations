from datetime import timedelta
from decimal import Decimal
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
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
    TripChecklist,
    TripStatus,
    Vehicle,
    VehicleStatus,
)
from accounts.models import UserRole
from media_store.models import UploadedAsset


class TripOperationsAPITest(APITestCase):
    @classmethod
    def setUpClass(cls):
        cls._temporary_media = TemporaryDirectory()
        cls._media_settings = override_settings(MEDIA_ROOT=cls._temporary_media.name)
        cls._media_settings.enable()
        try:
            super().setUpClass()
        except Exception:
            cls._media_settings.disable()
            cls._temporary_media.cleanup()
            raise

    @classmethod
    def tearDownClass(cls):
        try:
            super().tearDownClass()
        finally:
            cls._media_settings.disable()
            cls._temporary_media.cleanup()

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="driver-api",
            email="driver-api@example.com",
            password="driver123",
            role=UserRole.DRIVER,
        )
        license_asset = UploadedAsset.objects.create(
            kind=UploadedAsset.KIND_IMAGE,
            file_url="/media/test/license.jpg",
            original_name="license.jpg",
            content_type="image/jpeg",
        )
        self.evidence_asset = license_asset
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

    def _odometer_provenance(self, reference_km, *, source="MANUAL", decision=None, override=False, reason=""):
        payload = {
            "reading_source": source,
            "driver_confirmed": True,
            "expected_reference_km": reference_km,
            "client_version": "driver-app/test",
            "odometer_override": override,
            "odometer_override_reason": reason,
        }
        if decision is not None:
            payload["client_ocr_decision"] = decision
        return payload

    def _submit_start(
        self,
        *,
        reading=1005,
        reference=1000,
        key="start-helper",
        source="MANUAL",
        decision=None,
        override=False,
        reason="",
        **extra,
    ):
        payload = {
            "start_odometer_km": reading,
            "start_odometer_asset_id": str(self.evidence_asset.id),
            "idempotency_key": key,
            **self._odometer_provenance(
                reference,
                source=source,
                decision=decision,
                override=override,
                reason=reason,
            ),
            **extra,
        }
        return self.client.post(
            f"/api/fleet/trips/{self.trip.id}/checklist/", payload, format="json"
        )

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
            {"otp_code": code},
            format="json",
        )
        self.assertEqual(valid.status_code, 200)
        self.assertTrue(valid.data["otp"]["is_verified"])
        self.trip.refresh_from_db()
        self.vehicle.refresh_from_db()
        self.driver.refresh_from_db()
        self.assertEqual(self.trip.status, TripStatus.ACTIVE)
        self.assertEqual(self.vehicle.status, VehicleStatus.ACTIVE_TRIP)
        self.assertEqual(self.driver.status, DriverStatus.ON_TRIP)

    def test_mmt_otp_verifies_against_pricing_snapshot_and_blocks_local_generation(self):
        self.trip.ota_source = "GOMMT"
        self.trip.pricing_snapshot = {"verification_code": "2748"}
        self.trip.save(update_fields=["ota_source", "pricing_snapshot"])

        generated = self.client.post(
            f"/api/fleet/trips/{self.trip.id}/generate-otp/",
            {"digits": 4},
            format="json",
        )
        self.assertIn(generated.status_code, (200, 201))
        self.assertEqual(generated.data["code"], "2748")

        invalid = self.client.post(
            f"/api/fleet/trips/{self.trip.id}/verify-otp/",
            {"otp_code": "0000"},
            format="json",
        )
        self.assertEqual(invalid.status_code, 400)

        valid = self.client.post(
            f"/api/fleet/trips/{self.trip.id}/verify-otp/",
            {"otp_code": "2748"},
            format="json",
        )
        self.assertEqual(valid.status_code, 200)
        self.assertEqual(valid.data["trip"]["status"], TripStatus.ACTIVE)
        self.assertEqual(valid.data["trip"]["otp_mode"], "mmt")

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

    def test_location_rejects_completed_trip(self):
        self.trip.status = TripStatus.COMPLETED
        self.trip.save(update_fields=["status"])

        response = self.client.post(
            f"/api/fleet/trips/{self.trip.id}/location/",
            {
                "latitude": "28.48968000",
                "longitude": "77.09224000",
                "speed_kmh": 0,
                "heading": 0,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(TripLocationLog.objects.filter(trip=self.trip).count(), 0)

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
                **self._odometer_provenance(1000),
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
                **self._odometer_provenance(1005),
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

    def test_completion_rejects_equal_end_odometer(self):
        checklist = self.client.post(
            f"/api/fleet/trips/{self.trip.id}/checklist/",
            {
                "start_odometer_km": 1005,
                "start_odometer_photo": SimpleUploadedFile(
                    "start.jpg",
                    b"start-photo",
                    content_type="image/jpeg",
                ),
                "idempotency_key": "equal-odo-checklist-key",
                **self._odometer_provenance(1000),
            },
            format="multipart",
        )
        self.assertEqual(checklist.status_code, 201)

        complete = self.client.post(
            f"/api/fleet/trips/{self.trip.id}/complete/",
            {
                "end_odometer_km": 1005,
                "end_odometer_photo": SimpleUploadedFile(
                    "end.jpg",
                    b"end-photo",
                    content_type="image/jpeg",
                ),
                "idempotency_key": "equal-odo-complete-key",
                **self._odometer_provenance(1005),
            },
            format="multipart",
        )
        self.assertEqual(complete.status_code, 400)

    def test_odometer_contract_requires_confirmation_and_consistent_ocr_provenance(self):
        missing_confirmation = self.client.post(
            f"/api/fleet/trips/{self.trip.id}/checklist/",
            {
                "start_odometer_km": 1005,
                "start_odometer_asset_id": str(self.evidence_asset.id),
                "reading_source": "MANUAL",
                "expected_reference_km": 1000,
                "client_version": "driver-app/test",
            },
            format="json",
        )
        self.assertEqual(missing_confirmation.status_code, 400)
        self.assertIn("driver_confirmed", missing_confirmation.data)

        inconsistent_ocr = self.client.post(
            f"/api/fleet/trips/{self.trip.id}/checklist/",
            {
                "start_odometer_km": 1005,
                "start_odometer_asset_id": str(self.evidence_asset.id),
                **self._odometer_provenance(
                    1000, source="OCR_CONFIRMED", decision="NEEDS_REVIEW"
                ),
            },
            format="json",
        )
        self.assertEqual(inconsistent_ocr.status_code, 400)
        self.assertIn("client_ocr_decision", inconsistent_ocr.data)
        self.assertFalse(TripChecklist.objects.filter(trip=self.trip).exists())

    def test_start_rejects_stale_reference_without_any_trip_mutation(self):
        self.vehicle.odometer_km = 1002
        self.vehicle.save(update_fields=["odometer_km"])

        response = self._submit_start(reading=1005, reference=1000, key="stale-start")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "ODOMETER_REFERENCE_CONFLICT")
        self.assertEqual(response.data["authoritative_reference_km"], 1002)
        self.assertFalse(TripChecklist.objects.filter(trip=self.trip).exists())
        self.trip.refresh_from_db()
        self.vehicle.refresh_from_db()
        self.driver.refresh_from_db()
        self.assertEqual(self.trip.status, TripStatus.ASSIGNED)
        self.assertEqual(self.vehicle.status, VehicleStatus.IDLE)
        self.assertEqual(self.driver.status, DriverStatus.ASSIGNED)

    def test_start_rejects_implausible_delta_and_unprivileged_override(self):
        implausible = self._submit_start(reading=1501, key="implausible-start")
        self.assertEqual(implausible.status_code, 400)
        self.assertEqual(implausible.data["code"], "ODOMETER_PLAUSIBILITY_REJECTED")

        unauthorized = self._submit_start(
            reading=999,
            key="unauthorized-override",
            override=True,
            reason="Verified maintenance replacement cluster.",
        )
        self.assertEqual(unauthorized.status_code, 403)
        self.assertFalse(TripChecklist.objects.filter(trip=self.trip).exists())

    def test_authorized_override_is_reasoned_and_audited(self):
        self.user.role = UserRole.OPERATIONS_APPROVER
        self.user.save(update_fields=["role"])
        response = self._submit_start(
            reading=999,
            reference=998,
            key="authorized-override",
            override=True,
            reason="Instrument cluster replaced after workshop repair.",
        )

        self.assertEqual(response.status_code, 201)
        checklist = TripChecklist.objects.get(trip=self.trip)
        self.assertEqual(checklist.start_reading_source, "MANUAL")
        self.assertTrue(checklist.start_driver_confirmed)
        self.assertIsNotNone(checklist.start_confirmed_at)
        self.assertEqual(checklist.start_expected_reference_km, 998)
        self.assertEqual(checklist.start_client_version, "driver-app/test")
        self.assertEqual(checklist.start_overridden_by, self.user)
        self.assertIn("cluster replaced", checklist.start_override_reason)

    def test_ocr_provenance_is_persisted_without_raw_recognizer_output(self):
        response = self._submit_start(
            source="OCR_CONFIRMED",
            decision="ACCEPTED",
        )
        self.assertEqual(response.status_code, 201)
        checklist = TripChecklist.objects.get(trip=self.trip)
        self.assertEqual(checklist.start_reading_source, "OCR_CONFIRMED")
        self.assertEqual(checklist.start_client_ocr_decision, "ACCEPTED")
        serialized_keys = set(response.data.keys())
        self.assertNotIn("raw_text", serialized_keys)
        self.assertNotIn("confidence", serialized_keys)

    def test_completion_rejects_stale_reference_without_partial_mutation(self):
        self.assertEqual(self._submit_start().status_code, 201)
        response = self.client.post(
            f"/api/fleet/trips/{self.trip.id}/complete/",
            {
                "end_odometer_km": 1042,
                "end_odometer_asset_id": str(self.evidence_asset.id),
                "idempotency_key": "stale-complete",
                **self._odometer_provenance(1004),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 409)
        checklist = TripChecklist.objects.get(trip=self.trip)
        self.assertIsNone(checklist.end_odometer_km)
        self.trip.refresh_from_db()
        self.vehicle.refresh_from_db()
        self.driver.refresh_from_db()
        self.assertEqual(self.trip.status, TripStatus.EN_ROUTE_PICKUP)
        self.assertEqual(self.vehicle.odometer_km, 1000)
        self.assertEqual(self.driver.status, DriverStatus.ON_TRIP)

    def test_completion_failure_rolls_back_asset_and_all_operational_state(self):
        self.assertEqual(self._submit_start().status_code, 201)
        asset_count = UploadedAsset.objects.count()
        self.client.raise_request_exception = False
        with patch(
            "billing.services.CloseoutService.create_from_trip_completion",
            side_effect=RuntimeError("forced closeout failure"),
        ):
            response = self.client.post(
                f"/api/fleet/trips/{self.trip.id}/complete/",
                {
                    "end_odometer_km": 1042,
                    "end_odometer_photo": SimpleUploadedFile(
                        "rollback-end.jpg", b"rollback-photo", content_type="image/jpeg"
                    ),
                    "idempotency_key": "rollback-complete",
                    **self._odometer_provenance(1005),
                },
                format="multipart",
            )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(UploadedAsset.objects.count(), asset_count)
        checklist = TripChecklist.objects.get(trip=self.trip)
        self.assertIsNone(checklist.end_odometer_km)
        self.assertIsNone(checklist.end_odometer_asset_id)
        self.assertIsNone(checklist.complete_idempotency_key)
        self.trip.refresh_from_db()
        self.vehicle.refresh_from_db()
        self.driver.refresh_from_db()
        self.assertEqual(self.trip.status, TripStatus.EN_ROUTE_PICKUP)
        self.assertEqual(self.vehicle.status, VehicleStatus.EN_ROUTE_PICKUP)
        self.assertEqual(self.vehicle.odometer_km, 1000)
        self.assertEqual(self.driver.status, DriverStatus.ON_TRIP)

    def test_idempotency_key_cannot_return_or_mutate_another_trip(self):
        self.assertEqual(self._submit_start(key="trip-bound-key").status_code, 201)
        other_trip = Trip.objects.create(
            customer_name="Other passenger",
            pickup_city="Delhi",
            drop_city="Gurgaon",
            pickup_at=timezone.now() + timedelta(hours=3),
            estimated_drop_at=timezone.now() + timedelta(hours=5),
            status=TripStatus.ASSIGNED,
            vehicle=self.vehicle,
            driver=self.driver,
            fare_amount=1200,
        )

        response = self.client.post(
            f"/api/fleet/trips/{other_trip.id}/checklist/",
            {
                "start_odometer_km": 1006,
                "start_odometer_asset_id": str(self.evidence_asset.id),
                "idempotency_key": "trip-bound-key",
                **self._odometer_provenance(1000),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertFalse(TripChecklist.objects.filter(trip=other_trip).exists())

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
