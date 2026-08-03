from decimal import Decimal

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
    BillToType,
    PricingAmountStatus,
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
    FuelTransactionImage,
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


def sync_contract_to_rate_book(contract):
    from .models import RateBook, RateBookStatus, RateBookType, RatePackage
    from django.utils import timezone
    from decimal import Decimal

    book_code = f"RB-{contract.customer.code}"
    
    status_map = {
        "DRAFT": RateBookStatus.DRAFT,
        "ACTIVE": RateBookStatus.ACTIVE,
        "EXPIRED": RateBookStatus.RETIRED,
        "TERMINATED": RateBookStatus.RETIRED,
        "ARCHIVED": RateBookStatus.RETIRED,
    }
    book_status = status_map.get(contract.status, RateBookStatus.DRAFT)

    rate_book, created = RateBook.objects.update_or_create(
        contract=contract,
        defaults={
            "code": book_code,
            "name": f"Rate Book for {contract.title}",
            "version": 1,
            "book_type": RateBookType.CORPORATE,
            "status": book_status,
            "effective_start": contract.effective_start,
            "effective_end": contract.effective_end,
            "approved_at": timezone.now() if book_status == RateBookStatus.ACTIVE else None,
        }
    )

    # Delete existing packages for this rate book
    rate_book.packages.all().delete()

    # Resolve allowances to populate package-level allowance columns
    driver_allowance = Decimal("0.00")
    night_charge = Decimal("0.00")
    for allowance in contract.allowances.all():
        if allowance.allowance_type in ["OVERNIGHT_DRIVER_ALLOWANCE", "OUTSTATION_PER_DAY"]:
            driver_allowance = allowance.amount
        elif allowance.allowance_type in ["NIGHT_ALLOWANCE"]:
            night_charge = allowance.amount

    # Create RatePackages for each ContractRate under the contract
    for rate in contract.rates.all():
        pkg_code = f"PKG-{contract.customer.code}-{rate.city.upper()}-{rate.vehicle_category.upper()}-{rate.duty_type}"
        RatePackage.objects.create(
            rate_book=rate_book,
            code=pkg_code,
            name=f"{rate.city.title()} - {rate.vehicle_category.title()} ({rate.duty_type})",
            city=rate.city,
            vehicle_category=rate.vehicle_category,
            duty_type=rate.duty_type,
            included_hours=Decimal(str(rate.included_hours)),
            included_km=Decimal(str(rate.included_km)),
            base_rate=rate.base_rate,
            extra_hour_rate=rate.extra_hour_rate,
            extra_km_rate=rate.extra_km_rate,
            daily_minimum_km=Decimal(str(rate.outstation_daily_min_km or 0)),
            cgst_rate=contract.cgst_rate,
            sgst_rate=contract.sgst_rate,
            metering_policy=contract.metering_policy,
            driver_allowance_per_day=driver_allowance,
            night_charge=night_charge,
        )


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
            
            # Sync to rate book
            sync_contract_to_rate_book(contract)
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

            # Sync to rate book
            sync_contract_to_rate_book(instance)

        return instance

