from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from fleet.models import Driver, DriverStatus, Trip, Vehicle, VehicleStatus


class Command(BaseCommand):
    help = "Seed demo vehicles, drivers, and trips for local development."

    def handle(self, *args, **options):
        today = timezone.localdate()
        now = timezone.now()

        drivers = [
            ("Amit Rana", "+91 98765 10001", "DL-DRV-1001", "Delhi", DriverStatus.AVAILABLE),
            ("Suresh Thakur", "+91 98765 10002", "DL-DRV-1002", "Manali", DriverStatus.ASSIGNED),
            ("Imran Khan", "+91 98765 10003", "DL-DRV-1003", "Jaipur", DriverStatus.AVAILABLE),
        ]
        driver_map = {}
        for name, phone, license_number, home_base, status in drivers:
            driver, _ = Driver.objects.update_or_create(
                license_number=license_number,
                defaults={"name": name, "phone": phone, "home_base": home_base, "status": status},
            )
            driver_map[name] = driver

        vehicles = [
            ("DL01AB1234", "Toyota", "Etios", "Sedan", "Delhi", VehicleStatus.IDLE, "Amit Rana", 120),
            ("HR26CD4567", "Maruti Suzuki", "Ertiga", "MPV", "Manali", VehicleStatus.IDLE, "Suresh Thakur", 45),
            ("RJ14EF7890", "Toyota", "Innova Crysta", "SUV", "Jaipur", VehicleStatus.MAINTENANCE, None, 8),
        ]
        vehicle_map = {}
        for reg, make, model, category, city, status, driver_name, permit_days in vehicles:
            vehicle, _ = Vehicle.objects.update_or_create(
                registration_number=reg,
                defaults={
                    "make": make,
                    "model": model,
                    "category": category,
                    "current_city": city,
                    "status": status,
                    "assigned_driver": driver_map.get(driver_name),
                    "permit_expires_on": today + timedelta(days=permit_days),
                    "insurance_expires_on": today + timedelta(days=90),
                    "pollution_expires_on": today + timedelta(days=30),
                    "fitness_expires_on": today + timedelta(days=180),
                    "odometer_km": 52000,
                },
            )
            vehicle_map[reg] = vehicle

        Trip.objects.update_or_create(
            customer_name="MMT Return Candidate",
            pickup_at=now + timedelta(hours=18),
            defaults={
                "pickup_city": "Delhi",
                "drop_city": "Manali",
                "estimated_drop_at": now + timedelta(hours=30),
                "status": "assigned",
                "vehicle": vehicle_map["HR26CD4567"],
                "driver": driver_map["Suresh Thakur"],
                "ota_source": "MakeMyTrip",
                "fare_amount": 18500,
                "notes": "Used to demonstrate predictive availability after Manali drop.",
            },
        )
        Trip.objects.update_or_create(
            customer_name="Goibibo Open Request",
            pickup_at=now + timedelta(hours=5),
            defaults={
                "pickup_city": "Delhi",
                "drop_city": "Agra",
                "estimated_drop_at": now + timedelta(hours=11),
                "status": "requested",
                "ota_source": "Goibibo",
                "fare_amount": 9500,
            },
        )

        self.stdout.write(self.style.SUCCESS("Demo fleet data seeded."))

