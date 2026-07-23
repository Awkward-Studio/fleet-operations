import datetime
from decimal import Decimal
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from fleet.models import (
    CorporateCustomer,
    CorporateContract,
    ContractRate,
    ContractAllowance,
    CustomerStatus,
    DutyType,
    AllowanceType,
)
from fleet.pricing_service import calculate_quote, PricingError

User = get_user_model()


class PricingEngineTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="pricinguser",
            email="pricing@test.com",
            password="password123",
            role="dispatcher",
        )
        self.customer = CorporateCustomer.objects.create(
            code="CUST_PRICE_01",
            legal_name="Gamma Tech Pvt Ltd",
            display_name="Gamma Tech",
            status=CustomerStatus.ACTIVE,
        )
        self.contract = CorporateContract.objects.create(
            customer=self.customer,
            title="Master Pricing Agreement",
            version_name="v1.0",
            effective_start=datetime.date(2026, 1, 1),
            effective_end=datetime.date(2026, 12, 31),
            status="ACTIVE",
            cgst_rate=Decimal("2.50"),
            sgst_rate=Decimal("2.50"),
        )
        self.rate_local = ContractRate.objects.create(
            contract=self.contract,
            city="mumbai",
            vehicle_category="sedan",
            duty_type=DutyType.LOCAL_8HR_80KM,
            included_hours=8,
            included_km=80,
            base_rate=Decimal("2000.00"),
            extra_hour_rate=Decimal("200.00"),
            extra_km_rate=Decimal("15.00"),
        )
        self.rate_outstation = ContractRate.objects.create(
            contract=self.contract,
            city="mumbai",
            vehicle_category="sedan",
            duty_type=DutyType.OUTSTATION,
            included_hours=24,
            included_km=250,
            base_rate=Decimal("3500.00"),
            extra_km_rate=Decimal("14.00"),
            outstation_daily_min_km=250,
        )
        self.allowance_overtime = ContractAllowance.objects.create(
            contract=self.contract,
            allowance_type=AllowanceType.OVERTIME_PER_HOUR,
            amount=Decimal("100.00"),
            description="Overtime allowance per hour",
        )

    def test_local_within_limits_pricing(self):
        quote = calculate_quote(
            customer_id=self.customer.id,
            pickup_datetime="2026-07-25T10:00:00",
            pickup_city="Mumbai",
            vehicle_category="Sedan",
            duty_type=DutyType.LOCAL_8HR_80KM,
            planned_hours=7,
            planned_km=70,
        )
        charges = quote["itemized_charges"]
        self.assertEqual(charges["base_charge"], "2000.00")
        self.assertEqual(charges["excess_hour_charge"], "0.00")
        self.assertEqual(charges["excess_km_charge"], "0.00")
        self.assertEqual(charges["subtotal"], "2000.00")
        # 2.5% CGST = 50.00, 2.5% SGST = 50.00 -> Total = 2100.00
        self.assertEqual(charges["cgst_amount"], "50.00")
        self.assertEqual(charges["sgst_amount"], "50.00")
        self.assertEqual(quote["total_amount"], "2100.00")

    def test_local_excess_hours_and_km_with_allowance(self):
        quote = calculate_quote(
            customer_id=self.customer.id,
            pickup_datetime="2026-07-25T10:00:00",
            pickup_city="Mumbai",
            vehicle_category="Sedan",
            duty_type=DutyType.LOCAL_8HR_80KM,
            planned_hours=10,  # 2 excess hrs -> 2 * 200 = 400
            planned_km=100,    # 20 excess km -> 20 * 15 = 300
            requested_allowances=[{"allowance_type": AllowanceType.OVERTIME_PER_HOUR, "quantity": 2}], # 2 * 100 = 200
        )
        charges = quote["itemized_charges"]
        self.assertEqual(charges["base_charge"], "2000.00")
        self.assertEqual(charges["excess_hour_charge"], "400.00")
        self.assertEqual(charges["excess_km_charge"], "300.00")
        self.assertEqual(charges["allowances_total"], "200.00")
        # Subtotal = 2000 + 400 + 300 + 200 = 2900.00
        self.assertEqual(charges["subtotal"], "2900.00")
        # Tax = 2.5% + 2.5% of 2900 = 72.50 + 72.50 = 145.00 -> Total = 3045.00
        self.assertEqual(charges["cgst_amount"], "72.50")
        self.assertEqual(charges["sgst_amount"], "72.50")
        self.assertEqual(quote["total_amount"], "3045.00")

    def test_outstation_daily_minimum_enforcement(self):
        quote = calculate_quote(
            customer_id=self.customer.id,
            pickup_datetime="2026-07-25T08:00:00",
            pickup_city="Mumbai",
            vehicle_category="Sedan",
            duty_type=DutyType.OUTSTATION,
            planned_km=180, # below 250km min -> effective km should be 250km
            outstation_days=2, # min km = 500km
        )
        self.assertEqual(quote["inputs"]["effective_km"], 500.0)

    def test_missing_rate_raises_pricing_error(self):
        with self.assertRaises(PricingError):
            calculate_quote(
                customer_id=self.customer.id,
                pickup_datetime="2026-07-25T10:00:00",
                pickup_city="Delhi", # No rate for Delhi
                vehicle_category="Sedan",
                duty_type=DutyType.LOCAL_8HR_80KM,
            )

    def test_quote_api_endpoint(self):
        self.client.force_authenticate(user=self.user)
        payload = {
            "customer": self.customer.id,
            "pickup_datetime": "2026-07-25T10:00:00",
            "pickup_city": "Mumbai",
            "vehicle_category": "Sedan",
            "duty_type": DutyType.LOCAL_8HR_80KM,
            "planned_hours": 9,
            "planned_km": 90,
        }
        res = self.client.post("/api/pricing/quote/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("total_amount", res.data)
