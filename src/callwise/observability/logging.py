"""Structured JSON logging with PII and credential redaction filter."""

from datetime import datetime, timezone
import json
import logging
import re
import sys
import traceback
from typing import Any, Dict, Optional

from callwise.config import settings

# Sensitive data redaction patterns
CREDIT_CARD_REGEX = re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")
SSN_REGEX = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
BEARER_TOKEN_REGEX = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9_\-\.]{16,}")
API_KEY_REGEX = re.compile(r"(?i)(api[_-]?key\s*[:=]\s*['\"]?)[A-Za-z0-9_\-]{16,}(['\"]?)")
PASSWORD_REGEX = re.compile(r"(?i)([\"']?(?:password|secret)[\"']?\s*[:=]\s*['\"])[^'\"\n\r]+(['\"])")


def redact_sensitive_text(text: str) -> str:
    """Mask sensitive PII, passwords, credit card numbers, and API tokens from log text."""
    if not isinstance(text, str):
        return text

    # Redact credit card numbers
    redacted = CREDIT_CARD_REGEX.sub("[REDACTED_CARD]", text)
    # Redact SSNs
    redacted = SSN_REGEX.sub("[REDACTED_SSN]", redacted)
    # Redact Bearer tokens
    redacted = BEARER_TOKEN_REGEX.sub(r"\1[REDACTED_TOKEN]", redacted)
    # Redact API keys
    redacted = API_KEY_REGEX.sub(r"\1[REDACTED_KEY]\2", redacted)
    # Redact Passwords
    redacted = PASSWORD_REGEX.sub(r"\1[REDACTED_PASSWORD]\2", redacted)

    return redacted


class RedactionFilter(logging.Filter):
    """Logging filter that scrubs sensitive customer PII and credentials from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_sensitive_text(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: redact_sensitive_text(str(v)) for k, v in record.args.items()}
            elif isinstance(record.args, (list, tuple)):
                record.args = tuple(
                    redact_sensitive_text(str(a)) if isinstance(a, str) else a
                    for a in record.args
                )
        return True


class JSONFormatter(logging.Formatter):
    """Structured JSON formatter for container logs and centralized observability pipelines."""

    def format(self, record: logging.LogRecord) -> str:
        # Get base formatted message (with redaction already applied)
        message = record.getMessage()

        payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_sensitive_text(message),
        }

        # Include structured context attributes if attached
        for attr in ("call_id", "business_id", "session_type", "latency_ms", "provider", "status"):
            val = getattr(record, attr, None)
            if val is not None:
                payload[attr] = str(val) if not isinstance(val, (int, float, bool)) else val

        # Include exception tracebacks if present
        if record.exc_info:
            payload["exception"] = "".join(traceback.format_exception(*record.exc_info)).strip()

        return json.dumps(payload, ensure_ascii=False)


def setup_logging(
    log_format: Optional[str] = None,
    log_level: Optional[str] = None,
) -> None:
    """Configure root application logging with redaction filter and format."""
    fmt_choice = (log_format or settings.log_format).lower().strip()
    level_choice = (log_level or settings.log_level).upper().strip()

    root_logger = logging.getLogger()
    numeric_level = getattr(logging, level_choice, logging.INFO)
    root_logger.setLevel(numeric_level)

    # Clear existing handlers to avoid duplicates
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(numeric_level)
    handler.addFilter(RedactionFilter())

    if fmt_choice == "json":
        handler.setFormatter(JSONFormatter())
    else:
        text_fmt = logging.Formatter(
            "[%(asctime)s] %(levelname)-7s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(text_fmt)

    root_logger.addHandler(handler)

