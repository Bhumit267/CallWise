"""Pluggable messaging provider interface: Mock and Twilio SMS/WhatsApp integration."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import uuid

import httpx

from callwise.config import settings

logger = logging.getLogger(__name__)


@dataclass
class MessagingResult:
    """Outcome of an outbound SMS or WhatsApp message dispatch."""
    success: bool
    message_id: str
    channel: str  # "sms" or "whatsapp"
    to_phone: str
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class MessagingProvider(ABC):
    """Abstract base class for outbound customer messaging."""

    @abstractmethod
    async def send_sms(self, to_phone: str, body: str) -> MessagingResult:
        """Send a standard SMS text message."""
        pass

    @abstractmethod
    async def send_whatsapp(
        self,
        to_phone: str,
        body: str,
        media_url: Optional[str] = None,
    ) -> MessagingResult:
        """Send a formatted WhatsApp message."""
        pass


class MockMessagingProvider(MessagingProvider):
    """
    In-memory simulated messaging provider for local development, evaluations, and CI testing.
    Outputs clear terminal delivery banners and records all messages for inspection.
    """

    def __init__(self, should_succeed: bool = True):
        self.should_succeed = should_succeed
        self.recorded_messages: List[Dict[str, Any]] = []

    def clear(self) -> None:
        """Clear recorded message history."""
        self.recorded_messages.clear()

    async def send_sms(self, to_phone: str, body: str) -> MessagingResult:
        clean_phone = to_phone.strip()
        msg_id = f"mock_sms_{uuid.uuid4().hex[:10]}"
        timestamp = datetime.now(timezone.utc)

        record = {
            "id": msg_id,
            "channel": "sms",
            "to_phone": clean_phone,
            "body": body,
            "timestamp": timestamp,
            "success": self.should_succeed,
        }
        self.recorded_messages.append(record)

        if not self.should_succeed:
            logger.warning(f"[Mock SMS] Simulated delivery failure to {clean_phone}")
            return MessagingResult(
                success=False,
                message_id=msg_id,
                channel="sms",
                to_phone=clean_phone,
                error="Simulated SMS delivery failure.",
                timestamp=timestamp,
            )

        banner = [
            "\n" + "=" * 60,
            " [INSTANT SMS DISPATCHED: MOCK MESSAGING PROVIDER]",
            "=" * 60,
            f"To:      {clean_phone}",
            f"Message ID: {msg_id}",
            "-" * 60,
            f"{body.strip()}",
            "=" * 60 + "\n",
        ]
        print("\n".join(banner))
        logger.info(f"[Mock SMS] Delivered to {clean_phone} (id={msg_id})")

        return MessagingResult(
            success=True,
            message_id=msg_id,
            channel="sms",
            to_phone=clean_phone,
            timestamp=timestamp,
        )

    async def send_whatsapp(
        self,
        to_phone: str,
        body: str,
        media_url: Optional[str] = None,
    ) -> MessagingResult:
        clean_phone = to_phone.strip()
        msg_id = f"mock_wa_{uuid.uuid4().hex[:10]}"
        timestamp = datetime.now(timezone.utc)

        record = {
            "id": msg_id,
            "channel": "whatsapp",
            "to_phone": clean_phone,
            "body": body,
            "media_url": media_url,
            "timestamp": timestamp,
            "success": self.should_succeed,
        }
        self.recorded_messages.append(record)

        if not self.should_succeed:
            logger.warning(f"[Mock WhatsApp] Simulated delivery failure to {clean_phone}")
            return MessagingResult(
                success=False,
                message_id=msg_id,
                channel="whatsapp",
                to_phone=clean_phone,
                error="Simulated WhatsApp delivery failure.",
                timestamp=timestamp,
            )

        banner = [
            "\n" + "=" * 60,
            " [INSTANT WHATSAPP MESSAGE DISPATCHED: MOCK MESSAGING PROVIDER]",
            "=" * 60,
            f"To:      {clean_phone}",
            f"Message ID: {msg_id}",
            "-" * 60,
            f"{body.strip()}",
            "=" * 60 + "\n",
        ]
        print("\n".join(banner))
        logger.info(f"[Mock WhatsApp] Delivered to {clean_phone} (id={msg_id})")

        return MessagingResult(
            success=True,
            message_id=msg_id,
            channel="whatsapp",
            to_phone=clean_phone,
            timestamp=timestamp,
        )


class TwilioMessagingProvider(MessagingProvider):
    """
    Live Twilio SMS and WhatsApp integration via Twilio REST API.
    """

    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        from_sms: Optional[str] = None,
        from_whatsapp: Optional[str] = None,
    ):
        self.account_sid = account_sid.strip()
        self.auth_token = auth_token.strip()
        self.from_sms = from_sms.strip() if from_sms else None
        self.from_whatsapp = from_whatsapp.strip() if from_whatsapp else "whatsapp:+14155238886"
        self.base_url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"

    async def send_sms(self, to_phone: str, body: str) -> MessagingResult:
        if not self.from_sms:
            err = "Twilio SMS sender number (twilio_sms_from) is not configured."
            logger.error(err)
            return MessagingResult(
                success=False,
                message_id="",
                channel="sms",
                to_phone=to_phone,
                error=err,
            )

        data = {
            "To": to_phone.strip(),
            "From": self.from_sms,
            "Body": body,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    self.base_url,
                    data=data,
                    auth=(self.account_sid, self.auth_token),
                )
                if resp.is_success:
                    payload = resp.json()
                    msg_id = payload.get("sid", f"tw_sms_{uuid.uuid4().hex[:8]}")
                    logger.info(f"[Twilio SMS] Sent to {to_phone} (SID: {msg_id})")
                    return MessagingResult(
                        success=True,
                        message_id=msg_id,
                        channel="sms",
                        to_phone=to_phone,
                    )
                else:
                    err_msg = f"Twilio SMS HTTP {resp.status_code}: {resp.text}"
                    logger.error(err_msg)
                    return MessagingResult(
                        success=False,
                        message_id="",
                        channel="sms",
                        to_phone=to_phone,
                        error=err_msg,
                    )
        except Exception as exc:
            logger.error(f"[Twilio SMS] Exception sending to {to_phone}: {exc}")
            return MessagingResult(
                success=False,
                message_id="",
                channel="sms",
                to_phone=to_phone,
                error=str(exc),
            )

    async def send_whatsapp(
        self,
        to_phone: str,
        body: str,
        media_url: Optional[str] = None,
    ) -> MessagingResult:
        # Twilio WhatsApp requires 'whatsapp:' prefix on sender and recipient
        target_whatsapp = to_phone.strip()
        if not target_whatsapp.startswith("whatsapp:"):
            target_whatsapp = f"whatsapp:{target_whatsapp}"

        data = {
            "To": target_whatsapp,
            "From": self.from_whatsapp,
            "Body": body,
        }
        if media_url:
            data["MediaUrl"] = media_url

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    self.base_url,
                    data=data,
                    auth=(self.account_sid, self.auth_token),
                )
                if resp.is_success:
                    payload = resp.json()
                    msg_id = payload.get("sid", f"tw_wa_{uuid.uuid4().hex[:8]}")
                    logger.info(f"[Twilio WhatsApp] Sent to {to_phone} (SID: {msg_id})")
                    return MessagingResult(
                        success=True,
                        message_id=msg_id,
                        channel="whatsapp",
                        to_phone=to_phone,
                    )
                else:
                    err_msg = f"Twilio WhatsApp HTTP {resp.status_code}: {resp.text}"
                    logger.error(err_msg)
                    return MessagingResult(
                        success=False,
                        message_id="",
                        channel="whatsapp",
                        to_phone=to_phone,
                        error=err_msg,
                    )
        except Exception as exc:
            logger.error(f"[Twilio WhatsApp] Exception sending to {to_phone}: {exc}")
            return MessagingResult(
                success=False,
                message_id="",
                channel="whatsapp",
                to_phone=to_phone,
                error=str(exc),
            )


# Default singleton mock instance for test predictability
_global_mock_provider = MockMessagingProvider()


def get_messaging_provider(provider_type: Optional[str] = None) -> MessagingProvider:
    """
    Factory creating or returning the configured MessagingProvider.
    Defaults to MockMessagingProvider unless Twilio credentials are fully supplied.
    """
    chosen = (provider_type or settings.messaging_provider).lower().strip()

    if chosen == "twilio" and settings.twilio_account_sid and settings.twilio_auth_token:
        return TwilioMessagingProvider(
            account_sid=settings.twilio_account_sid,
            auth_token=settings.twilio_auth_token,
            from_sms=settings.twilio_sms_from,
            from_whatsapp=settings.twilio_whatsapp_from,
        )

    return _global_mock_provider

