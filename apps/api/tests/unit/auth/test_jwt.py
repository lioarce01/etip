"""Tests for etip_api.auth.jwt — token creation and decoding."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import jwt
import pytest

from etip_api.auth.jwt import create_access_token, decode_access_token
from tests.conftest import EMPLOYEE_ID, TENANT_ID, USER_ID


USER_EMAIL = "user@acme.com"
USER_ROLE = "tm"


class TestCreateAccessToken:
    def test_returns_string(self):
        token = create_access_token(USER_ID, USER_EMAIL, USER_ROLE, TENANT_ID)
        assert isinstance(token, str)
        assert len(token) > 20

    def test_payload_contains_expected_claims(self):
        token = create_access_token(USER_ID, USER_EMAIL, USER_ROLE, TENANT_ID)
        payload = decode_access_token(token)

        assert payload["sub"] == str(USER_ID)
        assert payload["email"] == USER_EMAIL
        assert payload["role"] == USER_ROLE
        assert payload["tenant_id"] == str(TENANT_ID)
        assert payload["type"] == "access"

    def test_token_has_expiry(self):
        token = create_access_token(USER_ID, USER_EMAIL, USER_ROLE, TENANT_ID)
        payload = decode_access_token(token)
        assert "exp" in payload
        assert payload["exp"] > datetime.now(UTC).timestamp()

    def test_different_users_produce_different_tokens(self):
        t1 = create_access_token(USER_ID, USER_EMAIL, "tm", TENANT_ID)
        t2 = create_access_token(uuid.uuid4(), "other@acme.com", "dev", TENANT_ID)
        assert t1 != t2


class TestDecodeAccessToken:
    def test_valid_token_decodes(self):
        token = create_access_token(USER_ID, USER_EMAIL, USER_ROLE, TENANT_ID)
        payload = decode_access_token(token)
        assert payload["sub"] == str(USER_ID)

    def test_expired_token_raises(self):
        from etip_core.settings import get_settings
        settings = get_settings()

        # Create a token that expired 1 second ago
        payload = {
            "sub": str(USER_ID),
            "email": USER_EMAIL,
            "role": USER_ROLE,
            "tenant_id": str(TENANT_ID),
            "type": "access",
            "exp": datetime.now(UTC) - timedelta(seconds=1),
        }
        expired_token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

        with pytest.raises(jwt.ExpiredSignatureError):
            decode_access_token(expired_token)

    def test_tampered_token_raises(self):
        token = create_access_token(USER_ID, USER_EMAIL, USER_ROLE, TENANT_ID)
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(jwt.InvalidTokenError):
            decode_access_token(tampered)

    def test_wrong_secret_raises(self):
        from etip_core.settings import get_settings
        settings = get_settings()

        token = jwt.encode(
            {"sub": str(USER_ID), "type": "access", "exp": datetime.now(UTC) + timedelta(minutes=15)},
            "a-different-32-byte-secret-key!!",
            algorithm=settings.jwt_algorithm,
        )
        with pytest.raises(jwt.InvalidTokenError):
            decode_access_token(token)

    def test_refresh_token_type_raises(self):
        from etip_core.settings import get_settings
        settings = get_settings()

        # A token with type=refresh should be rejected by decode_access_token
        payload = {
            "sub": str(USER_ID),
            "type": "refresh",   # wrong type
            "exp": datetime.now(UTC) + timedelta(days=7),
        }
        token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

        with pytest.raises(jwt.InvalidTokenError):
            decode_access_token(token)
