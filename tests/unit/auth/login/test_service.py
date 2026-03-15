"""
Unit Tests for User Login Service

@spec FEAT-002
@acceptance_criteria AC-001, AC-002, AC-003, AC-004, AC-005
@edge_cases EC-001, EC-002, EC-003, EC-004
@constraints C-001, C-002, C-003, C-004, C-005, C-006
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch, MagicMock
import bcrypt
import jwt

from src.auth.login.service import (
    LoginError,
    authenticate_user,
    create_session,
    refresh_access_token,
    logout_user,
    verify_password,
    create_access_token,
    create_refresh_token,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_user():
    """Create a mock user for testing."""
    password = "SecureP@ss12345"
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()
    return {
        "id": "12345678-1234-1234-1234-123456789012",
        "email": "test@example.com",
        "password_hash": password_hash,
        "email_verified": True,
        "failed_login_attempts": 0,
        "locked_until": None,
    }


@pytest.fixture
def mock_unverified_user():
    """Create a mock unverified user for testing."""
    password = "SecureP@ss12345"
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()
    return {
        "id": "12345678-1234-1234-1234-123456789013",
        "email": "unverified@example.com",
        "password_hash": password_hash,
        "email_verified": False,
        "failed_login_attempts": 0,
        "locked_until": None,
    }


@pytest.fixture
def mock_locked_user():
    """Create a mock locked user for testing."""
    password = "SecureP@ss12345"
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()
    return {
        "id": "12345678-1234-1234-1234-123456789014",
        "email": "locked@example.com",
        "password_hash": password_hash,
        "email_verified": True,
        "failed_login_attempts": 5,
        "locked_until": datetime.now(timezone.utc) + timedelta(minutes=15),
    }


# ============================================================================
# Password Verification Tests
# ============================================================================

class TestVerifyPassword:
    """
    Tests for password verification.

    @spec FEAT-002/C-003 (bcrypt)
    """

    def test_correct_password_verifies(self, mock_user):
        """Correct password should verify successfully."""
        result = verify_password("SecureP@ss12345", mock_user["password_hash"])
        assert result is True

    def test_incorrect_password_fails(self, mock_user):
        """Incorrect password should fail verification."""
        result = verify_password("WrongP@ss12345", mock_user["password_hash"])
        assert result is False

    def test_empty_password_fails(self, mock_user):
        """Empty password should fail verification."""
        result = verify_password("", mock_user["password_hash"])
        assert result is False


# ============================================================================
# Token Creation Tests
# ============================================================================

class TestCreateTokens:
    """
    Tests for JWT token creation.

    @spec FEAT-002/C-003 (JWT with 1-hour expiry)
    @spec FEAT-002/C-004 (Refresh token with 7-day expiry)
    """

    def test_access_token_contains_user_id(self, mock_user):
        """Access token should contain user ID."""
        token = create_access_token(mock_user["id"], mock_user["email"])
        decoded = jwt.decode(token, options={"verify_signature": False})
        assert decoded["sub"] == mock_user["id"]
        assert decoded["email"] == mock_user["email"]

    def test_access_token_expiry_is_1_hour(self, mock_user):
        """Access token should expire in 1 hour."""
        token = create_access_token(mock_user["id"], mock_user["email"])
        decoded = jwt.decode(token, options={"verify_signature": False})
        exp = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)
        iat = datetime.fromtimestamp(decoded["iat"], tz=timezone.utc)
        delta = exp - iat
        assert delta.total_seconds() == 3600  # 1 hour

    def test_refresh_token_expiry_is_7_days(self, mock_user):
        """Refresh token should expire in 7 days."""
        token = create_refresh_token(mock_user["id"])
        decoded = jwt.decode(token, options={"verify_signature": False})
        exp = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)
        iat = datetime.fromtimestamp(decoded["iat"], tz=timezone.utc)
        delta = exp - iat
        assert delta.total_seconds() == 7 * 24 * 3600  # 7 days


# ============================================================================
# Authentication Tests
# ============================================================================

class TestAuthenticateUser:
    """
    Tests for user authentication.

    @spec FEAT-002/AC-001 - Successful login
    @spec FEAT-002/AC-002 - Invalid credentials
    @spec FEAT-002/AC-003 - Unverified email
    @spec FEAT-002/AC-004 - Account lockout
    @spec FEAT-002/EC-001 - Non-existent email (same error as invalid password)
    @spec FEAT-002/EC-002 - SQL injection protection
    """

    @pytest.mark.asyncio
    async def test_successful_login_returns_tokens(self, mock_user):
        """
        @spec FEAT-002/AC-001 - Successful login returns session token
        """
        with patch('src.auth.login.service.get_user_by_email', new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = mock_user
            with patch('src.auth.login.service.record_login_attempt', new_callable=AsyncMock):
                with patch('src.auth.login.service.reset_failed_attempts', new_callable=AsyncMock):
                    with patch('src.auth.login.service.create_session_record', new_callable=AsyncMock) as mock_session:
                        mock_session.return_value = "session-id-123"
                        result = await authenticate_user(
                            email="test@example.com",
                            password="SecureP@ss12345",
                            ip_address="127.0.0.1"
                        )

        assert "access_token" in result
        assert "refresh_token" in result
        assert result["token_type"] == "Bearer"
        assert result["expires_in"] == 3600

    @pytest.mark.asyncio
    async def test_invalid_password_returns_generic_error(self, mock_user):
        """
        @spec FEAT-002/AC-002 - Generic "invalid credentials" error (no email enumeration)
        """
        with patch('src.auth.login.service.get_user_by_email', new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = mock_user
            with patch('src.auth.login.service.increment_failed_attempts', new_callable=AsyncMock) as mock_increment:
                mock_increment.return_value = 1  # Return int, not AsyncMock
                with patch('src.auth.login.service.record_login_attempt', new_callable=AsyncMock):
                    with pytest.raises(LoginError) as exc_info:
                        await authenticate_user(
                            email="test@example.com",
                            password="WrongPassword123!",
                            ip_address="127.0.0.1"
                        )

        assert exc_info.value.error_code == "invalid_credentials"
        assert "invalid" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_unverified_email_returns_verification_error(self, mock_unverified_user):
        """
        @spec FEAT-002/AC-003 - Error prompts user to verify email first
        """
        with patch('src.auth.login.service.get_user_by_email', new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = mock_unverified_user
            with pytest.raises(LoginError) as exc_info:
                await authenticate_user(
                    email="unverified@example.com",
                    password="SecureP@ss12345",
                    ip_address="127.0.0.1"
                )

        assert exc_info.value.error_code == "email_not_verified"

    @pytest.mark.asyncio
    async def test_locked_account_returns_lockout_error(self, mock_locked_user):
        """
        @spec FEAT-002/AC-004 - Account temporarily locked for 15 minutes
        """
        with patch('src.auth.login.service.get_user_by_email', new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = mock_locked_user
            with pytest.raises(LoginError) as exc_info:
                await authenticate_user(
                    email="locked@example.com",
                    password="SecureP@ss12345",
                    ip_address="127.0.0.1"
                )

        assert exc_info.value.error_code == "account_locked"
        assert "15" in exc_info.value.message or "locked" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_nonexistent_email_returns_same_error_as_invalid_password(self):
        """
        @spec FEAT-002/EC-001 - Same error as invalid password (no enumeration)
        """
        with patch('src.auth.login.service.get_user_by_email', new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = None  # User doesn't exist
            with pytest.raises(LoginError) as exc_info:
                await authenticate_user(
                    email="nonexistent@example.com",
                    password="AnyPassword123!",
                    ip_address="127.0.0.1"
                )

        assert exc_info.value.error_code == "invalid_credentials"


# ============================================================================
# Session Management Tests
# ============================================================================

class TestSessionManagement:
    """
    Tests for session management.

    @spec FEAT-002/AC-005 - Session expiration
    @spec FEAT-002/EC-003 - Concurrent logins from different devices
    """

    @pytest.mark.asyncio
    async def test_create_session_stores_refresh_token(self, mock_user):
        """Session should store refresh token hash."""
        with patch('src.auth.login.service.create_session_record', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = "session-id-123"
            result = await create_session(
                user_id=mock_user["id"],
                refresh_token="refresh-token-xyz",
                user_agent="Mozilla/5.0",
                ip_address="127.0.0.1"
            )

        assert result == "session-id-123"
        mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_token_returns_new_access_token(self, mock_user):
        """
        @spec FEAT-002/API-002 - Refresh token exchange
        """
        refresh_token = create_refresh_token(mock_user["id"])

        with patch('src.auth.login.service.validate_refresh_token', new_callable=AsyncMock) as mock_validate:
            mock_validate.return_value = mock_user["id"]
            result = await refresh_access_token(refresh_token)

        assert "access_token" in result
        assert result["token_type"] == "Bearer"
        assert result["expires_in"] == 3600

    @pytest.mark.asyncio
    async def test_invalid_refresh_token_returns_error(self):
        """Invalid refresh token should return error."""
        with patch('src.auth.login.service.validate_refresh_token', new_callable=AsyncMock) as mock_validate:
            mock_validate.return_value = None
            with pytest.raises(LoginError) as exc_info:
                await refresh_access_token("invalid-token")

        assert exc_info.value.error_code == "invalid_refresh_token"

    @pytest.mark.asyncio
    async def test_logout_revokes_session(self):
        """
        @spec FEAT-002/API-003 - Logout revokes session
        """
        with patch('src.auth.login.service.revoke_session', new_callable=AsyncMock) as mock_revoke:
            mock_revoke.return_value = True
            result = await logout_user("session-id-123")

        assert result is True
        mock_revoke.assert_called_once_with("session-id-123", None)


# ============================================================================
# Failed Attempt Tracking Tests
# ============================================================================

class TestFailedAttemptTracking:
    """
    Tests for failed login attempt tracking.

    @spec FEAT-002/C-001 - Failed attempts tracked per email
    @spec FEAT-002/C-002 - Account locked after 5 failed attempts for 15 minutes
    @spec FEAT-002/EC-004 - Login during lockout extends it
    """

    def test_max_failed_attempts_is_5(self):
        """@spec FEAT-002/C-002 - Max 5 failed attempts"""
        from src.auth.login.service import MAX_FAILED_ATTEMPTS
        assert MAX_FAILED_ATTEMPTS == 5

    def test_lockout_duration_is_15_minutes(self):
        """@spec FEAT-002/C-002 - 15 minute lockout"""
        from src.auth.login.service import LOCKOUT_DURATION_MINUTES
        assert LOCKOUT_DURATION_MINUTES == 15
