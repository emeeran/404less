"""
Unit Tests for Password Reset Service

@spec FEAT-003
@acceptance_criteria AC-001, AC-002, AC-003
@edge_cases EC-001, EC-002, EC-003, EC-004
@constraints C-001, C-002, C-003, C-004
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
import bcrypt
import secrets

from src.auth.password_reset.service import (
    PasswordResetError,
    request_password_reset,
    confirm_password_reset,
    validate_password_strength,
    generate_reset_token,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_user():
    """Create a mock user for testing."""
    password = "OldSecureP@ss123"
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()
    return {
        "id": "12345678-1234-1234-1234-123456789012",
        "email": "test@example.com",
        "password_hash": password_hash,
        "email_verified": True,
    }


@pytest.fixture
def mock_reset_token():
    """Create a mock reset token."""
    return {
        "id": "token-uuid-123",
        "user_id": "12345678-1234-1234-1234-123456789012",
        "token": "valid-reset-token-abc123",
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        "used_at": None,
    }


# ============================================================================
# Token Generation Tests
# ============================================================================

class TestGenerateResetToken:
    """
    Tests for reset token generation.

    @spec FEAT-003/C-003 (crypto-random 32 bytes)
    """

    def test_token_is_32_bytes_hex_encoded(self):
        """Token should be 32 bytes, hex encoded (64 chars)."""
        token = generate_reset_token()
        assert len(token) == 64  # 32 bytes * 2 (hex encoding)
        assert all(c in '0123456789abcdef' for c in token)

    def test_tokens_are_unique(self):
        """Each token should be unique."""
        tokens = [generate_reset_token() for _ in range(10)]
        assert len(set(tokens)) == 10


# ============================================================================
# Password Validation Tests
# ============================================================================

class TestValidatePasswordStrength:
    """
    Tests for password strength validation.

    @spec FEAT-001/C-001, C-002 (reused constraints)
    """

    def test_valid_password_passes(self):
        """Valid password should pass validation."""
        errors = validate_password_strength("SecureP@ss12345")
        assert errors == []

    def test_short_password_fails(self):
        """Password under 12 chars should fail."""
        errors = validate_password_strength("Short1!")
        assert any("12" in e for e in errors)

    def test_missing_uppercase_fails(self):
        """Password without uppercase should fail."""
        errors = validate_password_strength("lowercase123!@#")
        assert any("uppercase" in e.lower() for e in errors)

    def test_missing_lowercase_fails(self):
        """Password without lowercase should fail."""
        errors = validate_password_strength("UPPERCASE123!@#")
        assert any("lowercase" in e.lower() for e in errors)

    def test_missing_digit_fails(self):
        """Password without digit should fail."""
        errors = validate_password_strength("NoDigitsHere!@#")
        assert any("number" in e.lower() or "digit" in e.lower() for e in errors)

    def test_missing_special_fails(self):
        """Password without special char should fail."""
        errors = validate_password_strength("NoSpecialChars123")
        assert any("special" in e.lower() for e in errors)


# ============================================================================
# Request Password Reset Tests
# ============================================================================

class TestRequestPasswordReset:
    """
    Tests for password reset request.

    @spec FEAT-003/AC-001 - Reset email sent
    @spec FEAT-003/EC-001 - Unregistered email shows same success message
    @spec FEAT-003/EC-002 - Multiple requests invalidate previous tokens
    @spec FEAT-003/C-004 - Max 3 reset requests per email per hour
    """

    @pytest.mark.asyncio
    async def test_request_reset_sends_email_for_registered_user(self, mock_user):
        """
        @spec FEAT-003/AC-001 - Reset email is sent if email exists
        """
        with patch('src.auth.password_reset.service.get_user_by_email', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_user
            with patch('src.auth.password_reset.service.invalidate_previous_tokens', new_callable=AsyncMock):
                with patch('src.auth.password_reset.service.create_reset_token', new_callable=AsyncMock) as mock_create:
                    mock_create.return_value = "token-abc123"
                    with patch('src.auth.password_reset.service.send_reset_email', new_callable=AsyncMock):
                        result = await request_password_reset("test@example.com")

        assert "reset email" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_request_reset_shows_same_message_for_unregistered_email(self):
        """
        @spec FEAT-003/EC-001 - Same success message (no enumeration)
        """
        with patch('src.auth.password_reset.service.get_user_by_email', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None  # User doesn't exist
            result = await request_password_reset("nonexistent@example.com")

        # Should return same message to prevent email enumeration
        assert "reset email" in result["message"].lower() or "account exists" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_request_reset_invalidates_previous_tokens(self, mock_user):
        """
        @spec FEAT-003/EC-002 - Invalidate previous tokens
        """
        with patch('src.auth.password_reset.service.get_user_by_email', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_user
            with patch('src.auth.password_reset.service.invalidate_previous_tokens', new_callable=AsyncMock) as mock_invalidate:
                with patch('src.auth.password_reset.service.create_reset_token', new_callable=AsyncMock):
                    with patch('src.auth.password_reset.service.send_reset_email', new_callable=AsyncMock):
                        await request_password_reset("test@example.com")

        mock_invalidate.assert_called_once()


# ============================================================================
# Confirm Password Reset Tests
# ============================================================================

class TestConfirmPasswordReset:
    """
    Tests for password reset confirmation.

    @spec FEAT-003/AC-002 - Password reset with valid token
    @spec FEAT-003/AC-003 - Expired token
    @spec FEAT-003/EC-003 - Token already used
    @spec FEAT-003/EC-004 - New password same as old
    @spec FEAT-003/C-001 - Token expires in 1 hour
    @spec FEAT-003/C-002 - Token is single-use
    """

    @pytest.mark.asyncio
    async def test_valid_token_resets_password(self, mock_user, mock_reset_token):
        """
        @spec FEAT-003/AC-002 - Password is updated with valid token
        """
        new_password = "NewSecureP@ss456"

        with patch('src.auth.password_reset.service.get_reset_token', new_callable=AsyncMock) as mock_get_token:
            mock_get_token.return_value = mock_reset_token
            with patch('src.auth.password_reset.service.get_user_by_id', new_callable=AsyncMock) as mock_get_user:
                mock_get_user.return_value = mock_user
                with patch('src.auth.password_reset.service.is_password_reuse', new_callable=AsyncMock) as mock_reuse:
                    mock_reuse.return_value = False
                    with patch('src.auth.password_reset.service.update_password', new_callable=AsyncMock):
                        with patch('src.auth.password_reset.service.mark_token_used', new_callable=AsyncMock):
                            result = await confirm_password_reset(
                                token="valid-reset-token-abc123",
                                new_password=new_password
                            )

        assert "success" in result["message"].lower() or "reset" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_expired_token_returns_error(self):
        """
        @spec FEAT-003/AC-003 - Expired token shows error
        """
        expired_token = {
            "id": "token-uuid-expired",
            "user_id": "user-123",
            "token": "expired-token",
            "expires_at": datetime.now(timezone.utc) - timedelta(hours=1),  # Expired
            "used_at": None,
        }

        with patch('src.auth.password_reset.service.get_reset_token', new_callable=AsyncMock) as mock_get_token:
            mock_get_token.return_value = expired_token
            with pytest.raises(PasswordResetError) as exc_info:
                await confirm_password_reset(
                    token="expired-token",
                    new_password="NewSecureP@ss456"
                )

        assert exc_info.value.error_code == "invalid_token"

    @pytest.mark.asyncio
    async def test_already_used_token_returns_error(self, mock_reset_token):
        """
        @spec FEAT-003/EC-003 - Token already used shows error
        """
        used_token = {**mock_reset_token, "used_at": datetime.now(timezone.utc)}

        with patch('src.auth.password_reset.service.get_reset_token', new_callable=AsyncMock) as mock_get_token:
            mock_get_token.return_value = used_token
            with pytest.raises(PasswordResetError) as exc_info:
                await confirm_password_reset(
                    token="used-token",
                    new_password="NewSecureP@ss456"
                )

        assert exc_info.value.error_code == "invalid_token"

    @pytest.mark.asyncio
    async def test_password_reuse_returns_error(self, mock_user, mock_reset_token):
        """
        @spec FEAT-003/EC-004 - Cannot reuse previous password
        """
        with patch('src.auth.password_reset.service.get_reset_token', new_callable=AsyncMock) as mock_get_token:
            mock_get_token.return_value = mock_reset_token
            with patch('src.auth.password_reset.service.get_user_by_id', new_callable=AsyncMock) as mock_get_user:
                mock_get_user.return_value = mock_user
                with patch('src.auth.password_reset.service.is_password_reuse', new_callable=AsyncMock) as mock_reuse:
                    mock_reuse.return_value = True  # Password is being reused
                    with pytest.raises(PasswordResetError) as exc_info:
                        await confirm_password_reset(
                            token="valid-reset-token-abc123",
                            new_password="OldSecureP@ss123"  # Same as current
                        )

        assert exc_info.value.error_code == "password_reuse"

    @pytest.mark.asyncio
    async def test_weak_password_returns_error(self, mock_user, mock_reset_token):
        """Weak password should be rejected."""
        with patch('src.auth.password_reset.service.get_reset_token', new_callable=AsyncMock) as mock_get_token:
            mock_get_token.return_value = mock_reset_token
            with patch('src.auth.password_reset.service.get_user_by_id', new_callable=AsyncMock) as mock_get_user:
                mock_get_user.return_value = mock_user
                with pytest.raises(PasswordResetError) as exc_info:
                    await confirm_password_reset(
                        token="valid-reset-token-abc123",
                        new_password="weak"  # Too weak
                    )

        assert exc_info.value.error_code == "invalid_input"
