from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.test import TestCase
from rest_framework.test import APIClient


class AuthenticationTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(username="driver", password="StrongPass123!")

    def login(self, username="driver", password="StrongPass123!"):
        response = self.client.post("/api/auth/login/", {"username": username, "password": password})
        self.assertEqual(response.status_code, 200)
        return response.data

    def test_login_refresh_logout(self):
        # Registration needs a Telegram code; test_registration covers it.
        get_user_model().objects.create_user(username="newdriver", password="StrongPass123!")
        tokens = self.login("newdriver")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.assertEqual(self.client.get("/api/auth/me/").data["username"], "newdriver")
        refreshed = self.client.post("/api/auth/refresh/", {"refresh": tokens["refresh"]})
        self.assertEqual(refreshed.status_code, 200)
        self.assertIn("refresh", refreshed.data)
        self.assertEqual(self.client.post("/api/auth/refresh/", {"refresh": tokens["refresh"]}).status_code, 401)
        self.assertEqual(self.client.post("/api/auth/logout/", {"refresh": refreshed.data["refresh"]}).status_code, 204)
        self.assertEqual(self.client.post("/api/auth/refresh/", {"refresh": refreshed.data["refresh"]}).status_code, 401)

    def test_profile_and_admin_user_crud(self):
        tokens = self.login()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.assertEqual(self.client.get("/api/auth/users/").status_code, 403)
        response = self.client.patch("/api/auth/me/", {"first_name": "Ali", "is_staff": True, "role": "admin", "phone_number": "+998911112233"})
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Ali")
        self.assertFalse(self.user.is_staff)
        self.assertEqual(self.user.role, "user")
        # The Telegram-verified phone cannot be replaced from the profile.
        self.assertEqual(self.user.phone_number, "")

        admin = get_user_model().objects.create_superuser(username="admin", password="AdminPass123!")
        self.assertEqual(admin.role, "admin")
        tokens = self.login("admin", "AdminPass123!")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        created = self.client.post("/api/auth/users/", {"username": "dispatcher", "password": "StrongPass123!", "role": "dispatcher"})
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.data["role"], "dispatcher")
        pk = created.data["id"]
        self.assertEqual(self.client.get("/api/auth/users/").status_code, 200)
        self.assertEqual(self.client.get(f"/api/auth/users/{pk}/").status_code, 200)
        self.assertEqual(self.client.put(f"/api/auth/users/{pk}/", {"username": "dispatcher2", "email": "d@example.com"}).status_code, 200)
        self.assertEqual(self.client.patch(f"/api/auth/users/{pk}/", {"first_name": "Vali"}).status_code, 200)
        self.assertEqual(self.client.delete(f"/api/auth/users/{pk}/").status_code, 204)
        self.assertFalse(get_user_model().objects.filter(pk=pk).exists())

    def test_phone_and_role_validation(self):
        bad_phone = self.client.post("/api/auth/register/", {"username": "newuser", "password": "StrongPass123!", "phone_number": "901234567"})
        self.assertEqual(bad_phone.status_code, 400)
        admin = get_user_model().objects.create_superuser(username="admin", password="AdminPass123!")
        tokens = self.login("admin", "AdminPass123!")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        bad_role = self.client.patch(f"/api/auth/users/{self.user.pk}/", {"role": "pilot"})
        self.assertEqual(bad_role.status_code, 400)

    def test_logout_rejects_other_users_refresh(self):
        tokens = self.login()
        get_user_model().objects.create_user(username="other", password="OtherPass123!")
        other = self.login("other", "OtherPass123!")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {other['access']}")
        self.assertEqual(self.client.post("/api/auth/logout/", {"refresh": tokens["refresh"]}).status_code, 403)

    def test_custom_user_model(self):
        self.assertTrue(issubclass(get_user_model(), AbstractUser))
        self.assertEqual(settings.AUTH_USER_MODEL, "authentication.User")

    def test_password_change_requires_current_password_and_revokes_tokens(self):
        from django.core.cache import cache
        cache.clear()
        tokens = self.login()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.assertEqual(self.client.patch("/api/auth/me/", {"password": "UpdatedStrongPass!2026"}).status_code, 400)
        changed = self.client.patch("/api/auth/me/", {"password": "UpdatedStrongPass!2026", "current_password": "StrongPass123!"})
        self.assertEqual(changed.status_code, 200)
        self.assertNotIn("current_password", changed.data)
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)
        self.client.credentials()
        self.assertEqual(self.client.post("/api/auth/refresh/", {"refresh": tokens["refresh"]}).status_code, 401)

    def test_login_attempts_are_limited(self):
        from django.core.cache import cache
        cache.clear()
        for _ in range(5):
            self.assertEqual(self.client.post("/api/auth/login/", {"username": "nonexistent", "password": "wrong"}).status_code, 401)
        self.assertEqual(self.client.post("/api/auth/login/", {"username": "nonexistent", "password": "wrong"}).status_code, 429)
        cache.clear()

    def test_password_rules_are_length_and_not_only_digits(self):
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError
        # Common or username-like passwords are allowed now.
        for password in ("password", "driver123", "qwerty12"):
            validate_password(password, self.user)
        for password in ("12345678", "abc1234"):
            with self.assertRaises(ValidationError):
                validate_password(password, self.user)
