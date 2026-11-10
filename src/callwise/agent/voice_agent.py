"""LiveKit Voice Pipeline Agent: STT, VAD, LLM, TTS, tools, and greetings."""

import logging
from typing import Any, Optional
import uuid

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
        from livekit.plugins import groq
        return groq.LLM(
            model=settings.groq_model,
            api_key=settings.groq_api_key,
        )
    elif provider == "gemini":
        from livekit.plugins import google
        return google.LLM(
            model=settings.gemini_model,
            api_key=settings.gemini_api_key,
        )
    elif provider == "ollama":
        from livekit.plugins import openai
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
        from livekit.plugins import cartesia
        return cartesia.TTS(
            voice=settings.cartesia_voice,
            api_key=settings.cartesia_api_key,
        )
    elif provider == "deepgram":
        from livekit.plugins import deepgram
        return deepgram.TTS(
            model=settings.deepgram_voice,
            api_key=settings.deepgram_api_key,
        )
    else:
        raise ValueError(f"Unsupported voice TTS provider: {provider}")


def create_voice_agent(
    business: Business,
    call_id: Optional[uuid.UUID] = None,
) -> tuple[Any, Any]:
    """Assemble Agent and AgentSession with business-specific prompt and tools."""
    from livekit.agents import Agent, AgentSession
    from livekit.plugins import deepgram, silero

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


async def entrypoint(ctx):
    """
    LiveKit Agents Job Entrypoint.
    Executes in a spawned worker process when a call/room is assigned.
    Must be a top-level module function to support multiprocessing/forkserver pickling.
    """
    import os
    import uuid
    from callwise.db.session import get_sync_session
    from callwise.db.models import Business

    business_id_str = os.getenv("CALLWISE_BUSINESS_ID")
    if not business_id_str:
        logger.error("CALLWISE_BUSINESS_ID environment variable not set")
        return
    business_id = uuid.UUID(business_id_str)

    with get_sync_session() as db_session:
        business = db_session.get(Business, business_id)
        if not business:
            logger.error(f"Business not found with ID: {business_id}")
            return
        business_name = business.name
        greeting = (business.greeting or "").strip()

    logger.info(f"Connecting to LiveKit room for business: {business_name}")
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
    logger.info(f'Speaking initial greeting: "{greeting}"')
    await session.say(greeting)


def start_voice_worker(business_id: uuid.UUID, mode: str = "dev"):
    """
    Launch the LiveKit worker for a given business tenant.
    Supports console testing, playground testing, or production room WebRTC.
    """
    import os
    import sys
    from livekit.agents import WorkerOptions, cli

    os.environ["CALLWISE_BUSINESS_ID"] = str(business_id)

    with get_sync_session() as db_session:
        business = db_session.get(Business, business_id)
        if not business:
            raise ValueError(f"Business not found with ID: {business_id}")

    sys.argv = ["voice_agent.py", mode]
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
