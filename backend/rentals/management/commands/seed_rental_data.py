from datetime import timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone

from fleet.models import Driver, DriverStatus, Vehicle, VehicleStatus
from rentals.models import (
    CorporateCustomer,
    PackageType,
    RentalBooking,
    RentalPackage,
    RentalPricingRule,
    RentalStatus,
)


class Command(BaseCommand):
    help = "Seed demo rental packages, corporate customers, pricing rules, and bookings."

    def handle(self, *args, **options):
        now = timezone.now()

        # 1. Packages
        p_4h40k, _ = RentalPackage.objects.update_or_create(
            name="4 Hours / 40 KM",
            defaults={
                "package_type": PackageType.LOCAL,
                "included_hours": Decimal("4.0"),
                "included_km": Decimal("40.0"),
                "default_base_price": Decimal("1200.00"),
                "extra_hour_rate": Decimal("150.00"),
                "extra_km_rate": Decimal("15.00"),
                "driver_allowance_per_day": Decimal("300.00"),
            },
        )

        p_8h80k, _ = RentalPackage.objects.update_or_create(
            name="8 Hours / 80 KM",
            defaults={
                "package_type": PackageType.LOCAL,
                "included_hours": Decimal("8.0"),
                "included_km": Decimal("80.0"),
                "default_base_price": Decimal("2200.00"),
                "extra_hour_rate": Decimal("150.00"),
                "extra_km_rate": Decimal("15.00"),
                "driver_allowance_per_day": Decimal("300.00"),
            },
        )

        p_12h120k, _ = RentalPackage.objects.update_or_create(
            name="12 Hours / 120 KM",
            defaults={
                "package_type": PackageType.LOCAL,
                "included_hours": Decimal("12.0"),
                "included_km": Decimal("120.0"),
                "default_base_price": Decimal("3200.00"),
                "extra_hour_rate": Decimal("150.00"),
                "extra_km_rate": Decimal("15.00"),
                "driver_allowance_per_day": Decimal("300.00"),
            },
        )

        p_airport, _ = RentalPackage.objects.update_or_create(
            name="Airport Transfer",
            defaults={
                "package_type": PackageType.AIRPORT,
                "included_hours": Decimal("2.0"),
                "included_km": Decimal("30.0"),
                "default_base_price": Decimal("800.00"),
                "extra_hour_rate": Decimal("150.00"),
                "extra_km_rate": Decimal("15.00"),
                "driver_allowance_per_day": Decimal("0.00"),
            },
        )

        p_out250, _ = RentalPackage.objects.update_or_create(
            name="Outstation 250 KM",
            defaults={
                "package_type": PackageType.OUTSTATION,
                "included_hours": Decimal("24.0"),
                "included_km": Decimal("250.0"),
                "default_base_price": Decimal("4500.00"),
                "extra_hour_rate": Decimal("0.00"),
                "extra_km_rate": Decimal("16.00"),
                "driver_allowance_per_day": Decimal("400.00"),
                "night_stay_charge": Decimal("600.00"),
            },
        )

        p_out300, _ = RentalPackage.objects.update_or_create(
            name="Outstation 300 KM",
            defaults={
                "package_type": PackageType.OUTSTATION,
                "included_hours": Decimal("24.0"),
                "included_km": Decimal("300.0"),
                "default_base_price": Decimal("5400.00"),
                "extra_hour_rate": Decimal("0.00"),
                "extra_km_rate": Decimal("16.00"),
                "driver_allowance_per_day": Decimal("400.00"),
                "night_stay_charge": Decimal("600.00"),
            },
        )

        # 2. Corporate Customers
        google, _ = CorporateCustomer.objects.update_or_create(
            name="Google India Pvt Ltd",
            defaults={
                "gst_number": "24AAACG1234H1Z0",
                "pan_number": "AAACG1234H",
                "billing_address": "S.G. Highway, Bodakdev, Ahmedabad, Gujarat 380054",
                "email": "corporate-travel@google.com",
                "contact_person": "Ananya Sharma",
                "phone": "+91 98765 43210",
            },
        )

        tcs, _ = CorporateCustomer.objects.update_or_create(
            name="TCS Corporate Services",
            defaults={
                "gst_number": "27AAACT5678J1Z2",
                "pan_number": "AAACT5678J",
                "billing_address": "Bandra Kurla Complex, Mumbai, Maharashtra 400051",
                "email": "fleet.admin@tcs.com",
                "contact_person": "Rahul Verma",
                "phone": "+91 98200 11223",
            },
        )

        # 3. Pricing Rules
        # Google in Ahmedabad 4h/40k = 1200
        RentalPricingRule.objects.update_or_create(
            company=google,
            city="Ahmedabad",
            package=p_4h40k,
            defaults={
                "base_price": Decimal("1200.00"),
                "extra_hour_rate": Decimal("140.00"),
                "extra_km_rate": Decimal("14.00"),
                "driver_allowance": Decimal("250.00"),
            },
        )

        # Google in Delhi 4h/40k = 1500
        RentalPricingRule.objects.update_or_create(
            company=google,
            city="Delhi",
            package=p_4h40k,
            defaults={
                "base_price": Decimal("1500.00"),
                "extra_hour_rate": Decimal("160.00"),
                "extra_km_rate": Decimal("15.00"),
                "driver_allowance": Decimal("300.00"),
            },
        )

        # City specific Airport Transfers
        # Ahmedabad Airport = 700
        RentalPricingRule.objects.update_or_create(
            company=None,
            city="Ahmedabad",
            package=p_airport,
            defaults={
                "base_price": Decimal("700.00"),
                "extra_hour_rate": Decimal("150.00"),
                "extra_km_rate": Decimal("15.00"),
                "driver_allowance": Decimal("0.00"),
            },
        )

        # Delhi Airport = 900
        RentalPricingRule.objects.update_or_create(
            company=None,
            city="Delhi",
            package=p_airport,
            defaults={
                "base_price": Decimal("900.00"),
                "extra_hour_rate": Decimal("150.00"),
                "extra_km_rate": Decimal("15.00"),
                "driver_allowance": Decimal("0.00"),
            },
        )

        # Mumbai Airport = 1200
        RentalPricingRule.objects.update_or_create(
            company=None,
            city="Mumbai",
            package=p_airport,
            defaults={
                "base_price": Decimal("1200.00"),
                "extra_hour_rate": Decimal("180.00"),
                "extra_km_rate": Decimal("18.00"),
                "driver_allowance": Decimal("0.00"),
            },
        )

        # 4. Fetch drivers and vehicles for bookings
        drivers = list(Driver.objects.all())
        vehicles = list(Vehicle.objects.all())

        d_amit = drivers[0] if len(drivers) > 0 else None
        d_suresh = drivers[1] if len(drivers) > 1 else None
        v_etios = vehicles[0] if len(vehicles) > 0 else None
        v_ertiga = vehicles[1] if len(vehicles) > 1 else None

        # Sample active corporate rental
        b1, _ = RentalBooking.objects.update_or_create(
            booking_number="RNT-2026-0001",
            defaults={
                "customer_type": "corporate",
                "customer_name": "Ananya Sharma (Google)",
                "customer_phone": "+91 98765 43210",
                "customer_email": "ananya@google.com",
                "corporate_customer": google,
                "pickup_address": "Google Office, Bodakdev",
                "drop_address": "Ahmedabad Airport T2",
                "pickup_city": "Ahmedabad",
                "pickup_at": now - timedelta(hours=2),
                "expected_return_at": now + timedelta(hours=2),
                "package": p_4h40k,
                "vehicle_category": "Sedan",
                "vehicle": v_etios,
                "driver": d_amit,
                "status": RentalStatus.STARTED,
                "start_time": now - timedelta(hours=2),
                "start_odometer": 52000,
                "notes": "VIP Corporate Guest. Clean vehicle required.",
            },
        )

        # Sample upcoming individual rental
        b2, _ = RentalBooking.objects.update_or_create(
            booking_number="RNT-2026-0002",
            defaults={
                "customer_type": "individual",
                "customer_name": "Vikram Sethi",
                "customer_phone": "+91 99887 76655",
                "customer_email": "vikram.sethi@gmail.com",
                "pickup_address": "Connaught Place, Block B",
                "drop_address": "IGI Airport Terminal 3",
                "pickup_city": "Delhi",
                "pickup_at": now + timedelta(hours=4),
                "expected_return_at": now + timedelta(hours=6),
                "package": p_airport,
                "vehicle_category": "Sedan",
                "status": RentalStatus.PENDING,
                "notes": "Flight departure at 8:30 PM.",
            },
        )

        # Sample upcoming outstation rental
        b3, _ = RentalBooking.objects.update_or_create(
            booking_number="RNT-2026-0003",
            defaults={
                "customer_type": "corporate",
                "customer_name": "Rahul Verma (TCS)",
                "customer_phone": "+91 98200 11223",
                "customer_email": "r.verma@tcs.com",
                "corporate_customer": tcs,
                "pickup_address": "TCS House, BKC, Mumbai",
                "drop_address": "Pune Tech Park, Hinjewadi",
                "pickup_city": "Mumbai",
                "pickup_at": now + timedelta(days=1),
                "expected_return_at": now + timedelta(days=2),
                "package": p_out250,
                "vehicle_category": "SUV",
                "vehicle": v_ertiga,
                "driver": d_suresh,
                "status": RentalStatus.READY,
                "notes": "Overnight corporate outstation trip.",
            },
        )

        self.stdout.write(self.style.SUCCESS("Rental Module demo data successfully seeded!"))
