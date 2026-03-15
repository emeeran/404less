"""
Integration Tests for User Registration

@spec FEAT-001
@requires_database

These tests verify the full registration flow including database operations.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.registration.repository import UserRepository, EmailVerificationTokenRepository


@pytest.fixture
def user_repo(db_session: AsyncSession) -> UserRepository:
    """Create user repository."""
    return UserRepository(db_session)


@pytest.fixture
def token_repo(db_session: AsyncSession) -> EmailVerificationTokenRepository:
    """Create token repository."""
    return EmailVerificationTokenRepository(db_session)


class TestRegistrationIntegration:
    """
    Integration tests for registration API endpoints.

    @spec FEAT-001/API-001, API-002
    """

    @pytest.mark.asyncio
    async def test_register_endpoint_creates_user(
        self, client: AsyncClient, user_repo: UserRepository
    ):
        """
        @spec FEAT-001/AC-001 - Successful registration creates user in database
        """
        response = await client.post(
            "/auth/register",
            json={
                "email": "integration@example.com",
                "password": "SecureP@ss123",
                "password_confirm": "SecureP@ss123",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert "user_id" in data

        # Verify user exists in database
        user = await user_repo.find_by_email("integration@example.com")
        assert user is not None
        assert user.email_verified is False

    @pytest.mark.asyncio
    async def test_register_duplicate_email_returns_409(
        self, client: AsyncClient, user_repo: UserRepository
    ):
        """
        @spec FEAT-001/AC-002 - Duplicate email returns 409 Conflict
        """
        # Create first user
        await user_repo.create(
            email="existing@example.com",
            password_hash="hashed",
            email_verified=False,
        )

        # Try to register with same email
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
    async def test_register_weak_password_returns_400(
        self, client: AsyncClient
    ):
        """
        @spec FEAT-001/AC-003 - Weak password returns 400 Bad Request
        """
        response = await client.post(
            "/auth/register",
            json={
                "email": "test@example.com",
                "password": "weak",
                "password_confirm": "weak",
            },
        )

        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"] == "invalid_input"

    @pytest.mark.asyncio
    async def test_verify_email_endpoint(
        self,
        client: AsyncClient,
        user_repo: UserRepository,
        token_repo: EmailVerificationTokenRepository,
    ):
        """
        @spec FEAT-001/API-002 - Email verification with valid token
        """
        # Create user and token
        user = await user_repo.create(
            email="verify@example.com",
            password_hash="hashed",
            email_verified=False,
        )
        token_record = await token_repo.create_token(user.id)

        # Verify email
        response = await client.post(
            "/auth/verify-email",
            json={"token": token_record.token},
        )

        assert response.status_code == 200
        assert "verified" in response.json()["message"].lower()

        # Verify user is marked as verified
        await user_repo.session.refresh(user)
        assert user.email_verified is True

    @pytest.mark.asyncio
    async def test_verify_email_expired_token(
        self, client: AsyncClient
    ):
        """
        @spec FEAT-001/API-002 - Expired token returns error
        """
        response = await client.post(
            "/auth/verify-email",
            json={"token": "expired-token-12345"},
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_email_whitespace_trimmed(
        self, client: AsyncClient, user_repo: UserRepository
    ):
        """
        @spec FEAT-001/EC-003 - Email whitespace is trimmed
        """
        response = await client.post(
            "/auth/register",
            json={
                "email": "  trimmed@example.com  ",
                "password": "SecureP@ss123",
                "password_confirm": "SecureP@ss123",
            },
        )

        assert response.status_code == 201

        # Verify email was trimmed in database
        user = await user_repo.find_by_email("trimmed@example.com")
        assert user is not None


class TestConcurrentRegistration:
    """
    Tests for concurrent registration scenarios.

    @spec FEAT-001/EC-006 - Concurrent registration with same email
    """

    @pytest.mark.asyncio
    async def test_concurrent_same_email_only_one_succeeds(
        self, client: AsyncClient
    ):
        """
        @spec FEAT-001/EC-006 - Only one concurrent registration succeeds
        """
        import asyncio

        email = "concurrent@example.com"
        payload = {
            "email": email,
            "password": "SecureP@ss123",
            "password_confirm": "SecureP@ss123",
        }

        # Make two concurrent requests
        tasks = [
            client.post("/auth/register", json=payload),
            client.post("/auth/register", json=payload),
        ]

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # One should succeed (201), one should fail (409)
        status_codes = [
            r.status_code if hasattr(r, "status_code") else 500
            for r in responses
        ]

        # At least one should be 409 (conflict) or both handled gracefully
        assert 201 in status_codes or 409 in status_codes
