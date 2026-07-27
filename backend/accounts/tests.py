from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class AuthTests(APITestCase):
    def setUp(self):
        self.register_url = reverse("auth_register")
        self.login_url = reverse("token_obtain_pair")
        self.token_refresh_url = reverse("token_refresh")
        self.logout_url = reverse("auth_logout")
        self.me_url = reverse("auth_me")
        self.change_password_url = reverse("auth_change_password")
        
        self.user_data = {
            "username": "testuser",
            "email": "testuser@example.com",
            "password": "testpassword123",
            "confirm_password": "testpassword123",
            "first_name": "Test",
            "last_name": "User"
        }
        
    def test_register_user(self):
        response = self.client.post(self.register_url, self.user_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["user"]["username"], "testuser")
        self.assertEqual(response.data["user"]["email"], "testuser@example.com")
        self.assertNotIn("password", response.data["user"])

    def test_register_password_mismatch(self):
        data = self.user_data.copy()
        data["confirm_password"] = "differentpassword"
        response = self.client.post(self.register_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("confirm_password", response.data)

    def test_login_user(self):
        user = User.objects.create_user(
            username=self.user_data["username"],
            email=self.user_data["email"],
            password=self.user_data["password"]
        )
        
        login_data = {
            "username": self.user_data["username"],
            "password": self.user_data["password"]
        }
        response = self.client.post(self.login_url, login_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_get_current_user_authenticated(self):
        user = User.objects.create_user(
            username=self.user_data["username"],
            email=self.user_data["email"],
            password=self.user_data["password"]
        )
        self.client.force_authenticate(user=user)
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "testuser")

    def test_get_current_user_unauthenticated(self):
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_change_password(self):
        user = User.objects.create_user(
            username=self.user_data["username"],
            email=self.user_data["email"],
            password=self.user_data["password"]
        )
        self.client.force_authenticate(user=user)
        
        change_data = {
            "old_password": "testpassword123",
            "new_password": "newpassword123",
            "confirm_new_password": "newpassword123"
        }
        response = self.client.post(self.change_password_url, change_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        user.refresh_from_db()
        self.assertTrue(user.check_password("newpassword123"))

    def test_logout_blacklist(self):
        user = User.objects.create_user(
            username=self.user_data["username"],
            email=self.user_data["email"],
            password=self.user_data["password"]
        )
        login_data = {
            "username": self.user_data["username"],
            "password": self.user_data["password"]
        }
        login_res = self.client.post(self.login_url, login_data, format="json")
        refresh_token = login_res.data["refresh"]
        access_token = login_res.data["access"]
        
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.client.post(self.logout_url, {"refresh": refresh_token}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.client.credentials()
        refresh_res = self.client.post(self.token_refresh_url, {"refresh": refresh_token}, format="json")
        self.assertEqual(refresh_res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_with_email_and_spaces(self):
        user = User.objects.create_user(
            username="spaceduser",
            email="spaceduser@example.com",
            password="testpassword123"
        )
        
        # Test email login
        login_data_email = {
            "username": "spaceduser@example.com",
            "password": "testpassword123"
        }
        response = self.client.post(self.login_url, login_data_email, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

        # Test login with trailing/leading space in username input
        login_data_spaced = {
            "username": "  spaceduser  ",
            "password": "testpassword123"
        }
        response_spaced = self.client.post(self.login_url, login_data_spaced, format="json")
        self.assertEqual(response_spaced.status_code, status.HTTP_200_OK)


from rentals.models import CorporateCustomer
from .models import CorporateMembership, CorporateRole, ROLE_PERMISSIONS

class TenancyTests(APITestCase):
    def setUp(self):
        self.me_url = reverse("auth_me")
        self.customer = CorporateCustomer.objects.create(
            name="Acme Corp",
            billing_address="123 Road",
            email="acme@example.com",
            contact_person="John Acme",
            phone="12345678"
        )
        self.user = User.objects.create_user(
            username="acme_admin",
            email="admin@acme.com",
            password="password123"
        )
        self.membership = CorporateMembership.objects.create(
            user=self.user,
            company=self.customer,
            role=CorporateRole.ADMIN
        )

    def test_auth_me_returns_memberships_and_permissions(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["corporate_memberships"]), 1)
        membership_data = response.data["corporate_memberships"][0]
        self.assertEqual(membership_data["company_name"], "Acme Corp")
        self.assertEqual(membership_data["role"], "admin")
        self.assertEqual(membership_data["permissions"], ROLE_PERMISSIONS[CorporateRole.ADMIN])


from django.utils import timezone
from datetime import timedelta
from .models import CorporateInvitation

class InvitationTests(APITestCase):
    def setUp(self):
        self.invitations_url = reverse("portal_invitations")
        self.customer = CorporateCustomer.objects.create(
            name="Acme Corp",
            billing_address="123 Road",
            email="acme@example.com",
            contact_person="John Acme",
            phone="12345678"
        )
        self.admin_user = User.objects.create_user(
            username="acme_admin",
            email="admin@acme.com",
            password="password123"
        )
        CorporateMembership.objects.create(
            user=self.admin_user,
            company=self.customer,
            role=CorporateRole.ADMIN
        )
        self.regular_user = User.objects.create_user(
            username="regular",
            email="regular@acme.com",
            password="password123"
        )

    def test_create_invitation_success(self):
        self.client.force_authenticate(user=self.admin_user)
        data = {
            "email": "invitee@acme.com",
            "company": self.customer.id,
            "role": "travel_desk"
        }
        response = self.client.post(self.invitations_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["email"], "invitee@acme.com")
        self.assertEqual(response.data["role"], "travel_desk")

    def test_create_invitation_unauthorized(self):
        self.client.force_authenticate(user=self.regular_user)
        data = {
            "email": "invitee@acme.com",
            "company": self.customer.id,
            "role": "travel_desk"
        }
        response = self.client.post(self.invitations_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_accept_invitation_success(self):
        invite = CorporateInvitation.objects.create(
            email="new_user@acme.com",
            company=self.customer,
            role=CorporateRole.TRAVEL_DESK,
            invited_by=self.admin_user,
            expires_at=timezone.now() + timedelta(days=1)
        )
        accept_url = reverse("portal_accept_invitation", kwargs={"pk": invite.id})
        detail_url = reverse("portal_invitation_detail", kwargs={"pk": invite.id})
        
        # 1. Fetch detail first
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 2. Accept
        register_data = {
            "username": "new_travel_guy",
            "password": "newpassword123",
            "confirm_password": "newpassword123",
            "first_name": "Travel",
            "last_name": "Guy"
        }
        response = self.client.post(accept_url, register_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify user & membership exist
        user = User.objects.get(username="new_travel_guy")
        self.assertEqual(user.email, "new_user@acme.com")
        membership = user.corporate_memberships.first()
        self.assertIsNotNone(membership)
        self.assertEqual(membership.company, self.customer)
        self.assertEqual(membership.role, "travel_desk")
        
        # Verify invitation is marked used
        invite.refresh_from_db()
        self.assertIsNotNone(invite.used_at)
        
        # 3. Try to accept again
        response2 = self.client.post(accept_url, register_data, format="json")
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)



