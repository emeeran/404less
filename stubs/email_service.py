"""
Email Service Stub

@spec FEAT-001, FEAT-003
@stubs-first-builder

This is a stub interface for the email service.
Replace with actual implementation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class EmailMessage:
    """Email message structure. @spec FEAT-001"""

    to: str
    subject: str
    body: str
    html_body: Optional[str] = None
    from_email: Optional[str] = None


class EmailServiceInterface(ABC):
    """
    Interface for email service.

    @spec FEAT-001 - Registration verification emails
    @spec FEAT-003 - Password reset emails
    """

    @abstractmethod
    async def send_email(self, message: EmailMessage) -> bool:
        """
        Send an email.

        Args:
            message: Email message to send

        Returns:
            True if email was sent successfully

        Raises:
            EmailServiceError: If email fails to send
        """
        pass

    @abstractmethod
    async def send_verification_email(
        self, email: str, token: str, verification_url: str
    ) -> bool:
        """
        Send verification email.

        @spec FEAT-001/AC-001

        Args:
            email: Recipient email
            token: Verification token
            verification_url: Base URL for verification

        Returns:
            True if sent successfully
        """
        pass

    @abstractmethod
    async def send_password_reset_email(
        self, email: str, token: str, reset_url: str
    ) -> bool:
        """
        Send password reset email.

        @spec FEAT-003/AC-001

        Args:
            email: Recipient email
            token: Reset token
            reset_url: Base URL for reset

        Returns:
            True if sent successfully
        """
        pass


class MockEmailService(EmailServiceInterface):
    """
    Mock implementation for testing.

    Stores emails in memory instead of sending.
    """

    def __init__(self):
        self.sent_emails: list[EmailMessage] = []

    async def send_email(self, message: EmailMessage) -> bool:
        """Store email in memory."""
        self.sent_emails.append(message)
        return True

    async def send_verification_email(
        self, email: str, token: str, verification_url: str
    ) -> bool:
        """Store verification email."""
        message = EmailMessage(
            to=email,
            subject="Verify your email",
            body=f"Click here to verify: {verification_url}?token={token}",
        )
        return await self.send_email(message)

    async def send_password_reset_email(
        self, email: str, token: str, reset_url: str
    ) -> bool:
        """Store reset email."""
        message = EmailMessage(
            to=email,
            subject="Reset your password",
            body=f"Click here to reset: {reset_url}?token={token}",
        )
        return await self.send_email(message)

    def get_last_email(self) -> Optional[EmailMessage]:
        """Get the last sent email."""
        return self.sent_emails[-1] if self.sent_emails else None

    def clear(self):
        """Clear all stored emails."""
        self.sent_emails.clear()


class EmailServiceError(Exception):
    """Error sending email."""

    pass


# Factory function for dependency injection
def get_email_service() -> EmailServiceInterface:
    """
    Get email service instance.

    Returns mock in development, real service in production.
    """
    import os

    if os.getenv("ENVIRONMENT") == "production":
        # TODO: Return real implementation
        raise NotImplementedError("Production email service not implemented")
    else:
        return MockEmailService()
