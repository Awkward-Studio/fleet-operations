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

