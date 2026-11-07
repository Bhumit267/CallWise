"""Text-only runner for Callwise agent simulating conversations without audio."""

import asyncio
from datetime import datetime
import json
import logging
import time
from typing import Any, Dict, List, Optional
import unicodedata
import uuid

from callwise.agent.circuit_breaker import circuit_breaker
from callwise.agent.prompt import build_system_prompt
from callwise.agent.tools import CallwiseToolset
from callwise.calls.abuse import detect_nonsense_repetition
from callwise.calls.killswitch import FALLBACK_MESSAGE_TAKING_PROMPT, is_kill_switch_active
from callwise.calls.manager import record_call_turn_async
from callwise.calls.usage import check_usage_limits_async, record_usage_record_async
from callwise.config import settings
from callwise.db.models import Business
from callwise.notifications.service import notify_abuse_detected_async
from callwise.providers.llm import get_llm_provider

logger = logging.getLogger(__name__)

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_business_hours",
            "description": "Check whether the business is open right now or get opening hours for today or a specific day.",
            "parameters": {
                "type": "object",
                "properties": {
                    "day": {
                        "type": ["string", "null"],
                        "description": "Optional day of the week (e.g. 'Monday', 'Friday'). Pass null if checking general/current hours.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "Search the business's official records, services, pricing, and policies to answer questions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The specific question or search keywords.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "take_message",
            "description": "Take a message and callback request from the caller.",
            "parameters": {
                "type": "object",
                "properties": {
                    "caller_name": {
                        "type": "string",
                        "description": "Full name of the caller.",
                    },
                    "callback_number": {
                        "type": "string",
                        "description": "Phone number to reach the caller.",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for the message or callback.",
                    },
                },
                "required": ["caller_name", "callback_number", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_services",
            "description": "List all active bookable services, durations, and pricing.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Check available appointment slots for a service on a given date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_name": {
                        "type": "string",
                        "description": "Name of the service to check (e.g. 'Routine Dental Cleaning').",
                    },
                    "date": {
                        "type": "string",
                        "description": "Target date string (e.g. 'today', 'tomorrow', 'YYYY-MM-DD').",
                    },
                },
                "required": ["service_name", "date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Reserve an appointment. STRICT: Read back full details and get explicit caller confirmation before calling this.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_name": {
                        "type": "string",
                        "description": "Name of the service.",
                    },
                    "start_time": {
                        "type": "string",
                        "description": "Start time in YYYY-MM-DD HH:MM format.",
                    },
                    "customer_name": {
                        "type": "string",
                        "description": "Customer full name.",
                    },
                    "customer_phone": {
                        "type": "string",
                        "description": "Customer contact phone number.",
                    },
                    "customer_email": {
                        "type": ["string", "null"],
                        "description": "Optional email for confirmation.",
                    },
                },
                "required": ["service_name", "start_time", "customer_name", "customer_phone"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_appointment",
            "description": "Cancel an existing appointment with booking code and verified customer name or phone.",
            "parameters": {
                "type": "object",
                "properties": {
                    "booking_code": {
                        "type": "string",
                        "description": "6-character booking code (e.g. BK-4X2).",
                    },
                    "caller_name": {
                        "type": ["string", "null"],
                        "description": "Customer full name for identity verification.",
                    },
                    "caller_phone": {
                        "type": ["string", "null"],
                        "description": "Customer phone number for identity verification.",
                    },
                },
                "required": ["booking_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reschedule_appointment",
            "description": "Reschedule an existing appointment to a new date/time with verification.",
            "parameters": {
                "type": "object",
                "properties": {
                    "booking_code": {
                        "type": "string",
                        "description": "6-character booking code (e.g. BK-4X2).",
                    },
                    "new_time": {
                        "type": "string",
                        "description": "New appointment start time in YYYY-MM-DD HH:MM format.",
                    },
                    "caller_name": {
                        "type": ["string", "null"],
                        "description": "Customer full name for verification.",
                    },
                    "caller_phone": {
                        "type": ["string", "null"],
                        "description": "Customer phone number for verification.",
                    },
                },
                "required": ["booking_code", "new_time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "transfer_to_human",
            "description": "Transfer the caller to a human representative or staff member.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Reason for human escalation.",
                    },
                },
                "required": ["reason"],
            },
        },
    },
]


def clean_speech_text(text: str) -> str:
    """Normalize unicode special characters and strip markdown for speech/console output."""
    text = unicodedata.normalize("NFKD", text)
    replacements = {
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2026": "...",
        "\u202f": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    for md_char in ["*", "#", "`", "_", "[", "]"]:
        text = text.replace(md_char, "")
    return " ".join(text.split())


class TextAgent:
    """Runs interactive multi-turn dialogue through the LLM with tool calling."""

    def __init__(
        self,
        business: Business,
        call_id: Optional[uuid.UUID] = None,
        provider_name: Optional[str] = None,
        caller_number: Optional[str] = None,
    ):
        self.business = business
        self.call_id = call_id or uuid.uuid4()
        self.provider_name = (provider_name or settings.llm_provider).lower().strip()
        self.caller_number = caller_number
        self.toolset = CallwiseToolset(business, call_id=self.call_id)
        self.system_prompt = build_system_prompt(business)
        self.conversation_history: List[Dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt}
        ]
        self.consecutive_silence_count: int = 0
        self.caller_utterances: List[str] = []
        self.is_call_active: bool = True

    async def _execute_tool(self, name: str, args: Dict[str, Any]) -> str:
        """Route tool call execution to CallwiseToolset."""
        if name == "get_business_hours":
            day_val = args.get("day")
            if day_val and str(day_val).strip().lower() in ("null", "none"):
                day_val = None
            return self.toolset.get_business_hours(day=day_val)
        elif name == "search_knowledge":
            return await self.toolset.search_knowledge(query=args.get("query", ""))
        elif name == "take_message":
            return await self.toolset.take_message(
                caller_name=args.get("caller_name", "Anonymous"),
                callback_number=args.get("callback_number", "Unknown"),
                reason=args.get("reason", "No reason provided"),
            )
        elif name == "list_services":
            return await self.toolset.list_services()
        elif name == "check_availability":
            return await self.toolset.check_availability(
                service_name=args.get("service_name", ""),
                date_str=args.get("date", "today"),
            )
        elif name == "book_appointment":
            return await self.toolset.book_appointment(
                service_name=args.get("service_name", ""),
                start_time=args.get("start_time", ""),
                customer_name=args.get("customer_name", ""),
                customer_phone=args.get("customer_phone", ""),
                customer_email=args.get("customer_email"),
            )
        elif name == "cancel_appointment":
            return await self.toolset.cancel_appointment(
                booking_code=args.get("booking_code", ""),
                caller_name=args.get("caller_name"),
                caller_phone=args.get("caller_phone"),
            )
        elif name == "reschedule_appointment":
            return await self.toolset.reschedule_appointment(
                booking_code=args.get("booking_code", ""),
                new_time=args.get("new_time", ""),
                caller_name=args.get("caller_name"),
                caller_phone=args.get("caller_phone"),
            )
        elif name == "transfer_to_human":
            return await self.toolset.transfer_to_human(
                reason=args.get("reason", "Caller requested transfer"),
            )
        return f"Unknown tool: {name}"

    async def ask(
        self,
        user_message: str,
        session_type: str = "chat",
        call_duration_seconds: int = 0,
    ) -> str:
        """Send a user turn to the agent, executing any tool calls, and return conversational reply."""
        # Check if call is already ended
        if not self.is_call_active:
            return "This call has ended. Thank you for calling and have a great day!"

        cleaned_input = user_message.strip()

        # Check global emergency kill switch
        if is_kill_switch_active():
            logger.warning(f"[TextAgent] Global kill switch active for business {self.business.id}")
            await record_call_turn_async(
                call_id=self.call_id,
                business_id=self.business.id,
                speaker="caller",
                text=user_message,
            )
            await record_call_turn_async(
                call_id=self.call_id,
                business_id=self.business.id,
                speaker="agent",
                text=FALLBACK_MESSAGE_TAKING_PROMPT,
            )
            return FALLBACK_MESSAGE_TAKING_PROMPT

        # Handle Silence / Unresponsive Caller
        if not cleaned_input or cleaned_input.lower() in ("...", "[silence]", "silence"):
            self.consecutive_silence_count += 1
            if self.consecutive_silence_count == 1:
                prompt_reply = "Are you still there? How can I help you today?"
                await record_call_turn_async(
                    call_id=self.call_id,
                    business_id=self.business.id,
                    speaker="agent",
                    text=prompt_reply,
                )
                return prompt_reply
            else:
                self.is_call_active = False
                goodbye_reply = (
                    "I haven't heard anything from you, so I will let you go for now. "
                    "Please call us back whenever you are ready. Have a wonderful day! Goodbye."
                )
                await record_call_turn_async(
                    call_id=self.call_id,
                    business_id=self.business.id,
                    speaker="agent",
                    text=goodbye_reply,
                )
                return goodbye_reply

        # Reset silence counter upon receiving input
        self.consecutive_silence_count = 0

        # Check for caller abuse: nonsense repetition / flood patterns
        self.caller_utterances.append(user_message)
        if detect_nonsense_repetition(self.caller_utterances):
            logger.warning(f"[TextAgent] Nonsense repetition detected for call {self.call_id}")
            asyncio.create_task(
                notify_abuse_detected_async(
                    business_id=self.business.id,
                    caller_number=self.caller_number or "Unknown",
                    reason="Repeated nonsense or keyboard spam input",
                )
            )
            abuse_reply = (
                "I am having difficulty understanding your request. "
                "May I take down your name and callback number so someone from our team can follow up directly?"
            )
            await record_call_turn_async(
                call_id=self.call_id,
                business_id=self.business.id,
                speaker="caller",
                text=user_message,
            )
            await record_call_turn_async(
                call_id=self.call_id,
                business_id=self.business.id,
                speaker="agent",
                text=abuse_reply,
            )
            return abuse_reply

        # 1. Enforce usage limits and call duration cap before processing
        limit_check = await check_usage_limits_async(
            business_id=self.business.id,
            session_type=session_type,
            current_call_duration_seconds=call_duration_seconds,
        )
        if not limit_check.allowed:
            logger.warning(
                f"[TextAgent] Limit reached ({limit_check.limit_type}) for business {self.business.id}"
            )
            if limit_check.limit_type == "call_duration":
                self.is_call_active = False
            degrade_reply = (
                limit_check.graceful_message
                or "We are currently operating at capacity. May I take down your contact details so our team can follow up?"
            )
            await record_call_turn_async(
                call_id=self.call_id,
                business_id=self.business.id,
                speaker="caller",
                text=user_message,
            )
            await record_call_turn_async(
                call_id=self.call_id,
                business_id=self.business.id,
                speaker="agent",
                text=degrade_reply,
            )
            return degrade_reply

        await record_call_turn_async(
            call_id=self.call_id,
            business_id=self.business.id,
            speaker="caller",
            text=user_message,
        )

        self.conversation_history.append({"role": "user", "content": user_message})

        t_start = time.perf_counter()

        # Circuit Breaker Provider Selection
        active_provider = circuit_breaker.select_active_provider(
            primary=self.provider_name,
            fallback=settings.fallback_llm_provider,
        )

        raw_reply: Optional[str] = None
        used_provider = active_provider or self.provider_name

        if not active_provider:
            # Both primary and fallback circuits are open
            raw_reply = (
                "Our AI assistant is temporarily unavailable due to connectivity issues. "
                "May I take down your name and callback number so our staff can assist you directly?"
            )
        else:
            try:
                raw_reply = await self._run_provider_turn(active_provider, user_message)
                circuit_breaker.record_success(active_provider)
                used_provider = active_provider
            except Exception as exc:
                logger.error(f"[TextAgent] Provider '{active_provider}' error: {exc}")
                circuit_breaker.record_failure(active_provider, exc)

                # Attempt immediate failover if secondary is available
                fb = (settings.fallback_llm_provider or "").lower().strip()
                if fb and fb != active_provider and circuit_breaker.is_available(fb):
                    logger.info(f"[TextAgent] Failing over to secondary provider '{fb}'")
                    try:
                        raw_reply = await self._run_provider_turn(fb, user_message)
                        circuit_breaker.record_success(fb)
                        used_provider = fb
                    except Exception as fb_exc:
                        logger.critical(f"[TextAgent] Secondary provider '{fb}' also failed: {fb_exc}")
                        circuit_breaker.record_failure(fb, fb_exc)

            if not raw_reply:
                raw_reply = (
                    "I apologize, but our voice assistant is currently experiencing technical difficulties. "
                    "May I take down your name and callback number so someone can assist you directly?"
                )

        latency_ms = (time.perf_counter() - t_start) * 1000.0
        clean_reply = clean_speech_text(raw_reply)

        await record_call_turn_async(
            call_id=self.call_id,
            business_id=self.business.id,
            speaker="agent",
            text=clean_reply,
            latency_ms=latency_ms,
        )

        # Track usage record for this interaction
        try:
            # Estimate tokens roughly (~4 chars per token)
            in_tokens = max(1, len(user_message) // 4)
            out_tokens = max(1, len(clean_reply) // 4)
            await record_usage_record_async(
                business_id=self.business.id,
                call_id=self.call_id,
                session_type=session_type,
                duration_seconds=int(latency_ms / 1000.0) if latency_ms else 1,
                llm_input_tokens=in_tokens,
                llm_output_tokens=out_tokens,
                llm_provider=used_provider,
            )
        except Exception as exc:
            logger.warning(f"[TextAgent] Failed to record usage metric: {exc}")

        return clean_reply

    async def _run_provider_turn(self, provider: str, user_message: str) -> str:
        """Route turn to specified LLM provider."""
        if provider == "groq":
            return await self._run_groq_turn()
        elif provider == "gemini":
            return await self._run_gemini_turn(user_message)
        else:
            return await self._run_prompt_loop_turn(user_message)

    async def _run_groq_turn(self) -> str:
        """Execute turn using Groq with native tool calling."""
        import groq
        client = groq.AsyncGroq(api_key=settings.groq_api_key)

        for _ in range(3):
            response = await client.chat.completions.create(
                model=settings.groq_model,
                messages=self.conversation_history,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
                temperature=0.3,
                max_tokens=400,
            )
            msg = response.choices[0].message
            if msg.tool_calls:
                self.conversation_history.append(
                    {
                        "role": "assistant",
                        "content": msg.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                            for tc in msg.tool_calls
                        ],
                    }
                )
                for tc in msg.tool_calls:
                    fn_name = tc.function.name
                    try:
                        fn_args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        fn_args = {}

                    tool_output = await self._execute_tool(fn_name, fn_args)
                    self.conversation_history.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "name": fn_name,
                            "content": tool_output,
                        }
                    )
            else:
                agent_reply = msg.content or ""
                self.conversation_history.append({"role": "assistant", "content": agent_reply})
                return agent_reply

        return "Thank you. Is there anything else I can help you with today?"

    async def _run_gemini_turn(self, user_message: str) -> str:
        """Execute turn using Google Gemini with direct tool execution."""
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.gemini_api_key)

        lower_q = user_message.lower()
        tool_context = ""

        if any(w in lower_q for w in ["hour", "open", "close", "schedule", "when do you", "are you open"]):
            tool_context = f"\n[System Tool Result for get_business_hours]:\n{self.toolset.get_business_hours()}\n"
        elif any(w in lower_q for w in ["what services", "services do you", "list services", "bookable services"]):
            services_res = await self.toolset.list_services()
            tool_context = f"\n[System Tool Result for list_services]:\n{services_res}\n"
        elif any(w in lower_q for w in ["price", "cost", "how much", "insurance", "where", "located", "policy"]):
            search_res = await self.toolset.search_knowledge(user_message)
            tool_context = f"\n[System Tool Result for search_knowledge]:\n{search_res}\n"
        elif any(w in lower_q for w in ["transfer", "speak to someone", "human", "representative", "manager"]):
            transfer_res = await self.toolset.transfer_to_human("Caller requested transfer to staff")
            tool_context = f"\n[System Tool Result for transfer_to_human]:\n{transfer_res}\n"
        elif any(w in lower_q for w in ["take a message", "leave a message", "call me back"]):
            tool_context = "\n[System Tool Instruction]: Ask for the caller's full name, phone number, and brief reason for callback.\n"

        augmented_prompt = f"{user_message}\n{tool_context}"
        response = await client.aio.models.generate_content(
            model=settings.gemini_model,
            contents=augmented_prompt,
            config=types.GenerateContentConfig(
                system_instruction=self.system_prompt,
                temperature=0.3,
                max_output_tokens=300,
            ),
        )
        reply = response.text or ""
        self.conversation_history.append({"role": "assistant", "content": reply})
        return reply

    async def _run_prompt_loop_turn(self, user_message: str) -> str:
        """Generic fallback for local Ollama and simple LLMs."""
        llm = get_llm_provider(self.provider_name)
        lower_q = user_message.lower()

        context_inject = ""
        if any(w in lower_q for w in ["hour", "open", "close", "schedule", "when do you"]):
            context_inject = f"\n[Hours Info]: {self.toolset.get_business_hours()}"
        elif any(w in lower_q for w in ["what services", "services do you", "list services"]):
            context_inject = f"\n[Services List]: {await self.toolset.list_services()}"
        elif any(w in lower_q for w in ["price", "cost", "insurance", "service", "where", "how much"]):
            context_inject = f"\n[Records]: {await self.toolset.search_knowledge(user_message)}"
        elif any(w in lower_q for w in ["transfer", "speak to someone", "representative", "operator"]):
            context_inject = f"\n[Transfer]: {await self.toolset.transfer_to_human('Caller requested human')}"

        prompt = f"Caller: {user_message}{context_inject}\nAI Receptionist:"
        reply = await llm.generate_response(prompt, system_prompt=self.system_prompt)
        self.conversation_history.append({"role": "assistant", "content": reply})
        return reply
