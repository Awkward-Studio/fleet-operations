import random
from decimal import Decimal
from datetime import timedelta

from accounts.models import UserRole
from django.conf import settings
from django.db import models
from django.db.models import Count, Q
from django.db import transaction
from django.core.files.storage import default_storage
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from media_store.models import UploadedAsset
from media_store.storage import upload_asset

from .models import (
    ContractAllowance,
    ContractRate,
    CorporateContract,
    CorporateCustomer,
    CustomerContact,
    CustomerStatus,
    Driver,
    DriverStatus,
    RateBook,
    RatePackage,
    Trip,
    TripChecklist,
    TripLocationLog,
    TripOTP,
    TripStatus,
    Vehicle,
    VehicleStatus,
    FuelTransaction,
    FuelTransactionStatus,
    FuelType,
    FuelUnit,
)
from .permissions import IsCommercialAdminOrReadOnly, IsCommercialAdmin
from .pricing_service import PricingError, calculate_quote, calculate_unified_quote
from .serializers import (
    AssignTripSerializer,
    AvailabilitySerializer,
    ContractAllowanceSerializer,
    ContractRateSerializer,
    CorporateContractSerializer,
    CorporateCustomerSerializer,
    CustomerContactSerializer,
    DriverSerializer,
    RateBookSerializer,
    RatePackageSerializer,
    TripChecklistSerializer,
    TripChecklistSubmitSerializer,
    TripCompleteSerializer,
    TripGenerateOTPSerializer,
    TripLocationLogSerializer,
    TripOTPSerializer,
    TripVerifyOTPSerializer,
    TransitionTripSerializer,
    TripSerializer,
    VehicleSerializer,
    FuelTransactionSerializer,
    FuelTransactionDetailSerializer,
)
from rest_framework import permissions


def _get_idempotency_key(request, serializer=None):
    if serializer is not None and getattr(serializer, "validated_data", None):
        key = serializer.validated_data.get("idempotency_key")
        if key:
            return key
    return request.headers.get("Idempotency-Key") or request.headers.get("X-Idempotency-Key")


def _store_private_trip_asset(upload, folder, request):
    return upload_asset(
        upload,
        kind=UploadedAsset.KIND_IMAGE,
        folder=f"trip-assets/{folder}",
        request=request,
        metadata={"source": "fleet.trip_operation", "folder": folder},
    )


def _delete_asset_blob(asset):
    if asset and asset.storage_key:
        default_storage.delete(asset.storage_key)


def _can_override_odometer(user):
    return bool(user and user.is_authenticated)


def _odometer_guard_response(request, data, *, submitted_km, reference_km, maximum_delta_km, phase):
    override_requested = data["odometer_override"]
    if override_requested and not _can_override_odometer(request.user):
        return Response(
            {"detail": "Only an administrator or operations approver may override odometer safeguards."},
            status=status.HTTP_403_FORBIDDEN,
        )

    problems = []
    stale_reference = data["expected_reference_km"] != reference_km
    if stale_reference:
        problems.append("The odometer reference changed after this screen was loaded.")
    if phase == "start" and submitted_km < reference_km:
        problems.append("Start odometer cannot be below the vehicle odometer.")
    if phase == "end" and submitted_km <= reference_km:
        problems.append("End odometer must be greater than the trip start odometer.")
    if submitted_km > reference_km and submitted_km - reference_km > maximum_delta_km:
        problems.append(
            f"The reading exceeds the configured {phase} delta of {maximum_delta_km} km."
        )

    if problems and not override_requested:
        return Response(
            {
                "detail": " ".join(problems),
                "code": (
                    "ODOMETER_REFERENCE_CONFLICT"
                    if stale_reference
                    else "ODOMETER_PLAUSIBILITY_REJECTED"
                ),
                "authoritative_reference_km": reference_km,
            },
            status=(status.HTTP_409_CONFLICT if stale_reference else status.HTTP_400_BAD_REQUEST),
        )
    return None


def _odometer_provenance(data, *, prefix, user):
    overridden_by = user if data["odometer_override"] and user.is_authenticated else None
    return {
        f"{prefix}_reading_source": data["reading_source"],
        f"{prefix}_driver_confirmed": data["driver_confirmed"],
        f"{prefix}_confirmed_at": timezone.now(),
        f"{prefix}_expected_reference_km": data["expected_reference_km"],
        f"{prefix}_client_ocr_decision": data.get("client_ocr_decision"),
        f"{prefix}_client_version": data["client_version"],
        f"{prefix}_override_reason": data["odometer_override_reason"],
        f"{prefix}_overridden_by": overridden_by,
    }


def _assert_driver_can_operate_trip(request, trip):
    if not trip.driver_id:
        return Response({"detail": "Trip has no assigned driver."}, status=status.HTTP_400_BAD_REQUEST)

    if request.user.is_authenticated and hasattr(request.user, "driver_profile"):
        if request.user.driver_profile.id != trip.driver_id:
            return Response({"detail": "This trip is not assigned to the logged-in driver."}, status=status.HTTP_403_FORBIDDEN)

    return None


