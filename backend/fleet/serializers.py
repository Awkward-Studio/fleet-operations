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
class DriverSerializer(serializers.ModelSerializer):
    user_username = serializers.ReadOnlyField(source="user.username")
    user_email = serializers.ReadOnlyField(source="user.email")
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
            "user",
            "user_username",
            "user_email",
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
            "fuel_type",
            "fuel_unit",
            "tank_capacity",
            "expected_mileage_min",
            "expected_mileage_max",
            "baseline_mileage",
        ]


class TripSerializer(serializers.ModelSerializer):
    vehicle = VehicleSerializer(read_only=True)
    driver = DriverSerializer(read_only=True)
    customer_details = CorporateCustomerSerializer(source="customer", read_only=True)
    checklist = serializers.SerializerMethodField()
    otp_verified = serializers.SerializerMethodField()
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
            "customer_phone",
            "customer_display_name_snapshot",
            "pricing_snapshot",
            "pickup_city",
            "drop_city",
            "pickup_address",
            "drop_address",
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
            "checklist",
            "otp_verified",
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

    def get_checklist(self, obj):
        checklist = getattr(obj, "checklist", None)
        if not checklist:
            return None
        return TripChecklistSerializer(checklist, context=self.context).data

    def get_otp_verified(self, obj):
        otp_session = getattr(obj, "otp_session", None)
        return bool(otp_session and otp_session.is_verified)


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
            elif trip.status == TripStatus.ARRIVED_AT_PICKUP:
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
            if trip.status in [TripStatus.EN_ROUTE_PICKUP, TripStatus.ARRIVED_AT_PICKUP, TripStatus.ACTIVE]:
                trip.driver.status = DriverStatus.ON_TRIP
            elif trip.status in [TripStatus.COMPLETED, TripStatus.CANCELLED]:
                trip.driver.status = DriverStatus.AVAILABLE
            elif trip.status == TripStatus.ASSIGNED:
                trip.driver.status = DriverStatus.ASSIGNED
            trip.driver.save()

        return trip


