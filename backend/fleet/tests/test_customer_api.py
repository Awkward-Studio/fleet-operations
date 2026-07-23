from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from fleet.models import CorporateCustomer, CustomerContact, CustomerStatus, ContactType

User = get_user_model()


class CustomerAPITests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="adminuser",
            email="admin@test.com",
            password="password123",
            role="admin",
        )
        self.dispatcher = User.objects.create_user(
            username="dispatcheruser",
            email="dispatcher@test.com",
            password="password123",
            role="dispatcher",
        )
        self.commercial = User.objects.create_user(
            username="commercialuser",
            email="commercial@test.com",
            password="password123",
            role="commercial",
        )
        self.customer1 = CorporateCustomer.objects.create(
            code="CUST01",
            legal_name="Alpha Private Limited",
            display_name="Alpha Corp",
            status=CustomerStatus.ACTIVE,
            gstin="27ABCDE1234F1Z5",
        )
        self.contact1 = CustomerContact.objects.create(
            customer=self.customer1,
            name="Alice Smith",
            contact_type=ContactType.PRIMARY,
            email="alice@alpha.com",
            phone="9998887770",
            is_primary=True,
        )

    def test_unauthenticated_access_denied(self):
        response = self.client.get("/api/customers/")
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_dispatcher_read_only(self):
        self.client.force_authenticate(user=self.dispatcher)
        response = self.client.get("/api/customers/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        # Dispatcher cannot create a customer
        payload = {
            "code": "CUST02",
            "legal_name": "Beta Private Limited",
            "display_name": "Beta Corp",
            "status": "ACTIVE",
        }
        create_res = self.client.post("/api/customers/", payload)
        self.assertEqual(create_res.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_and_commercial_crud(self):
        self.client.force_authenticate(user=self.commercial)
        payload = {
            "code": "CUST02",
            "legal_name": "Beta Private Limited",
            "display_name": "Beta Corp",
            "status": "ACTIVE",
            "gstin": "27XYZ12345",
            "payment_terms_days": 45,
        }
        response = self.client.post("/api/customers/", payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["code"], "CUST02")

        # Soft deactivation test
        cust_id = response.data["id"]
        delete_res = self.client.delete(f"/api/customers/{cust_id}/")
        self.assertEqual(delete_res.status_code, status.HTTP_200_OK)
        cust = CorporateCustomer.objects.get(id=cust_id)
        self.assertFalse(cust.is_active)
        self.assertEqual(cust.status, CustomerStatus.INACTIVE)

    def test_search_and_contact_endpoints(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get("/api/customers/?search=Alpha")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        contacts_res = self.client.get(f"/api/customers/{self.customer1.id}/contacts/")
        self.assertEqual(contacts_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(contacts_res.data), 1)
