from decimal import Decimal
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class DriverStatus(models.TextChoices):
    AVAILABLE = "available", "Available"
    ASSIGNED = "assigned", "Assigned"
    ON_TRIP = "on_trip", "On trip"
    OFF_DUTY = "off_duty", "Off duty"
    SUSPENDED = "suspended", "Suspended"


class VehicleStatus(models.TextChoices):
    IDLE = "idle", "Idle"
    EN_ROUTE_PICKUP = "en_route_pickup", "En route to pickup"
    ACTIVE_TRIP = "active_trip", "Active trip"
    MAINTENANCE = "maintenance", "Maintenance"
    OFFLINE = "offline", "Offline"


class TripStatus(models.TextChoices):
    REQUESTED = "requested", "Requested"
    ASSIGNED = "assigned", "Assigned"
    EN_ROUTE_PICKUP = "en_route_pickup", "En route to pickup"
    ACTIVE = "active", "Active"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class CustomerStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    INACTIVE = "INACTIVE", "Inactive"
    SUSPENDED = "SUSPENDED", "Suspended"


class ContactType(models.TextChoices):
    PRIMARY = "PRIMARY", "Primary"
    BILLING = "BILLING", "Billing"
    DISPATCH = "DISPATCH", "Dispatch"
    COMMERCIAL = "COMMERCIAL", "Commercial"
    EMERGENCY = "EMERGENCY", "Emergency"
    OTHER = "OTHER", "Other"


class ContractStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    ACTIVE = "ACTIVE", "Active"
    EXPIRED = "EXPIRED", "Expired"
    TERMINATED = "TERMINATED", "Terminated"
    ARCHIVED = "ARCHIVED", "Archived"


class DutyType(models.TextChoices):
    LOCAL_8HR_80KM = "LOCAL_8HR_80KM", "Local (8h / 80km)"
    LOCAL_12HR_120KM = "LOCAL_12HR_120KM", "Local (12h / 120km)"
    OUTSTATION = "OUTSTATION", "Outstation"
    AIRPORT_TRANSFER = "AIRPORT_TRANSFER", "Airport Transfer"
    ONE_WAY = "ONE_WAY", "One-Way"
    FULL_DAY = "FULL_DAY", "Full Day"
    CUSTOM = "CUSTOM", "Custom Package"


class AllowanceType(models.TextChoices):
    OVERTIME_PER_HOUR = "OVERTIME_PER_HOUR", "Overtime per hour"
    OUTSTATION_PER_DAY = "OUTSTATION_PER_DAY", "Outstation per day"
    OVERNIGHT_DRIVER_ALLOWANCE = "OVERNIGHT_DRIVER_ALLOWANCE", "Overnight driver allowance"
    SUNDAY_ALLOWANCE = "SUNDAY_ALLOWANCE", "Sunday allowance"
    EARLY_START_ALLOWANCE = "EARLY_START_ALLOWANCE", "Early start allowance"
    NIGHT_ALLOWANCE = "NIGHT_ALLOWANCE", "Night allowance"
    EXTRA_DUTY_ALLOWANCE = "EXTRA_DUTY_ALLOWANCE", "Extra duty allowance"


class MeteringPolicy(models.TextChoices):
    GARAGE_TO_GARAGE = "GARAGE_TO_GARAGE", "Garage to Garage"
    PICKUP_TO_DROP = "PICKUP_TO_DROP", "Pickup to Drop"
    FIXED_PACKAGE = "FIXED_PACKAGE", "Fixed Package"
    OUTSTATION_DAILY_MINIMUM = "OUTSTATION_DAILY_MINIMUM", "Outstation Daily Minimum"
    AIRPORT_TRANSFER = "AIRPORT_TRANSFER", "Airport Transfer"


class Driver(models.Model):
    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=24)
    license_number = models.CharField(max_length=64, unique=True)
    home_base = models.CharField(max_length=120)
    status = models.CharField(max_length=24, choices=DriverStatus.choices, default=DriverStatus.AVAILABLE)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=4.5)
    created_at = models.DateTimeField(auto_now_add=True)

    # Documents
    aadhaar_card = models.ForeignKey(
        "media_store.UploadedAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="driver_aadhaar_cards",
    )
    driving_license = models.ForeignKey(
        "media_store.UploadedAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="driver_driving_licenses",
    )
    driving_license_expiry_date = models.DateField(null=True, blank=True)
    police_clearance_certificate = models.ForeignKey(
        "media_store.UploadedAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="driver_pccs",
    )

    def __str__(self):
        return self.name


