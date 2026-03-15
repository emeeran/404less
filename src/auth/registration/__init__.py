"""
Auth Registration Module

@spec FEAT-001
"""

from .service import register_user, verify_email, RegistrationError
from .routes import router

__all__ = ["register_user", "verify_email", "RegistrationError", "router"]
