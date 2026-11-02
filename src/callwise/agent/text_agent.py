"""Text-only runner for Callwise agent simulating conversations without audio."""

import json
import logging
from typing import Any, Dict, List, Optional
import uuid

from callwise.agent.prompt import build_system_prompt
from callwise.agent.tools import CallwiseToolset
from callwise.config import settings
from callwise.db.models import Business
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
                        "type": "string",
                        "description": "Optional day of the week (e.g. 'Monday', 'Friday').",
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
]


def clean_speech_text(text: str) -> str:
    """Normalize unicode special characters and strip markdown for speech/console output."""
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
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.strip()


class TextAgent:
    """Simulates the conversational voice agent in text mode without requiring audio WebRTC."""

    def __init__(
        self,
        business: Business,
        call_id: Optional[uuid.UUID] = None,
        provider_name: Optional[str] = None,
    ):
        self.business = business
        self.call_id = call_id or uuid.uuid4()
        self.provider_name = (provider_name or settings.llm_provider).lower()
        self.toolset = CallwiseToolset(business, call_id=self.call_id)
        self.system_prompt = build_system_prompt(business)
        self.conversation_history: List[Dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt}
        ]

    async def _execute_tool(self, name: str, args: Dict[str, Any]) -> str:
        """Dispatch tool calls to CallwiseToolset."""
        if name == "get_business_hours":
            return self.toolset.get_business_hours(day=args.get("day"))
        elif name == "search_knowledge":
            query = args.get("query", "")
            return await self.toolset.search_knowledge(query=query)
        elif name == "take_message":
            return await self.toolset.take_message(
                caller_name=args.get("caller_name", "Anonymous"),
                callback_number=args.get("callback_number", "Unknown"),
                reason=args.get("reason", "No reason provided"),
            )
        return f"Unknown tool: {name}"

    async def ask(self, user_message: str) -> str:
        """
        Send a user turn to the agent, executing any tool calls,
        and return the agent's conversational response.
        """
        self.conversation_history.append({"role": "user", "content": user_message})

        # Branch based on provider
        if self.provider_name == "groq":
            raw_reply = await self._run_groq_turn()
        elif self.provider_name == "gemini":
            raw_reply = await self._run_gemini_turn(user_message)
        else:
            raw_reply = await self._run_prompt_loop_turn(user_message)

        return clean_speech_text(raw_reply)

    async def _run_groq_turn(self) -> str:
        """Execute turn using Groq with native tool calling."""
        import groq
        client = groq.AsyncGroq(api_key=settings.groq_api_key)

        # Allow up to 2 tool execution iterations per turn
        for _ in range(2):
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

        # Fallback if loop finishes on tool output
        return "Thank you. Is there anything else I can help you with today?"


    async def _run_gemini_turn(self, user_message: str) -> str:
        """Execute turn using Google Gemini with direct tool execution."""
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.gemini_api_key)

        # Tool declaration for Gemini
        def get_business_hours(day: str = "") -> str:
            """Check opening hours."""
            return self.toolset.get_business_hours(day=day or None)

        async def search_knowledge(query: str) -> str:
            """Search knowledge base."""
            return await self.toolset.search_knowledge(query=query)

        async def take_message(caller_name: str, callback_number: str, reason: str) -> str:
            """Take a message."""
            return await self.toolset.take_message(caller_name, callback_number, reason)

        # Quick intent routing for Gemini text mode
        lower_q = user_message.lower()
        tool_context = ""

        if any(w in lower_q for w in ["hour", "open", "close", "schedule", "when do you", "are you open"]):
            tool_context = f"\n[System Tool Result for get_business_hours]:\n{self.toolset.get_business_hours()}\n"
        elif any(w in lower_q for w in ["price", "cost", "how much", "insurance", "service", "where", "located", "policy"]):
            search_res = await self.toolset.search_knowledge(user_message)
            tool_context = f"\n[System Tool Result for search_knowledge]:\n{search_res}\n"
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
        elif any(w in lower_q for w in ["price", "cost", "insurance", "service", "where", "how much"]):
            context_inject = f"\n[Records]: {await self.toolset.search_knowledge(user_message)}"

        prompt = f"Caller: {user_message}{context_inject}\nAI Receptionist:"
        reply = await llm.generate_response(prompt, system_prompt=self.system_prompt)
        self.conversation_history.append({"role": "assistant", "content": reply})
        return reply
