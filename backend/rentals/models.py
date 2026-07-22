import math
from datetime import timedelta
from decimal import Decimal
from django.db import models
from django.utils import timezone
from fleet.models import Driver, Vehicle


class RentalStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    VEHICLE_ASSIGNED = "vehicle_assigned", "Vehicle Assigned"
    DRIVER_ASSIGNED = "driver_assigned", "Driver Assigned"
    READY = "ready", "Ready"
    STARTED = "started", "Started"
    IN_PROGRESS = "in_progress", "In Progress"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class PackageType(models.TextChoices):
    LOCAL = "local", "Local Package"
    AIRPORT = "airport", "Airport Transfer"
    OUTSTATION = "outstation", "Outstation"


class CorporateCustomer(models.Model):
    name = models.CharField(max_length=120)
    gst_number = models.CharField(max_length=30, blank=True)
    pan_number = models.CharField(max_length=30, blank=True)
    billing_address = models.TextField()
    email = models.EmailField()
    contact_person = models.CharField(max_length=120)
    phone = models.CharField(max_length=24)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class RentalPackage(models.Model):
    name = models.CharField(max_length=80)
    package_type = models.CharField(max_length=30, choices=PackageType.choices, default=PackageType.LOCAL)
    included_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    included_km = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    default_base_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    extra_hour_rate = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    extra_km_rate = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    driver_allowance_per_day = models.DecimalField(max_digits=8, decimal_places=2, default=300.00)
    night_stay_charge = models.DecimalField(max_digits=8, decimal_places=2, default=500.00)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.package_type})"


class RentalPricingRule(models.Model):
    company = models.ForeignKey(CorporateCustomer, null=True, blank=True, on_delete=models.CASCADE, related_name="pricing_rules")
    city = models.CharField(max_length=120, blank=True, default="")
    package = models.ForeignKey(RentalPackage, on_delete=models.CASCADE, related_name="pricing_rules")
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    extra_hour_rate = models.DecimalField(max_digits=8, decimal_places=2)
    extra_km_rate = models.DecimalField(max_digits=8, decimal_places=2)
    driver_allowance = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["company", "city", "package"]

    def __str__(self):
        comp = self.company.name if self.company else "Default"
        city_str = self.city if self.city else "All Cities"
        return f"{comp} | {city_str} | {self.package.name} -> ₹{self.base_price}"


class RentalBooking(models.Model):
    booking_number = models.CharField(max_length=32, unique=True)
    customer_type = models.CharField(max_length=20, default="individual")  # "individual" or "corporate"
    customer_name = models.CharField(max_length=120)
    customer_phone = models.CharField(max_length=24)
    customer_email = models.EmailField(max_length=120, blank=True)
    corporate_customer = models.ForeignKey(CorporateCustomer, null=True, blank=True, on_delete=models.SET_NULL, related_name="bookings")
    pickup_address = models.TextField()
    drop_address = models.TextField(blank=True)
    pickup_city = models.CharField(max_length=120)
    pickup_at = models.DateTimeField()
    expected_return_at = models.DateTimeField()
    package = models.ForeignKey(RentalPackage, on_delete=models.PROTECT, related_name="bookings")
    vehicle_category = models.CharField(max_length=40, default="Sedan")
    vehicle = models.ForeignKey(Vehicle, null=True, blank=True, on_delete=models.SET_NULL, related_name="rental_bookings")
    driver = models.ForeignKey(Driver, null=True, blank=True, on_delete=models.SET_NULL, related_name="rental_bookings")
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=30, choices=RentalStatus.choices, default=RentalStatus.PENDING)
    
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    start_odometer = models.PositiveIntegerField(null=True, blank=True)
    end_odometer = models.PositiveIntegerField(null=True, blank=True)
    distance_travelled = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    actual_hours_used = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-pickup_at"]

    def __str__(self):
        return f"{self.booking_number} - {self.customer_name} ({self.status})"

    def resolve_pricing(self):
        """Find best matching pricing rule for company, city, and package."""
        # 1. Company + City match
        if self.corporate_customer and self.pickup_city:
            rule = RentalPricingRule.objects.filter(
                company=self.corporate_customer,
                city__iexact=self.pickup_city,
                package=self.package
            ).first()
            if rule:
                return rule.base_price, rule.extra_km_rate, rule.extra_hour_rate, rule.driver_allowance

        # 2. Company default match (any city)
        if self.corporate_customer:
            rule = RentalPricingRule.objects.filter(
                company=self.corporate_customer,
                city="",
                package=self.package
            ).first()
            if rule:
                return rule.base_price, rule.extra_km_rate, rule.extra_hour_rate, rule.driver_allowance

        # 3. City match for individual/default
        if self.pickup_city:
            rule = RentalPricingRule.objects.filter(
                company__isnull=True,
                city__iexact=self.pickup_city,
                package=self.package
            ).first()
            if rule:
                return rule.base_price, rule.extra_km_rate, rule.extra_hour_rate, rule.driver_allowance

        # 4. Fallback to package defaults
        return (
            self.package.default_base_price,
            self.package.extra_km_rate,
            self.package.extra_hour_rate,
            self.package.driver_allowance_per_day
        )


