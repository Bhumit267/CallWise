"""Email delivery provider interface: Console and SMTP implementations."""

from abc import ABC, abstractmethod
import asyncio
from dataclasses import dataclass
import email.message
import logging
import smtplib
from typing import List, Optional

from callwise.config import settings

logger = logging.getLogger(__name__)


@dataclass
class EmailMessage:
    """Standardized outgoing email payload."""
    to: str
    subject: str
    body_text: str
    body_html: Optional[str] = None
    from_email: Optional[str] = None


class EmailProvider(ABC):
    """Abstract base class for all email delivery providers."""

    @abstractmethod
    async def send_email(self, message: EmailMessage) -> bool:
        """
        Send an email message.

        Args:
            message: EmailMessage containing recipient, subject, and content.

        Returns:
            True if sent successfully, False otherwise.
        """
        pass


class ConsoleEmailProvider(EmailProvider):
    """
    Console/stdout email provider for local development, tests, and mock environments.
    Prints full email structure and records sent messages for assertions.
    """

    def __init__(self):
        self.sent_messages: List[EmailMessage] = []

    async def send_email(self, message: EmailMessage) -> bool:
        sender = message.from_email or settings.smtp_from_email
        output = [
            "\n" + "=" * 60,
            " [EMAIL NOTIFICATION DISPATCHED: CONSOLE PROVIDER]",
            "=" * 60,
            f"To:      {message.to}",
            f"From:    {sender}",
            f"Subject: {message.subject}",
            "-" * 60,
            message.body_text,
            "=" * 60 + "\n",
        ]
        formatted = "\n".join(output)
        print(formatted)
        logger.info(f"[Console Email] Sent to {message.to}: {message.subject}")
        self.sent_messages.append(message)
        return True

    def clear(self):
        """Clear recorded emails (useful for test assertions)."""
        self.sent_messages.clear()


class SMTPEmailProvider(EmailProvider):
    """
    Standard SMTP email provider compatible with Gmail app passwords,
    SendGrid, Mailgun, and custom SMTP servers.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        use_tls: Optional[bool] = None,
        default_from: Optional[str] = None,
    ):
        self.host = host or settings.smtp_host
        self.port = port or settings.smtp_port
        self.user = user or settings.smtp_user
        self.password = password or settings.smtp_password
        self.use_tls = use_tls if use_tls is not None else settings.smtp_use_tls
        self.default_from = default_from or settings.smtp_from_email

    async def send_email(self, message: EmailMessage) -> bool:
        """Send email synchronously in thread pool to avoid blocking async event loop."""
        return await asyncio.to_thread(self._send_sync, message)

    def _send_sync(self, message: EmailMessage) -> bool:
        sender = message.from_email or self.default_from
        msg = email.message.EmailMessage()
        msg["Subject"] = message.subject
        msg["From"] = sender
        msg["To"] = message.to
        msg.set_content(message.body_text)

        if message.body_html:
            msg.add_alternative(message.body_html, subtype="html")

        try:
            logger.info(f"Connecting to SMTP server {self.host}:{self.port}...")
            with smtplib.SMTP(self.host, self.port, timeout=15) as server:
                if self.use_tls:
                    server.starttls()
                if self.user and self.password:
                    server.login(self.user, self.password)
                server.send_message(msg)
            logger.info(f"[SMTP Email] Successfully sent email to {message.to}: {message.subject}")
            return True
        except Exception as exc:
            logger.error(f"[SMTP Email Error] Failed to send email to {message.to}: {exc}")
            raise


_email_provider_instance: Optional[EmailProvider] = None


def get_email_provider(provider_type: Optional[str] = None) -> EmailProvider:
    """
    Factory function to retrieve configured email provider instance.
    """
    global _email_provider_instance

    chosen = (provider_type or settings.email_provider).lower()

    if chosen == "console":
        if _email_provider_instance is None or not isinstance(_email_provider_instance, ConsoleEmailProvider):
            _email_provider_instance = ConsoleEmailProvider()
        return _email_provider_instance
    elif chosen == "smtp":
        return SMTPEmailProvider()
    else:
        raise ValueError(f"Unsupported email provider: {chosen}. Choose 'console' or 'smtp'.")

