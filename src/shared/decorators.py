"""
Error Handling Decorators

@spec Shared infrastructure - route error handling

Provides decorators to convert service errors to HTTP exceptions,
reducing boilerplate in route handlers.
"""

from functools import wraps
from typing import Callable, Dict, Optional, Any

from fastapi import HTTPException, status


# Default error code to HTTP status mapping
DEFAULT_ERROR_STATUS_MAP: Dict[str, int] = {
    "not_found": status.HTTP_404_NOT_FOUND,
    "invalid_url": status.HTTP_400_BAD_REQUEST,
    "invalid_format": status.HTTP_400_BAD_REQUEST,
    "invalid_input": status.HTTP_400_BAD_REQUEST,
    "invalid_credentials": status.HTTP_401_UNAUTHORIZED,
    "unauthorized": status.HTTP_401_UNAUTHORIZED,
    "forbidden": status.HTTP_403_FORBIDDEN,
    "email_not_verified": status.HTTP_403_FORBIDDEN,
    "account_locked": status.HTTP_423_LOCKED,
    "email_exists": status.HTTP_409_CONFLICT,
    "conflict": status.HTTP_409_CONFLICT,
    "rate_limited": status.HTTP_429_TOO_MANY_REQUESTS,
}


class ServiceError(Exception):
    """
    Base exception for service-layer errors.

    Attributes:
        error_code: Machine-readable error identifier
        message: Human-readable error message
        details: Optional additional details
    """

    def __init__(
        self,
        error_code: str,
        message: str,
        details: Optional[Any] = None,
    ):
        self.error_code = error_code
        self.message = message
        self.details = details
        super().__init__(message)


def handle_service_errors(
    error_status_map: Optional[Dict[str, int]] = None,
    default_status: int = status.HTTP_400_BAD_REQUEST,
):
    """
    Decorator that converts ServiceError exceptions to HTTPException.

    Reduces boilerplate in route handlers by centralizing error handling.

    Args:
        error_status_map: Custom mapping of error codes to HTTP status codes
        default_status: Default HTTP status for unmapped error codes

    Usage:
        @router.post("/endpoint")
        @handle_service_errors()
        async def my_endpoint(...):
            result = await service.do_something()
            return result

        # With custom mapping:
        @handle_service_errors({"custom_error": 422})
        async def custom_endpoint(...):
            ...

    Returns:
        Decorated function that handles ServiceError exceptions
    """
    status_map = {**DEFAULT_ERROR_STATUS_MAP, **(error_status_map or {})}

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except ServiceError as e:
                http_status = status_map.get(e.error_code, default_status)

                detail: Dict[str, Any] = {
                    "error": e.error_code,
                    "message": e.message,
                }

                if e.details is not None:
                    detail["details"] = e.details

                raise HTTPException(
                    status_code=http_status,
                    detail=detail,
                )

        return wrapper

    return decorator


def handle_errors(
    *error_classes: type,
    error_status_map: Optional[Dict[str, int]] = None,
    default_status: int = status.HTTP_400_BAD_REQUEST,
):
    """
    Generic decorator for handling multiple exception types.

    More flexible version that can handle any exception type with
    error_code and message attributes.

    Args:
        *error_classes: Exception classes to catch
        error_status_map: Custom mapping of error codes to HTTP status codes
        default_status: Default HTTP status for unmapped error codes

    Usage:
        @handle_errors(RegistrationError, LoginError)
        async def endpoint(...):
            ...
    """
    status_map = {**DEFAULT_ERROR_STATUS_MAP, **(error_status_map or {})}

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except error_classes as e:
                error_code = getattr(e, "error_code", "unknown_error")
                message = getattr(e, "message", str(e))
                details = getattr(e, "details", None)

                http_status = status_map.get(error_code, default_status)

                detail: Dict[str, Any] = {
                    "error": error_code,
                    "message": message,
                }

                if details is not None:
                    detail["details"] = details

                raise HTTPException(
                    status_code=http_status,
                    detail=detail,
                )

        return wrapper

    return decorator
