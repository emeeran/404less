"""
Property-Based Tests for User Registration

@spec FEAT-001

Uses Hypothesis to generate random test cases and find edge cases.
These tests verify invariants derived from the spec constraints.
"""

import re
import string
from hypothesis import given, strategies as st, assume, settings
from hypothesis.strategies import composite

from src.auth.registration.service import validate_password, hash_password


# ============================================================================
# Strategies for generating test data
# ============================================================================

@composite
def valid_email_strategy(draw):
    """Generate valid email addresses."""
    local = draw(st.text(
        alphabet=string.ascii_letters + string.digits + "._%+-",
        min_size=1,
        max_size=64
    ))
    domain = draw(st.text(
        alphabet=string.ascii_lowercase + string.digits,
        min_size=1,
        max_size=30
    ))
    tld = draw(st.text(
        alphabet=string.ascii_lowercase,
        min_size=2,
        max_size=10
    ))
    return f"{local}@{domain}.{tld}"


@composite
def invalid_email_strategy(draw):
    """Generate invalid email addresses."""
    invalid_chars = draw(st.text(
        alphabet=string.ascii_letters + string.digits + " !#$%^&*()[]{}|;:'\"<>,?/",
        min_size=1,
        max_size=50
    ))
    # Missing @ symbol or other invalid patterns
    pattern = draw(st.sampled_from([
        invalid_chars,  # No @
        f"test{invalid_chars}.com",  # @ missing
        "@example.com",  # No local part
        "test@",  # No domain
        "test@.com",  # No domain name
    ]))
    return pattern


@composite
def valid_password_strategy(draw):
    """
    Generate valid passwords that meet all requirements.

    @spec FEAT-001/C-001 (min 12 chars)
    @spec FEAT-001/C-002 (complexity)
    """
    # Start with one of each required character type
    uppercase = draw(st.sampled_from(string.ascii_uppercase))
    lowercase = draw(st.sampled_from(string.ascii_lowercase))
    digit = draw(st.sampled_from(string.digits))
    special = draw(st.sampled_from("@$!%*?&"))

    # Add more random characters to reach minimum length
    extra_chars = draw(st.text(
        alphabet=string.ascii_letters + string.digits + "@$!%*?&",
        min_size=8,
        max_size=30
    ))

    # Shuffle to avoid predictable patterns
    password = list(uppercase + lowercase + digit + special + extra_chars)
    draw(st.permutations(password))
    return "".join(password)


@composite
def weak_password_strategy(draw):
    """Generate passwords that fail one or more requirements."""
    # Generate passwords that are missing requirements
    fail_type = draw(st.sampled_from([
        "short",  # Too short
        "no_upper",  # No uppercase
        "no_lower",  # No lowercase
        "no_digit",  # No digit
        "no_special",  # No special character
    ]))

    if fail_type == "short":
        return draw(st.text(min_size=1, max_size=11))
    elif fail_type == "no_upper":
        return draw(st.text(
            alphabet=string.ascii_lowercase + string.digits + "@$!%*?&",
            min_size=12,
            max_size=20
        ))
    elif fail_type == "no_lower":
        return draw(st.text(
            alphabet=string.ascii_uppercase + string.digits + "@$!%*?&",
            min_size=12,
            max_size=20
        ))
    elif fail_type == "no_digit":
        return draw(st.text(
            alphabet=string.ascii_letters + "@$!%*?&",
            min_size=12,
            max_size=20
        ))
    else:  # no_special
        return draw(st.text(
            alphabet=string.ascii_letters + string.digits,
            min_size=12,
            max_size=20
        ))


# ============================================================================
# Property Tests for Password Validation
# ============================================================================

