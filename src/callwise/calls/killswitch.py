"""Global emergency kill switch mechanism for diverting voice calls and chat to message-taking."""

from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from callwise.config import settings

logger = logging.getLogger(__name__)

# State file location for persistent CLI-toggled killswitch across processes
KILL_SWITCH_FILE = Path(".callwise_killswitch.json")

FALLBACK_MESSAGE_TAKING_PROMPT = (
    "Our automated receptionist is temporarily offline for routine maintenance. "
    "May I take down your name and callback number so our staff can follow up with you directly?"
)


def _read_killswitch_file() -> Optional[Dict[str, Any]]:
    """Read dynamic state from killswitch file if it exists."""
    if KILL_SWITCH_FILE.exists():
        try:
            with open(KILL_SWITCH_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Error reading killswitch file: {e}")
    return None


def is_kill_switch_active() -> bool:
    """
    Check if the global emergency kill switch is currently active.
    Active if either settings.kill_switch_enabled is True OR dynamic file flag is True.
    """
    # 1. Environment variable setting
    if settings.kill_switch_enabled:
        return True

    # 2. Dynamic state file toggle
    file_state = _read_killswitch_file()
    if file_state and file_state.get("active", False):
        return True

    return False


def enable_kill_switch(reason: Optional[str] = None, activated_by: str = "admin") -> Dict[str, Any]:
    """Enable the global emergency kill switch."""
    data = {
        "active": True,
        "reason": reason or "Emergency manual kill switch activation",
        "activated_at": datetime.now(timezone.utc).isoformat(),
        "activated_by": activated_by,
    }
    try:
        with open(KILL_SWITCH_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to write killswitch file: {e}")

    logger.warning(f"[KILL SWITCH ACTIVATED] {data['reason']} by {activated_by}")
    return data


def disable_kill_switch() -> Dict[str, Any]:
    """Disable the global emergency kill switch."""
    if KILL_SWITCH_FILE.exists():
        try:
            os.remove(KILL_SWITCH_FILE)
        except Exception as e:
            logger.error(f"Failed to remove killswitch file: {e}")

    logger.info("[KILL SWITCH DEACTIVATED] Resumed normal AI voice and chat operations.")
    return {"active": False, "deactivated_at": datetime.now(timezone.utc).isoformat()}


def get_kill_switch_status() -> Dict[str, Any]:
    """Return structured status details of the kill switch."""
    active = is_kill_switch_active()
    file_state = _read_killswitch_file()

    return {
        "active": active,
        "env_enabled": settings.kill_switch_enabled,
        "dynamic_enabled": file_state.get("active", False) if file_state else False,
        "reason": file_state.get("reason") if file_state else ("Set by environment variable" if settings.kill_switch_enabled else None),
        "activated_at": file_state.get("activated_at") if file_state else None,
        "activated_by": file_state.get("activated_by") if file_state else None,
        "message": FALLBACK_MESSAGE_TAKING_PROMPT if active else None,
    }

