"""LiveKit voice agent and business hours logic."""

from typing import Any

from callwise.agent.hours import (
    BusinessHoursStatus,
    format_time_12h,
    get_business_hours_status,
    is_open_now,
    parse_time_str,
)
from callwise.agent.prompt import build_system_prompt
from callwise.agent.text_agent import TextAgent
from callwise.agent.tools import CallwiseToolset


def __getattr__(name: str) -> Any:
    if name in ("create_voice_agent", "start_voice_worker"):
        from callwise.agent.voice_agent import create_voice_agent, start_voice_worker

        if name == "create_voice_agent":
            return create_voice_agent
        return start_voice_worker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "BusinessHoursStatus",
    "CallwiseToolset",
    "TextAgent",
    "build_system_prompt",
    "create_voice_agent",
    "format_time_12h",
    "get_business_hours_status",
    "is_open_now",
    "parse_time_str",
    "start_voice_worker",
]
