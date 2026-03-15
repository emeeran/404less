"""
User Registration Routes

@spec FEAT-001
@api_endpoints API-001, API-002
"""

from pydantic import BaseModel, EmailStr, Field
from fastapi import APIRouter, HTTPException, Request, status, Body
from slowapi import Limiter
from slowapi.util import get_remote_address

from .service import register_user, verify_email, RegistrationError

router = APIRouter(prefix="/auth", tags=["Auth"])
limiter = Limiter(key_func=get_remote_address)


# @spec FEAT-001/API-001 - Request/Response models
class RegisterRequest(BaseModel):
    """Registration request body."""
    email: EmailStr
    password: str = Field(..., min_length=12)
    password_confirm: str = Field(..., min_length=12)


class VerifyEmailRequest(BaseModel):
    """Email verification request body."""
    token: str


@router.post("/register", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/hour")  # @spec FEAT-001/C-005 - Rate limit 5 per hour per IP
async def register(request: Request, body: RegisterRequest = Body(...)):
    """
    Register a new user.

    @spec FEAT-001/API-001
    """
    try:
        result = await register_user(body.email, body.password, body.password_confirm)
        return result
    except RegistrationError as e:
        if e.error_code == "email_exists":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
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


@router.post("/verify-email")
async def verify_email_endpoint(body: VerifyEmailRequest = Body(...)):
    """
    Verify user's email address.

    @spec FEAT-001/API-002
    """
    try:
        result = await verify_email(body.token)
        return result
    except RegistrationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": e.error_code, "message": e.message},
        )
