"""LiveKit Voice Pipeline Agent: Multi-tenant per-call routing, STT, VAD, LLM, TTS, tools, and greetings."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import time
from typing import Any, Optional
import uuid

from sqlalchemy import select

from callwise.agent.prompt import build_system_prompt
from callwise.agent.tools import CallwiseToolset
from callwise.calls.manager import end_call_async
from callwise.calls.usage import check_usage_limits_async
from callwise.config import settings
from callwise.db.models import Business, Call, Contact, VoiceSession
from callwise.db.session import get_async_session, get_sync_session
from callwise.telephony.router import (
    create_inbound_call_record_async,
    normalize_e164,
    resolve_inbound_call_async,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Rejection Audio Rate Limiter
# ============================================================================

class VoiceRejectionRateLimiter:
    """Rate limit TTS audio playback for rejected calls to prevent credit burning from spam."""

    def __init__(
        self,
        per_caller_limit: int = 3,
        per_caller_window_secs: float = 3600.0,
        global_limit: int = 30,
        global_window_secs: float = 60.0,
    ):
        self.per_caller_limit = per_caller_limit
        self.per_caller_window_secs = per_caller_window_secs
        self.global_limit = global_limit
        self.global_window_secs = global_window_secs
        self._caller_history: dict[str, list[float]] = {}
        self._global_history: list[float] = []

    def can_play_rejection_tts(self, caller: Optional[str]) -> bool:
        """Check whether rejection TTS playback is permitted under rate limits."""
        now = time.time()
        # Clean global history
        self._global_history = [t for t in self._global_history if now - t < self.global_window_secs]
        if len(self._global_history) >= self.global_limit:
            return False

        if caller:
            history = self._caller_history.get(caller, [])
            history = [t for t in history if now - t < self.per_caller_window_secs]
            self._caller_history[caller] = history
            if len(history) >= self.per_caller_limit:
                return False

        return True

    def record_rejection_tts(self, caller: Optional[str]) -> None:
        """Record a played rejection TTS playback timestamp."""
        now = time.time()
        self._global_history.append(now)
        if caller:
            self._caller_history.setdefault(caller, []).append(now)

    def reset(self) -> None:
        """Reset all in-memory tracking (for test suites)."""
        self._caller_history.clear()
        self._global_history.clear()


rejection_rate_limiter = VoiceRejectionRateLimiter()


# ============================================================================
# Plugin Instantiation Helpers
# ============================================================================

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


# ============================================================================
# Multi-Tenant Inbound Call Resolution
# ============================================================================

@dataclass
class ResolvedVoiceCall:
    """Context outcome of routing an inbound voice call."""
    allowed: bool
    business: Optional[Business] = None
    call_id: Optional[uuid.UUID] = None
    contact: Optional[Contact] = None
    caller_number: Optional[str] = None
    dialed_number: Optional[str] = None
    channel: str = "phone"  # "phone", "web", or "dev_fallback"
    reject_reason: Optional[str] = None
    reply_message: Optional[str] = None


async def _resolve_dev_fallback(
    caller_number: Optional[str] = "dev_caller",
) -> Optional[ResolvedVoiceCall]:
    """Resolve dev fallback business if and only if explicitly allowed."""
    if not settings.allow_default_business or not settings.default_business_id:
        return None

    try:
        def_biz_id = uuid.UUID(str(settings.default_business_id))
        async with get_async_session() as db_session:
            stmt = select(Business).where(Business.id == def_biz_id)
            fallback_biz = (await db_session.execute(stmt)).scalar_one_or_none()
            if fallback_biz:
                logger.warning(
                    f"[Voice Router] DEV FALLBACK ACTIVE: Routing call to {fallback_biz.name} ({def_biz_id})"
                )
                return ResolvedVoiceCall(
                    allowed=True,
                    business=fallback_biz,
                    caller_number=caller_number or "dev_caller",
                    channel="dev_fallback",
                )
    except Exception as exc:
        logger.error(f"[Voice Router] Dev fallback error: {exc}")
    return None


async def resolve_voice_call_context(ctx: Any) -> ResolvedVoiceCall:
    """
    Resolve the business tenant and caller context for an incoming LiveKit call:
    1. If participant is SIP (kind == ParticipantKind.PARTICIPANT_KIND_SIP):
       - Extract dialed number from `sip.trunkPhoneNumber` or `sip.dialedNumber`.
       - Normalize E.164 and lookup in `phone_numbers` table.
       - Verify blocklist, rate limits, and usage limits.
    2. If participant is NOT SIP (WebRTC / in-browser voice):
       - Ignore all `sip.*` attributes.
       - Extract `voice_session_id` from participant token metadata.
       - Single source of truth: lookup in `voice_sessions` table (rejection on expired, reused, unknown).
       - Verify usage limits.
    3. If unmapped and ALLOW_DEFAULT_BUSINESS=True (dev only), fallback to BUSINESS_ID.
    4. Otherwise, reject without loading any business prompt, tools, or creating DB rows.
    """
    # 1. Fetch remote participant
    participant = None
    if getattr(ctx, "room", None) and getattr(ctx.room, "remote_participants", None):
        participant = next(iter(ctx.room.remote_participants.values()), None)

    if not participant and hasattr(ctx, "wait_for_participant"):
        try:
            participant = await asyncio.wait_for(ctx.wait_for_participant(), timeout=8.0)
        except Exception as exc:
            logger.warning(f"[Voice Router] No participant connected within timeout: {exc}")

    if not participant:
        fallback = await _resolve_dev_fallback("unknown_caller")
        if fallback:
            return fallback
        return ResolvedVoiceCall(
            allowed=False,
            reject_reason="no_participant",
            reply_message="No caller detected. Goodbye.",
        )

    # 2. Check if participant is genuinely SIP
    is_sip = False
    try:
        from livekit import rtc
        is_sip = (getattr(participant, "kind", None) == rtc.ParticipantKind.PARTICIPANT_KIND_SIP)
    except Exception:
        # Fallback if rtc enum not available directly
        is_sip = (getattr(participant, "kind", None) in (3, "PARTICIPANT_KIND_SIP", "sip"))

    attrs = getattr(participant, "attributes", {}) or {}

    # 3. Branch A: Legitimate SIP Call
    if is_sip:
        dialed_raw = attrs.get("sip.trunkPhoneNumber") or attrs.get("sip.dialedNumber") or ""
        caller_raw = attrs.get("sip.phoneNumber") or ""

        if not dialed_raw:
            fallback = await _resolve_dev_fallback(caller_raw)
            if fallback:
                return fallback
            return ResolvedVoiceCall(
                allowed=False,
                caller_number=caller_raw,
                reject_reason="missing_dialed_number",
                reply_message="Thank you for calling. This number is not currently configured or in service. Goodbye.",
            )

        norm_dialed = normalize_e164(dialed_raw)
        caller_name = getattr(participant, "name", None)
        route = await resolve_inbound_call_async(
            dialed_number=norm_dialed,
            caller_number=caller_raw,
            caller_name=caller_name,
        )

        if not route.matched:
            fallback = await _resolve_dev_fallback(caller_raw)
            if fallback:
                return fallback
            return ResolvedVoiceCall(
                allowed=False,
                caller_number=caller_raw,
                dialed_number=norm_dialed,
                reject_reason=route.reject_reason,
                reply_message=route.reply_message,
            )

        if route.is_blocked:
            return ResolvedVoiceCall(
                allowed=False,
                caller_number=caller_raw,
                dialed_number=norm_dialed,
                reject_reason=route.reject_reason,
                reply_message=route.reply_message,
            )

        # Check tenant usage limits
        limit_check = await check_usage_limits_async(route.business.id, session_type="phone")
        if not limit_check.allowed:
            return ResolvedVoiceCall(
                allowed=False,
                caller_number=caller_raw,
                dialed_number=norm_dialed,
                reject_reason=limit_check.limit_type,
                reply_message=limit_check.graceful_message,
            )

        return ResolvedVoiceCall(
            allowed=True,
            business=route.business,
            contact=route.contact,
            caller_number=caller_raw,
            dialed_number=norm_dialed,
            channel="phone",
        )

    # 4. Branch B: Non-SIP Call (WebRTC In-Browser Voice)
    # Security Rule 2: NEVER trust sip.* attributes on a non-SIP participant
    # Security Rule 5: Exactly one source of truth -> VoiceSession in DB
    raw_meta = getattr(participant, "metadata", "") or ""
    voice_session_id_str = None
    if raw_meta:
        try:
            parsed = json.loads(raw_meta)
            if isinstance(parsed, dict):
                voice_session_id_str = parsed.get("voice_session_id")
        except Exception:
            pass

    if not voice_session_id_str:
        fallback = await _resolve_dev_fallback("web_browser")
        if fallback:
            return fallback
        return ResolvedVoiceCall(
            allowed=False,
            caller_number="web_browser",
            channel="web",
            reject_reason="missing_voice_session",
            reply_message="Invalid or missing voice session. Goodbye.",
        )

    try:
        session_uuid = uuid.UUID(str(voice_session_id_str))
    except (ValueError, TypeError):
        return ResolvedVoiceCall(
            allowed=False,
            caller_number="web_browser",
            channel="web",
            reject_reason="malformed_voice_session",
            reply_message="Invalid voice session identifier. Goodbye.",
        )

    now_utc = datetime.now(timezone.utc)
    async with get_async_session() as db_session:
        stmt = select(VoiceSession).where(VoiceSession.id == session_uuid)
        v_session = (await db_session.execute(stmt)).scalar_one_or_none()

        if not v_session:
            return ResolvedVoiceCall(
                allowed=False,
                caller_number="web_browser",
                channel="web",
                reject_reason="unknown_voice_session",
                reply_message="Voice session not found. Goodbye.",
            )

        if v_session.is_used:
            return ResolvedVoiceCall(
                allowed=False,
                caller_number="web_browser",
                channel="web",
                reject_reason="reused_voice_session",
                reply_message="This voice session has already been used. Goodbye.",
            )

        if v_session.expires_at < now_utc:
            return ResolvedVoiceCall(
                allowed=False,
                caller_number="web_browser",
                channel="web",
                reject_reason="expired_voice_session",
                reply_message="This voice session has expired. Goodbye.",
            )

        # Mark single-use session as used
        v_session.is_used = True
        v_session.used_at = now_utc

        biz_stmt = select(Business).where(Business.id == v_session.business_id)
        biz = (await db_session.execute(biz_stmt)).scalar_one_or_none()
        if not biz:
            await db_session.commit()
            return ResolvedVoiceCall(
                allowed=False,
                caller_number="web_browser",
                channel="web",
                reject_reason="business_not_found",
                reply_message="Business account not found. Goodbye.",
            )

        # Check tenant usage limits
        limit_check = await check_usage_limits_async(biz.id, session_type="widget")
        if not limit_check.allowed:
            await db_session.commit()
            return ResolvedVoiceCall(
                allowed=False,
                caller_number="web_browser",
                channel="web",
                reject_reason=limit_check.limit_type,
                reply_message=limit_check.graceful_message,
            )

        await db_session.commit()
        return ResolvedVoiceCall(
            allowed=True,
            business=biz,
            call_id=v_session.call_id,
            caller_number="web_browser",
            channel="web",
        )


# ============================================================================
# LiveKit Agents Job Entrypoint
# ============================================================================

async def entrypoint(ctx: Any):
    """
    LiveKit Agents Job Entrypoint.
    Executes in a spawned worker process when a call/room is assigned.
    Must be a top-level module function to support multiprocessing/forkserver pickling.
    """
    logger.info("Connecting to LiveKit room for incoming call...")
    await ctx.connect()

    resolved = await resolve_voice_call_context(ctx)

    if not resolved.allowed:
        logger.warning(
            f"[Voice Router] Call rejected: reason={resolved.reject_reason}, caller={resolved.caller_number}"
        )
        # Rate limit rejection TTS audio playback to prevent credit burning
        if resolved.reply_message and rejection_rate_limiter.can_play_rejection_tts(resolved.caller_number):
            rejection_rate_limiter.record_rejection_tts(resolved.caller_number)
            try:
                # Play audio rejection using lightweight agent session without business instructions
                from livekit.agents import Agent, AgentSession
                from livekit.plugins import deepgram, silero

                tts_plugin = create_tts_plugin()
                minimal_session = AgentSession(
                    tts=tts_plugin,
                    vad=silero.VAD.load(),
                    stt=deepgram.STT(api_key=settings.deepgram_api_key),
                    llm=create_llm_plugin(),
                )
                minimal_agent = Agent(instructions="You only speak the polite rejection message.")
                await minimal_session.start(agent=minimal_agent, room=ctx.room)
                await minimal_session.say(resolved.reply_message)
            except Exception as exc:
                logger.warning(f"[Voice Router] Could not speak rejection audio: {exc}")

        # Disconnect cleanly without writing any Call, Contact, or Usage records
        try:
            if hasattr(ctx.room, "disconnect"):
                await ctx.room.disconnect()
        except Exception:
            pass
        return

    business = resolved.business
    business_name = business.name
    greeting = (business.greeting or "").strip()

    # Determine or create call_id
    if resolved.channel == "phone":
        from callwise.telephony.router import InboundRouteResult
        dummy_route = InboundRouteResult(
            matched=True,
            business=resolved.business,
            contact=resolved.contact,
        )
        call_record = await create_inbound_call_record_async(
            route=dummy_route,
            caller_number=resolved.caller_number,
        )
        call_id = call_record.id
    else:
        call_id = resolved.call_id or uuid.uuid4()

    logger.info(f"[Voice Router] Accepted call {call_id} for business '{business_name}' ({business.id})")
    agent, session = create_voice_agent(business, call_id=call_id)

    # Real-time Terminal Logging with millisecond precision
    turn_metrics = {}

    @session.on("user_input_transcribed")
    def _on_user_input(ev):
        if getattr(ev, "is_final", False):
            transcript = getattr(ev, "transcript", "").strip()
            if transcript:
                turn_metrics["start"] = time.perf_counter()
                time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                print(f"\n" + "═" * 70, flush=True)
                print(f"🕒 [{time_str}] 👤 [{business_name}] CALLER QUESTION:", flush=True)
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
            if text and not text.startswith("Hello! Thanks for calling"):
                latency_ms = 0
                if "start" in turn_metrics:
                    latency_ms = int((time.perf_counter() - turn_metrics["start"]) * 1000)
                time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                print(f"🕒 [{time_str}] 🤖 [{business_name}] AGENT ANSWER (⏱️ Latency: {latency_ms}ms):", flush=True)
                print(f"   \"{text}\"", flush=True)
                print("═" * 70 + "\n", flush=True)

    # Start agent session inside the connected WebRTC room
    await session.start(agent=agent, room=ctx.room)

    async def on_shutdown():
        logger.info(f"Closing call {call_id} and generating summary...")
        await end_call_async(call_id)

    ctx.add_shutdown_callback(on_shutdown)

    # Greet caller with business-specific greeting
    logger.info(f'Speaking initial greeting for {business_name}: "{greeting}"')
    await session.say(greeting)


def start_voice_worker(business_id: Optional[uuid.UUID] = None, mode: str = "dev"):
    """
    Launch the LiveKit worker for multi-tenant voice routing.
    Supports console testing, playground testing, or production room WebRTC.
    """
    import os
    import sys
    from dotenv import load_dotenv
    load_dotenv()
    from livekit.agents import WorkerOptions, cli

    # Requirement 7: Startup guard refusing to start in production if ALLOW_DEFAULT_BUSINESS is true
    if settings.allow_default_business:
        env_mode = (settings.environment or "").lower().strip()
        cli_mode = (mode or "").lower().strip()
        if env_mode in ("prod", "production") or cli_mode in ("prod", "production"):
            raise RuntimeError(
                "CRITICAL SAFETY VIOLATION: ALLOW_DEFAULT_BUSINESS cannot be enabled in production mode! "
                "Voice agent must route calls multi-tenant per call."
            )

    if business_id and settings.allow_default_business:
        settings.default_business_id = str(business_id).strip()

    if settings.livekit_url:
        os.environ["LIVEKIT_URL"] = settings.livekit_url
    if settings.livekit_api_key:
        os.environ["LIVEKIT_API_KEY"] = settings.livekit_api_key
    if settings.livekit_api_secret:
        os.environ["LIVEKIT_API_SECRET"] = settings.livekit_api_secret

    sys.argv = ["voice_agent.py", mode]
    worker_opts = WorkerOptions(
        entrypoint_fnc=entrypoint,
        agent_name=settings.livekit_agent_name or None,
    )
    cli.run_app(worker_opts)
