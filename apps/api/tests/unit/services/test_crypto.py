"""Tests for etip_api.services.crypto — connector config encryption."""

import pytest
from cryptography.fernet import Fernet, InvalidToken
from unittest.mock import patch


class TestEncryptConfig:
    def test_returns_envelope_not_plaintext(self):
        from etip_api.services.crypto import encrypt_config

        result = encrypt_config({"api_key": "super-secret", "org": "acme"})

        assert "api_key" not in result
        assert "super-secret" not in str(result)
        assert result.get("v") == 1
        assert "ct" in result

    def test_ciphertext_is_string(self):
        from etip_api.services.crypto import encrypt_config

        result = encrypt_config({"token": "abc123"})
        assert isinstance(result["ct"], str)


class TestDecryptConfig:
    def test_round_trip_preserves_data(self):
        from etip_api.services.crypto import decrypt_config, encrypt_config

        original = {"access_token": "ghp_secret", "org": "acme", "nested": {"a": 1}}
        assert decrypt_config(encrypt_config(original)) == original

    def test_wrong_key_raises(self):
        from etip_api.services.crypto import encrypt_config

        encrypted = encrypt_config({"key": "val"})

        wrong_key = Fernet.generate_key().decode()
        with patch("etip_api.services.crypto.get_settings") as mock_settings:
            mock_settings.return_value.connector_encryption_key = wrong_key
            from etip_api.services import crypto
            with pytest.raises(InvalidToken):
                crypto.decrypt_config(encrypted)

    def test_empty_dict_round_trips(self):
        from etip_api.services.crypto import decrypt_config, encrypt_config

        assert decrypt_config(encrypt_config({})) == {}


class TestIsEncrypted:
    def test_envelope_returns_true(self):
        from etip_api.services.crypto import encrypt_config, is_encrypted

        assert is_encrypted(encrypt_config({"k": "v"})) is True

    def test_plaintext_dict_returns_false(self):
        from etip_api.services.crypto import is_encrypted

        assert is_encrypted({"api_key": "plaintext"}) is False

    def test_empty_dict_returns_false(self):
        from etip_api.services.crypto import is_encrypted

        assert is_encrypted({}) is False


