import math
import uuid
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from fleet.models import Driver, DriverStatus, Vehicle, VehicleStatus
from .models import (
    CorporateCustomer,
    PackageType,
    RentalBooking,
    RentalChecklist,
    RentalFuelLog,
    RentalInvoice,
    RentalPackage,
    RentalPricingRule,
    RentalStatus,
)
from .serializers import (
    CorporateCustomerSerializer,
    CreateRentalBookingSerializer,
    RentalBookingSerializer,
    RentalChecklistSerializer,
    RentalFuelLogSerializer,
    RentalInvoiceSerializer,
    RentalPackageSerializer,
    RentalPricingRuleSerializer,
    GuestProfileSerializer,
    CorporateApprovalPolicySerializer,
    BookingRequestSerializer,
    BookingRequestAmendmentSerializer,
)


class CorporateCustomerViewSet(viewsets.ModelViewSet):
    queryset = CorporateCustomer.objects.all().order_by("name")
    serializer_class = CorporateCustomerSerializer
    permission_classes = [AllowAny]


class RentalPackageViewSet(viewsets.ModelViewSet):
    queryset = RentalPackage.objects.all().order_by("id")
    serializer_class = RentalPackageSerializer
    permission_classes = [AllowAny]


class RentalPricingRuleViewSet(viewsets.ModelViewSet):
    queryset = RentalPricingRule.objects.all()
    serializer_class = RentalPricingRuleSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = super().get_queryset()
        company_id = self.request.query_params.get("company_id")
        city = self.request.query_params.get("city")
        if company_id:
            qs = qs.filter(company_id=company_id)
        if city:
            qs = qs.filter(city__iexact=city)
        return qs


