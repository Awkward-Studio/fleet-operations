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
