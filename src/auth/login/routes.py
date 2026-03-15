"""
User Login Routes

@spec FEAT-002
@api_endpoints API-001, API-002, API-003
"""

from pydantic import BaseModel, EmailStr, Field
from fastapi import APIRouter, HTTPException, Request, status, Body
from slowapi import Limiter
from slowapi.util import get_remote_address

from .service import (
    authenticate_user,
    refresh_access_token,
    logout_user,
    LoginError,
)

router = APIRouter(prefix="/auth", tags=["Auth"])
limiter = Limiter(key_func=get_remote_address)


# @spec FEAT-002/API-001 - Request/Response models
class LoginRequest(BaseModel):
    """Login request body."""
    email: EmailStr
    password: str = Field(..., min_length=1)


class RefreshTokenRequest(BaseModel):
    """Refresh token request body."""
    refresh_token: str


class LogoutRequest(BaseModel):
    """Logout request body."""
    session_id: str


@router.post("/login")
@limiter.limit("20/minute")  # @spec FEAT-002/C-005 - Rate limit 20 per minute per IP
async def login(request: Request, body: LoginRequest = Body(...)):
    """
    Authenticate user and return tokens.

    @spec FEAT-002/API-001
    """
    try:
        # Get client IP for logging
        client_ip = get_remote_address(request)

        result = await authenticate_user(
            email=body.email,
            password=body.password,
            ip_address=client_ip
        )
        return result
    except LoginError as e:
        if e.error_code == "invalid_credentials":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": e.error_code, "message": e.message},
            )
        elif e.error_code == "email_not_verified":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": e.error_code, "message": e.message},
            )
        elif e.error_code == "account_locked":
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail={"error": e.error_code, "message": e.message},
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": e.error_code, "message": e.message},
        )


@router.post("/refresh")
async def refresh(body: RefreshTokenRequest = Body(...)):
    """
    Refresh access token.

    @spec FEAT-002/API-002
    """
    try:
        result = await refresh_access_token(body.refresh_token)
        return result
    except LoginError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": e.error_code, "message": e.message},
        )


@router.post("/logout")
async def logout(body: LogoutRequest = Body(...)):
    """
    Logout user and revoke session.

    @spec FEAT-002/API-003
    """
    await logout_user(body.session_id)
    return {"message": "Logged out successfully"}
