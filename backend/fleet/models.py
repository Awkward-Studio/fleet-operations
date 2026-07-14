from datetime import timedelta

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


class Driver(models.Model):
    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=24)
    license_number = models.CharField(max_length=64, unique=True)
    home_base = models.CharField(max_length=120)
    status = models.CharField(max_length=24, choices=DriverStatus.choices, default=DriverStatus.AVAILABLE)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=4.5)
    created_at = models.DateTimeField(auto_now_add=True)

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


class Trip(models.Model):
    customer_name = models.CharField(max_length=120)
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
    pickup_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    pickup_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    drop_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    drop_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    distance_km = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["pickup_at"]

    def __str__(self):
        return f"{self.pickup_city} to {self.drop_city} at {self.pickup_at:%Y-%m-%d %H:%M}"

