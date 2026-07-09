from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response

from .models import Driver, DriverStatus, Trip, TripStatus, Vehicle, VehicleStatus
from .serializers import (
    AssignTripSerializer,
    AvailabilitySerializer,
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

