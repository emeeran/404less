"""
Email Service Module

@spec Shared infrastructure - email sending

Provides async email sending with template support.
"""

import os
from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass


@dataclass
class EmailMessage:
    """Email message data."""

    to: str
    subject: str
    body: str
    html_body: Optional[str] = None
    from_email: Optional[str] = None


class EmailBackend(ABC):
    """Abstract base class for email backends."""

    @abstractmethod
    async def send(self, message: EmailMessage) -> bool:
        """Send an email message. Returns True on success."""
        pass


class ConsoleEmailBackend(EmailBackend):
    """
    Console email backend for development.

    Prints emails to console instead of sending.
    """

    async def send(self, message: EmailMessage) -> bool:
        """Print email to console."""
        print("\n" + "=" * 60)
        print(f"To: {message.to}")
        print(f"From: {message.from_email or 'noreply@example.com'}")
        print(f"Subject: {message.subject}")
        print("-" * 60)
        print(message.body)
        if message.html_body:
            print("\n[HTML Body]:")
            print(message.html_body)
        print("=" * 60 + "\n")
        return True


class SMTPEmailBackend(EmailBackend):
    """
    SMTP email backend for production.

    @spec FEAT-001/AC-001 - Sends verification email
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 587,
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_tls: bool = True,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls

    async def send(self, message: EmailMessage) -> bool:
        """Send email via SMTP."""
        # TODO: Implement actual SMTP sending with aiosmtplib
        # import aiosmtplib
        # from email.message import EmailMessage as SMTPMessage
        #
        # msg = SMTPMessage()
        # msg["From"] = message.from_email or "noreply@example.com"
        # msg["To"] = message.to
        # msg["Subject"] = message.subject
        # msg.set_content(message.body)
        # if message.html_body:
        #     msg.add_alternative(message.html_body, subtype="html")
        #
        # await aiosmtplib.send(
        #     msg,
        #     hostname=self.host,
        #     port=self.port,
        #     username=self.username,
        #     password=self.password,
        #     start_tls=self.use_tls,
        # )
        raise NotImplementedError("SMTP backend not yet implemented")


class EmailService:
    """
    Email service for sending emails.

    @spec Shared infrastructure
    """

    def __init__(
        self,
        backend: Optional[EmailBackend] = None,
        from_email: str = "noreply@example.com",
        base_url: str = "http://localhost:3000",
    ):
        self.backend = backend or ConsoleEmailBackend()
        self.from_email = from_email
        self.base_url = base_url

    async def send(
        self,
        to: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
    ) -> bool:
        """Send an email."""
        message = EmailMessage(
            to=to,
            subject=subject,
            body=body,
            html_body=html_body,
            from_email=self.from_email,
        )
        return await self.backend.send(message)

    async def send_verification_email(
        self,
        email: str,
        token: str,
        user_id: str,
    ) -> bool:
        """
        Send email verification message.

        @spec FEAT-001/AC-001 - Verification email sent on registration
        @spec FEAT-001/US-002 - User receives verification email
        """
        from .templates import render_template

        verify_url = f"{self.base_url}/verify-email?token={token}"

        body = render_template(
            "verification.txt",
            email=email,
            verify_url=verify_url,
        )

        html_body = render_template(
            "verification.html",
            email=email,
            verify_url=verify_url,
        )

        return await self.send(
            to=email,
            subject="Verify your email address",
            body=body,
            html_body=html_body,
        )

    async def send_password_reset_email(
        self,
        email: str,
        token: str,
    ) -> bool:
        """
        Send password reset email.

        @spec FEAT-003 - Password reset email
        """
        from .templates import render_template

        reset_url = f"{self.base_url}/reset-password?token={token}"

        body = render_template(
            "password_reset.txt",
            email=email,
            reset_url=reset_url,
        )

        return await self.send(
            to=email,
            subject="Reset your password",
            body=body,
        )


# Global email service instance
_email_service: Optional[EmailService] = None


def get_email_service() -> EmailService:
    """
    Get the global email service instance.

    Uses environment variables for configuration:
    - EMAIL_BACKEND: "console" or "smtp" (default: console)
    - EMAIL_FROM: From email address
    - BASE_URL: Base URL for links
    """
    global _email_service

    if _email_service is None:
        backend_name = os.getenv("EMAIL_BACKEND", "console")

        if backend_name == "smtp":
            backend = SMTPEmailBackend(
                host=os.getenv("SMTP_HOST", "localhost"),
                port=int(os.getenv("SMTP_PORT", "587")),
                username=os.getenv("SMTP_USERNAME"),
                password=os.getenv("SMTP_PASSWORD"),
                use_tls=os.getenv("SMTP_USE_TLS", "true").lower() == "true",
            )
        else:
            backend = ConsoleEmailBackend()

        _email_service = EmailService(
            backend=backend,
            from_email=os.getenv("EMAIL_FROM", "noreply@example.com"),
            base_url=os.getenv("BASE_URL", "http://localhost:3000"),
        )

    return _email_service


async def send_email(
    to: str,
    subject: str,
    body: str,
    html_body: Optional[str] = None,
) -> bool:
    """Convenience function to send an email."""
    service = get_email_service()
    return await service.send(to, subject, body, html_body)
