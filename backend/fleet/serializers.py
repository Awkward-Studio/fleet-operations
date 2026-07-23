from django.db import models
from django.utils import timezone
from rest_framework import serializers

from .models import (
    ContractAllowance,
    ContractRate,
    CorporateContract,
    CorporateCustomer,
    CustomerContact,
    Driver,
    DriverStatus,
    Trip,
    TripStatus,
    Vehicle,
    VehicleStatus,
)
from media_store.models import UploadedAsset
from media_store.serializers import UploadedAssetSerializer


class CustomerContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerContact
        fields = [
            "id",
            "customer",
            "name",
            "contact_type",
            "phone",
            "email",
            "is_primary",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class CorporateCustomerSerializer(serializers.ModelSerializer):
    contacts = CustomerContactSerializer(many=True, read_only=True)
    active_contract_summary = serializers.SerializerMethodField()

    class Meta:
        model = CorporateCustomer
        fields = [
            "id",
            "code",
            "legal_name",
            "display_name",
            "status",
            "is_active",
            "gstin",
            "billing_address",
            "billing_email",
            "billing_phone",
            "booking_contact_name",
            "booking_contact_email",
            "booking_contact_phone",
            "payment_terms_days",
            "po_required",
            "notes",
            "contacts",
            "active_contract_summary",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_active_contract_summary(self, obj):
        today = timezone.localdate()
        active_contract = obj.contracts.filter(
            status="ACTIVE",
            effective_start__lte=today,
        ).filter(
            models.Q(effective_end__isnull=True) | models.Q(effective_end__gte=today)
        ).first() if hasattr(obj, "contracts") else None

        if active_contract:
            return {
                "id": active_contract.id,
                "title": active_contract.title,
                "version_name": active_contract.version_name,
                "rates_count": active_contract.rates.count() if hasattr(active_contract, "rates") else 0,
            }
        return None


class ContractRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractRate
        fields = [
            "id",
            "contract",
            "city",
            "vehicle_category",
            "duty_type",
            "included_hours",
            "included_km",
            "base_rate",
            "extra_hour_rate",
            "extra_km_rate",
            "switch_threshold_hours",
            "switch_threshold_km",
            "outstation_daily_min_km",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "contract", "created_at", "updated_at"]

    def validate_city(self, value):
        return value.strip().lower() if value else value

    def validate_vehicle_category(self, value):
        return value.strip().lower() if value else value

    def validate(self, attrs):
        base_rate = attrs.get("base_rate", getattr(self.instance, "base_rate", None))
        if base_rate is not None and base_rate < 0:
            raise serializers.ValidationError({"base_rate": "Base rate cannot be negative."})

        extra_hr = attrs.get("extra_hour_rate", getattr(self.instance, "extra_hour_rate", None))
        if extra_hr is not None and extra_hr < 0:
            raise serializers.ValidationError({"extra_hour_rate": "Extra hour rate cannot be negative."})

        extra_km = attrs.get("extra_km_rate", getattr(self.instance, "extra_km_rate", None))
        if extra_km is not None and extra_km < 0:
            raise serializers.ValidationError({"extra_km_rate": "Extra km rate cannot be negative."})

        return attrs


class ContractAllowanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractAllowance
        fields = [
            "id",
            "contract",
            "allowance_type",
            "amount",
            "description",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "contract", "created_at", "updated_at"]

    def validate_amount(self, value):
        if value < 0:
            raise serializers.ValidationError("Allowance amount cannot be negative.")
        return value


class CorporateContractSerializer(serializers.ModelSerializer):
    rates = ContractRateSerializer(many=True, required=False)
    allowances = ContractAllowanceSerializer(many=True, required=False)
    customer_display_name = serializers.ReadOnlyField(source="customer.display_name")

    class Meta:
        model = CorporateContract
        fields = [
            "id",
            "customer",
            "customer_display_name",
            "title",
            "version_name",
            "effective_start",
            "effective_end",
            "status",
            "currency",
            "cgst_rate",
            "sgst_rate",
            "payment_terms_days",
            "cancellation_terms",
            "metering_policy",
            "notes",
            "rates",
            "allowances",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        start = attrs.get("effective_start", getattr(self.instance, "effective_start", None))
        end = attrs.get("effective_end", getattr(self.instance, "effective_end", None))
        if start and end and end < start:
            raise serializers.ValidationError({"effective_end": "Effective end date cannot precede effective start date."})

        customer = attrs.get("customer", getattr(self.instance, "customer", None))
        status = attrs.get("status", getattr(self.instance, "status", None))

        if status == "ACTIVE" and customer:
            qs = CorporateContract.objects.filter(customer=customer, status="ACTIVE")
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            for contract in qs:
                # Overlap check
                c_start = contract.effective_start
                c_end = contract.effective_end
                if c_end is None and (end is None or end >= c_start):
                    raise serializers.ValidationError(
                        {"status": f"Overlaps with active contract '{contract.title}' ({contract.version_name})."}
                    )
                elif end is None and (c_end is None or c_end >= start):
                    raise serializers.ValidationError(
                        {"status": f"Overlaps with active contract '{contract.title}' ({contract.version_name})."}
                    )
                elif c_end and end and (start <= c_end and end >= c_start):
                    raise serializers.ValidationError(
                        {"status": f"Overlaps with active contract '{contract.title}' ({contract.version_name})."}
                    )

            # Check if rates exist when activating
            rates_data = attrs.get("rates", None)
            existing_rates_count = self.instance.rates.count() if self.instance else 0
            if (rates_data is not None and len(rates_data) == 0) or (rates_data is None and existing_rates_count == 0):
                raise serializers.ValidationError({"status": "Cannot activate contract with no valid rates."})

        return attrs

    def create(self, validated_data):
        rates_data = validated_data.pop("rates", [])
        allowances_data = validated_data.pop("allowances", [])

        from django.db import transaction
        with transaction.atomic():
            contract = CorporateContract.objects.create(**validated_data)
            for rate_item in rates_data:
                ContractRate.objects.create(contract=contract, **rate_item)
            for allowance_item in allowances_data:
                ContractAllowance.objects.create(contract=contract, **allowance_item)
        return contract

    def update(self, instance, validated_data):
        rates_data = validated_data.pop("rates", None)
        allowances_data = validated_data.pop("allowances", None)

        from django.db import transaction
        with transaction.atomic():
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

            if rates_data is not None:
                instance.rates.all().delete()
                for rate_item in rates_data:
                    ContractRate.objects.create(contract=instance, **rate_item)

            if allowances_data is not None:
                instance.allowances.all().delete()
                for allowance_item in allowances_data:
                    ContractAllowance.objects.create(contract=instance, **allowance_item)

        return instance
>>>>>>> fb782d6 (Implement Customer Management and Corporate Contract Pricing feature)


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
    customer_details = CorporateCustomerSerializer(source="customer", read_only=True)
    customer_id = serializers.PrimaryKeyRelatedField(
        queryset=CorporateCustomer.objects.all(),
        source="customer",
        allow_null=True,
        required=False,
        write_only=True,
    )

    class Meta:
        model = Trip
        fields = [
            "id",
            "booking_type",
            "customer",
            "customer_id",
            "customer_details",
            "contract",
            "contract_rate",
            "duty_type",
            "vehicle_category_requested",
            "customer_name",
            "customer_display_name_snapshot",
            "pricing_snapshot",
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
        read_only_fields = [
            "id",
            "customer_display_name_snapshot",
            "pricing_snapshot",
            "contract",
            "contract_rate",
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
        pickup_at = attrs.get("pickup_at", getattr(self.instance, "pickup_at", None))
        drop_at = attrs.get("estimated_drop_at", getattr(self.instance, "estimated_drop_at", None))
        if pickup_at and drop_at and drop_at <= pickup_at:
            raise serializers.ValidationError("Estimated drop time must be after pickup time.")

        booking_type = attrs.get("booking_type", getattr(self.instance, "booking_type", "ADHOC"))

        if booking_type == "CORPORATE":
            customer = attrs.get("customer", getattr(self.instance, "customer", None))
            if not customer:
                raise serializers.ValidationError({"customer": "Corporate trip requires a valid customer."})

            duty_type = attrs.get("duty_type", getattr(self.instance, "duty_type", ""))
            category = attrs.get("vehicle_category_requested", getattr(self.instance, "vehicle_category_requested", ""))
            if not duty_type:
                raise serializers.ValidationError({"duty_type": "Corporate trip requires duty_type."})
            if not category:
                raise serializers.ValidationError({"vehicle_category_requested": "Corporate trip requires vehicle_category_requested."})

            pickup_city = attrs.get("pickup_city", getattr(self.instance, "pickup_city", ""))
            distance_km = attrs.get("distance_km", getattr(self.instance, "distance_km", 0))

            from .pricing_service import calculate_quote, PricingError
            try:
                quote = calculate_quote(
                    customer_id=customer.id,
                    pickup_datetime=pickup_at,
                    pickup_city=pickup_city,
                    vehicle_category=category,
                    duty_type=duty_type,
                    planned_km=distance_km or 0,
                )
                from decimal import Decimal
                attrs["fare_amount"] = Decimal(quote["total_amount"])
                attrs["customer_display_name_snapshot"] = customer.display_name
                attrs["pricing_snapshot"] = quote
                attrs["contract_id"] = quote["contract"]["id"]
                attrs["contract_rate_id"] = quote["rate"]["id"]
            except PricingError as e:
                raise serializers.ValidationError({"pricing": str(e)})
        else:
            cust_name = attrs.get("customer_name", getattr(self.instance, "customer_name", ""))
            attrs["customer_display_name_snapshot"] = cust_name

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

