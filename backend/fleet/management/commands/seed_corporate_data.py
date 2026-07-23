import datetime
from decimal import Decimal
from django.core.management.base import BaseCommand
from fleet.models import (
    CorporateCustomer,
    CustomerContact,
    CorporateContract,
    ContractRate,
    ContractAllowance,
    CustomerStatus,
    ContactType,
    ContractStatus,
    DutyType,
    AllowanceType,
    MeteringPolicy,
)


class Command(BaseCommand):
    help = "Seeds demo corporate customers, contacts, rate cards, and allowances for testing."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding corporate customer and pricing data..."))

        # Customer 1: Acme Corp
        acme, created = CorporateCustomer.objects.get_or_create(
            code="ACME_IND_01",
            defaults={
                "legal_name": "ACME Logistics & Mobility Pvt Ltd",
                "display_name": "ACME Corp",
                "status": CustomerStatus.ACTIVE,
                "is_active": True,
                "gstin": "27AAACA1234A1Z5",
                "billing_address": "Floor 12, Tower B, Bandra Kurla Complex, Mumbai, MH 400051",
                "billing_email": "billing@acme.com",
                "billing_phone": "+91 22 6789 0000",
                "booking_contact_name": "Rajesh Sharma",
                "booking_contact_email": "travel@acme.com",
                "booking_contact_phone": "+91 98200 12345",
                "payment_terms_days": 30,
                "po_required": True,
                "notes": "VIP corporate account with priority vehicle allocation.",
            },
        )

        CustomerContact.objects.get_or_create(
            customer=acme,
            email="rajesh.sharma@acme.com",
            defaults={
                "name": "Rajesh Sharma",
                "contact_type": ContactType.PRIMARY,
                "phone": "+91 98200 12345",
                "is_primary": True,
            },
        )

        acme_contract, _ = CorporateContract.objects.get_or_create(
            customer=acme,
            title="ACME Master Corporate Rate Card 2026",
            defaults={
                "version_name": "v1.0",
                "effective_start": datetime.date(2026, 1, 1),
                "status": ContractStatus.ACTIVE,
                "cgst_rate": Decimal("2.50"),
                "sgst_rate": Decimal("2.50"),
                "payment_terms_days": 30,
                "metering_policy": MeteringPolicy.GARAGE_TO_GARAGE,
                "notes": "Standard Mumbai & Pune corporate package.",
            },
        )

        ContractRate.objects.get_or_create(
            contract=acme_contract,
            city="mumbai",
            vehicle_category="sedan",
            duty_type=DutyType.LOCAL_8HR_80KM,
            defaults={
                "included_hours": 8,
                "included_km": 80,
                "base_rate": Decimal("2400.00"),
                "extra_hour_rate": Decimal("200.00"),
                "extra_km_rate": Decimal("18.00"),
            },
        )

        ContractRate.objects.get_or_create(
            contract=acme_contract,
            city="mumbai",
            vehicle_category="suv",
            duty_type=DutyType.LOCAL_8HR_80KM,
            defaults={
                "included_hours": 8,
                "included_km": 80,
                "base_rate": Decimal("3500.00"),
                "extra_hour_rate": Decimal("250.00"),
                "extra_km_rate": Decimal("22.00"),
            },
        )

        ContractAllowance.objects.get_or_create(
            contract=acme_contract,
            allowance_type=AllowanceType.OVERNIGHT_DRIVER_ALLOWANCE,
            defaults={
                "amount": Decimal("350.00"),
                "description": "Driver night halt charge",
            },
        )

        # Customer 2: Globex Enterprises
        globex, _ = CorporateCustomer.objects.get_or_create(
            code="GLOBEX_02",
            defaults={
                "legal_name": "Globex Global Technology Solutions Ltd",
                "display_name": "Globex Corp",
                "status": CustomerStatus.ACTIVE,
                "is_active": True,
                "gstin": "27AABCG9876F1Z8",
                "billing_address": "Tech Park 4, Hinjewadi Phase 2, Pune, MH 411057",
                "billing_email": "accounts@globex.com",
                "billing_phone": "+91 20 4567 8900",
                "booking_contact_name": "Priya Nair",
                "booking_contact_email": "priya.nair@globex.com",
                "booking_contact_phone": "+91 98900 67890",
                "payment_terms_days": 45,
                "po_required": False,
            },
        )

        globex_contract, _ = CorporateContract.objects.get_or_create(
            customer=globex,
            title="Globex Pune & Outstation Contract",
            defaults={
                "version_name": "v2.1",
                "effective_start": datetime.date(2026, 2, 1),
                "status": ContractStatus.ACTIVE,
                "cgst_rate": Decimal("2.50"),
                "sgst_rate": Decimal("2.50"),
                "payment_terms_days": 45,
                "metering_policy": MeteringPolicy.PICKUP_TO_DROP,
                "notes": "City to city metering contract.",
            },
        )

        ContractRate.objects.get_or_create(
            contract=globex_contract,
            city="pune",
            vehicle_category="sedan",
            duty_type=DutyType.OUTSTATION,
            defaults={
                "included_hours": 24,
                "included_km": 300,
                "base_rate": Decimal("4800.00"),
                "extra_hour_rate": Decimal("180.00"),
                "extra_km_rate": Decimal("16.00"),
                "outstation_daily_min_km": 300,
            },
        )

        self.stdout.write(self.style.SUCCESS("Corporate customer seed data created successfully."))