class DriverSerializer(serializers.ModelSerializer):
    user_username = serializers.ReadOnlyField(source="user.username")
    user_email = serializers.ReadOnlyField(source="user.email")
    email = serializers.EmailField(required=False, write_only=True)
    password = serializers.CharField(
        required=False,
        write_only=True,
        style={"input_type": "password"},
    )
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
    current_vehicle = serializers.SerializerMethodField()

    class Meta:
        model = Driver
        fields = [
            "id",
            "user",
            "user_username",
            "user_email",
            "email",
            "password",
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
            "current_vehicle",
        ]

    def get_current_vehicle(self, obj):
        vehicle = obj.vehicles.first()
        if vehicle:
            return {
                "id": vehicle.id,
                "registration_number": vehicle.registration_number,
                "make": vehicle.make,
                "model": vehicle.model,
                "odometer_km": vehicle.odometer_km,
            }
        return None

    def validate_email(self, value):
        if value:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            if User.objects.filter(email__iexact=value).exists():
                raise serializers.ValidationError("A user with this email already exists.")
        return value.lower()

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")
        if email and not password:
            raise serializers.ValidationError({"password": "Password is required when email is provided."})
        if password and not email:
            raise serializers.ValidationError({"email": "Email is required when password is provided."})
        if password and len(password) < 6:
            raise serializers.ValidationError({"password": "Password must be at least 6 characters long."})
        return attrs

    def create(self, validated_data):
        email = validated_data.pop("email", None)
        password = validated_data.pop("password", None)
        
        from django.db import transaction
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        with transaction.atomic():
            user = None
            if email and password:
                user = User.objects.create_user(
                    username=email,
                    email=email,
                    password=password,
                    role="driver",
                    first_name=validated_data.get("name", "").split(" ")[0],
                    last_name=" ".join(validated_data.get("name", "").split(" ")[1:]) if len(validated_data.get("name", "").split(" ")) > 1 else "",
                )
            driver = Driver.objects.create(user=user, **validated_data)
            return driver


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
    vehicle_id = serializers.PrimaryKeyRelatedField(
        queryset=Vehicle.objects.all(),
        source="vehicle",
        allow_null=True,
        required=False,
        write_only=True,
    )
    driver = DriverSerializer(read_only=True)
    driver_id = serializers.PrimaryKeyRelatedField(
        queryset=Driver.objects.all(),
        source="driver",
        allow_null=True,
        required=False,
        write_only=True,
    )
    customer_details = CorporateCustomerSerializer(source="customer", read_only=True)
    checklist = serializers.SerializerMethodField()
    otp_verified = serializers.SerializerMethodField()
    financial_trace = serializers.SerializerMethodField()
    otp_mode = serializers.SerializerMethodField()
    customer_id = serializers.PrimaryKeyRelatedField(
        queryset=CorporateCustomer.objects.all(),
        source="customer",
        allow_null=True,
        required=False,
        write_only=True,
    )
    contract = CorporateContractSerializer(read_only=True)
    contract_id = serializers.PrimaryKeyRelatedField(
        queryset=CorporateContract.objects.all(),
        source="contract",
        allow_null=True,
        required=False,
        write_only=True,
    )
    contract_rate = ContractRateSerializer(read_only=True)
    contract_rate_id = serializers.PrimaryKeyRelatedField(
        queryset=ContractRate.objects.all(),
        source="contract_rate",
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
            "contract_id",
            "contract_rate",
            "contract_rate_id",
            "duty_type",

            "vehicle_category_requested",
            "customer_name",
            "customer_phone",
            "customer_display_name_snapshot",
            "bill_to_type",
            "bill_to_key",
            "bill_to_name_snapshot",
            "bill_to_address_snapshot",
            "bill_to_gstin_snapshot",
            "bill_to_email_snapshot",
            "bill_to_phone_snapshot",
            "po_number",
            "pricing_snapshot",
            "rate_package",
            "calculation_version",
            "pickup_city",
            "drop_city",
            "pickup_address",
            "drop_address",
            "pickup_at",
            "estimated_drop_at",
            "status",
            "vehicle",
            "vehicle_id",
            "driver",
            "driver_id",
            "ota_source",
            "ota_external_reference",
            "fare_amount",
            "pricing_amount_status",
            "quoted_taxable_amount",
            "quoted_tax_amount",
            "quoted_total_amount",
            "final_taxable_amount",
            "final_tax_amount",
            "final_total_amount",
            "notes",
            "pickup_latitude",
            "pickup_longitude",
            "drop_latitude",
            "drop_longitude",
            "distance_km",
            "checklist",
            "otp_verified",
            "financial_trace",
            "otp_mode",
        ]

    def get_financial_trace(self, obj):
        from billing.models import JournalEntry

        closeout = getattr(obj, "closeout", None)
        invoice_link = getattr(obj, "invoice_link", None)
        invoice = invoice_link.invoice if invoice_link else None
        journal = (
            JournalEntry.objects.filter(
                source_type="INVOICE", source_id=str(invoice.id)
            ).first()
            if invoice
            else None
        )
        return {
            "trip_id": obj.id,
            "quote": {
                "calculation_version": obj.calculation_version,
                "pricing_amount_status": obj.pricing_amount_status,
                "quoted_total_amount": (
                    str(obj.quoted_total_amount)
                    if obj.quoted_total_amount is not None
                    else None
                ),
            },
            "closeout": (
                {
                    "id": closeout.id,
                    "status": closeout.status,
                    "final_total_amount": (
                        str(closeout.final_total_amount)
                        if closeout.final_total_amount is not None
                        else None
                    ),
                }
                if closeout
                else None
            ),
            "invoice": (
                {
                    "id": invoice.id,
                    "number": invoice.invoice_number,
                    "status": invoice.status,
                    "total_amount": str(invoice.total_amount),
                    "balance_amount": str(invoice.balance_amount),
                }
                if invoice
                else None
            ),
            "journal": (
                {"id": journal.id, "entry_number": journal.entry_number}
                if journal
                else None
            ),
        }
        read_only_fields = [
            "id",
            "customer_display_name_snapshot",
            "bill_to_type",
            "bill_to_key",
            "bill_to_name_snapshot",
            "bill_to_address_snapshot",
            "bill_to_gstin_snapshot",
            "bill_to_email_snapshot",
            "bill_to_phone_snapshot",
            "pricing_snapshot",
            "rate_package",
            "calculation_version",
            "pricing_amount_status",
            "quoted_taxable_amount",
            "quoted_tax_amount",
            "quoted_total_amount",
            "final_taxable_amount",
            "final_tax_amount",
            "final_total_amount",
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

        contract = attrs.get("contract", getattr(self.instance, "contract", None))
        customer = None
        if booking_type == "CORPORATE":
            customer = attrs.get("customer", getattr(self.instance, "customer", None))
            if not customer:
                raise serializers.ValidationError({"customer": "Corporate trip requires a valid customer."})
            
            # Resolve active contract if not provided
            if not contract:
                pickup_date = timezone.localtime(pickup_at).date() if pickup_at else timezone.localdate()
                contracts = CorporateContract.objects.filter(
                    customer=customer,
                    status="ACTIVE",
                    effective_start__lte=pickup_date,
                ).filter(
                    models.Q(effective_end__isnull=True) | models.Q(effective_end__gte=pickup_date)
                )
                if contracts.exists():
                    contract = contracts.first()
                    attrs["contract"] = contract
        else:
            cust_name = attrs.get("customer_name", getattr(self.instance, "customer_name", ""))
            attrs["customer_display_name_snapshot"] = cust_name
            if booking_type == "OTA":
                ota_source = attrs.get("ota_source", getattr(self.instance, "ota_source", ""))
                if not ota_source:
                    raise serializers.ValidationError({"ota_source": "OTA trips require an OTA counterparty."})
                attrs["bill_to_type"] = BillToType.OTA
                attrs["bill_to_key"] = f"OTA:{ota_source.strip().upper()}"
                attrs["bill_to_name_snapshot"] = ota_source.strip()
            else:
                attrs["bill_to_type"] = BillToType.DIRECT
                attrs["bill_to_name_snapshot"] = cust_name
                attrs["bill_to_phone_snapshot"] = attrs.get(
                    "customer_phone",
                    getattr(self.instance, "customer_phone", ""),
                )

        duty_type = attrs.get("duty_type", getattr(self.instance, "duty_type", ""))
        category = attrs.get(
            "vehicle_category_requested",
            getattr(self.instance, "vehicle_category_requested", ""),
        )
        if not duty_type:
            raise serializers.ValidationError({"duty_type": "Every trip requires a pricing package type."})
        if not category:
            raise serializers.ValidationError({"vehicle_category_requested": "Every trip requires a vehicle category."})

        # Determine pricing category:
        # - vehicle_category_requested is always the primary source (it maps to rate package names like 'dzire', 'ertiga')
        # - vehicle.category is a broad fleet-management label (like 'Sedan', 'MPV') used only as last resort
        vehicle = attrs.get("vehicle", getattr(self.instance, "vehicle", None))
        pricing_category = category  # already resolved from vehicle_category_requested
        if vehicle and not pricing_category:
            # Only use vehicle.category as a fallback when vehicle_category_requested is empty
            pricing_category = vehicle.category

        from .pricing_service import PricingError, calculate_unified_quote
        try:
            quote = calculate_unified_quote(
                booking_type=booking_type,
                customer_id=customer.id if booking_type == "CORPORATE" else None,
                contract_id=contract.id if (booking_type == "CORPORATE" and contract) else None,
                pickup_datetime=pickup_at,
                pickup_city=attrs.get("pickup_city", getattr(self.instance, "pickup_city", "")),
                drop_city=attrs.get("drop_city", getattr(self.instance, "drop_city", "")),
                vehicle_category=pricing_category,
                duty_type=duty_type,
                planned_km=attrs.get("distance_km", getattr(self.instance, "distance_km", 0)) or 0,
                ota_source=attrs.get("ota_source", getattr(self.instance, "ota_source", "")),
            )
        except PricingError as exc:
            raise serializers.ValidationError({"pricing": str(exc)})
        attrs["fare_amount"] = Decimal(quote["gross_amount"])
        attrs["pricing_amount_status"] = PricingAmountStatus.QUOTED
        attrs["quoted_taxable_amount"] = Decimal(quote["taxable_amount"])
        attrs["quoted_tax_amount"] = Decimal(quote["tax_amount"])
        attrs["quoted_total_amount"] = Decimal(quote["gross_amount"])
        attrs["pricing_snapshot"] = quote
        attrs["rate_package_id"] = quote["package"]["id"]
        attrs["calculation_version"] = quote["calculation_version"]

        if booking_type == "CORPORATE":
            attrs["customer_display_name_snapshot"] = customer.display_name
            attrs["bill_to_type"] = BillToType.CORPORATE
            attrs["bill_to_key"] = f"CORPORATE:{customer.id}"
            attrs["bill_to_name_snapshot"] = customer.legal_name or customer.display_name
            attrs["bill_to_address_snapshot"] = customer.billing_address
            attrs["bill_to_gstin_snapshot"] = customer.gstin
            attrs["bill_to_email_snapshot"] = customer.billing_email
            attrs["bill_to_phone_snapshot"] = customer.billing_phone

            if contract:
                contract_rate = ContractRate.objects.filter(
                    contract=contract,
                    city__iexact=attrs.get("pickup_city", getattr(self.instance, "pickup_city", "")).strip().lower(),
                    vehicle_category__iexact=category.strip().lower(),
                    duty_type=duty_type,
                ).first()
                if not contract_rate:
                    contract_rate = ContractRate.objects.filter(
                        contract=contract,
                        city="*",
                        vehicle_category__iexact=category.strip().lower(),
                        duty_type=duty_type,
                    ).first()
                if contract_rate:
                    attrs["contract_rate"] = contract_rate


        # Validate driver and vehicle assignments
        driver = attrs.get("driver")
        vehicle = attrs.get("vehicle")

        if driver:
            if driver.status not in [DriverStatus.AVAILABLE, DriverStatus.ASSIGNED]:
                raise serializers.ValidationError({"driver_id": "Driver is not available."})
            
            if pickup_at and drop_at:
                driver_overlap = Trip.objects.filter(
                    driver=driver,
                    pickup_at__lt=drop_at,
                    estimated_drop_at__gt=pickup_at,
                ).exclude(status__in=[TripStatus.COMPLETED, TripStatus.CANCELLED])
                if self.instance:
                    driver_overlap = driver_overlap.exclude(pk=self.instance.pk)
                if driver_overlap.exists():
                    raise serializers.ValidationError({"driver_id": "Driver is already booked for this time window."})

        if vehicle:
            if vehicle.status not in [VehicleStatus.IDLE]:
                raise serializers.ValidationError({"vehicle_id": "Vehicle is not idle."})
            if not vehicle.is_compliant:
                raise serializers.ValidationError({"vehicle_id": "Vehicle has expired compliance documents."})

            if pickup_at and drop_at:
                overlap = Trip.objects.filter(
                    vehicle=vehicle,
                    pickup_at__lt=drop_at,
                    estimated_drop_at__gt=pickup_at,
                ).exclude(status__in=[TripStatus.COMPLETED, TripStatus.CANCELLED])
                if self.instance:
                    overlap = overlap.exclude(pk=self.instance.pk)
                if overlap.exists():
                    raise serializers.ValidationError({"vehicle_id": "Vehicle is already booked for this time window."})

        return attrs

    def create(self, validated_data):
        driver = validated_data.get("driver")
        vehicle = validated_data.get("vehicle")

        if driver or vehicle:
            validated_data["status"] = TripStatus.ASSIGNED

        from django.db import transaction
        with transaction.atomic():
            trip = super().create(validated_data)

            if driver:
                driver.status = DriverStatus.ASSIGNED
                driver.save(update_fields=["status"])

            if vehicle:
                if driver:
                    vehicle.assigned_driver = driver
                vehicle.status = VehicleStatus.IDLE
                vehicle.save(update_fields=["assigned_driver", "status"])

            return trip

    def update(self, instance, validated_data):
        old_driver = instance.driver
        old_vehicle = instance.vehicle

        driver = validated_data.get("driver", old_driver)
        vehicle = validated_data.get("vehicle", old_vehicle)

        if (driver and not old_driver) or (vehicle and not old_vehicle):
            validated_data["status"] = TripStatus.ASSIGNED

        from django.db import transaction
        with transaction.atomic():
            trip = super().update(instance, validated_data)

            if driver and driver != old_driver:
                driver.status = DriverStatus.ASSIGNED
                driver.save(update_fields=["status"])
                if old_driver and not Trip.objects.filter(driver=old_driver, status__in=[TripStatus.ASSIGNED, TripStatus.EN_ROUTE_PICKUP, TripStatus.ACTIVE]).exclude(pk=trip.pk).exists():
                    old_driver.status = DriverStatus.AVAILABLE
                    old_driver.save(update_fields=["status"])

            if vehicle and vehicle != old_vehicle:
                if driver:
                    vehicle.assigned_driver = driver
                vehicle.status = VehicleStatus.IDLE
                vehicle.save(update_fields=["assigned_driver", "status"])
                if old_vehicle and not Trip.objects.filter(vehicle=old_vehicle, status__in=[TripStatus.ASSIGNED, TripStatus.EN_ROUTE_PICKUP, TripStatus.ACTIVE]).exclude(pk=trip.pk).exists():
                    old_vehicle.status = VehicleStatus.IDLE
                    old_vehicle.save(update_fields=["status"])

            return trip

    def get_checklist(self, obj):
        checklist = getattr(obj, "checklist", None)
        if not checklist:
            return None
        return TripChecklistSerializer(checklist, context=self.context).data

    def get_otp_verified(self, obj):
        otp_session = getattr(obj, "otp_session", None)
        return bool(otp_session and otp_session.is_verified)

    def get_otp_mode(self, obj):
        return obj.otp_mode


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
    latitude = serializers.FloatField(required=True)
    longitude = serializers.FloatField(required=True)
    idempotency_key = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=120)
    speed_kmh = serializers.FloatField(required=False, allow_null=True, default=0.0)
    heading = serializers.FloatField(required=False, allow_null=True, default=0.0)

    def validate_latitude(self, value):
        return round(float(value), 6) if value is not None else value

    def validate_longitude(self, value):
        return round(float(value), 6) if value is not None else value

    def validate_speed_kmh(self, value):
        return round(float(value), 2) if value is not None else 0.0

    def validate_heading(self, value):
        return round(float(value), 2) if value is not None else 0.0

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
    code = serializers.CharField(min_length=4, max_length=6, required=False)
    otp_code = serializers.CharField(min_length=4, max_length=6, required=False)
    idempotency_key = serializers.CharField(required=False, allow_blank=False, max_length=120)

    def validate(self, attrs):
        code = attrs.get("otp_code") or attrs.get("code")
        if not code:
            raise serializers.ValidationError({"otp_code": "OTP code is required."})
        attrs["code"] = code
        return attrs


