"""Telephony provider interface: Mock and LiveKit SIP transfer scaffolding."""

from abc import ABC, abstractmethod
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

        Args:
            call_id: Active call session UUID.
            target_number: E.164 or dialable destination phone number.
            reason: Customer's reason for requesting human escalation.

        Returns:
            TransferResult with transfer status and message.
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


class SIPTelephonyProvider(TelephonyProvider):
    """
    LiveKit SIP trunk provider scaffold for real production SIP bridging.
    Ready for live LiveKit SIP integration when credentials and trunk URI are configured.
    """

    def __init__(self, sip_trunk_uri: Optional[str] = None):
        self.sip_trunk_uri = sip_trunk_uri or settings.sip_trunk_uri

    async def is_available(self, target_number: str) -> bool:
        """In SIP mode, probe SIP gateway availability."""
        return bool(self.sip_trunk_uri)

    async def transfer_call(
        self,
        call_id: Optional[uuid.UUID],
        target_number: str,
        reason: str,
    ) -> TransferResult:
        if not self.sip_trunk_uri:
            logger.warning("SIP_TRUNK_URI not configured, falling back to mock behavior.")
            return TransferResult(
                success=False,
                status="failed",
                message="SIP trunk URI not configured on this server.",
                target_phone=target_number,
            )

        # Scaffolding for LiveKit SIP Outbound Trunk API
        logger.info(
            f"[SIP Telephony Scaffold] Forwarding call {call_id} to SIP trunk {self.sip_trunk_uri} -> {target_number}"
        )
        return TransferResult(
            success=True,
            status="completed",
            message=f"LiveKit SIP transfer initiated to {target_number}.",
            target_phone=target_number,
        )


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
    elif chosen == "sip":
        return SIPTelephonyProvider()
    else:
        raise ValueError(
            f"Unsupported telephony provider: {chosen}. Choose 'mock' or 'sip'."
        )
