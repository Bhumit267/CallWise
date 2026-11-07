"""Authentication, hashing, token management, and rate limiting security utilities."""

from datetime import datetime, timezone, timedelta
import hashlib
import secrets
import time
from typing import Dict, List, Optional, Tuple
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# Argon2id password hasher with secure modern defaults
_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    """Hash password using Argon2id."""
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against Argon2id hash in constant time."""
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, Exception):
        return False


def generate_token(nbytes: int = 32) -> str:
    """Generate a cryptographically secure URL-safe random token string."""
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    """Compute SHA-256 hex digest of a token for secure database storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class RateLimiter:
    """In-memory sliding window rate limiter for brute-force and abuse prevention."""

    def __init__(self):
        # Maps key -> list of timestamp floats
        self._attempts: Dict[str, List[float]] = {}
        # Maps key -> lockout expiry timestamp float
        self._lockouts: Dict[str, float] = {}

    def is_rate_limited(
        self,
        key: str,
        max_attempts: int = 5,
        window_seconds: int = 900,  # 15 minutes
        lockout_seconds: int = 900,
    ) -> Tuple[bool, int]:
        """
        Check if an action is currently rate limited or locked out.

        Returns:
            (is_limited, retry_after_seconds)
        """
        now = time.time()

        # Check existing lockout
        lockout_until = self._lockouts.get(key, 0.0)
        if now < lockout_until:
            retry_after = int(lockout_until - now) + 1
            return True, retry_after

        # Clean old attempts outside the window
        attempts = [t for t in self._attempts.get(key, []) if now - t < window_seconds]
        self._attempts[key] = attempts

        if len(attempts) >= max_attempts:
            # Trigger lockout
            self._lockouts[key] = now + lockout_seconds
            return True, lockout_seconds

        return False, 0

    def record_attempt(self, key: str) -> None:
        """Record a failed attempt."""
        now = time.time()
        if key not in self._attempts:
            self._attempts[key] = []
        self._attempts[key].append(now)

    def reset(self, key: str) -> None:
        """Clear recorded attempts and lockouts (e.g. on successful login)."""
        self._attempts.pop(key, None)
        self._lockouts.pop(key, None)

    def clear_all(self) -> None:
        """Clear all rate limiter state (useful for test resets)."""
        self._attempts.clear()
        self._lockouts.clear()


# Global rate limiter instance
auth_rate_limiter = RateLimiter()
