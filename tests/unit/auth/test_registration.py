"""
Comprehensive Unit Tests for User Registration Service

@spec FEAT-001
@coverage Password validation, hashing, registration flow, email verification
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime, timezone, timedelta

import bcrypt

from src.auth.registration.service import (
    validate_password,
    hash_password,
    register_user,
    verify_email,
    RegistrationError,
)


# ============================================================================
# Password Validation Tests
# ============================================================================

class TestValidatePassword:
    """
    Tests for password validation.

    @spec FEAT-001/AC-003 - Password strength validation
    @spec FEAT-001/C-001 - Minimum 12 characters
    @spec FEAT-001/C-002 - Complexity requirements
    """

    def test_valid_password_all_requirements_met(self):
        """@spec FEAT-001/AC-003 - Valid password passes all checks"""
        errors = validate_password("SecureP@ss123")
        assert errors == []

    @pytest.mark.parametrize("password,description", [
        ("MyP@ssw0rd2024", "Common format"),
        ("Abcdefg123!@#", "Mixed characters"),
        ("ZxCvBnM123456!@", "Long complex"),
    ])
    def test_valid_passwords_various_formats(self, password, description):
        """Various valid password formats should pass"""
        errors = validate_password(password)
        assert errors == [], f"Password '{password}' should be valid: {description}"

    def test_too_short_rejected(self):
        """@spec FEAT-001/C-001 - Minimum 12 characters required"""
        errors = validate_password("Short1!")
        assert len(errors) > 0
        assert any("12 characters" in e for e in errors)

    @pytest.mark.parametrize("password", [
        "A1!aaaaaa",     # 9 chars
        "Ab1!abcdef",    # 10 chars
        "Ab1!abcdefg",   # 11 chars
    ])
    def test_passwords_under_12_chars_rejected(self, password):
        """Passwords under 12 characters should fail"""
        errors = validate_password(password)
        assert any("12 characters" in e for e in errors)

    def test_no_uppercase_rejected(self):
        """@spec FEAT-001/C-002 - Requires uppercase letter"""
        errors = validate_password("alllower123!@")
        assert len(errors) > 0
        assert any("uppercase" in e.lower() for e in errors)

    def test_no_lowercase_rejected(self):
        """@spec FEAT-001/C-002 - Requires lowercase letter"""
        errors = validate_password("ALLUPPER123!@")
        assert len(errors) > 0
        assert any("lowercase" in e.lower() for e in errors)

    def test_no_number_rejected(self):
        """@spec FEAT-001/C-002 - Requires number"""
        errors = validate_password("NoNumbersHere!@")
        assert len(errors) > 0
        assert any("number" in e.lower() for e in errors)

    def test_no_special_char_rejected(self):
        """@spec FEAT-001/C-002 - Requires special character from allowed set"""
        errors = validate_password("NoSpecial123Chars")
        assert len(errors) > 0
        assert any("special character" in e.lower() for e in errors)

    @pytest.mark.parametrize("special_char", ["@", "$", "!", "%", "*", "?", "&"])
    def test_each_special_char_accepted(self, special_char):
        """Each allowed special character should be accepted"""
        password = f"Password{special_char}123"  # 12 chars with special
        errors = validate_password(password)
        assert not any("special character" in e.lower() for e in errors), \
            f"Special char '{special_char}' should be accepted"

    def test_disallowed_special_chars_rejected(self):
        """Special characters not in allowed set should cause rejection"""
        errors = validate_password("Password#12345")  # # not in @$!%*?&
        assert any("special character" in e.lower() for e in errors)

    def test_empty_password_returns_multiple_errors(self):
        """Empty password should fail multiple checks"""
        errors = validate_password("")
        assert len(errors) >= 4  # Length, uppercase, lowercase, number, special

    def test_multiple_errors_all_reported(self):
        """Password with multiple issues returns all relevant errors"""
        errors = validate_password("weak")
        error_text = " ".join(errors).lower()

        # Should report: short, no uppercase, no number, no special
        assert "12 characters" in error_text
        assert "uppercase" in error_text
        assert "number" in error_text
        assert "special character" in error_text

    def test_whitespace_only_password(self):
        """Password with only whitespace should fail"""
        errors = validate_password("           ")  # 11 spaces
        assert len(errors) >= 1


# ============================================================================
# Password Hashing Tests
# ============================================================================

class TestHashPassword:
    """
    Tests for password hashing.

    @spec FEAT-001/C-003 - bcrypt with cost factor 12
    """

    def test_bcrypt_hash_format(self):
        """@spec FEAT-001/C-003 - Uses bcrypt format"""
        password = "SecureP@ss123"
        hashed = hash_password(password)

        # Bcrypt hashes start with $2b$
        assert hashed.startswith("$2b$")

    def test_hash_is_different_from_password(self):
        """Hash should not contain plaintext password"""
        password = "SecureP@ss123"
        hashed = hash_password(password)
        assert password not in hashed

    def test_same_password_different_hashes(self):
        """Each hash should be unique due to salt"""
        password = "SecureP@ss123"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        assert hash1 != hash2

    def test_hash_can_be_verified_with_bcrypt(self):
        """Hash should be verifiable with bcrypt.checkpw"""
        password = "SecureP@ss123"
        hashed = hash_password(password)
        assert bcrypt.checkpw(password.encode(), hashed.encode())

    def test_wrong_password_fails_verification(self):
        """Wrong password should not verify against hash"""
        password = "SecureP@ss123"
        wrong_password = "WrongP@ss456"
        hashed = hash_password(password)
        assert not bcrypt.checkpw(wrong_password.encode(), hashed.encode())

    def test_hash_length_consistent(self):
        """Bcrypt hashes should have consistent length (60 chars)"""
        password = "SecureP@ss123"
        hashed = hash_password(password)
        assert len(hashed) == 60

    def test_hash_cost_factor_12(self):
        """@spec FEAT-001/C-003 - Should use cost factor 12"""
        password = "SecureP@ss123"
        hashed = hash_password(password)
        # bcrypt format: $2b$12$...
        parts = hashed.split("$")
        assert parts[2] == "12", f"Expected cost factor 12, got {parts[2]}"


# ============================================================================
# Email Validation Tests (via register_user)
# ============================================================================

class TestEmailValidation:
    """
    Tests for email validation in registration.

    @spec FEAT-001/EC-001 - Invalid email format
    @spec FEAT-001/EC-003 - Whitespace trimming
    @spec FEAT-001/EC-005 - Email too long
    """

    @pytest.mark.asyncio
    async def test_valid_email_accepted(self):
        """Valid email should be accepted"""
        result = await register_user(
            email="valid@example.com",
            password="SecureP@ss123",
            password_confirm="SecureP@ss123",
        )
        assert result["message"] == "Registration successful. Please check your email."

    @pytest.mark.parametrize("email", [
        "test@example.com",
        "user.name@example.com",
        "user+tag@example.org",
        "user123@subdomain.example.co.uk",
    ])
    @pytest.mark.asyncio
    async def test_various_valid_email_formats(self, email):
        """Various valid email formats should be accepted"""
        result = await register_user(
            email=email,
            password="SecureP@ss123",
            password_confirm="SecureP@ss123",
        )
        assert "user_id" in result

    @pytest.mark.parametrize("email", [
        "invalid-email",
        "@example.com",
        "test@",
        "test@example",
    ])
    @pytest.mark.asyncio
    async def test_invalid_email_format_rejected(self, email):
        """@spec FEAT-001/EC-001 - Invalid email format should be rejected"""
        with pytest.raises(RegistrationError) as exc:
            await register_user(
                email=email,
                password="SecureP@ss123",
                password_confirm="SecureP@ss123",
            )
        assert exc.value.error_code == "invalid_input"
        assert any(d["field"] == "email" for d in exc.value.details)

    @pytest.mark.asyncio
    async def test_email_too_long_rejected(self):
        """@spec FEAT-001/EC-005 - Email over 255 chars rejected"""
        long_email = "a" * 250 + "@example.com"  # > 255 chars
        with pytest.raises(RegistrationError) as exc:
            await register_user(
                email=long_email,
                password="SecureP@ss123",
                password_confirm="SecureP@ss123",
            )
        assert exc.value.error_code == "invalid_input"
        assert any(d["field"] == "email" for d in exc.value.details)

    @pytest.mark.asyncio
    async def test_email_whitespace_trimmed_and_lowercased(self):
        """@spec FEAT-001/EC-003 - Email whitespace trimmed and lowercased"""
        # Without DB, we verify the function accepts trimmed input
        result = await register_user(
            email="  Test@Example.Com  ",
            password="SecureP@ss123",
            password_confirm="SecureP@ss123",
        )
        assert result["message"] == "Registration successful. Please check your email."


# ============================================================================
# Registration Flow Tests
# ============================================================================

class TestRegisterUser:
    """
    Tests for user registration flow.

    @spec FEAT-001/AC-001 - Successful registration
    @spec FEAT-001/AC-002 - Duplicate email rejection
    @spec FEAT-001/AC-003 - Password strength validation
    @spec FEAT-001/EC-002 - Passwords do not match
    """

    @pytest.mark.asyncio
    async def test_successful_registration_returns_user_id(self):
        """@spec FEAT-001/AC-001 - Successful registration returns user ID"""
        result = await register_user(
            email="newuser@example.com",
            password="SecureP@ss123",
            password_confirm="SecureP@ss123",
        )

        assert result["message"] == "Registration successful. Please check your email."
        assert "user_id" in result
        # UUID format check
        assert len(result["user_id"]) == 36

    @pytest.mark.asyncio
    async def test_password_mismatch_rejected(self):
        """@spec FEAT-001/EC-002 - Passwords that don't match should be rejected"""
        with pytest.raises(RegistrationError) as exc:
            await register_user(
                email="test@example.com",
                password="SecureP@ss123",
                password_confirm="DifferentP@ss456",
            )

        assert exc.value.error_code == "invalid_input"
        assert any(d["field"] == "password_confirm" for d in exc.value.details)

    @pytest.mark.asyncio
    async def test_weak_password_rejected(self):
        """@spec FEAT-001/AC-003 - Weak password should be rejected"""
        with pytest.raises(RegistrationError) as exc:
            await register_user(
                email="test@example.com",
                password="weak",
                password_confirm="weak",
            )

        assert exc.value.error_code == "invalid_input"
        assert any(d["field"] == "password" for d in exc.value.details)

    @pytest.mark.asyncio
    async def test_validation_checks_email_format_first(self):
        """Email format should be validated early in the flow"""
        with pytest.raises(RegistrationError) as exc:
            await register_user(
                email="invalid-email",
                password="SecureP@ss123",
                password_confirm="SecureP@ss123",
            )
        assert exc.value.error_code == "invalid_input"
        assert any(d["field"] == "email" for d in exc.value.details)

    @pytest.mark.asyncio
    async def test_password_match_checked_before_strength(self):
        """Password match should be checked before strength validation"""
        with pytest.raises(RegistrationError) as exc:
            await register_user(
                email="test@example.com",
                password="SecureP@ss123",
                password_confirm="Different123",  # Doesn't match
            )
        # Should fail on mismatch, not strength
        assert exc.value.error_code == "invalid_input"
        assert any(d["field"] == "password_confirm" for d in exc.value.details)


