from decimal import Decimal
import datetime
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
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


class FleetModelTests(TestCase):
    def setUp(self):
        self.customer = CorporateCustomer.objects.create(
            code="ACME01",
            legal_name="ACME Logistics Private Limited",
            display_name="ACME Corp",
            status=CustomerStatus.ACTIVE,
            gstin="27AAAAA0000A1Z5",
            payment_terms_days=30,
        )

    def test_customer_creation_and_cleaning(self):
        customer = CorporateCustomer(
            code=" test02 ",
            legal_name="Test Legal",
            display_name="Test Display",
        )
        customer.clean()
        self.assertEqual(customer.code, "TEST02")
        customer.save()
        self.assertEqual(str(customer), "Test Display (TEST02)")

    def test_customer_contact_creation(self):
        contact = CustomerContact.objects.create(
            customer=self.customer,
            name="John Doe",
            contact_type=ContactType.PRIMARY,
            email="john@acme.com",
            phone="9876543210",
            is_primary=True,
        )
        self.assertEqual(str(contact), "John Doe - ACME Corp (PRIMARY)")

    def test_contract_validation(self):
        start = datetime.date(2026, 1, 1)
        end = datetime.date(2025, 12, 31)
        contract = CorporateContract(
            customer=self.customer,
            title="Master Services Agreement 2026",
            effective_start=start,
            effective_end=end,
            cgst_rate=Decimal("2.50"),
            sgst_rate=Decimal("2.50"),
        )
        with self.assertRaises(ValidationError):
            contract.full_clean()

    def test_contract_rate_uniqueness(self):
        contract = CorporateContract.objects.create(
            customer=self.customer,
            title="MSA 2026",
            effective_start=datetime.date(2026, 1, 1),
            effective_end=datetime.date(2026, 12, 31),
            status=ContractStatus.ACTIVE,
        )
        ContractRate.objects.create(
            contract=contract,
            city="mumbai",
            vehicle_category="sedan",
            duty_type=DutyType.LOCAL_8HR_80KM,
            included_hours=8,
            included_km=80,
            base_rate=Decimal("2500.00"),
        )
        with self.assertRaises(IntegrityError):
            ContractRate.objects.create(
                contract=contract,
                city="mumbai",
                vehicle_category="sedan",
                duty_type=DutyType.LOCAL_8HR_80KM,
                included_hours=8,
                included_km=80,
                base_rate=Decimal("3000.00"),
            )

    def test_contract_allowance_uniqueness(self):
        contract = CorporateContract.objects.create(
            customer=self.customer,
            title="MSA 2026",
            effective_start=datetime.date(2026, 1, 1),
            effective_end=datetime.date(2026, 12, 31),
            status=ContractStatus.ACTIVE,
        )
        ContractAllowance.objects.create(
            contract=contract,
            allowance_type=AllowanceType.OVERTIME_PER_HOUR,
            amount=Decimal("150.00"),
        )
        with self.assertRaises(IntegrityError):
            ContractAllowance.objects.create(
                contract=contract,
                allowance_type=AllowanceType.OVERTIME_PER_HOUR,
                amount=Decimal("200.00"),
            )
