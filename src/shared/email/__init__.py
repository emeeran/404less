"""
Shared Email Module

Provides email sending capabilities for the application.
"""

from .service import EmailService, get_email_service, send_email
from .templates import render_template

__all__ = [
    "EmailService",
    "get_email_service",
    "send_email",
    "render_template",
]
