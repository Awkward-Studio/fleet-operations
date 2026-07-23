import datetime
from decimal import Decimal
from django.core.management.base import BaseCommand
from billing.models import LegalEntity, FinancialYear, FiscalPeriod, LedgerAccount, AccountType, DocumentSequence, DocumentType


class Command(BaseCommand):
    help = "Seed initial Legal Entity, Financial Year, Fiscal Periods, and Chart of Accounts for Fleet Billing"

    def handle(self, *args, **options):
        self.stdout.write("Seeding Fleet Accounting & Billing data...")

        # 1. Legal Entity
        entity, created = LegalEntity.objects.get_or_create(
            gstin="27AAACA9876A1Z4",
            defaults={
                "legal_name": "Awkward Fleet Operations Pvt Ltd",
                "trade_name": "Index Fleet Logistics",
                "pan": "AAACA9876A",
                "state_code": "27",
                "registered_address": "Suite 404, Tech Park, Andheri East, Mumbai - 400069",
                "bank_name": "HDFC Bank Ltd",
                "bank_account_number": "50200012345678",
                "ifsc_code": "HDFC0001234",
            },
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created Legal Entity: {entity.legal_name}"))
        else:
            self.stdout.write(f"Legal Entity already exists: {entity.legal_name}")

        # 2. Financial Year
        today = datetime.date.today()
        fy_name = f"FY {today.year}-{str(today.year+1)[-2:]}"
        fy, created = FinancialYear.objects.get_or_create(
            name=fy_name,
            defaults={
                "start_date": datetime.date(today.year, 4, 1),
                "end_date": datetime.date(today.year + 1, 3, 31),
                "is_closed": False,
            },
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created Financial Year: {fy.name}"))

            # 12 Fiscal Periods
            for m in range(1, 13):
                month_num = (m + 2) % 12 + 1  # April = month 1
                year_num = today.year if month_num >= 4 else today.year + 1
                p_start = datetime.date(year_num, month_num, 1)
                p_end = datetime.date(year_num, month_num, 28)
                FiscalPeriod.objects.create(
                    financial_year=fy,
                    period_number=m,
                    name=f"Period {m} ({p_start:%b %Y})",
                    start_date=p_start,
                    end_date=p_end,
                )

        # 3. Chart of Accounts
        accounts = [
            ("1100", "Accounts Receivable", AccountType.ASSET, "AR_1100"),
            ("1200", "Cash & Bank Balance", AccountType.ASSET, "BANK_1200"),
            ("2100", "Output CGST Payable", AccountType.LIABILITY, "TAX_2100"),
            ("2200", "Output SGST Payable", AccountType.LIABILITY, "TAX_2200"),
            ("2300", "Accounts Payable", AccountType.LIABILITY, "AP_2300"),
            ("4000", "Passenger Transport Revenue", AccountType.REVENUE, "REV_4000"),
            ("5100", "Vehicle Fuel Expense", AccountType.EXPENSE, "EXP_5100"),
            ("5200", "Toll & Fastag Expense", AccountType.EXPENSE, "EXP_5200"),
            ("5300", "Driver Allowances Expense", AccountType.EXPENSE, "EXP_5300"),
        ]

        for code, name, ac_type, ext_code in accounts:
            acc, ac_created = LedgerAccount.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "account_type": ac_type,
                    "external_mapping_code": ext_code,
                },
            )
            if ac_created:
                self.stdout.write(self.style.SUCCESS(f"Created Ledger Account: {acc.code} - {acc.name}"))

        self.stdout.write(self.style.SUCCESS("Fleet Accounting & Billing data seeding complete!"))