class RentalBookingViewSet(viewsets.ModelViewSet):
    queryset = RentalBooking.objects.all().order_by("-pickup_at")
    serializer_class = RentalBookingSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        if not data.get("booking_number"):
            data["booking_number"] = f"RNT-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
        
        serializer = self.get_serializer(data=data)
        serializer.is_validate_error = False
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        booking = serializer.save()
        
        # Auto update status if vehicle & driver are assigned
        if booking.vehicle and booking.driver:
            booking.status = RentalStatus.READY
        elif booking.vehicle:
            booking.status = RentalStatus.VEHICLE_ASSIGNED
        elif booking.driver:
            booking.status = RentalStatus.DRIVER_ASSIGNED
        else:
            booking.status = RentalStatus.PENDING
        booking.save()

        return Response(RentalBookingSerializer(booking).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        booking = self.get_object()
        vehicle_id = request.data.get("vehicle_id")
        driver_id = request.data.get("driver_id")

        if vehicle_id:
            try:
                vehicle = Vehicle.objects.get(pk=vehicle_id)
                booking.vehicle = vehicle
            except Vehicle.DoesNotExist:
                return Response({"detail": "Vehicle not found."}, status=status.HTTP_404_NOT_FOUND)

        if driver_id:
            try:
                driver = Driver.objects.get(pk=driver_id)
                booking.driver = driver
            except Driver.DoesNotExist:
                return Response({"detail": "Driver not found."}, status=status.HTTP_404_NOT_FOUND)

        if booking.vehicle and booking.driver:
            booking.status = RentalStatus.READY
        elif booking.vehicle:
            booking.status = RentalStatus.VEHICLE_ASSIGNED
        elif booking.driver:
            booking.status = RentalStatus.DRIVER_ASSIGNED
        
        booking.save()
        return Response(RentalBookingSerializer(booking).data)

    @action(detail=True, methods=["post"])
    def start_rental(self, request, pk=None):
        booking = self.get_object()
        if not booking.vehicle or not booking.driver:
            return Response({"detail": "Vehicle and driver must be assigned before starting rental."}, status=status.HTTP_400_BAD_REQUEST)

        checklist_data = request.data.get("checklist", {})
        odometer_reading = checklist_data.get("odometer_reading") or request.data.get("start_odometer") or booking.vehicle.odometer_km

        with transaction.atomic():
            booking.status = RentalStatus.STARTED
            booking.start_time = timezone.now()
            booking.start_odometer = int(odometer_reading)
            booking.save()

            # Update vehicle & driver status
            booking.vehicle.status = VehicleStatus.ACTIVE_TRIP
            booking.vehicle.save()

            booking.driver.status = DriverStatus.ON_TRIP
            booking.driver.save()

            # Save start checklist if photos/notes provided
            RentalChecklist.objects.create(
                booking=booking,
                checklist_type="start",
                front_photo=checklist_data.get("front_photo", ""),
                rear_photo=checklist_data.get("rear_photo", ""),
                left_photo=checklist_data.get("left_photo", ""),
                right_photo=checklist_data.get("right_photo", ""),
                dashboard_photo=checklist_data.get("dashboard_photo", ""),
                odometer_photo=checklist_data.get("odometer_photo", ""),
                fuel_gauge_photo=checklist_data.get("fuel_gauge_photo", ""),
                odometer_reading=int(odometer_reading),
                notes=checklist_data.get("notes", "Rental started")
            )

        return Response(RentalBookingSerializer(booking).data)

    @action(detail=True, methods=["post"])
    def end_rental(self, request, pk=None):
        booking = self.get_object()
        checklist_data = request.data.get("checklist", {})
        end_odometer = checklist_data.get("odometer_reading") or request.data.get("end_odometer")

        if not end_odometer:
            return Response({"detail": "Ending odometer reading is required."}, status=status.HTTP_400_BAD_REQUEST)

        end_odometer = int(end_odometer)
        start_odo = booking.start_odometer or (booking.vehicle.odometer_km if booking.vehicle else 0)
        
        if end_odometer < start_odo:
            return Response({"detail": f"Ending odometer ({end_odometer}) cannot be less than starting odometer ({start_odo})."}, status=status.HTTP_400_BAD_REQUEST)

        end_time = timezone.now()
        start_time = booking.start_time or booking.pickup_at
        
        # Calculate actual hours used
        duration_seconds = (end_time - start_time).total_seconds()
        actual_hours = Decimal(str(round(duration_seconds / 3600.0, 2)))
        if actual_hours < Decimal("0.5"):
            actual_hours = Decimal("1.0")

        distance_travelled = Decimal(str(end_odometer - start_odo))

        with transaction.atomic():
            booking.end_time = end_time
            booking.end_odometer = end_odometer
            booking.distance_travelled = distance_travelled
            booking.actual_hours_used = actual_hours
            booking.status = RentalStatus.COMPLETED
            booking.save()

            if booking.vehicle:
                booking.vehicle.odometer_km = end_odometer
                booking.vehicle.status = VehicleStatus.IDLE
                booking.vehicle.save()

            if booking.driver:
                booking.driver.status = DriverStatus.AVAILABLE
                booking.driver.save()

            # Save end checklist
            RentalChecklist.objects.create(
                booking=booking,
                checklist_type="end",
                front_photo=checklist_data.get("front_photo", ""),
                rear_photo=checklist_data.get("rear_photo", ""),
                left_photo=checklist_data.get("left_photo", ""),
                right_photo=checklist_data.get("right_photo", ""),
                dashboard_photo=checklist_data.get("dashboard_photo", ""),
                odometer_photo=checklist_data.get("odometer_photo", ""),
                fuel_gauge_photo=checklist_data.get("fuel_gauge_photo", ""),
                odometer_reading=end_odometer,
                notes=checklist_data.get("notes", "Rental completed")
            )

            # Auto calculate invoice
            base_price, extra_km_rate, extra_hr_rate, driver_allowance = booking.resolve_pricing()
            pkg = booking.package

            included_km = Decimal(str(pkg.included_km))
            included_hours = Decimal(str(pkg.included_hours))

            extra_km = max(Decimal("0.0"), distance_travelled - included_km) if included_km > 0 else Decimal("0.0")
            
            # Hour calculation (ceiling extra hours)
            if included_hours > 0 and actual_hours > included_hours:
                extra_hours = Decimal(str(math.ceil(float(actual_hours - included_hours))))
            else:
                extra_hours = Decimal("0.0")

            extra_km_charges = round(extra_km * extra_km_rate, 2)
            extra_hour_charges = round(extra_hours * extra_hr_rate, 2)
            
            subtotal = base_price + extra_km_charges + extra_hour_charges + driver_allowance
            tax_rate = Decimal("5.00")
            tax_amount = round(subtotal * (tax_rate / Decimal("100.00")), 2)
            final_total = subtotal + tax_amount

            invoice, _ = RentalInvoice.objects.update_or_create(
                booking=booking,
                defaults={
                    "invoice_number": f"INV-{timezone.now().strftime('%Y%m%d')}-{booking.id:04d}",
                    "distance_travelled": distance_travelled,
                    "hours_used": actual_hours,
                    "included_km": included_km,
                    "included_hours": included_hours,
                    "extra_km": extra_km,
                    "extra_hours": extra_hours,
                    "package_price": base_price,
                    "extra_km_charges": extra_km_charges,
                    "extra_hour_charges": extra_hour_charges,
                    "driver_allowance": driver_allowance,
                    "subtotal": subtotal,
                    "tax_rate_percent": tax_rate,
                    "tax_amount": tax_amount,
                    "final_total": final_total
                }
            )

        return Response(RentalBookingSerializer(booking).data)

    @action(detail=True, methods=["post"])
    def cancel_rental(self, request, pk=None):
        booking = self.get_object()
        booking.status = RentalStatus.CANCELLED
        booking.save()
        if booking.vehicle and booking.vehicle.status == VehicleStatus.ACTIVE_TRIP:
            booking.vehicle.status = VehicleStatus.IDLE
            booking.vehicle.save()
        if booking.driver and booking.driver.status == DriverStatus.ON_TRIP:
            booking.driver.status = DriverStatus.AVAILABLE
            booking.driver.save()
        return Response(RentalBookingSerializer(booking).data)


class RentalChecklistViewSet(viewsets.ModelViewSet):
    queryset = RentalChecklist.objects.all().order_by("-created_at")
    serializer_class = RentalChecklistSerializer
    permission_classes = [AllowAny]


class RentalFuelLogViewSet(viewsets.ModelViewSet):
    queryset = RentalFuelLog.objects.all().order_by("-logged_at")
    serializer_class = RentalFuelLogSerializer
    permission_classes = [AllowAny]


class RentalInvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = RentalInvoice.objects.all().order_by("-issued_at")
    serializer_class = RentalInvoiceSerializer
    permission_classes = [AllowAny]


@api_view(["GET"])
@permission_classes([AllowAny])
def rental_dashboard_summary(request):
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    active_rentals = RentalBooking.objects.filter(status__in=[RentalStatus.STARTED, RentalStatus.IN_PROGRESS]).count()
    upcoming_rentals = RentalBooking.objects.filter(status__in=[RentalStatus.PENDING, RentalStatus.VEHICLE_ASSIGNED, RentalStatus.DRIVER_ASSIGNED, RentalStatus.READY], pickup_at__gte=now).count()
    available_vehicles = Vehicle.objects.filter(status=VehicleStatus.IDLE).count()
    available_drivers = Driver.objects.filter(status=DriverStatus.AVAILABLE).count()
    ending_today = RentalBooking.objects.filter(status__in=[RentalStatus.STARTED, RentalStatus.IN_PROGRESS], expected_return_at__range=(today_start, today_end)).count()

    overdue_vehicles = RentalBooking.objects.filter(
        status__in=[RentalStatus.STARTED, RentalStatus.IN_PROGRESS],
        expected_return_at__lt=now
    )

    overdue_alerts = [
        {
            "id": r.id,
            "type": "overdue",
            "title": f"Rental {r.booking_number} Overdue",
            "description": f"Vehicle {r.vehicle.registration_number if r.vehicle else 'Unassigned'} with driver {r.driver.name if r.driver else 'Unassigned'} was expected at {r.expected_return_at.strftime('%H:%M %d %b')}"
        }
        for r in overdue_vehicles
    ]

    todays_rentals_qs = RentalBooking.objects.filter(pickup_at__range=(today_start, today_end)).order_by("pickup_at")
    upcoming_pickups_qs = RentalBooking.objects.filter(pickup_at__gt=now, status__in=[RentalStatus.PENDING, RentalStatus.READY, RentalStatus.VEHICLE_ASSIGNED, RentalStatus.DRIVER_ASSIGNED]).order_by("pickup_at")[:5]
    recent_rentals_qs = RentalBooking.objects.all().order_by("-created_at")[:10]

    return Response({
        "cards": {
            "active_rentals": active_rentals,
            "upcoming_rentals": upcoming_rentals,
            "available_vehicles": available_vehicles,
            "available_drivers": available_drivers,
            "rentals_ending_today": ending_today,
        },
        "alerts": overdue_alerts,
        "todays_rentals": RentalBookingSerializer(todays_rentals_qs, many=True).data,
        "upcoming_pickups": RentalBookingSerializer(upcoming_pickups_qs, many=True).data,
        "recent_rentals": RentalBookingSerializer(recent_rentals_qs, many=True).data,
    })


@api_view(["GET"])
@permission_classes([AllowAny])
def driver_portal_today(request):
    driver_id = request.query_params.get("driver_id")
    if not driver_id:
        driver = Driver.objects.first()
    else:
        try:
            driver = Driver.objects.get(pk=driver_id)
        except Driver.DoesNotExist:
            return Response({"detail": "Driver not found."}, status=status.HTTP_404_NOT_FOUND)

    bookings = RentalBooking.objects.filter(
        driver=driver,
        status__in=[RentalStatus.READY, RentalStatus.STARTED, RentalStatus.IN_PROGRESS, RentalStatus.VEHICLE_ASSIGNED, RentalStatus.DRIVER_ASSIGNED]
    ).order_by("pickup_at")

    return Response({
        "driver": {
            "id": driver.id,
            "name": driver.name,
            "phone": driver.phone,
            "status": driver.status
        },
        "assigned_rentals": RentalBookingSerializer(bookings, many=True).data
    })


import hashlib

def generate_quote_signature(company_id, package_id, city, base_price, extra_km_rate, extra_hour_rate, driver_allowance):
    secret = "portal-quote-secret-2026"
    msg = f"{company_id}-{package_id}-{city}-{base_price}-{extra_km_rate}-{extra_hour_rate}-{driver_allowance}-{secret}"
    return hashlib.sha256(msg.encode("utf-8")).hexdigest()


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def portal_packages(request):
    memberships = request.user.active_memberships
    if not memberships.exists() and not request.user.is_superuser:
        return Response({"detail": "User is not associated with any active corporate customer."}, status=status.HTTP_403_FORBIDDEN)
    
    company_id = request.query_params.get("company_id")
    if not company_id:
        if request.user.is_superuser:
            company_id = request.user.corporate_memberships.first().company_id if request.user.corporate_memberships.exists() else None
        else:
            company_id = memberships.first().company_id

    city = request.query_params.get("city")
    
    pricing_rules = RentalPricingRule.objects.all()
    if company_id:
        pricing_rules = pricing_rules.filter(company_id=company_id)
    if city:
        pricing_rules = pricing_rules.filter(Q(city__iexact=city) | Q(city=""))
        
    package_ids = pricing_rules.values_list("package_id", flat=True)
    packages = RentalPackage.objects.filter(id__in=package_ids, is_active=True)
    
    if not packages.exists():
        default_rules = RentalPricingRule.objects.filter(company__isnull=True)
        if city:
            default_rules = default_rules.filter(Q(city__iexact=city) | Q(city=""))
        def_pkg_ids = default_rules.values_list("package_id", flat=True)
        packages = RentalPackage.objects.filter(id__in=def_pkg_ids, is_active=True)

    serializer = RentalPackageSerializer(packages, many=True)
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def portal_quote(request):
    memberships = request.user.active_memberships
    if not memberships.exists() and not request.user.is_superuser:
        return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
        
    company_id = request.data.get("company_id")
    if not company_id:
        company_id = memberships.first().company_id if not request.user.is_superuser else None
    
    if not company_id:
         return Response({"detail": "company_id is required."}, status=status.HTTP_400_BAD_REQUEST)
         
    if not request.user.is_superuser and not memberships.filter(company_id=company_id).exists():
        return Response({"detail": "Access to this corporate customer is forbidden."}, status=status.HTTP_403_FORBIDDEN)
        
    pickup_city = request.data.get("pickup_city")
    package_id = request.data.get("package_id")
    vehicle_category = request.data.get("vehicle_category", "Sedan")
    
    if not pickup_city or not package_id:
        return Response({"detail": "pickup_city and package_id are required."}, status=status.HTTP_400_BAD_REQUEST)
        
    try:
        package = RentalPackage.objects.get(pk=package_id, is_active=True)
    except RentalPackage.DoesNotExist:
        return Response({"detail": "Package not found or inactive."}, status=status.HTTP_404_NOT_FOUND)
        
    try:
        company = CorporateCustomer.objects.get(pk=company_id)
    except CorporateCustomer.DoesNotExist:
        return Response({"detail": "Company not found."}, status=status.HTTP_404_NOT_FOUND)
        
    rule = RentalPricingRule.objects.filter(
        company=company,
        city__iexact=pickup_city,
        package=package
    ).first()
    
    if not rule:
        rule = RentalPricingRule.objects.filter(
            company=company,
            city="",
            package=package
        ).first()
        
    if not rule:
        rule = RentalPricingRule.objects.filter(
            company__isnull=True,
            city__iexact=pickup_city,
            package=package
        ).first()
        
    if rule:
        base_price = rule.base_price
        extra_km_rate = rule.extra_km_rate
        extra_hour_rate = rule.extra_hour_rate
        driver_allowance = rule.driver_allowance
    else:
        base_price = package.default_base_price
        extra_km_rate = package.extra_km_rate
        extra_hour_rate = package.extra_hour_rate
        driver_allowance = package.driver_allowance_per_day
        
    expiry = timezone.now() + timedelta(hours=24)
    sig = generate_quote_signature(company_id, package_id, pickup_city, base_price, extra_km_rate, extra_hour_rate, driver_allowance)
    
    return Response({
        "company_id": company_id,
        "pickup_city": pickup_city,
        "package_id": package.id,
        "package_name": package.name,
        "vehicle_category": vehicle_category,
        "base_price": base_price,
        "extra_km_rate": extra_km_rate,
        "extra_hour_rate": extra_hour_rate,
        "driver_allowance": driver_allowance,
        "included_km": package.included_km,
        "included_hours": package.included_hours,
        "expires_at": expiry,
        "signature": sig
    })


from .models import GuestProfile, CorporateApprovalPolicy, BookingRequest, BookingRequestAmendment, BookingRequestStatus
from accounts.models import CorporateRole
from rest_framework.exceptions import ValidationError

class GuestProfileViewSet(viewsets.ModelViewSet):
    queryset = GuestProfile.objects.all()
    serializer_class = GuestProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_superuser:
            return qs
        memberships = self.request.user.active_memberships
        company_ids = memberships.values_list("company_id", flat=True)
        return qs.filter(company_id__in=company_ids)

    def perform_create(self, serializer):
        company = serializer.validated_data["company"]
        if not self.request.user.is_superuser:
            if not self.request.user.active_memberships.filter(company=company).exists():
                raise ValidationError("You do not have permission to add guests to this company.")
        serializer.save()


class CorporateApprovalPolicyViewSet(viewsets.ModelViewSet):
    queryset = CorporateApprovalPolicy.objects.all()
    serializer_class = CorporateApprovalPolicySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_superuser:
            return qs
        memberships = self.request.user.active_memberships
        company_ids = memberships.values_list("company_id", flat=True)
        return qs.filter(company_id__in=company_ids)

    def perform_create(self, serializer):
        company = serializer.validated_data["company"]
        if not self.request.user.is_superuser:
            if not self.request.user.active_memberships.filter(company=company, role=CorporateRole.ADMIN).exists():
                raise ValidationError("Only corporate admins can set approval policies.")
        serializer.save()


def handoff_booking_request_to_rental_booking(booking_request):
    with transaction.atomic():
        existing = RentalBooking.objects.filter(booking_number=booking_request.booking_number).first()
        if existing:
            return existing

        booking = RentalBooking.objects.create(
            booking_number=booking_request.booking_number,
            customer_type="corporate",
            customer_name=booking_request.passenger_name,
            customer_phone=booking_request.passenger_phone,
            customer_email=booking_request.passenger_email,
            corporate_customer=booking_request.company,
            pickup_address=booking_request.pickup_address,
            drop_address=booking_request.drop_address,
            pickup_city=booking_request.pickup_city,
            pickup_at=booking_request.pickup_at,
            expected_return_at=booking_request.expected_return_at,
            package=booking_request.package,
            vehicle_category=booking_request.vehicle_category,
            notes=f"Cost Centre: {booking_request.cost_centre}. PO: {booking_request.po_reference}.",
            status=RentalStatus.PENDING
        )
        return booking


class BookingRequestViewSet(viewsets.ModelViewSet):
    queryset = BookingRequest.objects.all()
    serializer_class = BookingRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_superuser:
            return qs
        memberships = self.request.user.active_memberships
        company_ids = memberships.values_list("company_id", flat=True)
        return qs.filter(company_id__in=company_ids)

    def perform_create(self, serializer):
        company = serializer.validated_data["company"]
        package = serializer.validated_data["package"]
        city = serializer.validated_data["pickup_city"]
        
        memberships = self.request.user.active_memberships
        user_membership = memberships.filter(company=company).first()
        if not self.request.user.is_superuser and not user_membership:
            raise ValidationError("You do not have permission to book for this company.")
            
        rule = RentalPricingRule.objects.filter(company=company, city__iexact=city, package=package).first()
        if not rule:
            rule = RentalPricingRule.objects.filter(company=company, city="", package=package).first()
        if not rule:
            rule = RentalPricingRule.objects.filter(company__isnull=True, city__iexact=city, package=package).first()
            
        if rule:
            base_price = rule.base_price
            extra_km_rate = rule.extra_km_rate
            extra_hour_rate = rule.extra_hour_rate
            driver_allowance = rule.driver_allowance
        else:
            base_price = package.default_base_price
            extra_km_rate = package.extra_km_rate
            extra_hour_rate = package.extra_hour_rate
            driver_allowance = package.driver_allowance_per_day

        sig = serializer.validated_data.get("quote_signature")
        if sig:
            expected_sig = generate_quote_signature(str(company.id), str(package.id), city, base_price, extra_km_rate, extra_hour_rate, driver_allowance)
            if sig != expected_sig:
                raise ValidationError({"quote_signature": "Pricing details have changed since the quote was generated. Please request a new quote."})
                
        policy = CorporateApprovalPolicy.objects.filter(company=company).first()
        require_approval = False
        if policy:
            if policy.require_po and not serializer.validated_data.get("po_reference"):
                raise ValidationError({"po_reference": "PO Reference is required by your corporate policy."})
            if policy.require_cost_centre and not serializer.validated_data.get("cost_centre"):
                raise ValidationError({"cost_centre": "Cost Centre is required by your corporate policy."})
            if policy.approval_threshold_amount > 0 and base_price > policy.approval_threshold_amount:
                require_approval = True
                
        role = user_membership.role if user_membership else "admin"
        if role in [CorporateRole.APPROVER, CorporateRole.ADMIN] or self.request.user.is_superuser:
            status_val = BookingRequestStatus.APPROVED
        elif require_approval:
            status_val = BookingRequestStatus.APPROVAL_REQUIRED
        else:
            status_val = BookingRequestStatus.SUBMITTED
            
        booking_number = f"PQ-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        
        booking_req = serializer.save(
            booking_number=booking_number,
            requester=self.request.user,
            status=status_val,
            quote_base_price=base_price,
            quote_extra_km_rate=extra_km_rate,
            quote_extra_hour_rate=extra_hour_rate,
            quote_driver_allowance=driver_allowance
        )
        
        if status_val == BookingRequestStatus.APPROVED:
            handoff_booking_request_to_rental_booking(booking_req)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        booking_req = self.get_object()
        memberships = request.user.active_memberships
        user_membership = memberships.filter(company=booking_req.company).first()
        
        if not request.user.is_superuser:
            role = user_membership.role if user_membership else None
            if role not in [CorporateRole.APPROVER, CorporateRole.ADMIN]:
                return Response({"detail": "Only approvers or corporate admins can approve bookings."}, status=status.HTTP_403_FORBIDDEN)
                
        if booking_req.status not in [BookingRequestStatus.SUBMITTED, BookingRequestStatus.APPROVAL_REQUIRED]:
            return Response({"detail": "This booking request cannot be approved in its current state."}, status=status.HTTP_400_BAD_REQUEST)
            
        with transaction.atomic():
            booking_req.status = BookingRequestStatus.APPROVED
            booking_req.approver = request.user
            booking_req.approved_at = timezone.now()
            booking_req.save()
            
            handoff_booking_request_to_rental_booking(booking_req)
            
        return Response(BookingRequestSerializer(booking_req).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        booking_req = self.get_object()
        memberships = request.user.active_memberships
        user_membership = memberships.filter(company=booking_req.company).first()
        
        if not request.user.is_superuser:
            role = user_membership.role if user_membership else None
            if role not in [CorporateRole.APPROVER, CorporateRole.ADMIN]:
                return Response({"detail": "Only approvers or corporate admins can reject bookings."}, status=status.HTTP_403_FORBIDDEN)
                
        if booking_req.status not in [BookingRequestStatus.SUBMITTED, BookingRequestStatus.APPROVAL_REQUIRED]:
            return Response({"detail": "This booking request cannot be rejected in its current state."}, status=status.HTTP_400_BAD_REQUEST)
            
        booking_req.status = BookingRequestStatus.REJECTED
        booking_req.save()
        
        return Response(BookingRequestSerializer(booking_req).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        booking_req = self.get_object()
        memberships = request.user.active_memberships
        user_membership = memberships.filter(company=booking_req.company).first()
        
        if not request.user.is_superuser and not user_membership:
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
            
        if booking_req.status == BookingRequestStatus.CANCELLED:
            return Response({"detail": "Booking request is already cancelled."}, status=status.HTTP_400_BAD_REQUEST)
            
        with transaction.atomic():
            booking_req.status = BookingRequestStatus.CANCELLED
            booking_req.save()
            
            rental_booking = RentalBooking.objects.filter(booking_number=booking_req.booking_number).first()
            if rental_booking:
                rental_booking.status = RentalStatus.CANCELLED
                rental_booking.save()
                
        return Response(BookingRequestSerializer(booking_req).data)

    @action(detail=True, methods=["post"])
    def amend(self, request, pk=None):
        booking_req = self.get_object()
        memberships = request.user.active_memberships
        user_membership = memberships.filter(company=booking_req.company).first()
        
        if not request.user.is_superuser and not user_membership:
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
            
        if booking_req.status in [BookingRequestStatus.CANCELLED, BookingRequestStatus.COMPLETED, BookingRequestStatus.REJECTED]:
            return Response({"detail": "Cannot amend cancelled, completed, or rejected bookings."}, status=status.HTTP_400_BAD_REQUEST)
            
        reason = request.data.get("reason", "Amendment from portal")
        fields_to_change = ["passenger_name", "passenger_phone", "passenger_email", "pickup_address", "drop_address", "pickup_city", "pickup_at", "expected_return_at", "cost_centre", "po_reference"]
        
        changes = {}
        for field in fields_to_change:
            if field in request.data:
                val = request.data[field]
                old_val = getattr(booking_req, field)
                if str(old_val) != str(val):
                    changes[field] = str(val)
                    setattr(booking_req, field, val)
                    
        if not changes:
            return Response({"detail": "No fields were changed."}, status=status.HTTP_400_BAD_REQUEST)
            
        with transaction.atomic():
            booking_req.save()
            BookingRequestAmendment.objects.create(
                booking_request=booking_req,
                amended_by=request.user,
                changes=changes,
                reason=reason
            )
            
            rental_booking = RentalBooking.objects.filter(booking_number=booking_req.booking_number).first()
            if rental_booking:
                for field, val in changes.items():
                    if field == "passenger_name":
                        rental_booking.customer_name = val
                    elif field == "passenger_phone":
                        rental_booking.customer_phone = val
                    elif field == "passenger_email":
                        rental_booking.customer_email = val
                    elif hasattr(rental_booking, field):
                        setattr(rental_booking, field, val)
                rental_booking.save()
                
        return Response(BookingRequestSerializer(booking_req).data)