class TripChecklistSerializer(serializers.ModelSerializer):
    start_odometer_asset = UploadedAssetSerializer(read_only=True)
    end_odometer_asset = UploadedAssetSerializer(read_only=True)

    class Meta:
        model = TripChecklist
        fields = [
            "id",
            "trip",
            "start_odometer_km",
            "start_odometer_asset",
            "end_odometer_km",
            "end_odometer_asset",
            "cleanliness_ok",
            "fuel_level_percent",
            "tire_pressure_ok",
            "notes",
            "start_idempotency_key",
            "complete_idempotency_key",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class TripChecklistSubmitSerializer(serializers.Serializer):
    start_odometer_km = serializers.IntegerField(min_value=0)
    start_odometer_asset_id = serializers.PrimaryKeyRelatedField(
        queryset=UploadedAsset.objects.all(),
        required=False,
        allow_null=True,
        source="start_odometer_asset",
    )
    start_odometer_photo = serializers.FileField(required=False, write_only=True)
    cleanliness_ok = serializers.BooleanField(default=True)
    fuel_level_percent = serializers.IntegerField(min_value=0, max_value=100, default=100)
    tire_pressure_ok = serializers.BooleanField(default=True)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    idempotency_key = serializers.CharField(required=False, allow_blank=False, max_length=120)

    def validate(self, attrs):
        if not attrs.get("start_odometer_asset") and not attrs.get("start_odometer_photo"):
            raise serializers.ValidationError("Provide start_odometer_asset_id or start_odometer_photo.")
        return attrs


class TripCompleteSerializer(serializers.Serializer):
    end_odometer_km = serializers.IntegerField(min_value=0)
    end_odometer_asset_id = serializers.PrimaryKeyRelatedField(
        queryset=UploadedAsset.objects.all(),
        required=False,
        allow_null=True,
        source="end_odometer_asset",
    )
    end_odometer_photo = serializers.FileField(required=False, write_only=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    idempotency_key = serializers.CharField(required=False, allow_blank=False, max_length=120)

    def validate(self, attrs):
        if not attrs.get("end_odometer_asset") and not attrs.get("end_odometer_photo"):
            raise serializers.ValidationError("Provide end_odometer_asset_id or end_odometer_photo.")
        return attrs


class TripLocationLogSerializer(serializers.ModelSerializer):
    idempotency_key = serializers.CharField(required=False, allow_blank=False, max_length=120)

    class Meta:
        model = TripLocationLog
        fields = [
            "id",
            "trip",
            "latitude",
            "longitude",
            "speed_kmh",
            "heading",
            "timestamp",
            "idempotency_key",
        ]
        read_only_fields = ["id", "trip"]


class TripOTPSerializer(serializers.ModelSerializer):
    class Meta:
        model = TripOTP
        fields = ["id", "trip", "code", "is_verified", "created_at", "updated_at"]
        read_only_fields = fields


class TripGenerateOTPSerializer(serializers.Serializer):
    digits = serializers.IntegerField(min_value=4, max_value=6, default=6)
    idempotency_key = serializers.CharField(required=False, allow_blank=False, max_length=120)


class TripVerifyOTPSerializer(serializers.Serializer):
    code = serializers.CharField(min_length=4, max_length=6)
    idempotency_key = serializers.CharField(required=False, allow_blank=False, max_length=120)


class AvailabilitySerializer(serializers.Serializer):
    vehicle_id = serializers.IntegerField()
    registration_number = serializers.CharField()
    category = serializers.CharField()
    available_from = serializers.DateTimeField()
    available_city = serializers.CharField()
    driver_name = serializers.CharField(allow_null=True)
    compliance_blockers = serializers.ListField(child=serializers.CharField())


class FuelTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FuelTransaction
        fields = [
            "id",
            "vehicle",
            "driver",
            "vendor",
            "invoice_number",
            "transaction_datetime",
            "odometer_km",
            "quantity",
            "unit_price",
            "tax_amount",
            "total_amount",
            "is_full_fill",
            "source",
            "notes",
            "status",
            "receipt_asset",
            "odometer_asset",
            "is_correction",
            "corrected_by_transaction",
            "corrected_from_transaction",
            "approved_by",
            "approved_at",
            "has_anomaly",
            "anomaly_flags",
            "anomaly_review_notes",
            "anomaly_reviewed_by",
            "anomaly_reviewed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "is_correction",
            "corrected_by_transaction",
            "corrected_from_transaction",
            "approved_by",
            "approved_at",
            "expense_posted",
            "posted_at",
            "has_anomaly",
            "anomaly_flags",
            "anomaly_review_notes",
            "anomaly_reviewed_by",
            "anomaly_reviewed_at",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        quantity = attrs.get("quantity")
        unit_price = attrs.get("unit_price")
        tax_amount = attrs.get("tax_amount", 0)
        total_amount = attrs.get("total_amount")

        if quantity is not None and unit_price is not None and total_amount is not None:
            expected_total = quantity * unit_price + tax_amount
            from decimal import Decimal
            if abs(total_amount - expected_total) > Decimal("0.05"):
                raise serializers.ValidationError(
                    {"total_amount": f"Reconciliation failed: quantity ({quantity}) * price ({unit_price}) + tax ({tax_amount}) = {expected_total}, but total is {total_amount}."}
                )

        if quantity is not None and quantity <= 0:
            raise serializers.ValidationError({"quantity": "Quantity must be greater than zero."})

        if total_amount is not None and total_amount < 0:
            raise serializers.ValidationError({"total_amount": "Total amount cannot be negative."})

        source = attrs.get("source", "console")
        if source == "mobile_app":
            if not attrs.get("receipt_asset"):
                raise serializers.ValidationError({"receipt_asset": "Receipt evidence photo is required for mobile submissions."})
            if not attrs.get("odometer_asset"):
                raise serializers.ValidationError({"odometer_asset": "Odometer verification photo is required for mobile submissions."})

        return attrs


class FuelTransactionDetailSerializer(FuelTransactionSerializer):
    vehicle_details = VehicleSerializer(source="vehicle", read_only=True)
    driver_details = DriverSerializer(source="driver", read_only=True)
    receipt_asset_details = UploadedAssetSerializer(source="receipt_asset", read_only=True)
    odometer_asset_details = UploadedAssetSerializer(source="odometer_asset", read_only=True)

    class Meta(FuelTransactionSerializer.Meta):
        fields = FuelTransactionSerializer.Meta.fields + [
            "vehicle_details",
            "driver_details",
            "receipt_asset_details",
            "odometer_asset_details",
        ]

