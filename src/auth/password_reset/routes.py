"""
Password Reset Routes

@spec FEAT-003
@api_endpoints API-001, API-002
"""

from pydantic import BaseModel, EmailStr, Field
from fastapi import APIRouter, HTTPException, Request, status, Body
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.shared.config import RATE_LIMIT_PASSWORD_RESET
from .service import (
    request_password_reset,
    confirm_password_reset,
    PasswordResetError,
)

router = APIRouter(prefix="/auth/password-reset", tags=["Auth"])
limiter = Limiter(key_func=get_remote_address)


# @spec FEAT-003/API-001 - Request models
class PasswordResetRequest(BaseModel):
    """Password reset request body."""
    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    """Password reset confirmation body."""
    token: str
    new_password: str = Field(..., min_length=12)


@router.post("/request")
@limiter.limit(RATE_LIMIT_PASSWORD_RESET)  # @spec FEAT-003/C-004 - Configurable rate limit
async def request_reset(request: Request, body: PasswordResetRequest = Body(...)):
    """
    Request a password reset email.

    @spec FEAT-003/API-001
    """
    result = await request_password_reset(body.email)
    return result


@router.post("/confirm")
async def confirm_reset(body: PasswordResetConfirmRequest = Body(...)):
    """
    Confirm password reset with token.

    @spec FEAT-003/API-002
    """
    try:
        result = await confirm_password_reset(body.token, body.new_password)
        return result
    except PasswordResetError as e:
        if e.error_code == "invalid_token":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": e.error_code, "message": e.message},
            )
        elif e.error_code == "password_reuse":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": e.error_code, "message": e.message},
            )
        elif e.error_code == "invalid_input":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": e.error_code, "message": e.message, "details": e.details},
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": e.error_code, "message": e.message},
        )
