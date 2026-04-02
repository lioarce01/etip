"""Integration tests — /auth endpoints."""

import pytest
from httpx import AsyncClient

from tests.integration.conftest import auth, login, register


class TestRegister:
    async def test_register_returns_access_token(self, client: AsyncClient):
        resp = await client.post(
            "/auth/register",
            json={"company_name": "ACME", "slug": "acme", "email": "admin@acme.com", "password": "Password1!"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"

    async def test_register_sets_refresh_cookie(self, client: AsyncClient):
        resp = await client.post(
            "/auth/register",
            json={"company_name": "ACME", "slug": "acme", "email": "admin@acme.com", "password": "Password1!"},
        )
        assert resp.status_code == 201
        assert "refresh_token" in resp.cookies

    async def test_register_duplicate_slug_returns_409(self, client: AsyncClient):
        await client.post(
            "/auth/register",
            json={"company_name": "ACME", "slug": "acme", "email": "admin@acme.com", "password": "Password1!"},
        )
        resp = await client.post(
            "/auth/register",
            json={"company_name": "ACME2", "slug": "acme", "email": "other@acme2.com", "password": "Password1!"},
        )
        assert resp.status_code == 409

    async def test_register_invalid_slug_returns_422(self, client: AsyncClient):
        resp = await client.post(
            "/auth/register",
            json={"company_name": "ACME", "slug": "UPPER_CASE", "email": "admin@acme.com", "password": "Password1!"},
        )
        assert resp.status_code == 422

    async def test_register_short_password_returns_422(self, client: AsyncClient):
        resp = await client.post(
            "/auth/register",
            json={"company_name": "ACME", "slug": "acme", "email": "admin@acme.com", "password": "short"},
        )
        assert resp.status_code == 422


class TestTenantBySlug:
    async def test_returns_tenant_id_for_known_slug(self, client: AsyncClient):
        token, tenant_id = await register(client)

        resp = await client.get("/auth/tenant-by-slug/acme")
        assert resp.status_code == 200
        body = resp.json()
        assert body["tenant_id"] == tenant_id
        assert body["slug"] == "acme"

    async def test_unknown_slug_returns_404(self, client: AsyncClient):
        resp = await client.get("/auth/tenant-by-slug/no-such-company")
        assert resp.status_code == 404


class TestLogin:
    async def test_valid_credentials_return_access_token(self, client: AsyncClient):
        _, tenant_id = await register(client)

        resp = await client.post(
            "/auth/login",
            json={"email": "admin@acme.com", "password": "Password1!", "tenant_id": tenant_id},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    async def test_login_sets_refresh_cookie(self, client: AsyncClient):
        _, tenant_id = await register(client)

        resp = await client.post(
            "/auth/login",
            json={"email": "admin@acme.com", "password": "Password1!", "tenant_id": tenant_id},
        )
        assert resp.status_code == 200
        assert "refresh_token" in resp.cookies

    async def test_wrong_password_returns_401(self, client: AsyncClient):
        _, tenant_id = await register(client)

        resp = await client.post(
            "/auth/login",
            json={"email": "admin@acme.com", "password": "WrongPass!", "tenant_id": tenant_id},
        )
        assert resp.status_code == 401

    async def test_unknown_email_returns_401(self, client: AsyncClient):
        _, tenant_id = await register(client)

        resp = await client.post(
            "/auth/login",
            json={"email": "nobody@acme.com", "password": "Password1!", "tenant_id": tenant_id},
        )
        assert resp.status_code == 401

    async def test_wrong_tenant_returns_401(self, client: AsyncClient):
        import uuid
        _, _ = await register(client)

        resp = await client.post(
            "/auth/login",
            json={"email": "admin@acme.com", "password": "Password1!", "tenant_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 401

    async def test_inactive_user_returns_401(self, client: AsyncClient):
        token, tenant_id = await register(client)

        # Deactivate own account via admin creating another admin then deactivating self is complex,
        # so create a member user and deactivate them instead
        create_resp = await client.post(
            "/api/v1/users",
            json={"email": "member@acme.com", "password": "Password1!", "role": "dev"},
            headers=auth(token),
        )
        assert create_resp.status_code == 201
        member_id = create_resp.json()["id"]

        await client.patch(
            f"/api/v1/users/{member_id}",
            json={"is_active": False},
            headers=auth(token),
        )

        resp = await client.post(
            "/auth/login",
            json={"email": "member@acme.com", "password": "Password1!", "tenant_id": tenant_id},
        )
        assert resp.status_code == 401


class TestRefresh:
    async def test_valid_refresh_returns_new_access_token(self, client: AsyncClient):
        _, tenant_id = await register(client)

        # Login to get refresh cookie
        login_resp = await client.post(
            "/auth/login",
            json={"email": "admin@acme.com", "password": "Password1!", "tenant_id": tenant_id},
        )
        assert "refresh_token" in login_resp.cookies

        resp = await client.post("/auth/refresh")
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    async def test_refresh_rotates_cookie(self, client: AsyncClient):
        _, tenant_id = await register(client)

        await client.post(
            "/auth/login",
            json={"email": "admin@acme.com", "password": "Password1!", "tenant_id": tenant_id},
        )
        old_cookie = client.cookies.get("refresh_token")

        await client.post("/auth/refresh")
        new_cookie = client.cookies.get("refresh_token")

        assert new_cookie is not None
        assert new_cookie != old_cookie

    async def test_no_cookie_returns_401(self, client: AsyncClient):
        resp = await client.post("/auth/refresh")
        assert resp.status_code == 401

    async def test_used_refresh_token_is_revoked(self, client: AsyncClient):
        _, tenant_id = await register(client)

        await client.post(
            "/auth/login",
            json={"email": "admin@acme.com", "password": "Password1!", "tenant_id": tenant_id},
        )
        old_token = client.cookies.get("refresh_token")

        # First refresh succeeds and rotates
        await client.post("/auth/refresh")

        # Manually set the old token back and try again — should fail
        client.cookies.set("refresh_token", old_token)
        resp = await client.post("/auth/refresh")
        assert resp.status_code == 401


class TestMe:
    async def test_returns_current_user_profile(self, client: AsyncClient):
        token, tenant_id = await register(client)

        resp = await client.get("/auth/me", headers=auth(token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == "admin@acme.com"
        assert body["role"] == "admin"
        assert body["tenant_id"] == tenant_id

    async def test_no_token_returns_403(self, client: AsyncClient):
        resp = await client.get("/auth/me")
        assert resp.status_code in (401, 403)


class TestLogout:
    async def test_logout_returns_204(self, client: AsyncClient):
        token, tenant_id = await register(client)
        await client.post(
            "/auth/login",
            json={"email": "admin@acme.com", "password": "Password1!", "tenant_id": tenant_id},
        )

        resp = await client.post("/auth/logout", headers=auth(token))
        assert resp.status_code == 204

    async def test_refresh_fails_after_logout(self, client: AsyncClient):
        token, tenant_id = await register(client)
        await client.post(
            "/auth/login",
            json={"email": "admin@acme.com", "password": "Password1!", "tenant_id": tenant_id},
        )

        await client.post("/auth/logout", headers=auth(token))
        resp = await client.post("/auth/refresh")
        assert resp.status_code == 401

    async def test_unauthenticated_returns_403(self, client: AsyncClient):
        resp = await client.post("/auth/logout")
        assert resp.status_code in (401, 403)


class TestChangePassword:
    async def test_valid_change_returns_204(self, client: AsyncClient):
        token, _ = await register(client)

        resp = await client.post(
            "/auth/change-password",
            json={"current_password": "Password1!", "new_password": "NewPass1!"},
            headers=auth(token),
        )
        assert resp.status_code == 204

    async def test_can_login_with_new_password(self, client: AsyncClient):
        token, tenant_id = await register(client)

        await client.post(
            "/auth/change-password",
            json={"current_password": "Password1!", "new_password": "NewPass1!"},
            headers=auth(token),
        )

        new_token = await login(client, "admin@acme.com", "NewPass1!", tenant_id)
        assert new_token

    async def test_old_password_rejected_after_change(self, client: AsyncClient):
        token, tenant_id = await register(client)

        await client.post(
            "/auth/change-password",
            json={"current_password": "Password1!", "new_password": "NewPass1!"},
            headers=auth(token),
        )

        resp = await client.post(
            "/auth/login",
            json={"email": "admin@acme.com", "password": "Password1!", "tenant_id": tenant_id},
        )
        assert resp.status_code == 401

    async def test_wrong_current_password_returns_400(self, client: AsyncClient):
        token, _ = await register(client)

        resp = await client.post(
            "/auth/change-password",
            json={"current_password": "WrongPass!", "new_password": "NewPass1!"},
            headers=auth(token),
        )
        assert resp.status_code == 400

    async def test_change_password_revokes_refresh_tokens(self, client: AsyncClient):
        token, tenant_id = await register(client)
        await client.post(
            "/auth/login",
            json={"email": "admin@acme.com", "password": "Password1!", "tenant_id": tenant_id},
        )
        old_refresh = client.cookies.get("refresh_token")

        await client.post(
            "/auth/change-password",
            json={"current_password": "Password1!", "new_password": "NewPass1!"},
            headers=auth(token),
        )

        client.cookies.set("refresh_token", old_refresh)
        resp = await client.post("/auth/refresh")
        assert resp.status_code == 401

    async def test_response_body_is_empty(self, client: AsyncClient):
        """204 must have no body — callers must NOT call .json() on this response."""
        token, _ = await register(client)

        resp = await client.post(
            "/auth/change-password",
            json={"current_password": "Password1!", "new_password": "NewPass1!"},
            headers=auth(token),
        )
        assert resp.status_code == 204
        assert resp.content == b""

    async def test_sequential_password_changes(self, client: AsyncClient):
        """A→B then B→C: the second change must use the NEW password as current."""
        token, tenant_id = await register(client)

        # First change: Password1! → NewPass1!
        resp = await client.post(
            "/auth/change-password",
            json={"current_password": "Password1!", "new_password": "NewPass1!"},
            headers=auth(token),
        )
        assert resp.status_code == 204

        # Re-login with new password to get a fresh token
        token2 = await login(client, "admin@acme.com", "NewPass1!", tenant_id)
        assert token2

        # Second change: NewPass1! → FinalPass1!
        resp2 = await client.post(
            "/auth/change-password",
            json={"current_password": "NewPass1!", "new_password": "FinalPass1!"},
            headers=auth(token2),
        )
        assert resp2.status_code == 204

        # Login with final password works
        final_token = await login(client, "admin@acme.com", "FinalPass1!", tenant_id)
        assert final_token

        # Login with intermediate password is rejected
        resp3 = await client.post(
            "/auth/login",
            json={"email": "admin@acme.com", "password": "NewPass1!", "tenant_id": tenant_id},
        )
        assert resp3.status_code == 401

    async def test_old_password_rejected_immediately_after_change(self, client: AsyncClient):
        """Reproduces the reported bug scenario: change password then try to use old one."""
        token, tenant_id = await register(client)

        # Change the password
        resp = await client.post(
            "/auth/change-password",
            json={"current_password": "Password1!", "new_password": "NewPass1!"},
            headers=auth(token),
        )
        assert resp.status_code == 204

        # Immediately try to log in with the OLD password — must fail
        resp2 = await client.post(
            "/auth/login",
            json={"email": "admin@acme.com", "password": "Password1!", "tenant_id": tenant_id},
        )
        assert resp2.status_code == 401

        # But the NEW password works
        new_token = await login(client, "admin@acme.com", "NewPass1!", tenant_id)
        assert new_token

    async def test_wrong_current_password_does_not_change_password(self, client: AsyncClient):
        """A failed change-password attempt must leave the password unchanged."""
        token, tenant_id = await register(client)

        # Attempt with wrong current password
        resp = await client.post(
            "/auth/change-password",
            json={"current_password": "WrongPass!", "new_password": "NewPass1!"},
            headers=auth(token),
        )
        assert resp.status_code == 400

        # Original password must still work
        original_token = await login(client, "admin@acme.com", "Password1!", tenant_id)
        assert original_token
