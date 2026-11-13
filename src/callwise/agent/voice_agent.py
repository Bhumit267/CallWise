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


def build_turn_handling_options() -> Any:
    """Build ultra-responsive voice turn handling & barge-in interruption resilience options."""
    from livekit.agents import TurnHandlingOptions
    from livekit.agents.voice.turn import EndpointingOptions, InterruptionOptions

    return TurnHandlingOptions(
        turn_detection="vad",
        endpointing=EndpointingOptions(
            mode="dynamic",
            min_delay=0.04,
            max_delay=0.20,
        ),
        interruption=InterruptionOptions(
            enabled=True,
            mode="vad",
            min_duration=0.15,
            discard_audio_if_uninterruptible=True,
        ),
    )


def create_voice_agent(
    business: Business,
    call_id: Optional[uuid.UUID] = None,
) -> tuple[Any, Any]:
    """Assemble Agent and AgentSession with business-specific prompt, tools, and sub-300ms latency options."""
    from livekit.agents import Agent, AgentSession
    from livekit.plugins import deepgram, silero

    toolset = CallwiseToolset(business, call_id=call_id)
    instructions = build_system_prompt(business)

    agent = Agent(
        instructions=instructions,
        tools=toolset.get_livekit_tools(),
    )

    turn_opts = build_turn_handling_options()

    session = AgentSession(
        stt=deepgram.STT(
            api_key=settings.deepgram_api_key,
            endpointing_ms=25,
            interim_results=True,
        ),
        vad=silero.VAD.load(
            min_speech_duration=0.04,
            min_silence_duration=0.20,
            prefix_padding_duration=0.15,
        ),
        llm=create_llm_plugin(),
        tts=create_tts_plugin(),
        turn_handling=turn_opts,
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

    # Real-time Terminal Logging with millisecond precision
    import time
    from datetime import datetime
    turn_metrics = {}

    @session.on("user_input_transcribed")
    def _on_user_input(ev):
        if getattr(ev, "is_final", False):
            transcript = getattr(ev, "transcript", "").strip()
            if transcript:
                turn_metrics["start"] = time.perf_counter()
                time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                print(f"\n" + "═" * 70, flush=True)
                print(f"🕒 [{time_str}] 👤 CALLER QUESTION:", flush=True)
                print(f"   \"{transcript}\"", flush=True)
                print("─" * 70, flush=True)

    @session.on("conversation_item_added")
    def _on_item_added(ev):
        item = getattr(ev, "item", None)
        role = getattr(item, "role", None)
        if role == "assistant":
            raw_content = getattr(item, "content", None)
            text = ""
            if isinstance(raw_content, list):
                text = " ".join(str(c) for c in raw_content if isinstance(c, str))
            elif isinstance(raw_content, str):
                text = raw_content
            elif hasattr(item, "text") and item.text:
                text = item.text

            text = text.strip()
            # Exclude the greeting from response latency tracking
            if text and not text.startswith("Hello! Thanks for calling"):
                latency_ms = 0
                if "start" in turn_metrics:
                    latency_ms = int((time.perf_counter() - turn_metrics["start"]) * 1000)
                time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                print(f"🕒 [{time_str}] 🤖 AGENT ANSWER (⏱️ Latency: {latency_ms}ms):", flush=True)
                print(f"   \"{text}\"", flush=True)
                print("═" * 70 + "\n", flush=True)

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
    from dotenv import load_dotenv
    load_dotenv()
    from livekit.agents import WorkerOptions, cli

    os.environ["CALLWISE_BUSINESS_ID"] = str(business_id).strip()
    if settings.livekit_url:
        os.environ["LIVEKIT_URL"] = settings.livekit_url
    if settings.livekit_api_key:
        os.environ["LIVEKIT_API_KEY"] = settings.livekit_api_key
    if settings.livekit_api_secret:
        os.environ["LIVEKIT_API_SECRET"] = settings.livekit_api_secret

    with get_sync_session() as db_session:
        business = db_session.get(Business, business_id)
        if not business:
            raise ValueError(f"Business not found with ID: {business_id}")

    sys.argv = ["voice_agent.py", mode]
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))