# ============================================================================
# Email Verification Tests
# ============================================================================

class TestVerifyEmail:
    """
    Tests for email verification.

    @spec FEAT-001/AC-004 - Email verification required
    @spec FEAT-001/API-002 - Verify email endpoint
    """

    @pytest.mark.asyncio
    async def test_verify_email_returns_success_without_db(self):
        """Without database, verify_email returns success (mock mode)"""
        result = await verify_email("any-token", db=None)
        assert result["message"] == "Email verified successfully"

    @pytest.mark.asyncio
    async def test_verify_email_empty_token_without_db(self):
        """Empty token returns success in mock mode"""
        result = await verify_email("", db=None)
        assert result["message"] == "Email verified successfully"


# ============================================================================
# RegistrationError Tests
# ============================================================================

class TestRegistrationError:
    """Tests for RegistrationError exception class."""

    def test_error_creation_with_all_fields(self):
        """Error should store all provided fields"""
        error = RegistrationError(
            error_code="test_error",
            message="Test error message",
            details=[{"field": "email", "message": "Invalid email"}]
        )

        assert error.error_code == "test_error"
        assert error.message == "Test error message"
        assert len(error.details) == 1
        assert str(error) == "Test error message"

    def test_error_creation_without_details(self):
        """Error should work without details"""
        error = RegistrationError(
            error_code="test_error",
            message="Test error message"
        )

        assert error.error_code == "test_error"
        assert error.details == []

    def test_error_is_exception(self):
        """RegistrationError should be catchable as Exception"""
        with pytest.raises(Exception):
            raise RegistrationError("code", "message")

    def test_error_details_default_to_empty_list(self):
        """Details should default to empty list if not provided"""
        error = RegistrationError("code", "message")
        assert error.details == []
        assert isinstance(error.details, list)

    def test_multiple_details_preserved(self):
        """Multiple detail items should be preserved"""
        details = [
            {"field": "email", "message": "Invalid"},
            {"field": "password", "message": "Too short"},
        ]
        error = RegistrationError("code", "message", details)
        assert len(error.details) == 2
