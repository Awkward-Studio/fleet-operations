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

        # Trigger event and notification if ready
        booking_req = BookingRequest.objects.filter(booking_number=booking.booking_number).first()
        if booking.vehicle and booking.driver:
            RentalBookingEvent.objects.create(
                booking=booking,
                event_type="driver_allocated",
                description=f"Chauffeur {booking.driver.name} and vehicle {booking.vehicle.registration_number} have been assigned."
            )
            if booking_req:
                send_rental_notification(booking_req, "driver_allocated", reason=f"Chauffeur {booking.driver.name.split()[0]} ({booking.driver.phone}) assigned. Vehicle: {booking.vehicle.registration_number}")

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

        old_status = booking.status
        if booking.vehicle and booking.driver:
            booking.status = RentalStatus.READY
        elif booking.vehicle:
            booking.status = RentalStatus.VEHICLE_ASSIGNED
        elif booking.driver:
            booking.status = RentalStatus.DRIVER_ASSIGNED
        
        booking.save()

        # Log event and notify
        booking_req = BookingRequest.objects.filter(booking_number=booking.booking_number).first()
        if booking.driver and booking.vehicle and old_status != RentalStatus.READY:
            RentalBookingEvent.objects.create(
                booking=booking,
                event_type="driver_allocated",
                description=f"Chauffeur {booking.driver.name} and vehicle {booking.vehicle.registration_number} have been assigned."
            )
            RentalBookingEvent.objects.create(
                booking=booking,
                event_type="driver_arrived",
                description="Chauffeur is ready for pickup."
            )
            if booking_req:
                send_rental_notification(booking_req, "driver_allocated", reason=f"Chauffeur {booking.driver.name.split()[0]} ({booking.driver.phone}) assigned. Vehicle: {booking.vehicle.registration_number}")
                send_rental_notification(booking_req, "arrived")

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

            # Log Event & Notify
            RentalBookingEvent.objects.create(
                booking=booking,
                event_type="trip_started",
                description=f"Trip started with starting odometer: {odometer_reading} km."
            )
            booking_req = BookingRequest.objects.filter(booking_number=booking.booking_number).first()
            if booking_req:
                send_rental_notification(booking_req, "started")

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

            # Log Event & Notify
            RentalBookingEvent.objects.create(
                booking=booking,
                event_type="trip_completed",
                description=f"Trip completed successfully. Distance: {distance_travelled} km. Duration: {actual_hours} hours."
            )
            
            booking_req = BookingRequest.objects.filter(booking_number=booking.booking_number).first()
            if booking_req:
                booking_req.status = BookingRequestStatus.COMPLETED
                booking_req.save(update_fields=["status"])
                send_rental_notification(booking_req, "completed")

        return Response(RentalBookingSerializer(booking).data)

    @action(detail=True, methods=["post"])
    def cancel_rental(self, request, pk=None):
        booking = self.get_object()
        with transaction.atomic():
            booking.status = RentalStatus.CANCELLED
            booking.save()
            if booking.vehicle and booking.vehicle.status == VehicleStatus.ACTIVE_TRIP:
                booking.vehicle.status = VehicleStatus.IDLE
                booking.vehicle.save()
            if booking.driver and booking.driver.status == DriverStatus.ON_TRIP:
                booking.driver.status = DriverStatus.AVAILABLE
                booking.driver.save()

            # Log Event & Notify
            RentalBookingEvent.objects.create(
                booking=booking,
                event_type="trip_cancelled",
                description="Trip was cancelled."
            )
            
            booking_req = BookingRequest.objects.filter(booking_number=booking.booking_number).first()
            if booking_req:
                booking_req.status = BookingRequestStatus.CANCELLED
                booking_req.save(update_fields=["status"])
                send_rental_notification(booking_req, "cancelled")

        return Response(RentalBookingSerializer(booking).data)

    @action(detail=True, methods=["post"])
    def location(self, request, pk=None):
        booking = self.get_object()
        latitude = request.data.get("latitude")
        longitude = request.data.get("longitude")
        if not latitude or not longitude:
            return Response({"detail": "latitude and longitude are required."}, status=status.HTTP_400_BAD_REQUEST)
        
        RentalBookingLocationLog.objects.create(
            booking=booking,
            latitude=Decimal(str(latitude)),
            longitude=Decimal(str(longitude)),
            timestamp=timezone.now()
        )
        return Response({"status": "success"})


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