def _assert_trip_compliance(trip):
    if not trip.vehicle_id:
        return Response({"detail": "Trip has no assigned vehicle."}, status=status.HTTP_400_BAD_REQUEST)
    if not trip.vehicle.is_compliant:
        return Response(
            {"detail": "Vehicle compliance documents block trip start.", "blockers": trip.vehicle.compliance_blockers},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not trip.driver_id:
        return Response({"detail": "Trip has no assigned driver."}, status=status.HTTP_400_BAD_REQUEST)
    if not trip.driver.driving_license:
        return Response({"detail": "Driver driving license document is missing."}, status=status.HTTP_400_BAD_REQUEST)
    if trip.driver.driving_license_expiry_date and trip.driver.driving_license_expiry_date < timezone.localdate():
        return Response({"detail": "Driver driving license is expired."}, status=status.HTTP_400_BAD_REQUEST)
    return None


def _generate_numeric_otp(digits):
    lower = 10 ** (digits - 1)
    upper = (10 ** digits) - 1
    return str(random.randint(lower, upper))


def _ensure_local_trip_otp(trip, request, digits=4, idempotency_key=None):
    otp_session = getattr(trip, "otp_session", None)
    if otp_session and not otp_session.is_verified:
        return otp_session, False

    if trip.is_mmt_booking and trip.mmt_verification_code:
        code = trip.mmt_verification_code
    else:
        code = _generate_numeric_otp(digits)

    user = getattr(request, "user", None)
    generated_by = user if (user and getattr(user, "is_authenticated", False)) else None

    otp_session, created = TripOTP.objects.update_or_create(
        trip=trip,
        defaults={
            "code": code,
            "is_verified": False,
            "idempotency_key": idempotency_key,
            "generated_by": generated_by,
            "verified_by": None,
            "verified_at": None,
        },
    )
    return otp_session, created



@api_view(["GET"])
def current_driver_trip(request):
    if not request.user.is_authenticated:
        return Response({"detail": "Authentication credentials were not provided."}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        driver = request.user.driver_profile
    except Driver.DoesNotExist:
        return Response(None, status=status.HTTP_200_OK)

    trip = (
        Trip.objects.select_related("vehicle", "driver")
        .filter(
            driver=driver,
            status__in=[
                TripStatus.ASSIGNED,
                TripStatus.EN_ROUTE_PICKUP,
                TripStatus.ARRIVED_AT_PICKUP,
                TripStatus.ACTIVE,
            ],
        )
        .order_by("pickup_at")
        .first()
    )
    if not trip:
        return Response(None, status=status.HTTP_200_OK)

    return Response(TripSerializer(trip, context={"request": request}).data, status=status.HTTP_200_OK)


class DriverViewSet(viewsets.ModelViewSet):
    queryset = Driver.objects.all().order_by("name")
    serializer_class = DriverSerializer

    @action(detail=False, methods=["get"])
    def me(self, request):
        try:
            driver = request.user.driver_profile
        except Driver.DoesNotExist:
            return Response({"detail": "No driver profile is linked to this user."}, status=status.HTTP_404_NOT_FOUND)

        return Response(self.get_serializer(driver).data)


class VehicleViewSet(viewsets.ModelViewSet):
    queryset = Vehicle.objects.select_related("assigned_driver").all().order_by("registration_number")
    serializer_class = VehicleSerializer


class TripViewSet(viewsets.ModelViewSet):
    queryset = Trip.objects.select_related("vehicle", "driver").all()
    serializer_class = TripSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        trip = self.get_object()
        serializer = AssignTripSerializer(data=request.data, context={"trip": trip})
        serializer.is_valid(raise_exception=True)

        trip.vehicle = serializer.validated_data["vehicle"]
        trip.driver = serializer.validated_data["driver"]
        trip.status = TripStatus.ASSIGNED
        trip.save(update_fields=["vehicle", "driver", "status", "updated_at"])

        trip.vehicle.assigned_driver = trip.driver
        trip.vehicle.status = VehicleStatus.IDLE
        trip.vehicle.save(update_fields=["assigned_driver", "status"])

        trip.driver.status = DriverStatus.ASSIGNED
        trip.driver.save(update_fields=["status"])

        return Response(TripSerializer(trip).data)

    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        trip = self.get_object()
        serializer = TransitionTripSerializer(data=request.data, context={"trip": trip})
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            trip = serializer.save()
            if trip.status == TripStatus.ARRIVED_AT_PICKUP:
                _ensure_local_trip_otp(trip, request, digits=4)
        return Response(TripSerializer(trip).data)

    @action(detail=True, methods=["post"])
    def checklist(self, request, pk=None):
        trip = self.get_object()
        permission_error = _assert_driver_can_operate_trip(request, trip)
        if permission_error:
            return permission_error

        serializer = TripChecklistSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        idempotency_key = _get_idempotency_key(request, serializer)
        if idempotency_key:
            existing = TripChecklist.objects.filter(start_idempotency_key=idempotency_key).first()
            if existing:
                if existing.trip_id != trip.id:
                    return Response(
                        {"detail": "The idempotency key is already bound to another trip."},
                        status=status.HTTP_409_CONFLICT,
                    )
                return Response(TripChecklistSerializer(existing, context={"request": request}).data, status=status.HTTP_200_OK)

        created_asset = None
        try:
            with transaction.atomic():
                trip = Trip.objects.select_for_update().select_related("driver", "vehicle").get(pk=trip.pk)
                if idempotency_key:
                    existing = TripChecklist.objects.select_for_update().filter(
                        start_idempotency_key=idempotency_key
                    ).first()
                    if existing:
                        if existing.trip_id != trip.id:
                            return Response(
                                {"detail": "The idempotency key is already bound to another trip."},
                                status=status.HTTP_409_CONFLICT,
                            )
                        return Response(
                            TripChecklistSerializer(existing, context={"request": request}).data,
                            status=status.HTTP_200_OK,
                        )
                if TripChecklist.objects.select_for_update().filter(trip=trip).exists():
                    return Response(
                        {"detail": "The start checklist has already been submitted."},
                        status=status.HTTP_409_CONFLICT,
                    )

                compliance_error = _assert_trip_compliance(trip)
                if compliance_error:
                    return compliance_error
                vehicle = Vehicle.objects.select_for_update().get(pk=trip.vehicle_id)
                guard_error = _odometer_guard_response(
                    request,
                    serializer.validated_data,
                    submitted_km=serializer.validated_data["start_odometer_km"],
                    reference_km=vehicle.odometer_km,
                    maximum_delta_km=getattr(settings, "ODOMETER_MAX_START_DELTA_KM", 500),
                    phase="start",
                )
                if guard_error:
                    return guard_error

                start_asset = serializer.validated_data.get("start_odometer_asset")
                upload = serializer.validated_data.get("start_odometer_photo")
                if upload:
                    created_asset = _store_private_trip_asset(upload, "odometers/start", request)
                    start_asset = created_asset

                checklist = TripChecklist.objects.create(
                    trip=trip,
                    start_odometer_km=serializer.validated_data["start_odometer_km"],
                    start_odometer_asset=start_asset,
                    cleanliness_ok=serializer.validated_data["cleanliness_ok"],
                    fuel_level_percent=serializer.validated_data["fuel_level_percent"],
                    tire_pressure_ok=serializer.validated_data["tire_pressure_ok"],
                    notes=serializer.validated_data.get("notes", ""),
                    start_idempotency_key=idempotency_key,
                    created_by=request.user if request.user.is_authenticated else None,
                    **_odometer_provenance(serializer.validated_data, prefix="start", user=request.user),
                )
                trip.status = TripStatus.EN_ROUTE_PICKUP
                trip.save(update_fields=["status", "updated_at"])
                vehicle.status = VehicleStatus.EN_ROUTE_PICKUP
                vehicle.save(update_fields=["status"])
                if trip.driver_id:
                    driver = Driver.objects.select_for_update().get(pk=trip.driver_id)
                    driver.status = DriverStatus.ON_TRIP
                    driver.save(update_fields=["status"])
        except Exception:
            _delete_asset_blob(created_asset)
            raise

        return Response(
            TripChecklistSerializer(checklist, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get", "post"])
    def location(self, request, pk=None):
        trip = self.get_object()
        if request.method.lower() == "get":
            logs = TripLocationLog.objects.filter(trip=trip).order_by("timestamp", "id")
            serializer = TripLocationLogSerializer(logs, many=True)
            latest = logs.last()
            return Response(
                {
                    "trip_id": trip.id,
                    "total_pings": logs.count(),
                    "latest_ping": TripLocationLogSerializer(latest).data if latest else None,
                    "logs": serializer.data,
                    "trajectory": [
                        [float(l.latitude), float(l.longitude)]
                        for l in logs
                        if l.latitude is not None and l.longitude is not None
                    ],
                },
                status=status.HTTP_200_OK,
            )

        if trip.driver_id:
            permission_error = _assert_driver_can_operate_trip(request, trip)
            if permission_error:
                return permission_error

        serializer = TripLocationLogSerializer(data=request.data)
        if not serializer.is_valid():
            print("=== LOCATION LOG SERIALIZER ERROR ===")
            print("Errors:", serializer.errors)
            print("Received Payload:", request.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        idempotency_key = _get_idempotency_key(request, serializer)
        if idempotency_key:
            existing = TripLocationLog.objects.filter(idempotency_key=idempotency_key).first()
            if existing:
                return Response(TripLocationLogSerializer(existing).data, status=status.HTTP_200_OK)

        location_log = serializer.save(
            trip=trip,
            idempotency_key=idempotency_key,
            recorded_by=request.user if request.user.is_authenticated else None,
        )
        return Response(TripLocationLogSerializer(location_log).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="generate-otp")
    def generate_otp(self, request, pk=None):
        trip = self.get_object()
        permission_error = _assert_driver_can_operate_trip(request, trip)
        if permission_error:
            return permission_error

        serializer = TripGenerateOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        idempotency_key = _get_idempotency_key(request, serializer)
        if idempotency_key:
            existing = TripOTP.objects.filter(idempotency_key=idempotency_key).first()
            if existing:
                return Response(TripOTPSerializer(existing).data, status=status.HTTP_200_OK)

        otp_session, created = _ensure_local_trip_otp(
            trip,
            request,
            digits=serializer.validated_data.get("digits", 4),
            idempotency_key=idempotency_key,
        )
        return Response(
            TripOTPSerializer(otp_session).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="verify-otp")
    def verify_otp(self, request, pk=None):
        trip = self.get_object()
        permission_error = _assert_driver_can_operate_trip(request, trip)
        if permission_error:
            return permission_error

        serializer = TripVerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data["code"]

        otp_session, _ = _ensure_local_trip_otp(trip, request)
        expected_codes = {otp_session.code}
        if trip.is_mmt_booking and trip.mmt_verification_code:
            expected_codes.add(trip.mmt_verification_code)

        if code not in expected_codes:
            return Response({"detail": "Invalid OTP."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            otp_session.is_verified = True
            otp_session.verified_by = request.user if request.user.is_authenticated else None
            otp_session.verified_at = timezone.now()
            otp_session.save(update_fields=["is_verified", "verified_by", "verified_at", "updated_at"])

            transition_serializer = TransitionTripSerializer(
                data={"status": TripStatus.ACTIVE},
                context={"trip": trip},
            )
            transition_serializer.is_valid(raise_exception=True)
            transition_serializer.save()

        return Response(
            {
                "otp": TripOTPSerializer(otp_session).data,
                "trip": TripSerializer(trip, context={"request": request}).data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        trip = self.get_object()
        permission_error = _assert_driver_can_operate_trip(request, trip)
        if permission_error:
            return permission_error

        retry_key = (
            request.data.get("idempotency_key")
            or request.headers.get("Idempotency-Key")
            or request.headers.get("X-Idempotency-Key")
        )
        if retry_key:
            existing = TripChecklist.objects.filter(complete_idempotency_key=retry_key).first()
            if existing:
                if existing.trip_id != trip.id:
                    return Response(
                        {"detail": "The idempotency key is already bound to another trip."},
                        status=status.HTTP_409_CONFLICT,
                    )
                if existing.trip.status == TripStatus.COMPLETED:
                    from billing.services import CloseoutService
                    CloseoutService.create_from_trip_completion(existing.trip_id, retry_key)
                return Response(
                    TripChecklistSerializer(existing, context={"request": request}).data,
                    status=status.HTTP_200_OK,
                )

        serializer = TripCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        idempotency_key = _get_idempotency_key(request, serializer)
        if idempotency_key:
            existing = TripChecklist.objects.filter(complete_idempotency_key=idempotency_key).first()
            if existing:
                if existing.trip_id != trip.id:
                    return Response(
                        {"detail": "The idempotency key is already bound to another trip."},
                        status=status.HTTP_409_CONFLICT,
                    )
                if existing.trip.status == TripStatus.COMPLETED:
                    from billing.services import CloseoutService
                    CloseoutService.create_from_trip_completion(existing.trip_id, idempotency_key)
                return Response(TripChecklistSerializer(existing, context={"request": request}).data, status=status.HTTP_200_OK)

        end_odometer_km = serializer.validated_data["end_odometer_km"]
        created_asset = None
        try:
            with transaction.atomic():
                trip = Trip.objects.select_for_update().select_related("driver", "vehicle").get(pk=trip.pk)
                if idempotency_key:
                    existing = TripChecklist.objects.select_for_update().filter(
                        complete_idempotency_key=idempotency_key
                    ).first()
                    if existing:
                        if existing.trip_id != trip.id:
                            return Response(
                                {"detail": "The idempotency key is already bound to another trip."},
                                status=status.HTTP_409_CONFLICT,
                            )
                        return Response(
                            TripChecklistSerializer(existing, context={"request": request}).data,
                            status=status.HTTP_200_OK,
                        )
                try:
                    checklist = TripChecklist.objects.select_for_update().get(trip=trip)
                except TripChecklist.DoesNotExist:
                    return Response(
                        {"detail": "Start checklist must be submitted before completing trip."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if checklist.end_odometer_km is not None:
                    return Response(
                        {"detail": "The trip completion has already been submitted."},
                        status=status.HTTP_409_CONFLICT,
                    )

                guard_error = _odometer_guard_response(
                    request,
                    serializer.validated_data,
                    submitted_km=end_odometer_km,
                    reference_km=checklist.start_odometer_km,
                    maximum_delta_km=getattr(settings, "ODOMETER_MAX_TRIP_DELTA_KM", 1000),
                    phase="end",
                )
                if guard_error:
                    return guard_error

                end_asset = serializer.validated_data.get("end_odometer_asset")
                upload = serializer.validated_data.get("end_odometer_photo")
                if upload:
                    created_asset = _store_private_trip_asset(upload, "odometers/end", request)
                    end_asset = created_asset

                checklist.end_odometer_km = end_odometer_km
                checklist.end_odometer_asset = end_asset
                checklist.complete_idempotency_key = idempotency_key
                checklist.completed_by = request.user if request.user.is_authenticated else None
                for field, value in _odometer_provenance(
                    serializer.validated_data, prefix="end", user=request.user
                ).items():
                    setattr(checklist, field, value)
                if serializer.validated_data.get("notes"):
                    checklist.notes = serializer.validated_data["notes"]
                checklist.save()

                trip.status = TripStatus.COMPLETED
                trip.distance_km = Decimal(end_odometer_km - checklist.start_odometer_km)
                trip.save(update_fields=["status", "distance_km", "updated_at"])
                if trip.vehicle_id:
                    vehicle = Vehicle.objects.select_for_update().get(pk=trip.vehicle_id)
                    vehicle.status = VehicleStatus.IDLE
                    vehicle.current_city = trip.drop_city
                    vehicle.odometer_km = end_odometer_km
                    vehicle.save(update_fields=["status", "current_city", "odometer_km"])
                if trip.driver_id:
                    driver = Driver.objects.select_for_update().get(pk=trip.driver_id)
                    driver.status = DriverStatus.AVAILABLE
                    driver.save(update_fields=["status"])
                from billing.services import CloseoutService
                CloseoutService.create_from_trip_completion(trip.id, idempotency_key)
        except Exception:
            _delete_asset_blob(created_asset)
            raise

        return Response(TripChecklistSerializer(checklist, context={"request": request}).data, status=status.HTTP_200_OK)


class CorporateCustomerViewSet(viewsets.ModelViewSet):
    permission_classes = [IsCommercialAdminOrReadOnly]
    serializer_class = CorporateCustomerSerializer

    def get_queryset(self):
        qs = CorporateCustomer.objects.prefetch_related("contacts", "contracts", "contracts__rates").all()
        search = self.request.query_params.get("search") or self.request.query_params.get("q")
        if search:
            qs = qs.filter(
                Q(display_name__icontains=search)
                | Q(legal_name__icontains=search)
                | Q(code__icontains=search)
                | Q(gstin__icontains=search)
            )
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param.upper())
        is_active_param = self.request.query_params.get("is_active")
        if is_active_param is not None:
            val = is_active_param.lower() in ["true", "1"]
            qs = qs.filter(is_active=val)
        return qs.order_by("display_name")

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        # Soft deactivate instead of hard delete
        instance.is_active = False
        instance.status = CustomerStatus.INACTIVE
        instance.save(update_fields=["is_active", "status", "updated_at"])
        return Response(
            {"detail": f"Customer '{instance.display_name}' deactivated successfully."},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get", "post"])
    def contacts(self, request, pk=None):
        customer = self.get_object()
        if request.method == "GET":
            contacts = customer.contacts.all()
            return Response(CustomerContactSerializer(contacts, many=True).data)
        elif request.method == "POST":
            data = request.data.copy()
            data["customer"] = customer.id
            serializer = CustomerContactSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)


class CustomerContactViewSet(viewsets.ModelViewSet):
    permission_classes = [IsCommercialAdminOrReadOnly]
    serializer_class = CustomerContactSerializer

    def get_queryset(self):
        qs = CustomerContact.objects.select_related("customer").all()
        customer_id = self.request.query_params.get("customer")
        if customer_id:
            qs = qs.filter(customer_id=customer_id)
        contact_type = self.request.query_params.get("contact_type")
        if contact_type:
            qs = qs.filter(contact_type=contact_type)
        return qs.order_by("-is_primary", "name")


class CorporateContractViewSet(viewsets.ModelViewSet):
    permission_classes = [IsCommercialAdminOrReadOnly]
    serializer_class = CorporateContractSerializer

    def get_queryset(self):
        qs = CorporateContract.objects.select_related("customer").prefetch_related("rates", "allowances").all()
        customer_id = self.request.query_params.get("customer")
        if customer_id:
            qs = qs.filter(customer_id=customer_id)
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param.upper())
        eff_date = self.request.query_params.get("effective_date")
        if eff_date:
            qs = qs.filter(
                effective_start__lte=eff_date
            ).filter(
                models.Q(effective_end__isnull=True) | models.Q(effective_end__gte=eff_date)
            )
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(
                Q(title__icontains=search)
                | Q(version_name__icontains=search)
                | Q(customer__display_name__icontains=search)
            )
        return qs.order_by("-effective_start")

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        contract = self.get_object()
        serializer = self.get_serializer(contract, data={"status": "ACTIVE"}, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def validate_contract(self, request, pk=None):
        contract = self.get_object()
        errors = []
        warnings = []

        if contract.effective_end and contract.effective_end < contract.effective_start:
            errors.append("Effective end date cannot precede effective start date.")

        rates_count = contract.rates.count()
        if rates_count == 0:
            errors.append("Contract contains no rate rows.")

        # Check overlapping active contracts
        overlaps = CorporateContract.objects.filter(
            customer=contract.customer,
            status="ACTIVE",
        ).exclude(pk=contract.pk)

        for c in overlaps:
            c_start = c.effective_start
            c_end = c.effective_end
            start = contract.effective_start
            end = contract.effective_end
            if c_end is None and (end is None or end >= c_start):
                errors.append(f"Overlaps with active contract '{c.title}' ({c.version_name}).")
            elif end is None and (c_end is None or c_end >= start):
                errors.append(f"Overlaps with active contract '{c.title}' ({c.version_name}).")
            elif c_end and end and (start <= c_end and end >= c_start):
                errors.append(f"Overlaps with active contract '{c.title}' ({c.version_name}).")

        if contract.allowances.count() == 0:
            warnings.append("No contract allowances configured.")

        is_valid = len(errors) == 0
        return Response({
            "is_valid": is_valid,
            "errors": errors,
            "warnings": warnings,
            "rates_count": rates_count,
            "allowances_count": contract.allowances.count(),
        })

    @action(detail=True, methods=["post"])
    def copy_contract(self, request, pk=None):
        contract = self.get_object()
        from django.db import transaction
        with transaction.atomic():
            new_contract = CorporateContract.objects.create(
                customer=contract.customer,
                title=f"{contract.title} (Copy)",
                version_name=f"{contract.version_name}.1",
                effective_start=timezone.localdate(),
                effective_end=contract.effective_end,
                status="DRAFT",
                currency=contract.currency,
                cgst_rate=contract.cgst_rate,
                sgst_rate=contract.sgst_rate,
                payment_terms_days=contract.payment_terms_days,
                cancellation_terms=contract.cancellation_terms,
                metering_policy=contract.metering_policy,
                notes=contract.notes,
            )

            for r in contract.rates.all():
                ContractRate.objects.create(
                    contract=new_contract,
                    city=r.city,
                    vehicle_category=r.vehicle_category,
                    duty_type=r.duty_type,
                    included_hours=r.included_hours,
                    included_km=r.included_km,
                    base_rate=r.base_rate,
                    extra_hour_rate=r.extra_hour_rate,
                    extra_km_rate=r.extra_km_rate,
                    switch_threshold_hours=r.switch_threshold_hours,
                    switch_threshold_km=r.switch_threshold_km,
                    outstation_daily_min_km=r.outstation_daily_min_km,
                )

            for a in contract.allowances.all():
                ContractAllowance.objects.create(
                    contract=new_contract,
                    allowance_type=a.allowance_type,
                    amount=a.amount,
                    description=a.description,
                )

        serializer = self.get_serializer(new_contract)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ContractRateViewSet(viewsets.ModelViewSet):
    permission_classes = [IsCommercialAdminOrReadOnly]
    serializer_class = ContractRateSerializer

    def get_queryset(self):
        qs = ContractRate.objects.select_related("contract", "contract__customer").all()
        contract_id = self.request.query_params.get("contract")
        if contract_id:
            qs = qs.filter(contract_id=contract_id)
        city = self.request.query_params.get("city")
        if city:
            qs = qs.filter(city__iexact=city.strip())
        category = self.request.query_params.get("vehicle_category")
        if category:
            qs = qs.filter(vehicle_category__iexact=category.strip())
        duty_type = self.request.query_params.get("duty_type")
        if duty_type:
            qs = qs.filter(duty_type=duty_type)
        return qs.order_by("city", "vehicle_category", "duty_type")


class ContractAllowanceViewSet(viewsets.ModelViewSet):
    permission_classes = [IsCommercialAdminOrReadOnly]
    serializer_class = ContractAllowanceSerializer

    def get_queryset(self):
        qs = ContractAllowance.objects.select_related("contract").all()
        contract_id = self.request.query_params.get("contract")
        if contract_id:
            qs = qs.filter(contract_id=contract_id)
        return qs.order_by("allowance_type")


@api_view(["GET"])
def availability(request):
    records = []
    buffer_minutes = int(request.query_params.get("buffer_minutes", "60"))
    active_statuses = [TripStatus.ASSIGNED, TripStatus.EN_ROUTE_PICKUP, TripStatus.ACTIVE]

    for vehicle in Vehicle.objects.select_related("assigned_driver").all():
        latest_trip = (
            Trip.objects.filter(vehicle=vehicle, status__in=active_statuses)
            .order_by("-estimated_drop_at")
            .first()
        )

        if latest_trip:
            available_from = latest_trip.estimated_drop_at + timedelta(minutes=buffer_minutes)
            available_city = latest_trip.drop_city
        else:
            available_from = timezone.now()
            available_city = vehicle.current_city

        records.append(
            {
                "vehicle_id": vehicle.id,
                "registration_number": vehicle.registration_number,
                "category": vehicle.category,
                "available_from": available_from,
                "available_city": available_city,
                "driver_name": vehicle.assigned_driver.name if vehicle.assigned_driver else None,
                "compliance_blockers": vehicle.compliance_blockers,
            }
        )

    serializer = AvailabilitySerializer(records, many=True)
    return Response(serializer.data)


@api_view(["GET"])
def dashboard_summary(request):
    today = timezone.localdate()
    expiring_soon = today + timedelta(days=15)
    trips_today = Trip.objects.filter(pickup_at__date=today)

    data = {
        "vehicles": {
            "total": Vehicle.objects.count(),
            "idle": Vehicle.objects.filter(status=VehicleStatus.IDLE).count(),
            "on_trip": Vehicle.objects.filter(status__in=[VehicleStatus.EN_ROUTE_PICKUP, VehicleStatus.ACTIVE_TRIP]).count(),
            "maintenance": Vehicle.objects.filter(status=VehicleStatus.MAINTENANCE).count(),
        },
        "drivers": {
            "total": Driver.objects.count(),
            "available": Driver.objects.filter(status=DriverStatus.AVAILABLE).count(),
            "assigned": Driver.objects.filter(status=DriverStatus.ASSIGNED).count(),
            "on_trip": Driver.objects.filter(status=DriverStatus.ON_TRIP).count(),
        },
        "trips": {
            "today": trips_today.count(),
            "unassigned": Trip.objects.filter(status=TripStatus.REQUESTED).count(),
            "active": Trip.objects.filter(status__in=[TripStatus.EN_ROUTE_PICKUP, TripStatus.ACTIVE]).count(),
        },
        "compliance_alerts": Vehicle.objects.filter(
            Q(permit_expires_on__lte=expiring_soon)
            | Q(insurance_expires_on__lte=expiring_soon)
            | Q(pollution_expires_on__lte=expiring_soon)
            | Q(fitness_expires_on__lte=expiring_soon)
        ).count(),
        "vehicle_status_breakdown": list(Vehicle.objects.values("status").annotate(count=Count("id"))),
    }

    return Response(data, status=status.HTTP_200_OK)


@api_view(["POST"])
def quote_api(request):
    data = request.data
    customer_id = data.get("customer") or data.get("customer_id")
    pickup_datetime = data.get("pickup_datetime") or data.get("pickup_at")
    pickup_city = data.get("pickup_city")
    vehicle_category = data.get("vehicle_category") or data.get("category")
    duty_type = data.get("duty_type")
    planned_hours = data.get("planned_hours", 0)
    planned_km = data.get("planned_km") or data.get("distance_km", 0)
    outstation_days = data.get("outstation_days", 1)
    requested_allowances = data.get("allowances", [])

    booking_type = data.get("booking_type") or ("CORPORATE" if customer_id else "ADHOC")
    if not all([pickup_datetime, pickup_city, vehicle_category, duty_type]):
        return Response(
            {"detail": "Missing required fields: pickup_datetime, pickup_city, vehicle_category, duty_type."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    contract_id = data.get("contract") or data.get("contract_id")

    try:
        quote = calculate_unified_quote(
            booking_type=booking_type,
            customer_id=customer_id,
            contract_id=contract_id,
            pickup_datetime=pickup_datetime,
            pickup_city=pickup_city,
            drop_city=data.get("drop_city", ""),
            vehicle_category=vehicle_category,
            duty_type=duty_type,
            planned_hours=planned_hours,
            planned_km=planned_km,
            outstation_days=outstation_days,
            waiting_hours=data.get("waiting_hours", 0),
            night_charge_count=data.get("night_charge_count", 0),
            driver_allowance_days=data.get("driver_allowance_days", 0),
            ota_source=data.get("ota_source", ""),
        )
        return Response(quote, status=status.HTTP_200_OK)

    except PricingError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class FuelTransactionViewSet(viewsets.ModelViewSet):
    queryset = FuelTransaction.objects.all().order_by("-transaction_datetime")
    serializer_class = FuelTransactionSerializer

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return FuelTransaction.objects.none()

        # Drivers can only view their own fuel logs
        if hasattr(user, "driver_profile"):
            return FuelTransaction.objects.filter(driver=user.driver_profile).order_by("-transaction_datetime")

        # Dispatchers / Managers can see all
        return FuelTransaction.objects.all().order_by("-transaction_datetime")

    def get_serializer_class(self):
        if self.action in ["retrieve", "list"]:
            return FuelTransactionDetailSerializer
        return FuelTransactionSerializer

    def get_permissions(self):
        if self.action in ["approve", "reject", "reverse", "correct", "resolve_anomaly"]:
            return [permissions.IsAuthenticated(), IsCommercialAdmin()]
        return [permissions.IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        # Dispatchers / Managers cannot manually create fuel transactions
        if not hasattr(request.user, "driver_profile") and not request.user.is_superuser:
            return Response(
                {"detail": "Only drivers can log fuel purchases."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Support multipart file upload
        files = request.FILES.getlist("images")
        image_assets = []
        for file_obj in files:
            asset = upload_asset(
                file_obj,
                kind=UploadedAsset.KIND_IMAGE,
                folder="fuel-assets",
                request=request,
            )
            image_assets.append(asset.id)

        data = request.data
        if hasattr(data, "_mutable"):
            old_mutable = data._mutable
            data._mutable = True
            data.setlist("image_asset_ids", image_assets + data.getlist("image_asset_ids"))
            data._mutable = old_mutable
        else:
            if isinstance(data, dict):
                data = data.copy()
                data["image_asset_ids"] = image_assets + data.get("image_asset_ids", [])
            else:
                data = data.copy()
                data.setlist("image_asset_ids", image_assets + data.getlist("image_asset_ids"))

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()

        # Drivers cannot edit approved logs
        if hasattr(request.user, "driver_profile") and instance.status == FuelTransactionStatus.APPROVED:
            return Response(
                {"detail": "Drivers cannot edit an approved fuel log."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        # Drivers cannot delete fuel logs
        if hasattr(request.user, "driver_profile"):
            return Response(
                {"detail": "Drivers cannot delete fuel logs."},
                status=status.HTTP_403_FORBIDDEN
            )

        return super().destroy(request, *args, **kwargs)

    def perform_create(self, serializer):
        tx = serializer.save()
        from .fuel_service import detect_anomalies
        has_anom, flags = detect_anomalies(tx)
        tx.has_anomaly = has_anom
        tx.anomaly_flags = flags
        tx.save(update_fields=["has_anomaly", "anomaly_flags"])

    def perform_update(self, serializer):
        tx = serializer.save()
        from .fuel_service import detect_anomalies
        has_anom, flags = detect_anomalies(tx)
        tx.has_anomaly = has_anom
        tx.anomaly_flags = flags
        tx.save(update_fields=["has_anomaly", "anomaly_flags"])

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        tx = self.get_object()
        if tx.status != FuelTransactionStatus.SUBMITTED:
            return Response(
                {"error": f"Cannot approve transaction with status: {tx.status}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tx.status = FuelTransactionStatus.APPROVED
        tx.approved_by = request.user
        tx.approved_at = timezone.now()
        tx.review_notes = request.data.get("review_notes", "")
        tx.save(update_fields=["status", "approved_by", "approved_at", "review_notes"])

        # Post to Fleet Accounting (Task 7)
        try:
            from billing.models import TripExpense, ExpenseCategory, ExpenseStatus, SupplierProfile
            supplier, _ = SupplierProfile.objects.get_or_create(
                name=tx.vendor or "Fuel Supplier",
                defaults={"is_active": True}
            )

            expense = TripExpense.objects.create(
                trip=None,
                supplier=supplier,
                category=ExpenseCategory.FUEL,
                amount=tx.total_amount,
                tax_amount=tx.tax_amount,
                status=ExpenseStatus.APPROVED,
                evidence_url=tx.receipt_asset.file_url if tx.receipt_asset else "",
                description=f"Fuel Fill: {tx.vehicle.registration_number} @ {tx.vendor}. Odo: {tx.odometer_km}",
                approved_by=request.user,
            )

            tx.expense_posted = expense
            tx.posted_at = timezone.now()
            tx.save(update_fields=["expense_posted", "posted_at"])

            from billing.services import PostingEngine
            PostingEngine.post_fuel_journal(tx, expense)

        except Exception as exc:
            # Revert status changes if posting fails
            tx.status = FuelTransactionStatus.SUBMITTED
            tx.approved_by = None
            tx.approved_at = None
            tx.expense_posted = None
            tx.posted_at = None
            tx.save()
            return Response(
                {"error": f"Accounting posting failed: {str(exc)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(FuelTransactionDetailSerializer(tx).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        tx = self.get_object()
        if tx.status != FuelTransactionStatus.SUBMITTED:
            return Response(
                {"error": f"Cannot reject transaction with status: {tx.status}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tx.status = FuelTransactionStatus.REJECTED
        tx.review_notes = request.data.get("review_notes", "")
        tx.save(update_fields=["status", "review_notes"])
        return Response(FuelTransactionDetailSerializer(tx).data)

    @action(detail=True, methods=["post"])
    def reverse(self, request, pk=None):
        tx = self.get_object()
        if tx.status != FuelTransactionStatus.APPROVED:
            return Response(
                {"error": f"Only approved transactions can be reversed. Current: {tx.status}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tx.status = FuelTransactionStatus.REVERSED
        tx.save(update_fields=["status"])

        if tx.expense_posted:
            try:
                from billing.models import ExpenseStatus
                expense = tx.expense_posted
                expense.status = ExpenseStatus.REJECTED
                expense.save(update_fields=["status"])

                from billing.services import PostingEngine
                PostingEngine.post_fuel_reversal_journal(tx)
            except Exception as exc:
                tx.status = FuelTransactionStatus.APPROVED
                tx.save(update_fields=["status"])
                return Response(
                    {"error": f"Reversal posting failed: {str(exc)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        return Response(FuelTransactionDetailSerializer(tx).data)

    @action(detail=True, methods=["post"])
    def correct(self, request, pk=None):
        tx = self.get_object()
        if tx.status not in [FuelTransactionStatus.APPROVED, FuelTransactionStatus.SUBMITTED]:
            return Response(
                {"error": f"Cannot correct transaction with status: {tx.status}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = FuelTransactionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from django.db import transaction
        with transaction.atomic():
            if tx.status == FuelTransactionStatus.APPROVED and tx.expense_posted:
                from billing.models import ExpenseStatus
                expense = tx.expense_posted
                expense.status = ExpenseStatus.REJECTED
                expense.save(update_fields=["status"])
                from billing.services import PostingEngine
                PostingEngine.post_fuel_reversal_journal(tx)

            tx.status = FuelTransactionStatus.CORRECTED
            tx.save(update_fields=["status"])

            corrected_tx = serializer.save(
                is_correction=True,
                corrected_from_transaction=tx,
                status=FuelTransactionStatus.SUBMITTED,
            )

            tx.corrected_by_transaction = corrected_tx
            tx.save(update_fields=["corrected_by_transaction"])

            from .fuel_service import detect_anomalies
            has_anom, flags = detect_anomalies(corrected_tx)
            corrected_tx.has_anomaly = has_anom
            corrected_tx.anomaly_flags = flags
            corrected_tx.save(update_fields=["has_anomaly", "anomaly_flags"])

        return Response(FuelTransactionDetailSerializer(corrected_tx).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def resolve_anomaly(self, request, pk=None):
        tx = self.get_object()
        if not tx.has_anomaly:
            return Response(
                {"error": "Transaction has no active anomalies."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        review_notes = request.data.get("anomaly_review_notes", "")
        tx.anomaly_review_notes = review_notes
        tx.anomaly_reviewed_by = request.user
        tx.anomaly_reviewed_at = timezone.now()
        tx.has_anomaly = False
        tx.save(update_fields=["anomaly_review_notes", "anomaly_reviewed_by", "anomaly_reviewed_at", "has_anomaly"])

        return Response(FuelTransactionDetailSerializer(tx).data)

    @action(detail=False, methods=["get"])
    def vehicle_mileage(self, request):
        vehicle_id = request.query_params.get("vehicle")
        if not vehicle_id:
            return Response(
                {"error": "Query parameter 'vehicle' (id) is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            vehicle = Vehicle.objects.get(pk=vehicle_id)
        except Vehicle.DoesNotExist:
            return Response(
                {"error": f"Vehicle with id {vehicle_id} does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )

        from .fuel_service import calculate_vehicle_mileage
        metrics = calculate_vehicle_mileage(vehicle)
        return Response(metrics)


class RateBookViewSet(viewsets.ModelViewSet):
    queryset = RateBook.objects.prefetch_related("packages").all()
    serializer_class = RateBookSerializer
    permission_classes = [IsCommercialAdminOrReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        book_type = self.request.query_params.get("book_type")
        status_param = self.request.query_params.get("status")
        if book_type:
            qs = qs.filter(book_type=book_type)
        if status_param:
            qs = qs.filter(status=status_param)
        return qs


class RatePackageViewSet(viewsets.ModelViewSet):
    queryset = RatePackage.objects.all()
    serializer_class = RatePackageSerializer
    permission_classes = [IsCommercialAdminOrReadOnly]
