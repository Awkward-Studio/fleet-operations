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
    FuelTransaction,
    FuelTransactionStatus,
    FuelType,
    FuelUnit,
)
from .permissions import IsCommercialAdminOrReadOnly, IsCommercialAdmin
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
    FuelTransactionSerializer,
    FuelTransactionDetailSerializer,
)
from rest_framework import permissions


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


class FuelTransactionViewSet(viewsets.ModelViewSet):
    queryset = FuelTransaction.objects.all().order_by("-transaction_datetime")
    serializer_class = FuelTransactionSerializer

    def get_serializer_class(self):
        if self.action in ["retrieve", "list"]:
            return FuelTransactionDetailSerializer
        return FuelTransactionSerializer

    def get_permissions(self):
        if self.action in ["approve", "reject", "reverse", "correct", "resolve_anomaly"]:
            return [permissions.IsAuthenticated(), IsCommercialAdmin()]
        return [permissions.IsAuthenticated()]

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
        tx.save(update_fields=["status", "approved_by", "approved_at"])

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
        tx.save(update_fields=["status"])
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