from .models import GuestProfile, CorporateApprovalPolicy, BookingRequest, BookingRequestAmendment, BookingRequestStatus, RentalBookingLocationLog, RentalBookingEvent, RentalNotification
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


def send_rental_notification(booking_req, notification_type, recipients=None, reason=""):
    import hashlib
    emails = []
    if recipients == "requester" or recipients is None:
        emails.append(booking_req.requester.email)
    if recipients == "guest" or recipients is None:
        if booking_req.passenger_email:
            emails.append(booking_req.passenger_email)
        elif booking_req.guest and booking_req.guest.email:
            emails.append(booking_req.guest.email)

    emails = list(set(filter(None, emails)))
    if not emails:
        return None

    emails_str = ",".join(sorted(emails))
    raw_key = f"{booking_req.booking_number}:{notification_type}:{emails_str}:{reason}"
    idempotency_key = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    existing = RentalNotification.objects.filter(idempotency_key=idempotency_key).first()
    if existing:
        return existing

    subject = f"Travel Alert: {notification_type.upper().replace('_', ' ')} for Booking {booking_req.booking_number}"
    body = f"Hello,\n\nThis is an automated notification regarding your booking {booking_req.booking_number}.\n"
    body += f"Event: {notification_type.upper().replace('_', ' ')}\n"
    if reason:
        body += f"Details: {reason}\n"
    body += f"Passenger: {booking_req.passenger_name}\n"
    body += f"Pickup: {booking_req.pickup_city} - {booking_req.pickup_address} at {booking_req.pickup_at.strftime('%Y-%m-%d %H:%M')}\n"

    notif = RentalNotification.objects.create(
        booking_number=booking_req.booking_number,
        recipient_email=emails_str,
        notification_type=notification_type,
        subject=subject,
        body=body,
        status="pending",
        idempotency_key=idempotency_key
    )

    try:
        from django.core.mail import send_mail
        send_mail(
            subject=subject,
            message=body,
            from_email="no-reply@indexfleet.com",
            recipient_list=emails,
            fail_silently=False
        )
        notif.status = "sent"
        notif.last_attempt_at = timezone.now()
        notif.save(update_fields=["status", "last_attempt_at"])
    except Exception as e:
        notif.status = "failed"
        notif.last_attempt_at = timezone.now()
        notif.error_log = str(e)
        notif.save(update_fields=["status", "last_attempt_at", "error_log"])

    return notif


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
            send_rental_notification(booking_req, "confirmed")
        elif status_val == BookingRequestStatus.APPROVAL_REQUIRED:
            send_rental_notification(booking_req, "approval_required")
        else:
            send_rental_notification(booking_req, "submitted")

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
            send_rental_notification(booking_req, "confirmed")
            
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
        send_rental_notification(booking_req, "rejected")
        
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
                
            send_rental_notification(booking_req, "cancelled")
                
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
                
            send_rental_notification(booking_req, "amended", reason=reason)
                
        return Response(BookingRequestSerializer(booking_req).data)

    @action(detail=True, methods=["get"])
    def status(self, request, pk=None):
        booking_req = self.get_object()
        rental_booking = RentalBooking.objects.filter(booking_number=booking_req.booking_number).first()
        
        op_status = booking_req.status
        driver_details = None
        vehicle_details = None
        live_location = None
        milestones = []

        milestones.append({
            "milestone": "requested",
            "title": "Booking Requested",
            "description": f"Trip requested by {booking_req.requester.username}.",
            "timestamp": booking_req.created_at,
            "completed": True
        })

        if booking_req.status == BookingRequestStatus.APPROVAL_REQUIRED:
            milestones.append({
                "milestone": "approval_pending",
                "title": "Manager Approval Pending",
                "description": "Exceeds policy limits. Awaiting manager approval.",
                "timestamp": booking_req.created_at,
                "completed": False
            })
        elif booking_req.status == BookingRequestStatus.REJECTED:
            milestones.append({
                "milestone": "rejected",
                "title": "Booking Rejected",
                "description": "Request was rejected by the manager.",
                "timestamp": booking_req.updated_at,
                "completed": True
            })

        if booking_req.approved_at:
            milestones.append({
                "milestone": "approved",
                "title": "Booking Approved",
                "description": f"Approved by {booking_req.approver.username if booking_req.approver else 'Manager'}.",
                "timestamp": booking_req.approved_at,
                "completed": True
            })

        if rental_booking:
            op_status = rental_booking.status
            
            milestones.append({
                "milestone": "dispatched",
                "title": "Trip Confirmed",
                "description": "Operational booking confirmed.",
                "timestamp": rental_booking.created_at,
                "completed": True
            })

            driver_assigned = rental_booking.driver is not None
            vehicle_assigned = rental_booking.vehicle is not None

            milestones.append({
                "milestone": "driver_assigned",
                "title": "Chauffeur & Car Assigned",
                "description": f"Vehicle: {rental_booking.vehicle.category if vehicle_assigned else 'Pending'}. Chauffeur: {rental_booking.driver.name.split()[0] if driver_assigned else 'Pending'}.",
                "timestamp": rental_booking.updated_at if (driver_assigned or vehicle_assigned) else None,
                "completed": driver_assigned and vehicle_assigned
            })

            milestones.append({
                "milestone": "started",
                "title": "Trip Started",
                "description": "Chauffeur has started the trip.",
                "timestamp": rental_booking.start_time,
                "completed": rental_booking.start_time is not None
            })

            milestones.append({
                "milestone": "completed",
                "title": "Trip Completed",
                "description": "Ride has completed successfully.",
                "timestamp": rental_booking.end_time,
                "completed": rental_booking.status == RentalStatus.COMPLETED
            })

            if rental_booking.status in [RentalStatus.DRIVER_ASSIGNED, RentalStatus.VEHICLE_ASSIGNED, RentalStatus.READY, RentalStatus.STARTED, RentalStatus.IN_PROGRESS, RentalStatus.COMPLETED]:
                if driver_assigned:
                    driver_details = {
                        "first_name": rental_booking.driver.name.split()[0],
                        "phone": rental_booking.driver.phone,
                    }
                if vehicle_assigned:
                    vehicle_details = {
                        "category": rental_booking.vehicle.category,
                        "registration_number": rental_booking.vehicle.registration_number,
                    }

            if rental_booking.status in [RentalStatus.STARTED, RentalStatus.IN_PROGRESS]:
                latest_log = rental_booking.location_logs.first()
                if latest_log:
                    policy = CorporateApprovalPolicy.objects.filter(company=booking_req.company).first()
                    precision = policy.location_precision_digits if policy else 4
                    
                    live_location = {
                        "latitude": round(float(latest_log.latitude), precision),
                        "longitude": round(float(latest_log.longitude), precision),
                        "timestamp": latest_log.timestamp
                    }

        events_qs = []
        if rental_booking:
            events_qs = rental_booking.events.filter(is_customer_visible=True)
        events_data = [{
            "id": e.id,
            "event_type": e.event_type,
            "description": e.description,
            "created_at": e.created_at
        } for e in events_qs]

        return Response({
            "booking_number": booking_req.booking_number,
            "status": op_status,
            "driver": driver_details,
            "vehicle": vehicle_details,
            "live_location": live_location,
            "milestones": milestones,
            "events": events_data
        })


