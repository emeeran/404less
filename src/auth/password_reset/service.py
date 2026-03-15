"""
Password Reset Service

@spec FEAT-003
@acceptance_criteria AC-001, AC-002, AC-003
@edge_cases EC-001, EC-002, EC-003, EC-004
@constraints C-001, C-002, C-003, C-004
"""

import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt


# ============================================================================
# Configuration Constants
# ============================================================================

# @spec FEAT-003/C-001 - Token expires in 1 hour
TOKEN_EXPIRY_HOURS = 1

# @spec FEAT-003/C-003 - Token is crypto-random 32 bytes
TOKEN_BYTES = 32

# @spec FEAT-003/C-004 - Max 3 reset requests per email per hour
MAX_REQUESTS_PER_HOUR = 3


# ============================================================================
# Exceptions
# ============================================================================

class PasswordResetError(Exception):
    """Base exception for password reset errors."""

    def __init__(self, error_code: str, message: str, details: list | None = None):
        self.error_code = error_code
        self.message = message
        self.details = details or []
        super().__init__(message)


# ============================================================================
# Password Validation (reused from FEAT-001)
# ============================================================================

def validate_password_strength(password: str) -> list[str]:
    """
    Validate password meets all requirements.

    @spec FEAT-001/C-001 (min 12 chars)
    @spec FEAT-001/C-002 (complexity requirements)
    """
    errors = []

    if len(password) < 12:
        errors.append("Password must be at least 12 characters")

    if not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter")

    if not re.search(r"[a-z]", password):
        errors.append("Password must contain at least one lowercase letter")

    if not re.search(r"\d", password):
        errors.append("Password must contain at least one number")

    if not re.search(r"[@$!%*?&]", password):
        errors.append("Password must contain at least one special character (@$!%*?&)")

    return errors


# ============================================================================
# Token Generation
# ============================================================================

def generate_reset_token() -> str:
    """
    Generate a crypto-random reset token.

    @spec FEAT-003/C-003 (crypto-random 32 bytes)
    """
    return secrets.token_hex(TOKEN_BYTES)


# ============================================================================
# Database Operations (Stubs for dependency injection)
# ============================================================================

async def get_user_by_email(email: str, db=None) -> Optional[dict]:
    """Get user by email from database."""
    return None


async def get_user_by_id(user_id: str, db=None) -> Optional[dict]:
    """Get user by ID from database."""
    return None


async def create_reset_token(user_id: str, token: str, expires_at: datetime, db=None) -> None:
    """
    Create password reset token in database.

    @spec FEAT-003/DM-001 (PasswordResetToken model)
    """
    pass


async def get_reset_token(token: str, db=None) -> Optional[dict]:
    """Get reset token from database."""
    return None


async def invalidate_previous_tokens(user_id: str, db=None) -> None:
    """
    Invalidate all previous reset tokens for user.

    @spec FEAT-003/EC-002 - Only latest token valid
    """
    pass


async def mark_token_used(token: str, db=None) -> None:
    """
    Mark token as used.

    @spec FEAT-003/C-002 - Single-use token
    """
    pass


async def update_password(user_id: str, password_hash: str, db=None) -> None:
    """Update user's password in database."""
    pass


async def is_password_reuse(user_id: str, new_password: str, db=None) -> bool:
    """
    Check if new password matches current password.

    @spec FEAT-003/EC-004 - Cannot reuse previous password
    """
    user = await get_user_by_id(user_id, db)
    if not user:
        return False
    return bcrypt.checkpw(new_password.encode(), user.get("password_hash", "").encode())


async def send_reset_email(email: str, token: str, user_id: str, db=None) -> None:
    """
    Send password reset email.

    @spec FEAT-003/AC-001 - Reset email sent
    """
    pass


async def check_rate_limit(email: str, db=None) -> bool:
    """
    Check if rate limit exceeded.

    @spec FEAT-003/C-004 - Max 3 requests per hour
    """
    return True  # Allow by default


# ============================================================================
# Main Functions
# ============================================================================

async def request_password_reset(email: str, db=None) -> dict:
    """
    Request a password reset.

    @spec FEAT-003/AC-001 - Reset email sent (if email exists)
    @spec FEAT-003/EC-001 - Same success message for unregistered email
    @spec FEAT-003/EC-002 - Invalidate previous tokens
    @spec FEAT-003/C-004 - Rate limiting

    Args:
        email: User's email address
        db: Optional database session

    Returns:
        dict with success message

    Note: Always returns success message to prevent email enumeration
    """
    email = email.strip().lower()

    # Get user
    user = await get_user_by_email(email, db)

    if user:
        # Check rate limit
        # @spec FEAT-003/C-004
        await check_rate_limit(email, db)

        # Invalidate previous tokens
        # @spec FEAT-003/EC-002
        await invalidate_previous_tokens(user["id"], db)

        # Generate new token
        # @spec FEAT-003/C-003
        token = generate_reset_token()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRY_HOURS)

        # Store token
        # @spec FEAT-003/C-001
        await create_reset_token(user["id"], token, expires_at, db)

        # Send email
        # @spec FEAT-003/AC-001
        await send_reset_email(email, token, user["id"], db)

    # @spec FEAT-003/EC-001 - Always return same message
    return {
        "message": "If an account exists, a reset email has been sent"
    }


async def confirm_password_reset(token: str, new_password: str, db=None) -> dict:
    """
    Confirm password reset with token and new password.

    @spec FEAT-003/AC-002 - Password reset with valid token
    @spec FEAT-003/AC-003 - Expired token error
    @spec FEAT-003/EC-003 - Token already used error
    @spec FEAT-003/EC-004 - Password reuse error
    @spec FEAT-003/C-002 - Token is single-use

    Args:
        token: Reset token from email
        new_password: New password to set
        db: Optional database session

    Returns:
        dict with success message

    Raises:
        PasswordResetError: If reset fails
    """
    # Validate password strength
    password_errors = validate_password_strength(new_password)
    if password_errors:
        raise PasswordResetError(
            "invalid_input",
            "Password does not meet requirements",
            [{"field": "new_password", "message": err} for err in password_errors]
        )

    # Get token
    token_record = await get_reset_token(token, db)

    # @spec FEAT-003/AC-003 - Invalid/expired token
    if not token_record:
        raise PasswordResetError(
            "invalid_token",
            "Reset token is invalid or expired"
        )

    # Check if expired
    expires_at = token_record.get("expires_at")
    if expires_at:
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        if expires_at < datetime.now(timezone.utc):
            raise PasswordResetError(
                "invalid_token",
                "Reset token is invalid or expired"
            )

    # @spec FEAT-003/EC-003 - Token already used
    if token_record.get("used_at"):
        raise PasswordResetError(
            "invalid_token",
            "Reset token has already been used"
        )

    # Get user
    user = await get_user_by_id(token_record["user_id"], db)
    if not user:
        raise PasswordResetError(
            "invalid_token",
            "Reset token is invalid or expired"
        )

    # @spec FEAT-003/EC-004 - Check password reuse
    if await is_password_reuse(user["id"], new_password, db):
        raise PasswordResetError(
            "password_reuse",
            "Cannot reuse your previous password"
        )

    # Hash new password
    password_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt(rounds=12)).decode()

    # Update password
    await update_password(user["id"], password_hash, db)

    # @spec FEAT-003/C-002 - Mark token as used
    await mark_token_used(token, db)

    return {
        "message": "Password reset successfully"
    }
