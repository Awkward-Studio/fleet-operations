from datetime import timedelta

from django.db import models
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response

from .models import (
    ContractAllowance,
    ContractRate,
    CorporateContract,
    CorporateCustomer,
    CustomerContact,
    CustomerStatus,
    Driver,
    DriverStatus,
    Trip,
    TripStatus,
    Vehicle,
    VehicleStatus,
)
from .permissions import IsCommercialAdminOrReadOnly
from .pricing_service import PricingError, calculate_quote
from .serializers import (
    AssignTripSerializer,
    AvailabilitySerializer,
    ContractAllowanceSerializer,
    ContractRateSerializer,
    CorporateContractSerializer,
    CorporateCustomerSerializer,
    CustomerContactSerializer,
    DriverSerializer,
    TransitionTripSerializer,
    TripSerializer,
    VehicleSerializer,
)


class DriverViewSet(viewsets.ModelViewSet):
    queryset = Driver.objects.all().order_by("name")
    serializer_class = DriverSerializer


class VehicleViewSet(viewsets.ModelViewSet):
    queryset = Vehicle.objects.select_related("assigned_driver").all().order_by("registration_number")
    serializer_class = VehicleSerializer


class TripViewSet(viewsets.ModelViewSet):
    queryset = Trip.objects.select_related("vehicle", "driver").all()
    serializer_class = TripSerializer

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
        trip = serializer.save()
        return Response(TripSerializer(trip).data)


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

    if not all([customer_id, pickup_datetime, pickup_city, vehicle_category, duty_type]):
        return Response(
            {"detail": "Missing required fields: customer, pickup_datetime, pickup_city, vehicle_category, duty_type."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        quote = calculate_quote(
            customer_id=customer_id,
            pickup_datetime=pickup_datetime,
            pickup_city=pickup_city,
            vehicle_category=vehicle_category,
            duty_type=duty_type,
            planned_hours=planned_hours,
            planned_km=planned_km,
            outstation_days=outstation_days,
            requested_allowances=requested_allowances,
        )
        return Response(quote, status=status.HTTP_200_OK)
    except PricingError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