from billing.models import Invoice as BillingInvoice, InvoiceStatus as BillingInvoiceStatus
from rentals.models import RentalInvoice

class PortalInvoiceViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        memberships = request.user.active_memberships
        if not memberships.exists() and not request.user.is_superuser:
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
            
        authorized = memberships.filter(
            role__in=[CorporateRole.ADMIN, CorporateRole.FINANCE]
        )
        if not request.user.is_superuser and not authorized.exists():
            return Response({"detail": "Invoice permission required."}, status=status.HTTP_403_FORBIDDEN)
        company_ids = list(authorized.values_list("company_id", flat=True)) if not request.user.is_superuser else None
        
        search = request.query_params.get("search")
        po_reference = request.query_params.get("po_reference")
        
        from django.db.models import Q
        from fleet.models import CorporateCustomer as FleetCorporateCustomer
        
        fleet_company_ids = []
        if company_ids:
            rent_companies = CorporateCustomer.objects.filter(id__in=company_ids)
            for rc in rent_companies:
                fc = rc.fleet_customer or FleetCorporateCustomer.objects.filter(
                    legal_name__iexact=rc.name
                ).first()
                if fc:
                    fleet_company_ids.append(fc.id)

        # 1. Fetch Fleet Invoices (billing.Invoice)
        fleet_qs = BillingInvoice.objects.all()
        if company_ids:
            fleet_qs = fleet_qs.filter(customer_id__in=fleet_company_ids)
        fleet_qs = fleet_qs.exclude(status__in=[BillingInvoiceStatus.DRAFT, BillingInvoiceStatus.REVIEW])
        
        if search:
            fleet_qs = fleet_qs.filter(Q(invoice_number__icontains=search) | Q(po_number__icontains=search))
        if po_reference:
            fleet_qs = fleet_qs.filter(po_number__icontains=po_reference)

        # 2. Fetch Chauffeur Rental Invoices (rentals.RentalInvoice)
        rental_qs = RentalInvoice.objects.all()
        if company_ids:
            rental_qs = rental_qs.filter(booking__corporate_customer_id__in=company_ids)
            
        if search:
            rental_qs = rental_qs.filter(Q(invoice_number__icontains=search) | Q(booking__booking_number__icontains=search))
            
        results = []
        for inv in fleet_qs:
            results.append({
                "id": inv.id,
                "invoice_number": inv.invoice_number,
                "type": "trip",
                "type_display": "Fleet Dispatch Invoice",
                "issue_date": inv.issue_date,
                "due_date": inv.due_date,
                "po_number": inv.po_number,
                "total_amount": float(inv.total_amount),
                "balance_amount": float(inv.balance_amount),
                "status": inv.status
            })
            
        for inv in rental_qs:
            results.append({
                "id": inv.id,
                "invoice_number": inv.invoice_number,
                "type": "chauffeur",
                "type_display": "Chauffeur Rental Invoice",
                "issue_date": inv.issued_at.date(),
                "due_date": inv.issued_at.date() + timedelta(days=15),
                "po_number": inv.booking.notes,
                "total_amount": float(inv.final_total),
                "balance_amount": 0.0 if inv.booking.status == "completed" else float(inv.final_total),
                "status": "ISSUED" if inv.booking.status != "completed" else "PAID"
            })
            
        results.sort(key=lambda x: x["issue_date"], reverse=True)
        return Response(results)

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        inv_type = request.query_params.get("type", "trip")
        from django.http import HttpResponse
        
        memberships = request.user.active_memberships
        authorized = memberships.filter(
            role__in=[CorporateRole.ADMIN, CorporateRole.FINANCE]
        )
        if not request.user.is_superuser and not authorized.exists():
            return Response({"detail": "Invoice permission required."}, status=status.HTTP_403_FORBIDDEN)
        company_ids = list(authorized.values_list("company_id", flat=True)) if not request.user.is_superuser else None

        if inv_type == "trip":
            try:
                inv = BillingInvoice.objects.get(id=pk)
                if company_ids:
                    from fleet.models import CorporateCustomer as FleetCorporateCustomer
                    rent_companies = CorporateCustomer.objects.filter(id__in=company_ids)
                    fleet_ids = {
                        rc.fleet_customer_id
                        for rc in rent_companies
                        if rc.fleet_customer_id
                    }
                    rent_names = [rc.name.lower() for rc in rent_companies]
                    if not inv.customer or (
                        inv.customer_id not in fleet_ids
                        and inv.customer.legal_name.lower() not in rent_names
                    ):
                        return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
                
                from billing.pdf_service import PDFService
                from django.core.files.storage import default_storage
                from django.http import FileResponse
                document = PDFService.get_or_create_document(inv, request=request)
                return FileResponse(
                    default_storage.open(document.attachment.storage_key, "rb"),
                    content_type="application/pdf",
                    as_attachment=True,
                    filename=document.attachment.original_name,
                )
            except BillingInvoice.DoesNotExist:
                return Response({"detail": "Invoice not found."}, status=status.HTTP_404_NOT_FOUND)
        else:
            try:
                inv = RentalInvoice.objects.get(id=pk)
                if company_ids and inv.booking.corporate_customer_id not in company_ids:
                    return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
                
                html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Invoice {inv.invoice_number}</title>
    <style>
        body {{ font-family: Arial, sans-serif; padding: 40px; color: #333; }}
        .header {{ border-bottom: 2px solid #10b981; padding-bottom: 20px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 30px; }}
        th {{ background: #f3f4f6; padding: 10px; text-align: left; }}
        td {{ padding: 10px; border-bottom: 1px solid #e5e7eb; }}
    </style>
</head>
<body>
    <div class="header">
        <h2>CHAUFFEUR RENTAL INVOICE</h2>
        <h3>Invoice No: {inv.invoice_number}</h3>
        <p>Booking No: {inv.booking.booking_number}</p>
        <p>Date: {inv.issued_at.strftime('%Y-%m-%d')}</p>
    </div>
    <div style="margin-top: 20px;">
        <p><strong>Customer Name:</strong> {inv.booking.customer_name}</p>
        <p><strong>Pickup City:</strong> {inv.booking.pickup_city}</p>
        <p><strong>Pickup Address:</strong> {inv.booking.pickup_address}</p>
        <p><strong>Duration:</strong> {inv.hours_used} Hours | Distance: {inv.distance_travelled} km</p>
    </div>
    <table>
        <thead>
            <tr>
                <th>Description</th>
                <th style="text-align: right;">Amount (INR)</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>Package Rate ({inv.booking.package.name})</td>
                <td style="text-align: right;">₹{inv.package_price:.2f}</td>
            </tr>
            <tr>
                <td>Extra Km Charges ({inv.extra_km} km)</td>
                <td style="text-align: right;">₹{inv.extra_km_charges:.2f}</td>
            </tr>
            <tr>
                <td>Extra Hour Charges ({inv.extra_hours} hrs)</td>
                <td style="text-align: right;">₹{inv.extra_hour_charges:.2f}</td>
            </tr>
            <tr>
                <td>Driver Allowance</td>
                <td style="text-align: right;">₹{inv.driver_allowance:.2f}</td>
            </tr>
            <tr style="font-weight: bold; border-top: 2px solid #333;">
                <td>Subtotal</td>
                <td style="text-align: right;">₹{inv.subtotal:.2f}</td>
            </tr>
            <tr>
                <td>Tax Amount ({inv.tax_rate_percent}%)</td>
                <td style="text-align: right;">₹{inv.tax_amount:.2f}</td>
            </tr>
            <tr style="font-weight: bold; font-size: 1.2em; color: #10b981;">
                <td>Total</td>
                <td style="text-align: right;">₹{inv.final_total:.2f}</td>
            </tr>
        </tbody>
    </table>
</body>
</html>"""
                return HttpResponse(html, content_type="text/html")
            except RentalInvoice.DoesNotExist:
                return Response({"detail": "Invoice not found."}, status=status.HTTP_404_NOT_FOUND)


class PortalStatementsViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        memberships = request.user.active_memberships
        if not memberships.exists() and not request.user.is_superuser:
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
            
        authorized = memberships.filter(
            role__in=[CorporateRole.ADMIN, CorporateRole.FINANCE]
        )
        if not request.user.is_superuser and not authorized.exists():
            return Response({"detail": "Statement permission required."}, status=status.HTTP_403_FORBIDDEN)
        company_id = request.query_params.get("company_id")
        if not company_id:
            company_id = authorized.first().company_id if not request.user.is_superuser else None
            
        if not company_id:
            return Response({"detail": "company_id is required."}, status=status.HTTP_400_BAD_REQUEST)
            
        if not request.user.is_superuser and not authorized.filter(company_id=company_id).exists():
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
            
        start_date_str = request.query_params.get("start_date")
        end_date_str = request.query_params.get("end_date")
        
        from django.utils.dateparse import parse_date
        import datetime
        start_date = parse_date(start_date_str) if start_date_str else datetime.date.today() - timedelta(days=30)
        end_date = parse_date(end_date_str) if end_date_str else datetime.date.today()

        from fleet.models import CorporateCustomer as FleetCorporateCustomer
        rent_comp = CorporateCustomer.objects.filter(id=company_id).first()
        fleet_company_id = None
        if rent_comp:
            fc = rent_comp.fleet_customer or FleetCorporateCustomer.objects.filter(
                legal_name__iexact=rent_comp.name
            ).first()
            if fc:
                fleet_company_id = fc.id
                
        if not fleet_company_id:
            return Response({
                "company_id": company_id,
                "start_date": start_date,
                "end_date": end_date,
                "opening_balance": 0.0,
                "closing_balance": 0.0,
                "entries": []
            })
            
        billing_invoices = BillingInvoice.objects.filter(
            customer_id=fleet_company_id,
            issue_date__range=(start_date, end_date)
        ).exclude(status__in=[BillingInvoiceStatus.DRAFT, BillingInvoiceStatus.REVIEW])
        
        prior_invoices = BillingInvoice.objects.filter(
            customer_id=fleet_company_id,
            issue_date__lt=start_date
        ).exclude(status__in=[BillingInvoiceStatus.DRAFT, BillingInvoiceStatus.REVIEW])
        
        prior_invoice_sum = sum(inv.total_amount for inv in prior_invoices)
        prior_paid_sum = sum(inv.paid_amount for inv in prior_invoices)
        opening_balance = float(prior_invoice_sum - prior_paid_sum)
        
        entries = []
        for inv in billing_invoices:
            entries.append({
                "date": inv.issue_date,
                "type": "invoice",
                "reference": inv.invoice_number,
                "description": f"Tax Invoice {inv.invoice_number}",
                "debit": float(inv.total_amount),
                "credit": 0.0,
            })
            
            from billing.models import PaymentAllocation
            allocs = PaymentAllocation.objects.filter(
                invoice=inv,
                receipt__receipt_date__range=(start_date, end_date)
            )
            for alloc in allocs:
                entries.append({
                    "date": alloc.receipt.receipt_date,
                    "type": "payment",
                    "reference": alloc.receipt.receipt_number,
                    "description": f"Payment allocation from receipt {alloc.receipt.receipt_number}",
                    "debit": 0.0,
                    "credit": float(alloc.allocated_amount),
                })
                
        entries.sort(key=lambda x: x["date"])
        
        current_bal = opening_balance
        for entry in entries:
            current_bal += entry["debit"] - entry["credit"]
            entry["balance"] = current_bal
            
        return Response({
            "company_id": company_id,
            "start_date": start_date,
            "end_date": end_date,
            "opening_balance": opening_balance,
            "closing_balance": current_bal,
            "entries": entries
        })


from .models import PortalSupportCase, PortalAuditEvent, PortalHandoffQueue
from .serializers import PortalSupportCaseSerializer, PortalAuditEventSerializer
from accounts.models import User, UserRole

class PortalSupportCaseViewSet(viewsets.ModelViewSet):
    serializer_class = PortalSupportCaseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_superuser:
            return PortalSupportCase.objects.all()
        memberships = self.request.user.active_memberships
        company_ids = memberships.values_list("company_id", flat=True)
        return PortalSupportCase.objects.filter(company_id__in=company_ids)

    def perform_create(self, serializer):
        company = serializer.validated_data.get("company")
        if not company:
            memberships = self.request.user.active_memberships
            if not memberships.exists():
                raise ValidationError("You must belong to a company to create a support case.")
            company = memberships.first().company
        else:
            if not self.request.user.is_superuser and not self.request.user.active_memberships.filter(company=company).exists():
                raise ValidationError("Forbidden company.")
                
        case = serializer.save(company=company, created_by=self.request.user)
        
        # Log Audit Log
        PortalAuditEvent.objects.create(
            company=company,
            user=self.request.user,
            action_type="support_ticket",
            description=f"Created support case #{case.id}: '{case.subject}'"
        )


class PortalAuditingViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PortalAuditEventSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        memberships = self.request.user.active_memberships
        user_membership = memberships.first()
        if not self.request.user.is_superuser:
            if not user_membership or user_membership.role != CorporateRole.ADMIN:
                return PortalAuditEvent.objects.none()
                
        if self.request.user.is_superuser:
            return PortalAuditEvent.objects.all()
            
        return PortalAuditEvent.objects.filter(company_id=user_membership.company_id)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def portal_support_impersonate(request):
    is_authorized = request.user.is_superuser or request.user.role in [UserRole.ADMIN, UserRole.COMMERCIAL]
    if not is_authorized:
        is_authorized = request.user.active_memberships.filter(role=CorporateRole.SUPPORT).exists()
        
    if not is_authorized:
        return Response({"detail": "You do not have permission to impersonate corporate users."}, status=status.HTTP_403_FORBIDDEN)
        
    target_user_id = request.data.get("user_id")
    company_id = request.data.get("company_id")
    
    if not target_user_id or not company_id:
        return Response({"detail": "user_id and company_id are required."}, status=status.HTTP_400_BAD_REQUEST)
        
    try:
        target_user = User.objects.get(pk=target_user_id)
    except User.DoesNotExist:
        return Response({"detail": "Target user not found."}, status=status.HTTP_404_NOT_FOUND)
        
    try:
        company = CorporateCustomer.objects.get(pk=company_id)
    except CorporateCustomer.DoesNotExist:
        return Response({"detail": "Corporate Customer not found."}, status=status.HTTP_404_NOT_FOUND)
        
    PortalAuditEvent.objects.create(
        company=company,
        user=request.user,
        action_type="impersonation",
        description=f"Support user '{request.user.username}' started impersonating '{target_user.username}' for company '{company.name}'."
    )
    
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(target_user)
    
    return Response({
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "impersonation_active": True,
        "impersonator": request.user.username,
        "impersonated_user": target_user.username,
        "company_name": company.name
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def portal_health_metrics(request):
    is_authorized = request.user.is_superuser or request.user.role in [UserRole.ADMIN, UserRole.COMMERCIAL]
    if not is_authorized:
        memberships = request.user.active_memberships
        is_authorized = memberships.filter(role=CorporateRole.ADMIN).exists()
        
    if not is_authorized:
        return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
            
    failed_handoffs = PortalHandoffQueue.objects.filter(status="failed").count()
    failed_notifications = RentalNotification.objects.filter(status="failed").count()
    total_bookings = BookingRequest.objects.count()
    
    return Response({
        "status": "healthy",
        "failed_handoffs": failed_handoffs,
        "failed_notifications": failed_notifications,
        "total_bookings": total_bookings
    })

