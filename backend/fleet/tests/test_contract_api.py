import datetime
from decimal import Decimal
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from fleet.models import CorporateCustomer, CorporateContract, ContractRate, CustomerStatus, DutyType

User = get_user_model()


class ContractAPITests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="contractadmin",
            email="cadmin@test.com",
            password="password123",
            role="admin",
        )
        self.customer = CorporateCustomer.objects.create(
            code="CUST01",
            legal_name="Alpha Corp Ltd",
            display_name="Alpha Corp",
            status=CustomerStatus.ACTIVE,
        )

    def test_contract_draft_to_active_lifecycle(self):
        self.client.force_authenticate(user=self.admin)
        payload = {
            "customer": self.customer.id,
            "title": "Annual Fleet Contract 2026",
            "version_name": "v1.0",
            "effective_start": "2026-01-01",
            "effective_end": "2026-12-31",
            "status": "DRAFT",
            "rates": [
                {
                    "city": "Mumbai",
                    "vehicle_category": "Sedan",
                    "duty_type": DutyType.LOCAL_8HR_80KM,
                    "included_hours": 8,
                    "included_km": 80,
                    "base_rate": "2500.00",
                    "extra_hour_rate": "200.00",
                    "extra_km_rate": "18.00",
                }
            ],
            "allowances": [
                {
                    "allowance_type": "OVERTIME_PER_HOUR",
                    "amount": "150.00",
                }
            ]
        }
        res = self.client.post("/api/contracts/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        contract_id = res.data["id"]

        # Validate contract endpoint
        val_res = self.client.post(f"/api/contracts/{contract_id}/validate_contract/")
        self.assertEqual(val_res.status_code, status.HTTP_200_OK)
        self.assertTrue(val_res.data["is_valid"])

        # Activate contract endpoint
        act_res = self.client.post(f"/api/contracts/{contract_id}/activate/")
        self.assertEqual(act_res.status_code, status.HTTP_200_OK)
        self.assertEqual(act_res.data["status"], "ACTIVE")

    def test_cannot_activate_without_rates(self):
        self.client.force_authenticate(user=self.admin)
        payload = {
            "customer": self.customer.id,
            "title": "Empty Contract",
            "version_name": "v1.0",
            "effective_start": "2026-01-01",
            "status": "DRAFT",
        }
        res = self.client.post("/api/contracts/", payload, format="json")
        contract_id = res.data["id"]

        act_res = self.client.post(f"/api/contracts/{contract_id}/activate/")
        self.assertEqual(act_res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reject_overlapping_active_contracts(self):
        self.client.force_authenticate(user=self.admin)
        c1 = CorporateContract.objects.create(
            customer=self.customer,
            title="Contract A",
            effective_start=datetime.date(2026, 1, 1),
            effective_end=datetime.date(2026, 6, 30),
            status="ACTIVE",
        )
        ContractRate.objects.create(
            contract=c1,
            city="mumbai",
            vehicle_category="sedan",
            duty_type=DutyType.LOCAL_8HR_80KM,
            base_rate=Decimal("2000.00"),
        )

        payload = {
            "customer": self.customer.id,
            "title": "Contract B Overlapping",
            "version_name": "v1.0",
            "effective_start": "2026-05-01",
            "effective_end": "2026-12-31",
            "status": "ACTIVE",
            "rates": [
                {
                    "city": "Mumbai",
                    "vehicle_category": "Sedan",
                    "duty_type": DutyType.LOCAL_8HR_80KM,
                    "base_rate": "2200.00",
                }
            ],
        }
        res = self.client.post("/api/contracts/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_copy_contract(self):
        self.client.force_authenticate(user=self.admin)
        c1 = CorporateContract.objects.create(
            customer=self.customer,
            title="Base Contract",
            version_name="v1.0",
            effective_start=datetime.date(2026, 1, 1),
            status="DRAFT",
        )
        ContractRate.objects.create(
            contract=c1,
            city="pune",
            vehicle_category="suv",
            duty_type=DutyType.LOCAL_12HR_120KM,
            base_rate=Decimal("4000.00"),
        )

        res = self.client.post(f"/api/contracts/{c1.id}/copy_contract/")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn("Copy", res.data["title"])
        self.assertEqual(len(res.data["rates"]), 1)