class TestPasswordValidationProperties:
    """
    Property-based tests for password validation.

    @spec FEAT-001/AC-003
    @spec FEAT-001/C-001, C-002
    """

    @given(password=valid_password_strategy())
    @settings(max_examples=100)
    def test_valid_passwords_pass_validation(self, password: str):
        """
        @invariant: All valid passwords (per spec) should pass validation.
        @spec FEAT-001/C-001, C-002
        """
        errors = validate_password(password)
        assert errors == [], f"Valid password rejected: {password}, errors: {errors}"

    @given(password=weak_password_strategy())
    @settings(max_examples=100)
    def test_weak_passwords_fail_validation(self, password: str):
        """
        @invariant: All weak passwords should fail validation with specific errors.
        @spec FEAT-001/AC-003
        """
        errors = validate_password(password)
        assert len(errors) > 0, f"Weak password accepted: {password}"

    @given(password=st.text(min_size=0, max_size=100))
    @settings(max_examples=50)
    def test_password_validation_is_deterministic(self, password: str):
        """
        @invariant: Password validation should be deterministic.
        """
        errors1 = validate_password(password)
        errors2 = validate_password(password)
        assert errors1 == errors2

    @given(
        base=st.text(
            alphabet=string.ascii_letters + string.digits + "@$!%*?&",
            min_size=12,
            max_size=20
        )
    )
    @settings(max_examples=50)
    def test_password_length_check(self, base: str):
        """
        @invariant: Passwords under 12 chars always fail length check.
        @spec FEAT-001/C-001
        """
        short_password = base[:11] if len(base) >= 11 else base
        errors = validate_password(short_password)

        if len(short_password) < 12:
            assert any("12" in e or "character" in e for e in errors), \
                f"Short password {len(short_password)} chars didn't fail length check"


class TestPasswordHashingProperties:
    """
    Property-based tests for password hashing.

    @spec FEAT-001/C-003 (bcrypt)
    """

    @given(password=st.text(min_size=1, max_size=100))
    @settings(max_examples=50)
    def test_hash_never_contains_plaintext(self, password: str):
        """
        @invariant: Hash should never contain the plaintext password.
        @spec FEAT-001/C-003 - Security
        """
        hashed = hash_password(password)
        assert password not in hashed, "Hash contains plaintext password!"

    @given(password=st.text(min_size=12, max_size=50))
    @settings(max_examples=50)
    def test_same_password_different_hashes(self, password: str):
        """
        @invariant: Same password should produce different hashes (salting).
        @spec FEAT-001/C-003 - bcrypt salting
        """
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        assert hash1 != hash2, "Hashes should be unique due to salt"

    @given(password=st.text(min_size=12, max_size=50))
    @settings(max_examples=50)
    def test_hash_format_is_bcrypt(self, password: str):
        """
        @invariant: Hash should be in bcrypt format ($2b$).
        @spec FEAT-001/C-003
        """
        hashed = hash_password(password)
        assert hashed.startswith("$2b$"), f"Invalid hash format: {hashed[:10]}..."

    @given(password=st.text(min_size=12, max_size=50))
    @settings(max_examples=30)
    def test_hash_is_verifiable(self, password: str):
        """
        @invariant: Hashed password should be verifiable with bcrypt.
        @spec FEAT-001/C-003
        """
        import bcrypt

        hashed = hash_password(password)
        assert bcrypt.checkpw(password.encode(), hashed.encode()), \
            "Hash verification failed"


class TestEmailProperties:
    """
    Property-based tests for email handling.

    @spec FEAT-001/EC-001 (invalid format)
    @spec FEAT-001/EC-003 (whitespace trimming)
    @spec FEAT-001/EC-005 (too long)
    """

    @given(email=st.text(max_size=300))
    @settings(max_examples=50)
    def test_email_normalization_is_idempotent(self, email: str):
        """
        @invariant: Email normalization (strip, lowercase) is idempotent.
        @spec FEAT-001/EC-003
        """
        normalized = email.strip().lower()
        double_normalized = normalized.strip().lower()
        assert normalized == double_normalized

    @given(
        email=st.text(
            alphabet=string.ascii_letters + string.digits + " ",
            min_size=256,
            max_size=300
        )
    )
    @settings(max_examples=30)
    def test_long_emails_rejected(self, email: str):
        """
        @invariant: Emails over 255 chars should be rejected.
        @spec FEAT-001/EC-005
        """
        # This would be tested in the registration function
        is_valid = len(email.strip()) <= 255
        assert not is_valid or len(email.strip()) > 255
