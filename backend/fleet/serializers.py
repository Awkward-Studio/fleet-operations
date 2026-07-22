from django.utils import timezone
from rest_framework import serializers

from .models import Driver, DriverStatus, Trip, TripStatus, Vehicle, VehicleStatus
from media_store.models import UploadedAsset
from media_store.serializers import UploadedAssetSerializer


class DriverSerializer(serializers.ModelSerializer):
    aadhaar_card = UploadedAssetSerializer(read_only=True)
    aadhaar_card_id = serializers.PrimaryKeyRelatedField(
        queryset=UploadedAsset.objects.all(),
        source="aadhaar_card",
        allow_null=True,
        required=False,
        write_only=True,
    )
    driving_license = UploadedAssetSerializer(read_only=True)
    driving_license_id = serializers.PrimaryKeyRelatedField(
        queryset=UploadedAsset.objects.all(),
        source="driving_license",
        allow_null=True,
        required=False,
        write_only=True,
    )
    police_clearance_certificate = UploadedAssetSerializer(read_only=True)
    police_clearance_certificate_id = serializers.PrimaryKeyRelatedField(
        queryset=UploadedAsset.objects.all(),
        source="police_clearance_certificate",
        allow_null=True,
        required=False,
        write_only=True,
    )

    class Meta:
        model = Driver
        fields = [
            "id",
            "name",
            "phone",
            "license_number",
            "home_base",
            "status",
            "rating",
            "aadhaar_card",
            "aadhaar_card_id",
            "driving_license",
            "driving_license_id",
            "driving_license_expiry_date",
            "police_clearance_certificate",
            "police_clearance_certificate_id",
        ]


class VehicleSerializer(serializers.ModelSerializer):
    assigned_driver = DriverSerializer(read_only=True)
    assigned_driver_id = serializers.PrimaryKeyRelatedField(
        queryset=Driver.objects.all(),
        source="assigned_driver",
        allow_null=True,
        required=False,
        write_only=True,
    )
    compliance_blockers = serializers.ListField(read_only=True)
    is_compliant = serializers.BooleanField(read_only=True)

    class Meta:
        model = Vehicle
        fields = [
            "id",
            "registration_number",
            "make",
            "model",
            "category",
            "current_city",
            "status",
            "assigned_driver",
            "assigned_driver_id",
            "permit_expires_on",
            "insurance_expires_on",
            "pollution_expires_on",
            "fitness_expires_on",
            "odometer_km",
            "compliance_blockers",
            "is_compliant",
        ]


class TripSerializer(serializers.ModelSerializer):
    vehicle = VehicleSerializer(read_only=True)
    driver = DriverSerializer(read_only=True)

    class Meta:
        model = Trip
        fields = [
            "id",
            "customer_name",
            "pickup_city",
            "drop_city",
            "pickup_at",
            "estimated_drop_at",
            "status",
            "vehicle",
            "driver",
            "ota_source",
            "fare_amount",
            "notes",
            "pickup_latitude",
            "pickup_longitude",
            "drop_latitude",
            "drop_longitude",
            "distance_km",
        ]

    def to_internal_value(self, data):
        if isinstance(data, dict):
            data = data.copy()
            for field in ["pickup_latitude", "pickup_longitude", "drop_latitude", "drop_longitude"]:
                if field in data and data[field] is not None and data[field] != "":
                    try:
                        data[field] = round(float(data[field]), 8)
                    except (ValueError, TypeError):
                        pass
        return super().to_internal_value(data)

    def validate(self, attrs):
        if attrs["estimated_drop_at"] <= attrs["pickup_at"]:
            raise serializers.ValidationError("Estimated drop time must be after pickup time.")
        return attrs


class AssignTripSerializer(serializers.Serializer):
    vehicle_id = serializers.PrimaryKeyRelatedField(queryset=Vehicle.objects.all(), source="vehicle")
    driver_id = serializers.PrimaryKeyRelatedField(queryset=Driver.objects.all(), source="driver")

    def validate(self, attrs):
        trip = self.context["trip"]
        vehicle = attrs["vehicle"]
        driver = attrs["driver"]

        if vehicle.status not in [VehicleStatus.IDLE]:
            raise serializers.ValidationError("Vehicle is not idle.")
        if not vehicle.is_compliant:
            raise serializers.ValidationError("Vehicle has expired compliance documents.")
        if driver.status not in [DriverStatus.AVAILABLE, DriverStatus.ASSIGNED]:
            raise serializers.ValidationError("Driver is not available.")

        overlap = Trip.objects.filter(
            vehicle=vehicle,
            pickup_at__lt=trip.estimated_drop_at,
            estimated_drop_at__gt=trip.pickup_at,
        ).exclude(status__in=[TripStatus.COMPLETED, TripStatus.CANCELLED])
        if overlap.exists():
            raise serializers.ValidationError("Vehicle is already booked for this time window.")

        driver_overlap = Trip.objects.filter(
            driver=driver,
            pickup_at__lt=trip.estimated_drop_at,
            estimated_drop_at__gt=trip.pickup_at,
        ).exclude(status__in=[TripStatus.COMPLETED, TripStatus.CANCELLED])
        if driver_overlap.exists():
            raise serializers.ValidationError("Driver is already booked for this time window.")

        return attrs


class TransitionTripSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=TripStatus.choices)

    def save(self, **kwargs):
        trip = self.context["trip"]
        trip.status = self.validated_data["status"]
        trip.save(update_fields=["status", "updated_at"])

        if trip.vehicle_id:
            if trip.status == TripStatus.EN_ROUTE_PICKUP:
                trip.vehicle.status = VehicleStatus.EN_ROUTE_PICKUP
            elif trip.status == TripStatus.ACTIVE:
                trip.vehicle.status = VehicleStatus.ACTIVE_TRIP
            elif trip.status in [TripStatus.COMPLETED, TripStatus.CANCELLED]:
                trip.vehicle.status = VehicleStatus.IDLE
                trip.vehicle.current_city = trip.drop_city
            elif trip.status == TripStatus.ASSIGNED:
                trip.vehicle.status = VehicleStatus.IDLE
            trip.vehicle.save()

        if trip.driver_id:
            if trip.status in [TripStatus.EN_ROUTE_PICKUP, TripStatus.ACTIVE]:
                trip.driver.status = DriverStatus.ON_TRIP
            elif trip.status in [TripStatus.COMPLETED, TripStatus.CANCELLED]:
                trip.driver.status = DriverStatus.AVAILABLE
            elif trip.status == TripStatus.ASSIGNED:
                trip.driver.status = DriverStatus.ASSIGNED
            trip.driver.save()

        return trip


class AvailabilitySerializer(serializers.Serializer):
    vehicle_id = serializers.IntegerField()
    registration_number = serializers.CharField()
    category = serializers.CharField()
    available_from = serializers.DateTimeField()
    available_city = serializers.CharField()
    driver_name = serializers.CharField(allow_null=True)
    compliance_blockers = serializers.ListField(child=serializers.CharField())