class RentalChecklist(models.Model):
    CHECKLIST_TYPE = (("start", "Pre-Rental Start"), ("end", "Post-Rental End"))
    booking = models.ForeignKey(RentalBooking, related_name="checklists", on_delete=models.CASCADE)
    checklist_type = models.CharField(max_length=10, choices=CHECKLIST_TYPE)
    front_photo = models.TextField(blank=True)
    rear_photo = models.TextField(blank=True)
    left_photo = models.TextField(blank=True)
    right_photo = models.TextField(blank=True)
    dashboard_photo = models.TextField(blank=True)
    odometer_photo = models.TextField(blank=True)
    fuel_gauge_photo = models.TextField(blank=True)
    odometer_reading = models.PositiveIntegerField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.booking.booking_number} - {self.checklist_type.upper()} Checklist"


class RentalFuelLog(models.Model):
    booking = models.ForeignKey(RentalBooking, null=True, blank=True, related_name="fuel_logs", on_delete=models.SET_NULL)
    vehicle = models.ForeignKey(Vehicle, related_name="fuel_logs", on_delete=models.CASCADE)
    driver = models.ForeignKey(Driver, related_name="fuel_logs", on_delete=models.CASCADE)
    fuel_quantity_liters = models.DecimalField(max_digits=6, decimal_places=2)
    fuel_cost = models.DecimalField(max_digits=10, decimal_places=2)
    odometer_reading = models.PositiveIntegerField()
    fuel_station = models.CharField(max_length=120, blank=True)
    logged_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.vehicle.registration_number} - {self.fuel_quantity_liters}L (₹{self.fuel_cost})"


class RentalInvoice(models.Model):
    invoice_number = models.CharField(max_length=32, unique=True)
    booking = models.OneToOneField(RentalBooking, related_name="invoice", on_delete=models.CASCADE)
    distance_travelled = models.DecimalField(max_digits=10, decimal_places=2)
    hours_used = models.DecimalField(max_digits=8, decimal_places=2)
    included_km = models.DecimalField(max_digits=10, decimal_places=2)
    included_hours = models.DecimalField(max_digits=8, decimal_places=2)
    extra_km = models.DecimalField(max_digits=10, decimal_places=2)
    extra_hours = models.DecimalField(max_digits=8, decimal_places=2)
    package_price = models.DecimalField(max_digits=10, decimal_places=2)
    extra_km_charges = models.DecimalField(max_digits=10, decimal_places=2)
    extra_hour_charges = models.DecimalField(max_digits=10, decimal_places=2)
    driver_allowance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    tax_rate_percent = models.DecimalField(max_digits=5, decimal_places=2, default=5.00)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2)
    final_total = models.DecimalField(max_digits=10, decimal_places=2)
    issued_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.invoice_number} - ₹{self.final_total}"
