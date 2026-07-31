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

        CustomerContact.objects.get_or_create(
            customer=globex,
            email="priya.nair@globex.com",
            defaults={
                "name": "Priya Nair",
                "contact_type": ContactType.PRIMARY,
                "phone": "+91 98900 67890",
                "is_primary": True,
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

        # Customer 3: Hooli Inc
        hooli, _ = CorporateCustomer.objects.get_or_create(
            code="HOOLI_BLR_03",
            defaults={
                "legal_name": "Hooli India R&D Center Pvt Ltd",
                "display_name": "Hooli Inc",
                "status": CustomerStatus.ACTIVE,
                "is_active": True,
                "gstin": "29AAACH0099C1Z9",
                "billing_address": "Block A, Embassy TechVillage, Outer Ring Road, Bangalore, KA 560103",
                "billing_email": "finance@hooli.co.in",
                "billing_phone": "+91 80 4444 8888",
                "booking_contact_name": "Dinesh Chugtai",
                "booking_contact_email": "dinesh@hooli.com",
                "booking_contact_phone": "+91 90000 11111",
                "payment_terms_days": 15,
                "po_required": True,
                "notes": "VIP Technology client. Strict invoicing compliance.",
            },
        )

        CustomerContact.objects.get_or_create(
            customer=hooli,
            email="dinesh@hooli.com",
            defaults={
                "name": "Dinesh Chugtai",
                "contact_type": ContactType.PRIMARY,
                "phone": "+91 90000 11111",
                "is_primary": True,
            },
        )

        CustomerContact.objects.get_or_create(
            customer=hooli,
            email="richard@hooli.com",
            defaults={
                "name": "Richard Hendricks",
                "contact_type": ContactType.COMMERCIAL,
                "phone": "+91 90000 22222",
                "is_primary": False,
            },
        )

        hooli_contract, _ = CorporateContract.objects.get_or_create(
            customer=hooli,
            title="Hooli KA Regional Agreement",
            defaults={
                "version_name": "v1.2",
                "effective_start": datetime.date(2026, 1, 15),
                "status": ContractStatus.ACTIVE,
                "cgst_rate": Decimal("2.50"),
                "sgst_rate": Decimal("2.50"),
                "payment_terms_days": 15,
                "metering_policy": MeteringPolicy.PICKUP_TO_DROP,
                "notes": "Covers Bangalore and Pune operations.",
            },
        )

        ContractRate.objects.get_or_create(
            contract=hooli_contract,
            city="bangalore",
            vehicle_category="sedan",
            duty_type=DutyType.LOCAL_8HR_80KM,
            defaults={
                "included_hours": 8,
                "included_km": 80,
                "base_rate": Decimal("2200.00"),
                "extra_hour_rate": Decimal("180.00"),
                "extra_km_rate": Decimal("15.00"),
            },
        )

        ContractRate.objects.get_or_create(
            contract=hooli_contract,
            city="bangalore",
            vehicle_category="suv",
            duty_type=DutyType.LOCAL_8HR_80KM,
            defaults={
                "included_hours": 8,
                "included_km": 80,
                "base_rate": Decimal("3200.00"),
                "extra_hour_rate": Decimal("220.00"),
                "extra_km_rate": Decimal("20.00"),
            },
        )

        ContractRate.objects.get_or_create(
            contract=hooli_contract,
            city="bangalore",
            vehicle_category="sedan",
            duty_type=DutyType.AIRPORT_TRANSFER,
            defaults={
                "included_hours": 3,
                "included_km": 45,
                "base_rate": Decimal("1200.00"),
                "extra_hour_rate": Decimal("150.00"),
                "extra_km_rate": Decimal("15.00"),
            },
        )

        ContractAllowance.objects.get_or_create(
            contract=hooli_contract,
            allowance_type=AllowanceType.OVERTIME_PER_HOUR,
            defaults={
                "amount": Decimal("150.00"),
                "description": "Standard chauffeur overtime",
            },
        )

        ContractAllowance.objects.get_or_create(
            contract=hooli_contract,
            allowance_type=AllowanceType.EARLY_START_ALLOWANCE,
            defaults={
                "amount": Decimal("250.00"),
                "description": "Duty starting before 06:00 AM",
            },
        )

        # Customer 4: Umbrella Corporation (Suspended & Expired Contract)
        umbrella, _ = CorporateCustomer.objects.get_or_create(
            code="UMBRELLA_DL_04",
            defaults={
                "legal_name": "Umbrella Pharmaceuticals & Biometrics Corp",
                "display_name": "Umbrella Corp",
                "status": CustomerStatus.SUSPENDED,
                "is_active": False,
                "gstin": "07AAACU9999P1ZA",
                "billing_address": "Sector 62, Noida, UP 201301",
                "billing_email": "accounts@umbrella.com",
                "billing_phone": "+91 120 999 9999",
                "booking_contact_name": "Albert Wesker",
                "booking_contact_email": "wesker@umbrella.com",
                "booking_contact_phone": "+91 99999 99999",
                "payment_terms_days": 60,
                "po_required": False,
                "notes": "Account suspended pending legal audits.",
            },
        )

        CustomerContact.objects.get_or_create(
            customer=umbrella,
            email="wesker@umbrella.com",
            defaults={
                "name": "Albert Wesker",
                "contact_type": ContactType.PRIMARY,
                "phone": "+91 99999 99999",
                "is_primary": True,
            },
        )

        umbrella_contract, _ = CorporateContract.objects.get_or_create(
            customer=umbrella,
            title="Umbrella Delhi National Travel SLA",
            defaults={
                "version_name": "v1.0",
                "effective_start": datetime.date(2025, 1, 1),
                "effective_end": datetime.date(2025, 12, 31),
                "status": ContractStatus.EXPIRED,
                "cgst_rate": Decimal("2.50"),
                "sgst_rate": Decimal("2.50"),
                "payment_terms_days": 60,
                "metering_policy": MeteringPolicy.GARAGE_TO_GARAGE,
                "notes": "SLA expired, needs renewal.",
            },
        )

        ContractRate.objects.get_or_create(
            contract=umbrella_contract,
            city="delhi",
            vehicle_category="suv",
            duty_type=DutyType.LOCAL_12HR_120KM,
            defaults={
                "included_hours": 12,
                "included_km": 120,
                "base_rate": Decimal("5000.00"),
                "extra_hour_rate": Decimal("300.00"),
                "extra_km_rate": Decimal("25.00"),
            },
        )

        ContractAllowance.objects.get_or_create(
            contract=umbrella_contract,
            allowance_type=AllowanceType.OUTSTATION_PER_DAY,
            defaults={
                "amount": Decimal("500.00"),
                "description": "Daily outstation driver allowance",
            },
        )

        # Customer 5: Initech Solutions (Draft Contract)
        initech, _ = CorporateCustomer.objects.get_or_create(
            code="INITECH_05",
            defaults={
                "legal_name": "Initech Software Services India Pvt Ltd",
                "display_name": "Initech",
                "status": CustomerStatus.ACTIVE,
                "is_active": True,
                "gstin": "27AABCI4444E1Z4",
                "billing_address": "Special Economic Zone, Phase 1, Hinjewadi, Pune, MH 411057",
                "billing_email": "billing@initech.com",
                "billing_phone": "+91 20 8888 1234",
                "booking_contact_name": "Peter Gibbons",
                "booking_contact_email": "peter@initech.com",
                "booking_contact_phone": "+91 98888 77777",
                "payment_terms_days": 30,
                "po_required": False,
                "notes": "Draft phase, rates under negotiation.",
            },
        )

        CustomerContact.objects.get_or_create(
            customer=initech,
            email="peter@initech.com",
            defaults={
                "name": "Peter Gibbons",
                "contact_type": ContactType.PRIMARY,
                "phone": "+91 98888 77777",
                "is_primary": True,
            },
        )

        initech_contract, _ = CorporateContract.objects.get_or_create(
            customer=initech,
            title="Initech Pune Local & Airport SLA",
            defaults={
                "version_name": "v1.0",
                "effective_start": datetime.date(2026, 8, 1),
                "status": ContractStatus.DRAFT,
                "cgst_rate": Decimal("2.50"),
                "sgst_rate": Decimal("2.50"),
                "payment_terms_days": 30,
                "metering_policy": MeteringPolicy.GARAGE_TO_GARAGE,
            },
        )

        ContractRate.objects.get_or_create(
            contract=initech_contract,
            city="pune",
            vehicle_category="sedan",
            duty_type=DutyType.LOCAL_8HR_80KM,
            defaults={
                "included_hours": 8,
                "included_km": 80,
                "base_rate": Decimal("2100.00"),
                "extra_hour_rate": Decimal("180.00"),
                "extra_km_rate": Decimal("16.00"),
            },
        )

        # Create corresponding RateBooks and RatePackages for all seeded CorporateContracts
        from django.utils import timezone
        from fleet.models import RateBook, RateBookStatus, RateBookType, RatePackage

        self.stdout.write(self.style.NOTICE("Creating RateBooks and RatePackages from corporate contracts..."))
        approved_at = timezone.now()
        for contract in CorporateContract.objects.all():
            # Get or create RateBook
            book_code = f"RB-{contract.customer.code}"
            rate_book, book_created = RateBook.objects.get_or_create(
                contract=contract,
                defaults={
                    "code": book_code,
                    "name": f"Rate Book for {contract.title}",
                    "version": 1,
                    "book_type": RateBookType.CORPORATE,
                    "status": RateBookStatus.ACTIVE,
                    "effective_start": contract.effective_start,
                    "effective_end": contract.effective_end,
                    "approved_at": approved_at,
                }
            )
            
            # Create RatePackages for each ContractRate
            for rate in contract.rates.all():
                pkg_code = f"PKG-{contract.customer.code}-{rate.city.upper()}-{rate.vehicle_category.upper()}-{rate.duty_type}"
                RatePackage.objects.get_or_create(
                    rate_book=rate_book,
                    code=pkg_code,
                    defaults={
                        "name": f"{rate.city.title()} - {rate.vehicle_category.title()} ({rate.duty_type})",
                        "city": rate.city,
                        "vehicle_category": rate.vehicle_category,
                        "duty_type": rate.duty_type,
                        "included_hours": Decimal(str(rate.included_hours)),
                        "included_km": Decimal(str(rate.included_km)),
                        "base_rate": rate.base_rate,
                        "extra_hour_rate": rate.extra_hour_rate,
                        "extra_km_rate": rate.extra_km_rate,
                        "daily_minimum_km": Decimal(str(rate.outstation_daily_min_km or 0)),
                        "cgst_rate": contract.cgst_rate,
                        "sgst_rate": contract.sgst_rate,
                        "metering_policy": contract.metering_policy,
                    }
                )

        self.stdout.write(self.style.SUCCESS("Corporate customer seed data created successfully."))