class AvailabilitySerializer(serializers.Serializer):
    vehicle_id = serializers.IntegerField()
    registration_number = serializers.CharField()
    category = serializers.CharField()
    available_from = serializers.DateTimeField()
    available_city = serializers.CharField()
    driver_name = serializers.CharField(allow_null=True)
    compliance_blockers = serializers.ListField(child=serializers.CharField())


class FuelTransactionImageSerializer(serializers.ModelSerializer):
    asset_id = serializers.PrimaryKeyRelatedField(source="asset", read_only=True)
    file_url = serializers.ReadOnlyField(source="asset.file_url")
    original_name = serializers.ReadOnlyField(source="asset.original_name")

    class Meta:
        model = FuelTransactionImage
        fields = ["id", "asset_id", "file_url", "original_name"]


class FuelTransactionSerializer(serializers.ModelSerializer):
    images = FuelTransactionImageSerializer(many=True, read_only=True)
    image_asset_ids = serializers.PrimaryKeyRelatedField(
        queryset=UploadedAsset.objects.all(),
        many=True,
        write_only=True,
        required=False,
    )

    class Meta:
        model = FuelTransaction
        fields = [
            "id",
            "vehicle",
            "driver",
            "trip",
            "latitude",
            "longitude",
            "review_notes",
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
            "images",
            "image_asset_ids",
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
            # For mobile submissions, receipt photo or generic images are required
            pass

        return attrs

    def create(self, validated_data):
        image_asset_ids = validated_data.pop("image_asset_ids", [])
        tx = super().create(validated_data)
        for asset in image_asset_ids:
            FuelTransactionImage.objects.create(transaction=tx, asset=asset)
        return tx

    def update(self, instance, validated_data):
        image_asset_ids = validated_data.pop("image_asset_ids", None)
        tx = super().update(instance, validated_data)
        if image_asset_ids is not None:
            instance.images.all().delete()
            for asset in image_asset_ids:
                FuelTransactionImage.objects.create(transaction=tx, asset=asset)
        return tx


class FuelTransactionDetailSerializer(FuelTransactionSerializer):
    vehicle_details = VehicleSerializer(source="vehicle", read_only=True)
    driver_details = DriverSerializer(source="driver", read_only=True)
    trip_details = TripSerializer(source="trip", read_only=True)
    receipt_asset_details = UploadedAssetSerializer(source="receipt_asset", read_only=True)
    odometer_asset_details = UploadedAssetSerializer(source="odometer_asset", read_only=True)

    class Meta(FuelTransactionSerializer.Meta):
        fields = FuelTransactionSerializer.Meta.fields + [
            "vehicle_details",
            "driver_details",
            "trip_details",
            "receipt_asset_details",
            "odometer_asset_details",
        ]


class RatePackageSerializer(serializers.ModelSerializer):
    class Meta:
        model = RatePackage
        fields = "__all__"


class RateBookSerializer(serializers.ModelSerializer):
    packages = RatePackageSerializer(many=True, read_only=True)

    class Meta:
        model = RateBook
        fields = "__all__"