class Vehicle(models.Model):
    registration_number = models.CharField(max_length=24, unique=True)
    make = models.CharField(max_length=80)
    model = models.CharField(max_length=80)
    category = models.CharField(max_length=40, default="Sedan")
    current_city = models.CharField(max_length=120)
    status = models.CharField(max_length=24, choices=VehicleStatus.choices, default=VehicleStatus.IDLE)
    assigned_driver = models.ForeignKey(
        Driver,
        related_name="vehicles",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    permit_expires_on = models.DateField()
    insurance_expires_on = models.DateField()
    pollution_expires_on = models.DateField()
    fitness_expires_on = models.DateField()
    odometer_km = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.registration_number

    @property
    def compliance_blockers(self):
        today = timezone.localdate()
        blockers = []
        checks = {
            "permit": self.permit_expires_on,
            "insurance": self.insurance_expires_on,
            "pollution": self.pollution_expires_on,
            "fitness": self.fitness_expires_on,
        }
        for label, expiry in checks.items():
            if expiry < today:
                blockers.append(f"{label} expired")
            elif expiry <= today + timedelta(days=15):
                blockers.append(f"{label} expires soon")
        return blockers

    @property
    def is_compliant(self):
        return not any("expired" in blocker for blocker in self.compliance_blockers)


class CorporateCustomer(models.Model):
    code = models.CharField(max_length=40, unique=True)
    legal_name = models.CharField(max_length=150)
    display_name = models.CharField(max_length=150)
    status = models.CharField(max_length=24, choices=CustomerStatus.choices, default=CustomerStatus.ACTIVE)
    is_active = models.BooleanField(default=True)
    gstin = models.CharField(max_length=20, blank=True)
    billing_address = models.TextField(blank=True)
    billing_email = models.EmailField(blank=True)
    billing_phone = models.CharField(max_length=24, blank=True)
    booking_contact_name = models.CharField(max_length=120, blank=True)
    booking_contact_email = models.EmailField(blank=True)
    booking_contact_phone = models.CharField(max_length=24, blank=True)
    payment_terms_days = models.PositiveIntegerField(default=30)
    po_required = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_name"]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["status"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.display_name} ({self.code})"

    def clean(self):
        super().clean()
        if self.code:
            self.code = self.code.strip().upper()


class CustomerContact(models.Model):
    customer = models.ForeignKey(CorporateCustomer, related_name="contacts", on_delete=models.CASCADE)
    name = models.CharField(max_length=120)
    contact_type = models.CharField(max_length=24, choices=ContactType.choices, default=ContactType.PRIMARY)
    phone = models.CharField(max_length=24, blank=True)
    email = models.EmailField(blank=True)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_primary", "name"]

    def __str__(self):
        return f"{self.name} - {self.customer.display_name} ({self.contact_type})"


class CorporateContract(models.Model):
    customer = models.ForeignKey(CorporateCustomer, related_name="contracts", on_delete=models.CASCADE)
    title = models.CharField(max_length=120)
    version_name = models.CharField(max_length=40, default="v1.0")
    effective_start = models.DateField()
    effective_end = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=24, choices=ContractStatus.choices, default=ContractStatus.DRAFT)
    currency = models.CharField(max_length=10, default="INR")
    cgst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("2.50"))
    sgst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("2.50"))
    payment_terms_days = models.PositiveIntegerField(null=True, blank=True)
    cancellation_terms = models.TextField(blank=True)
    metering_policy = models.CharField(
        max_length=32,
        choices=MeteringPolicy.choices,
        default=MeteringPolicy.GARAGE_TO_GARAGE,
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-effective_start"]
        indexes = [
            models.Index(fields=["customer", "status", "effective_start", "effective_end"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.version_name}) - {self.customer.display_name}"

    def clean(self):
        super().clean()
        if self.effective_end and self.effective_start and self.effective_end < self.effective_start:
            raise ValidationError({"effective_end": "Effective end date cannot precede effective start date."})
        if self.cgst_rate < Decimal("0.00") or self.cgst_rate > Decimal("100.00"):
            raise ValidationError({"cgst_rate": "CGST rate must be between 0 and 100."})
        if self.sgst_rate < Decimal("0.00") or self.sgst_rate > Decimal("100.00"):
            raise ValidationError({"sgst_rate": "SGST rate must be between 0 and 100."})


class ContractRate(models.Model):
    contract = models.ForeignKey(CorporateContract, related_name="rates", on_delete=models.CASCADE)
    city = models.CharField(max_length=120)
    vehicle_category = models.CharField(max_length=80)
    duty_type = models.CharField(max_length=40, choices=DutyType.choices)
    included_hours = models.PositiveIntegerField(default=0)
    included_km = models.PositiveIntegerField(default=0)
    base_rate = models.DecimalField(max_digits=10, decimal_places=2)
    extra_hour_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    extra_km_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    switch_threshold_hours = models.PositiveIntegerField(null=True, blank=True)
    switch_threshold_km = models.PositiveIntegerField(null=True, blank=True)
    outstation_daily_min_km = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["city", "vehicle_category", "duty_type"]
        constraints = [
            models.UniqueConstraint(
                fields=["contract", "city", "vehicle_category", "duty_type"],
                name="unique_contract_rate_key",
            )
        ]
        indexes = [
            models.Index(fields=["contract", "city", "vehicle_category", "duty_type"]),
        ]

    def __str__(self):
        return f"{self.city} - {self.vehicle_category} ({self.duty_type}): {self.base_rate}"

    def clean(self):
        super().clean()
        if self.city:
            self.city = self.city.strip().lower()
        if self.vehicle_category:
            self.vehicle_category = self.vehicle_category.strip().lower()
        if self.base_rate < Decimal("0.00"):
            raise ValidationError({"base_rate": "Base rate cannot be negative."})
        if self.extra_hour_rate < Decimal("0.00"):
            raise ValidationError({"extra_hour_rate": "Extra hour rate cannot be negative."})
        if self.extra_km_rate < Decimal("0.00"):
            raise ValidationError({"extra_km_rate": "Extra km rate cannot be negative."})


class ContractAllowance(models.Model):
    contract = models.ForeignKey(CorporateContract, related_name="allowances", on_delete=models.CASCADE)
    allowance_type = models.CharField(max_length=40, choices=AllowanceType.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["allowance_type"]
        constraints = [
            models.UniqueConstraint(
                fields=["contract", "allowance_type"],
                name="unique_contract_allowance_key",
            )
        ]

    def __str__(self):
        return f"{self.contract.title} - {self.allowance_type}: {self.amount}"

    def clean(self):
        super().clean()
        if self.amount < Decimal("0.00"):
            raise ValidationError({"amount": "Allowance amount cannot be negative."})


class BookingType(models.TextChoices):
    CORPORATE = "CORPORATE", "Corporate"
    ADHOC = "ADHOC", "Ad-hoc / Direct"
    OTA = "OTA", "OTA / Aggregator"


class Trip(models.Model):
    booking_type = models.CharField(
        max_length=24,
        choices=BookingType.choices,
        default=BookingType.ADHOC,
    )
    customer = models.ForeignKey(
        CorporateCustomer,
        related_name="trips",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    contract = models.ForeignKey(
        CorporateContract,
        related_name="trips",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    contract_rate = models.ForeignKey(
        ContractRate,
        related_name="trips",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    duty_type = models.CharField(max_length=40, blank=True)
    vehicle_category_requested = models.CharField(max_length=80, blank=True)
    customer_name = models.CharField(max_length=120, blank=True)
    customer_display_name_snapshot = models.CharField(max_length=150, blank=True)
    pricing_snapshot = models.JSONField(default=dict, blank=True)

    pickup_city = models.CharField(max_length=120)
    drop_city = models.CharField(max_length=120)
    pickup_at = models.DateTimeField()
    estimated_drop_at = models.DateTimeField()
    status = models.CharField(max_length=24, choices=TripStatus.choices, default=TripStatus.REQUESTED)
    vehicle = models.ForeignKey(Vehicle, related_name="trips", null=True, blank=True, on_delete=models.SET_NULL)
    driver = models.ForeignKey(Driver, related_name="trips", null=True, blank=True, on_delete=models.SET_NULL)
    ota_source = models.CharField(max_length=80, blank=True)
    fare_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    pickup_latitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    pickup_longitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    drop_latitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    drop_longitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    distance_km = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["pickup_at"]

    def __str__(self):
        name = self.customer_display_name_snapshot or self.customer_name or "Trip"
        return f"{name}: {self.pickup_city} to {self.drop_city} at {self.pickup_at:%Y-%m-%d %H:%M}"
