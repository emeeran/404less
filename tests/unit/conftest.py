"""
Unit test fixtures for FEAT-001.

@spec FEAT-001
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime, timezone, timedelta


# ============================================================================
# Mock Database Fixtures
# ============================================================================

@pytest.fixture
def mock_db():
    """
    Mock database session.

    Returns an async mock that can be used in place of AsyncSession.
    """
    mock = AsyncMock()
    mock.commit = AsyncMock()
    mock.rollback = AsyncMock()
    mock.flush = AsyncMock()
    mock.refresh = AsyncMock()
    return mock


@pytest.fixture
def mock_user_repo():
    """
    Mock UserRepository.

    @spec FEAT-001/DM-001
    """
    mock = AsyncMock()

    # Default behavior: no existing user
    mock.find_by_email = AsyncMock(return_value=None)

    # Mock user creation
    mock_user = MagicMock()
    mock_user.id = uuid4()
    mock_user.email = "test@example.com"
    mock_user.email_verified = False
    mock_user.created_at = datetime.now(timezone.utc)
    mock.create = AsyncMock(return_value=mock_user)

    mock.find_by_id = AsyncMock(return_value=mock_user)
    mock.set_email_verified = AsyncMock()

    return mock, mock_user


@pytest.fixture
def mock_token_repo():
    """
    Mock EmailVerificationTokenRepository.

    @spec FEAT-001/DM-002
    """
    mock = AsyncMock()

    # Mock token creation
    mock_token = MagicMock()
    mock_token.id = uuid4()
    mock_token.user_id = uuid4()
    mock_token.token = "test-verification-token-123"
    mock_token.expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    mock_token.used_at = None
    mock.create_token = AsyncMock(return_value=mock_token)

    mock.find_valid_token = AsyncMock(return_value=mock_token)
    mock.mark_used = AsyncMock()

    return mock, mock_token


# ============================================================================
# Mock Email Service Fixtures
# ============================================================================

@pytest.fixture
def mock_email_service():
    """
    Mock email service.

    @spec FEAT-001/AC-001 - Verification email sending
    """
    mock = AsyncMock()
    mock.send = AsyncMock(return_value=True)
    mock.send_verification_email = AsyncMock(return_value=True)
    return mock


# ============================================================================
# Test Data Fixtures
# ============================================================================

@pytest.fixture
def valid_password():
    """A password that meets all complexity requirements."""
    return "SecureP@ssw0rd123"


@pytest.fixture
def valid_email():
    """A valid email address."""
    return "test@example.com"


@pytest.fixture
def valid_registration_data(valid_email, valid_password):
    """Valid registration request data."""
    return {
        "email": valid_email,
        "password": valid_password,
        "password_confirm": valid_password,
    }


@pytest.fixture
def weak_passwords():
    """Passwords that fail various requirements."""
    return {
        "too_short": "Short1!",
        "no_uppercase": "alllower123!@",
        "no_lowercase": "ALLUPPER123!@",
        "no_number": "NoNumbersHere!@",
        "no_special": "NoSpecialChars123",
        "empty": "",
        "only_spaces": " " * 12,
    }


@pytest.fixture
def invalid_emails():
    """Invalid email formats."""
    return {
        "no_at": "testexample.com",
        "no_domain": "test@",
        "no_local": "@example.com",
        "double_dots": "test..user@example.com",
        "trailing_dot": "test@example.",
        "spaces": "test @example.com",
        "empty": "",
    }
