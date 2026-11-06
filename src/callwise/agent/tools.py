"""LLM tool definitions: get_business_hours, search_knowledge, and take_message."""

from typing import Any, Callable, Dict, List, Optional
import logging
import uuid

logger = logging.getLogger(__name__)
from sqlalchemy.orm import Session
from livekit.agents import function_tool

from callwise.agent.hours import get_business_hours_status
from callwise.db.models import Business, Call, Message
from callwise.db.session import get_async_session, get_sync_session
from callwise.knowledge.search import search_knowledge_async


class CallwiseToolset:
    """Encapsulates the 3 required tools bound to a specific business tenant and call."""

    def __init__(
        self,
        business: Business,
        call_id: Optional[uuid.UUID] = None,
    ):
        self.business = business
        self.business_id = business.id
        self.call_id = call_id

    def get_business_hours(self, day: Optional[str] = None) -> str:
        """
        Check whether the business is currently open or get opening hours for today or a specific day.

        Args:
            day: Optional day of the week (e.g. 'Monday', 'Friday', 'Saturday') to check.
        """
        status = get_business_hours_status(self.business)

        if day:
            day_clean = day.strip().lower()
            day_cfg = (self.business.hours or {}).get(day_clean)
            if not day_cfg or day_cfg.get("closed", False) or not day_cfg.get("open"):
                return f"On {day.capitalize()}, {self.business.name} is closed."
            open_t = day_cfg.get("open")
            close_t = day_cfg.get("close")
            return f"On {day.capitalize()}, {self.business.name} is open from {open_t} to {close_t} {self.business.timezone}."

        # Return live current status
        return f"{status.spoken_summary} Full weekly schedule: {status.weekly_schedule_summary}."

    async def search_knowledge(self, query: str) -> str:
        """
        Search the business's official documents, pricing, and services to answer caller questions.

        Args:
            query: The specific question or search keywords to look up in the business knowledge base.
        """
        result = await search_knowledge_async(
            business_id=self.business_id,
            query=query,
            call_id=self.call_id,
            log_miss=True,
        )

        if result.is_match and result.matches:
            top_match = result.matches[0]
            context_text = "\n\n".join(m.content for m in result.matches)
            return (
                f"Information found in '{top_match.source_title}':\n"
                f"{context_text}\n\n"
                "Instruction: Answer the caller's question concisely using ONLY this information. "
                "Keep your answer short for speech."
            )

        return (
            "NO MATCH: No relevant information was found in the official records. "
            "STRICT INSTRUCTION: Do NOT invent or speculate. Tell the caller you do not have "
            "that specific information in your records, and offer to take a message for the team."
        )

    async def take_message(
        self,
        caller_name: str,
        callback_number: str,
        reason: str,
    ) -> str:
        """
        Take a message from the caller to request a callback or when an answer is not known.

        Args:
            caller_name: The full name of the caller.
            callback_number: The best phone number to reach the caller.
            reason: The reason for the call or inquiry details.
        """
        cleaned_name = caller_name.strip()
        cleaned_phone = callback_number.strip()
        cleaned_reason = reason.strip()

        async with get_async_session() as session:
            # Ensure parent Call record exists if call_id is supplied
            valid_call_id = None
            if self.call_id:
                call_obj = await session.get(Call, self.call_id)
                if not call_obj:
                    call_obj = Call(
                        id=self.call_id,
                        business_id=self.business_id,
                        caller_number="console",
                    )
                    session.add(call_obj)
                    await session.flush()
                valid_call_id = self.call_id

            msg = Message(
                business_id=self.business_id,
                call_id=valid_call_id,
                caller_name=cleaned_name,
                callback_number=cleaned_phone,
                reason=cleaned_reason,
            )
            session.add(msg)
            await session.flush()

            try:
                from callwise.notifications.service import notify_message
                await notify_message(session=session, business=self.business, message=msg)
            except Exception as exc:
                logger.error(f"Error dispatching message notification: {exc}")

            await session.commit()

        return (
            f"Message recorded successfully for {cleaned_name} at {cleaned_phone} regarding '{cleaned_reason}'. "
            "Confirm to the caller that their message has been passed to the team and thank them."
        )

    def get_livekit_tools(self) -> List[Any]:
        """Wrap tool methods with LiveKit's @function_tool decorator."""
        toolset = self

        @function_tool
        def get_business_hours(day: Optional[str] = None) -> str:
            """Check whether the business is currently open or get operating hours for today or a specific day."""
            return toolset.get_business_hours(day=day)

        @function_tool
        async def search_knowledge(query: str) -> str:
            """Search official business documents, pricing, and services to answer caller questions."""
            return await toolset.search_knowledge(query=query)

        @function_tool
        async def take_message(caller_name: str, callback_number: str, reason: str) -> str:
            """Take a message and callback request from the caller."""
            return await toolset.take_message(
                caller_name=caller_name,
                callback_number=callback_number,
                reason=reason,
            )

        return [get_business_hours, search_knowledge, take_message]
