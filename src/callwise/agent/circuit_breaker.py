"""Provider Circuit Breaker ensuring graceful failover and degradation on LLM failures."""

from datetime import datetime, timezone
from enum import Enum
import logging
import time
from typing import Callable, Dict, List, Optional

from callwise.config import settings

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "CLOSED"        # Normal operation: requests pass through
    OPEN = "OPEN"            # Tripped: requests are blocked from this provider
    HALF_OPEN = "HALF_OPEN"  # Testing: recovery cooldown elapsed, probing provider


class ProviderCircuit:
    """Manages failure tracking and state transitions for a single LLM provider."""

    def __init__(
        self,
        provider: str,
        failure_threshold: int = 3,
        recovery_seconds: int = 60,
        on_trip: Optional[Callable[[str, int], None]] = None,
    ):
        self.provider = provider.lower()
        self.failure_threshold = failure_threshold
        self.recovery_seconds = recovery_seconds
        self.on_trip = on_trip

        self.state = CircuitState.CLOSED
        self.consecutive_failures = 0
        self.last_failure_time: Optional[float] = None
        self.last_success_time: Optional[float] = None

    def is_available(self) -> bool:
        """Check if provider is available or ready for probe."""
        now = time.time()

        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Check if cooldown has elapsed
            if self.last_failure_time and (now - self.last_failure_time) >= self.recovery_seconds:
                logger.info(
                    f"[Circuit Breaker] Provider '{self.provider}' cooldown elapsed. Transitioning OPEN -> HALF_OPEN."
                )
                self.state = CircuitState.HALF_OPEN
                return True
            return False

        if self.state == CircuitState.HALF_OPEN:
            return True

        return False

    def record_success(self) -> None:
        """Register successful turn completion."""
        self.consecutive_failures = 0
        self.last_success_time = time.time()
        if self.state != CircuitState.CLOSED:
            logger.info(
                f"[Circuit Breaker] Provider '{self.provider}' recovered. Transitioning {self.state} -> CLOSED."
            )
            self.state = CircuitState.CLOSED

    def record_failure(self, error: Optional[Exception] = None) -> None:
        """Register failed attempt (timeout, API error, rate limit)."""
        self.consecutive_failures += 1
        self.last_failure_time = time.time()
        err_msg = f" ({error})" if error else ""

        logger.warning(
            f"[Circuit Breaker] Failure on '{self.provider}' (count: {self.consecutive_failures}/{self.failure_threshold}){err_msg}"
        )

        if self.state in (CircuitState.CLOSED, CircuitState.HALF_OPEN):
            if self.consecutive_failures >= self.failure_threshold or self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                logger.error(
                    f"[Circuit Breaker TRIPPED] Provider '{self.provider}' circuit opened! Failing over."
                )
                if self.on_trip:
                    try:
                        self.on_trip(self.provider, self.consecutive_failures)
                    except Exception as e:
                        logger.error(f"Error calling on_trip handler: {e}")


class CircuitBreakerRegistry:
    """Singleton registry tracking provider circuits across the application."""

    def __init__(self):
        self._circuits: Dict[str, ProviderCircuit] = {}
        self._trip_listeners: List[Callable[[str, int], None]] = []

    def register_trip_listener(self, listener: Callable[[str, int], None]) -> None:
        """Register callback invoked whenever any provider circuit trips OPEN."""
        self._trip_listeners.append(listener)

    def _notify_trip(self, provider: str, failures: int) -> None:
        for listener in self._trip_listeners:
            try:
                listener(provider, failures)
            except Exception as e:
                logger.error(f"Trip listener error: {e}")

    def get_circuit(self, provider: str) -> ProviderCircuit:
        """Get or initialize circuit for specified provider."""
        key = provider.lower().strip()
        if key not in self._circuits:
            self._circuits[key] = ProviderCircuit(
                provider=key,
                failure_threshold=settings.circuit_breaker_failure_threshold,
                recovery_seconds=settings.circuit_breaker_recovery_seconds,
                on_trip=self._notify_trip,
            )
        return self._circuits[key]

    def is_available(self, provider: str) -> bool:
        """Check if provider circuit allows requests."""
        return self.get_circuit(provider).is_available()

    def record_success(self, provider: str) -> None:
        """Record success for provider."""
        self.get_circuit(provider).record_success()

    def record_failure(self, provider: str, error: Optional[Exception] = None) -> None:
        """Record failure for provider."""
        self.get_circuit(provider).record_failure(error)

    def select_active_provider(
        self, primary: str, fallback: Optional[str] = None
    ) -> Optional[str]:
        """
        Choose the best available provider.
        1. Primary if circuit is not OPEN
        2. Fallback if primary is OPEN and fallback is available
        3. None if both are tripped/unavailable (triggering graceful message taking)
        """
        primary = primary.lower().strip()
        if self.is_available(primary):
            return primary

        fb = (fallback or settings.fallback_llm_provider).lower().strip()
        if fb != primary and self.is_available(fb):
            logger.info(
                f"[Circuit Breaker] Primary '{primary}' is OPEN. Routing turn to fallback provider '{fb}'."
            )
            return fb

        logger.critical(
            f"[Circuit Breaker] Both primary '{primary}' and fallback '{fb}' circuits are OPEN. Graceful degradation active."
        )
        return None

    def reset_all(self) -> None:
        """Reset all circuit breakers to healthy CLOSED state (useful for tests)."""
        for circuit in self._circuits.values():
            circuit.state = CircuitState.CLOSED
            circuit.consecutive_failures = 0
            circuit.last_failure_time = None
            circuit.last_success_time = None


# Global singleton registry
circuit_breaker = CircuitBreakerRegistry()

