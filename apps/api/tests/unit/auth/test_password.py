"""Tests for etip_api.auth.password — bcrypt hash/verify."""

import pytest

from etip_api.auth.password import hash_password, verify_password


class TestHashPassword:
    def test_returns_string(self):
        h = hash_password("secret123")
        assert isinstance(h, str)

    def test_hash_is_not_plain(self):
        assert hash_password("secret123") != "secret123"

    def test_two_hashes_differ(self):
        # bcrypt uses random salt — same input produces different hashes
        h1 = hash_password("secret123")
        h2 = hash_password("secret123")
        assert h1 != h2

    def test_hash_starts_with_bcrypt_prefix(self):
        assert hash_password("password").startswith("$2b$")


class TestVerifyPassword:
    def test_correct_password_returns_true(self):
        h = hash_password("mypassword")
        assert verify_password("mypassword", h) is True

    def test_wrong_password_returns_false(self):
        h = hash_password("mypassword")
        assert verify_password("wrongpassword", h) is False

    def test_empty_password(self):
        h = hash_password("")
        assert verify_password("", h) is True
        assert verify_password(" ", h) is False

    def test_case_sensitive(self):
        h = hash_password("Password")
        assert verify_password("password", h) is False
        assert verify_password("Password", h) is True
