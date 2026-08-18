import pytest
from django.contrib.auth import get_user_model

from core.utils import get_cached_otp

User = get_user_model()

pytestmark = pytest.mark.django_db


class TestRegistration:
    def test_register_creates_unverified_user_and_caches_otp(self, api_client):
        response = api_client.post(
            "/api/v1/auth/register/",
            {"username": "newuser", "phone_number": "+14155559999", "password": "S3curePass!"},
            format="json",
        )
        assert response.status_code == 201
        user = User.objects.get(phone_number="+14155559999")
        assert user.is_phone_verified is False
        assert get_cached_otp("+14155559999") is not None

    def test_register_rejects_weak_password(self, api_client):
        response = api_client.post(
            "/api/v1/auth/register/",
            {"username": "newuser2", "phone_number": "+14155559998", "password": "123"},
            format="json",
        )
        assert response.status_code == 400


class TestVerifyOtp:
    def test_correct_code_verifies_the_account(self, api_client):
        api_client.post(
            "/api/v1/auth/register/",
            {"username": "otpuser", "phone_number": "+14155559997", "password": "S3curePass!"},
            format="json",
        )
        code = get_cached_otp("+14155559997")

        response = api_client.post(
            "/api/v1/auth/verify-otp/",
            {"phone_number": "+14155559997", "code": code},
            format="json",
        )
        assert response.status_code == 200
        user = User.objects.get(phone_number="+14155559997")
        assert user.is_phone_verified is True

    def test_incorrect_code_is_rejected(self, api_client):
        api_client.post(
            "/api/v1/auth/register/",
            {"username": "otpuser2", "phone_number": "+14155559996", "password": "S3curePass!"},
            format="json",
        )
        response = api_client.post(
            "/api/v1/auth/verify-otp/",
            {"phone_number": "+14155559996", "code": "000000"},
            format="json",
        )
        assert response.status_code == 400


class TestLogin:
    def test_login_succeeds_for_verified_user(self, api_client, verified_user):
        response = api_client.post(
            "/api/v1/auth/login/",
            {"username": "buyer1", "password": "S3curePass!"},
            format="json",
        )
        assert response.status_code == 200
        assert "access" in response.data
        assert "refresh" in response.data

    def test_login_fails_for_unverified_user(self, api_client, db):
        User.objects.create_user(
            username="unverified", phone_number="+14155551111", password="S3curePass!"
        )
        response = api_client.post(
            "/api/v1/auth/login/",
            {"username": "unverified", "password": "S3curePass!"},
            format="json",
        )
        assert response.status_code == 400

    def test_login_fails_with_wrong_password(self, api_client, verified_user):
        response = api_client.post(
            "/api/v1/auth/login/",
            {"username": "buyer1", "password": "WrongPassword!"},
            format="json",
        )
        assert response.status_code == 400


class TestProfile:
    def test_change_username(self, auth_client):
        response = auth_client.patch(
            "/api/v1/profile/change-username/", {"username": "buyer1_renamed"}, format="json"
        )
        assert response.status_code == 200
        assert response.data["username"] == "buyer1_renamed"

    def test_change_password_requires_correct_current_password(self, auth_client):
        response = auth_client.post(
            "/api/v1/profile/change-password/",
            {"current_password": "WrongOne!", "new_password": "NewS3cure!Pass"},
            format="json",
        )
        assert response.status_code == 400
