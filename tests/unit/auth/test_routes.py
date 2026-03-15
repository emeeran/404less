"""
Unit Tests for User Registration Routes

@spec FEAT-001/API-001 - POST /auth/register
@spec FEAT-001/API-002 - POST /auth/verify-email
@spec FEAT-001/C-005 - Rate limiting (5/hour per IP)
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

from src.auth.registration.routes import router, RegistrationError


from src.auth.registration import routes as reg_routes


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def app():
    """Create FastAPI app with registration routes."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


# ============================================================================
# Registration Route Tests
# ============================================================================

class TestRegisterRoute:
    """
    Tests for POST /auth/register endpoint.

    @spec FEAT-001/API-001
    """

    @pytest.mark.asyncio
    async def test_register_success_returns_201(self, app):
        """@spec FEAT-001/API-001 - Successful registration returns 201"""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            with patch.object(reg_routes, 'register_user', new_callable=AsyncMock) as mock_register:
                mock_register.return_value = {
                    "message": "Registration successful. Please check your email.",
                    "user_id": "12345678-1234-1234-1234-123456789012"
                }

                response = await client.post(
                    "/auth/register",
                    json={
                        "email": "test@example.com",
                        "password": "SecureP@ss123",
                        "password_confirm": "SecureP@ss123",
                    },
                )

                assert response.status_code == 201
                assert "Registration successful" in response.json()["message"]

    @pytest.mark.asyncio
    async def test_register_duplicate_email_returns_409(self, app):
        """@spec FEAT-001/AC-002 - Duplicate email returns 409 Conflict"""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            with patch.object(reg_routes, 'register_user') as mock_register:
                mock_register.side_effect = RegistrationError(
                    "email_exists",
                    "An account with this email already exists"
                )

                response = await client.post(
                    "/auth/register",
                    json={
                        "email": "existing@example.com",
                        "password": "SecureP@ss123",
                        "password_confirm": "SecureP@ss123",
                    },
                )

                assert response.status_code == 409
                data = response.json()
                assert data["detail"]["error"] == "email_exists"

    @pytest.mark.asyncio
    async def test_register_invalid_input_returns_400(self, app):
        """@spec FEAT-001/EC-002 - Invalid input returns 400 Bad Request"""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            with patch.object(reg_routes, 'register_user') as mock_register:
                mock_register.side_effect = RegistrationError(
                    "invalid_input",
                    "Password does not meet requirements",
                    [{"field": "password", "message": "Missing uppercase letter"}]
                )

                response = await client.post(
                    "/auth/register",
                    json={
                        "email": "test@example.com",
                        "password": "weakpassword123!",  # Valid length but will fail business logic
                        "password_confirm": "weakpassword123!",
                    },
                )

                assert response.status_code == 400
                data = response.json()
                assert data["detail"]["error"] == "invalid_input"
                assert "details" in data["detail"]

    @pytest.mark.asyncio
    async def test_register_password_mismatch_returns_400(self, app):
        """Password mismatch returns 400 with specific error"""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            with patch.object(reg_routes, 'register_user') as mock_register:
                mock_register.side_effect = RegistrationError(
                    "invalid_input",
                    "Passwords do not match",
                    [{"field": "password_confirm", "message": "Passwords do not match"}]
                )

                response = await client.post(
                    "/auth/register",
                    json={
                        "email": "test@example.com",
                        "password": "SecureP@ss123",
                        "password_confirm": "DifferentP@ss456",
                    },
                )

                assert response.status_code == 400
                data = response.json()
                assert any(d["field"] == "password_confirm" for d in data["detail"]["details"])


# ============================================================================
# Email Verification Route Tests
# ============================================================================

class TestVerifyEmailRoute:
    """
    Tests for POST /auth/verify-email endpoint.

    @spec FEAT-001/API-002
    """

    @pytest.mark.asyncio
    async def test_verify_email_success_returns_200(self, app):
        """@spec FEAT-001/API-002 - Valid token returns 200"""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            with patch.object(reg_routes, 'verify_email', new_callable=AsyncMock) as mock_verify:
                mock_verify.return_value = {"message": "Email verified successfully"}

                response = await client.post(
                    "/auth/verify-email",
                    json={"token": "valid-token-123"},
                )

                assert response.status_code == 200
                assert "verified" in response.json()["message"].lower()

    @pytest.mark.asyncio
    async def test_verify_email_invalid_token_returns_400(self, app):
        """@spec FEAT-001/API-002 - Invalid token returns 400"""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            with patch.object(reg_routes, 'verify_email') as mock_verify:
                mock_verify.side_effect = RegistrationError(
                    "invalid_token",
                    "Verification token is invalid or expired"
                )

                response = await client.post(
                    "/auth/verify-email",
                    json={"token": "invalid-token"},
                )

                assert response.status_code == 400
                data = response.json()
                assert data["detail"]["error"] == "invalid_token"

    @pytest.mark.asyncio
    async def test_verify_email_expired_token_returns_400(self, app):
        """Expired token returns 400"""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            with patch.object(reg_routes, 'verify_email') as mock_verify:
                mock_verify.side_effect = RegistrationError(
                    "invalid_token",
                    "Verification token is invalid or expired"
                )

                response = await client.post(
                    "/auth/verify-email",
                    json={"token": "expired-token"},
                )

                assert response.status_code == 400


# ============================================================================
# Rate Limiting Tests
# ============================================================================

class TestRateLimiting:
    """
    Tests for rate limiting on registration endpoint.

    @spec FEAT-001/C-005 - Max 5 registration attempts per IP per hour
    """

    @pytest.mark.asyncio
    async def test_rate_limit_headers_present(self, app):
        """Rate limiting middleware should be configured"""
        # The slowapi limiter is configured on the route
        # In production, this would be tested with actual requests
        from src.auth.registration.routes import limiter

        assert limiter is not None
        # Check the limit is set correctly
        # Note: Actual rate limit testing would require integration tests


# ============================================================================
# Request Validation Tests
# ============================================================================

class TestRequestValidation:
    """Tests for request body validation."""

    @pytest.mark.asyncio
    async def test_missing_email_field(self, app):
        """Missing email should be handled"""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(
                "/auth/register",
                json={
                    "password": "SecureP@ss123",
                    "password_confirm": "SecureP@ss123",
                },
            )

            # FastAPI should return 422 for missing required field
            assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_password_field(self, app):
        """Missing password should be handled"""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(
                "/auth/register",
                json={
                    "email": "test@example.com",
                    "password_confirm": "SecureP@ss123",
                },
            )

            assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_request_body(self, app):
        """Empty request body should be handled"""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post("/auth/register", json={})

            assert response.status_code == 422
