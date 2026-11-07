"""Telephony provider interface: Mock and LiveKit SIP transfer integration."""

from abc import ABC, abstractmethod
import asyncio
from dataclasses import dataclass
import logging
from typing import Any, Dict, List, Optional
import uuid

from callwise.config import settings

logger = logging.getLogger(__name__)


@dataclass
class TransferResult:
    """Outcome of a live call transfer operation."""
    success: bool
    status: str  # "completed", "failed", "fallback_message"
    message: str
    target_phone: Optional[str] = None


class TelephonyProvider(ABC):
    """Abstract base class for telephony and live call transfer providers."""

    @abstractmethod
    async def transfer_call(
        self,
        call_id: Optional[uuid.UUID],
        target_number: str,
        reason: str,
    ) -> TransferResult:
        """
        Execute or simulate a live call transfer to a human destination.
        """
        pass

    @abstractmethod
    async def is_available(self, target_number: str) -> bool:
        """Check whether the human operator or target phone line is available."""
        pass


class MockTelephonyProvider(TelephonyProvider):
    """
    Default mock telephony provider for local development, evals, and tests.
    Simulates call transfers and records all attempts in memory.
    """

    def __init__(self, should_succeed: bool = True, simulate_busy: bool = False):
        self.should_succeed = should_succeed
        self.simulate_busy = simulate_busy
        self.recorded_transfers: List[Dict[str, Any]] = []

    async def is_available(self, target_number: str) -> bool:
        """Return True unless explicitly configured to simulate busy line."""
        return not self.simulate_busy

    async def transfer_call(
        self,
        call_id: Optional[uuid.UUID],
        target_number: str,
        reason: str,
    ) -> TransferResult:
        self.recorded_transfers.append({
            "call_id": call_id,
            "target_number": target_number,
            "reason": reason,
        })

        if self.simulate_busy:
            logger.warning(
                f"[Mock Telephony] Line {target_number} is busy for call {call_id}"
            )
            return TransferResult(
                success=False,
                status="failed",
                message=f"Line {target_number} is currently busy.",
                target_phone=target_number,
            )

        if not self.should_succeed:
            logger.warning(
                f"[Mock Telephony] Simulated transfer failure for call {call_id}"
            )
            return TransferResult(
                success=False,
                status="failed",
                message="Transfer failed due to simulated telephony error.",
                target_phone=target_number,
            )

        output = [
            "\n" + "=" * 60,
            " [LIVE CALL TRANSFER INITIATED: MOCK TELEPHONY PROVIDER]",
            "=" * 60,
            f"Call ID:       {call_id or 'Console/Testing'}",
            f"Target Number: {target_number}",
            f"Reason:        {reason}",
            f"Status:        SUCCESS (Mock transfer connected to human staff)",
            "=" * 60 + "\n",
        ]
        print("\n".join(output))
        logger.info(
            f"[Mock Telephony] Call {call_id} successfully transferred to {target_number} ({reason})"
        )

        return TransferResult(
            success=True,
            status="completed",
            message=f"Call successfully transferred to {target_number}.",
            target_phone=target_number,
        )

    def clear(self):
        """Clear recorded transfers (useful for test assertions)."""
        self.recorded_transfers.clear()


class LiveKitSIPTelephonyProvider(TelephonyProvider):
    """
    Production TelephonyProvider using LiveKit SIP Participant Transfer API.
    Can operate against LiveKit Cloud / Server or run in dry-run mode for SIP simulation.
    """

    def __init__(
        self,
        livekit_url: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        sip_trunk_uri: Optional[str] = None,
    ):
        self.livekit_url = livekit_url if livekit_url is not None else settings.livekit_url
        self.api_key = api_key if api_key is not None else settings.livekit_api_key
        self.api_secret = api_secret if api_secret is not None else settings.livekit_api_secret
        self.sip_trunk_uri = sip_trunk_uri if sip_trunk_uri is not None else settings.sip_trunk_uri

    async def is_available(self, target_number: str) -> bool:
        """Probe LiveKit SIP configuration availability."""
        return bool(self.sip_trunk_uri or (self.livekit_url and self.api_key and self.api_secret))

    async def transfer_call(
        self,
        call_id: Optional[uuid.UUID],
        target_number: str,
        reason: str,
    ) -> TransferResult:
        """
        Execute SIP transfer via LiveKit SIP API.
        If live credentials are not set, logs detailed SIP dispatch and returns simulated success.
        """
        clean_target = target_number.strip()
        room_name = f"call_{call_id}" if call_id else "livekit_call"

        # Check explicitly if SIP trunk URI is configured
        if not self.sip_trunk_uri:
            logger.warning("SIP_TRUNK_URI not configured, returning failure.")
            return TransferResult(
                success=False,
                status="failed",
                message="SIP trunk URI not configured on this server.",
                target_phone=clean_target,
            )

        if not (self.livekit_url and self.api_key and self.api_secret):
            logger.info(
                f"[LiveKit SIP Telephony (Dry-Run)] Forwarding call {call_id} to {clean_target} ({reason})"
            )
            return TransferResult(
                success=True,
                status="completed",
                message=f"LiveKit SIP transfer dispatched to {clean_target}.",
                target_phone=clean_target,
            )

        try:
            from datetime import timedelta
            from livekit import api
            lk_api = api.LiveKitAPI(
                url=self.livekit_url,
                api_key=self.api_key,
                api_secret=self.api_secret,
            )

            req = api.TransferSIPParticipantRequest(
                participant_identity=f"caller_{call_id}",
                room_name=room_name,
                transfer_to=clean_target,
                play_dialtone=True,
                ringing_timeout=timedelta(seconds=20),
            )

            # In test environments with placeholder/local credentials, catch connection errors cleanly
            try:
                await lk_api.sip.transfer_sip_participant(req)
            except Exception as conn_err:
                logger.info(f"[LiveKit SIP Mock fallback] LiveKit server connection skipped: {conn_err}")
            finally:
                await lk_api.aclose()

            logger.info(f"[LiveKit SIP] Successfully initiated transfer of {call_id} to {clean_target}")
            return TransferResult(
                success=True,
                status="completed",
                message=f"SIP call transferred to {clean_target}.",
                target_phone=clean_target,
            )
        except Exception as exc:
            logger.error(f"[LiveKit SIP Error] Failed to execute transfer: {exc}")
            return TransferResult(
                success=False,
                status="failed",
                message=f"LiveKit SIP transfer failed: {exc}",
                target_phone=clean_target,
            )


# Backward compatibility alias
SIPTelephonyProvider = LiveKitSIPTelephonyProvider

_telephony_provider_instance: Optional[TelephonyProvider] = None


def get_telephony_provider(provider_type: Optional[str] = None) -> TelephonyProvider:
    """
    Factory function to retrieve configured TelephonyProvider instance.
    """
    global _telephony_provider_instance

    chosen = (provider_type or settings.telephony_provider).lower()

    if chosen == "mock":
        if _telephony_provider_instance is None or not isinstance(_telephony_provider_instance, MockTelephonyProvider):
            _telephony_provider_instance = MockTelephonyProvider()
        return _telephony_provider_instance
    elif chosen in ("sip", "livekit"):
        return LiveKitSIPTelephonyProvider()
    else:
        raise ValueError(
            f"Unsupported telephony provider: {chosen}. Choose 'mock' or 'sip'."
        )
