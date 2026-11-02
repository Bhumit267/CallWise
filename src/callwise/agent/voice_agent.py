"""LiveKit Voice Pipeline Agent: STT, VAD, LLM, TTS, tools, and greetings."""

import logging
from typing import Any, Optional
import uuid

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    WorkerOptions,
    cli,
)
from livekit.plugins import cartesia, deepgram, google, groq, openai, silero

from callwise.agent.prompt import build_system_prompt
from callwise.agent.tools import CallwiseToolset
from callwise.calls.manager import end_call_async
from callwise.config import settings
from callwise.db.models import Business
from callwise.db.session import get_sync_session

logger = logging.getLogger(__name__)


def create_llm_plugin():
    """Instantiate the active LiveKit LLM plugin based on settings."""
    provider = settings.llm_provider.lower().strip()
    if provider == "groq":
        return groq.LLM(
            model=settings.groq_model,
            api_key=settings.groq_api_key,
        )
    elif provider == "gemini":
        return google.LLM(
            model=settings.gemini_model,
            api_key=settings.gemini_api_key,
        )
    elif provider == "ollama":
        return openai.LLM(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            api_key="ollama",
        )
    else:
        raise ValueError(f"Unsupported voice LLM provider: {provider}")


def create_tts_plugin():
    """Instantiate the active LiveKit TTS plugin based on settings."""
    provider = settings.tts_provider.lower().strip()
    if provider == "cartesia":
        return cartesia.TTS(
            voice=settings.cartesia_voice,
            api_key=settings.cartesia_api_key,
        )
    elif provider == "deepgram":
        return deepgram.TTS(
            model=settings.deepgram_voice,
            api_key=settings.deepgram_api_key,
        )
    else:
        raise ValueError(f"Unsupported voice TTS provider: {provider}")


def create_voice_agent(
    business: Business,
    call_id: Optional[uuid.UUID] = None,
) -> tuple[Agent, AgentSession]:
    """Assemble Agent and AgentSession with business-specific prompt and tools."""
    toolset = CallwiseToolset(business, call_id=call_id)
    instructions = build_system_prompt(business)

    agent = Agent(
        instructions=instructions,
        tools=toolset.get_livekit_tools(),
    )

    session = AgentSession(
        stt=deepgram.STT(api_key=settings.deepgram_api_key),
        vad=silero.VAD.load(),
        llm=create_llm_plugin(),
        tts=create_tts_plugin(),
    )

    return agent, session


def start_voice_worker(business_id: uuid.UUID, mode: str = "dev"):
    """
    Launch the LiveKit worker for a given business tenant.
    Supports console testing, playground testing, or production room WebRTC.
    """
    with get_sync_session() as db_session:
        business = db_session.get(Business, business_id)
        if not business:
            raise ValueError(f"Business not found with ID: {business_id}")

    async def entrypoint(ctx: JobContext):
        logger.info(f"Connecting to LiveKit room for business: {business.name}")
        await ctx.connect()

        call_id = uuid.uuid4()
        agent, session = create_voice_agent(business, call_id=call_id)

        # Start agent session inside the connected WebRTC room
        await session.start(agent=agent, room=ctx.room)

        async def on_shutdown():
            logger.info(f"Closing call {call_id} and generating summary...")
            await end_call_async(call_id)

        ctx.add_shutdown_callback(on_shutdown)

        # Greet caller with business-specific greeting
        greeting = business.greeting.strip()
        logger.info(f"Speaking initial greeting: \"{greeting}\"")
        await session.say(greeting)

    import sys
    sys.argv = ["voice_agent.py", mode]
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
