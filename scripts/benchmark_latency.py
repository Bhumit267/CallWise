"""Clean turn latency benchmark of the Callwise TextAgent path (LLM + tools + knowledge search).

Measures turnaround time across 32 real conversational turns for:
1. Aarav Health & Dental Clinic (16 turns)
2. Luxe Glow Salon & Spa (16 turns)

A 3.5s pause is applied between turns to prevent hitting Groq's on-demand free tier rate limits (30 RPM).
Tracks:
- Turn turnaround latency (time.perf_counter)
- Whether any rate-limiting retries or errors occurred
- Summary statistics: n, median, p95, min, max, retries count
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import platform
import statistics
import time
from typing import Any, Dict, List
import uuid

from sqlalchemy import select

from callwise.agent.text_agent import TextAgent
from callwise.config import settings
from callwise.db.models import Business
from callwise.db.session import get_sync_session

# Custom log handler to detect any retries or rate-limit warnings
class RetryTracker(logging.Handler):
    def __init__(self):
        super().__init__()
        self.retry_events = []
        self.current_turn_retries = 0

    def emit(self, record):
        msg = record.getMessage().lower()
        if "429" in msg or "rate limit" in msg or "circuit breaker" in msg or "retry" in msg:
            self.retry_events.append(record.getMessage())
            self.current_turn_retries += 1

    def reset_turn(self):
        self.current_turn_retries = 0

BENCHMARK_QUESTIONS = [
    # --- Aarav Health & Dental Clinic (Bengaluru) ---
    {
        "biz": "aarav",
        "category": "pricing",
        "question": "How much does a routine dental cleaning and scaling cost?",
    },
    {
        "biz": "aarav",
        "category": "pricing",
        "question": "What is the fee for root canal treatment?",
    },
    {
        "biz": "aarav",
        "category": "hours",
        "question": "What time does your clinic open on Saturday?",
    },
    {
        "biz": "aarav",
        "category": "hours",
        "question": "Are you open on Sundays for consultations?",
    },
    {
        "biz": "aarav",
        "category": "scheduling",
        "question": "Can you check what appointment times are open for cleaning tomorrow?",
    },
    {
        "biz": "aarav",
        "category": "scheduling",
        "question": "What services do you offer for dental hygiene?",
    },
    {
        "biz": "aarav",
        "category": "policy",
        "question": "Do you accept digital UPI payments like Google Pay or PhonePe?",
    },
    {
        "biz": "aarav",
        "category": "policy",
        "question": "Do you offer cashless dental insurance with Star Health?",
    },
    {
        "biz": "aarav",
        "category": "unanswerable",
        "question": "Do you repair cracked iPhone screens while patients wait?",
    },
    {
        "biz": "aarav",
        "category": "unanswerable",
        "question": "Can I leave my pet parrot with your reception staff during my visit?",
    },
    {
        "biz": "aarav",
        "category": "advice_refusal",
        "question": "Can you prescribe me Amoxicillin 500mg for my swollen gum right now?",
    },
    {
        "biz": "aarav",
        "category": "advice_refusal",
        "question": "Should I invest in sovereign gold bonds or fixed deposits for dental savings?",
    },
    {
        "biz": "aarav",
        "category": "pricing",
        "question": "How much is an in-office teeth whitening session?",
    },
    {
        "biz": "aarav",
        "category": "hours",
        "question": "Are you open right now?",
    },
    {
        "biz": "aarav",
        "category": "scheduling",
        "question": "How do I cancel an existing appointment?",
    },
    {
        "biz": "aarav",
        "category": "message",
        "question": "Can you take a message for Dr. Aarav to call back regarding my x-ray report?",
    },

    # --- Luxe Glow Salon & Spa (Los Angeles) ---
    {
        "biz": "luxe",
        "category": "pricing",
        "question": "How much does a full custom balayage cost?",
    },
    {
        "biz": "luxe",
        "category": "pricing",
        "question": "What is the price for a signature hydrafacial?",
    },
    {
        "biz": "luxe",
        "category": "hours",
        "question": "What are your business hours on Friday?",
    },
    {
        "biz": "luxe",
        "category": "hours",
        "question": "Are you open on Monday mornings?",
    },
    {
        "biz": "luxe",
        "category": "scheduling",
        "question": "Can you check if there are appointments available for a blowout this Saturday?",
    },
    {
        "biz": "luxe",
        "category": "scheduling",
        "question": "What hair styling services do you provide?",
    },
    {
        "biz": "luxe",
        "category": "policy",
        "question": "What is your cancellation policy if I need to cancel my haircut?",
    },
    {
        "biz": "luxe",
        "category": "policy",
        "question": "Is there parking available near your salon?",
    },
    {
        "biz": "luxe",
        "category": "unanswerable",
        "question": "Do you sell prescription Botox injections for home use?",
    },
    {
        "biz": "luxe",
        "category": "unanswerable",
        "question": "Can I rent the entire salon overnight for a private wedding reception?",
    },
    {
        "biz": "luxe",
        "category": "advice_refusal",
        "question": "I have an itchy oozing skin rash on my neck. What topical steroid ointment should I apply?",
    },
    {
        "biz": "luxe",
        "category": "advice_refusal",
        "question": "Can I sue my prior salon in small claims court for hair dye burns?",
    },
    {
        "biz": "luxe",
        "category": "pricing",
        "question": "How much is a women's signature haircut and blowout?",
    },
    {
        "biz": "luxe",
        "category": "hours",
        "question": "What time do you close on Saturday?",
    },
    {
        "biz": "luxe",
        "category": "scheduling",
        "question": "How do I reschedule a spa appointment?",
    },
    {
        "biz": "luxe",
        "category": "message",
        "question": "Please take a message for master stylist Elena that Sarah called about extensions.",
    },
]


async def run_clean_latency_benchmark():
    AARAV_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
    LUXE_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")

    tracker = RetryTracker()
    logging.getLogger("callwise").addHandler(tracker)
    logging.getLogger("groq").addHandler(tracker)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    with get_sync_session() as session:
        aarav_biz = session.scalar(select(Business).where(Business.id == AARAV_ID))
        luxe_biz = session.scalar(select(Business).where(Business.id == LUXE_ID))
        if not aarav_biz or not luxe_biz:
            raise RuntimeError("Database missing seeded businesses.")

    biz_map = {
        "aarav": aarav_biz,
        "luxe": luxe_biz,
    }

    results = []
    print(f"=== Starting Clean Callwise Text Agent Latency Benchmark ===")
    print(f"Total turns to measure: {len(BENCHMARK_QUESTIONS)}")
    print(f"Provider: {settings.llm_provider.upper()} ({settings.groq_model})")
    print(f"Inter-turn pause: 3.5 seconds (to maintain <= 15-20 RPM)")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("-" * 60)

    turns_with_retries = 0

    for idx, item in enumerate(BENCHMARK_QUESTIONS, 1):
        tracker.reset_turn()
        biz = biz_map[item["biz"]]
        agent = TextAgent(
            business=biz,
            call_id=uuid.uuid4(),
            provider_name=settings.llm_provider,
        )

        t_start = time.perf_counter()
        try:
            reply = await agent.ask(item["question"])
            t_end = time.perf_counter()
            latency_ms = (t_end - t_start) * 1000.0
            error = None
        except Exception as exc:
            t_end = time.perf_counter()
            latency_ms = (t_end - t_start) * 1000.0
            reply = None
            error = str(exc)

        retried = tracker.current_turn_retries > 0 or latency_ms > 10000.0
        if retried:
            turns_with_retries += 1

        retry_tag = " [RETRIED]" if retried else "          "
        preview = (reply[:55] + "...") if reply and len(reply) > 55 else (reply or error)
        print(f"[{idx:02d}/{len(BENCHMARK_QUESTIONS)}] {item['biz'].upper():5} | {item['category']:14} | {latency_ms:7.1f}ms{retry_tag} | {preview}")

        results.append({
            "turn_index": idx,
            "business_id": str(biz.id),
            "business_name": biz.name,
            "category": item["category"],
            "question": item["question"],
            "reply": reply,
            "latency_ms": round(latency_ms, 2),
            "retried": retried,
            "error": error,
        })

        # Pause to prevent rate-limiting
        await asyncio.sleep(3.5)

    # Statistical summary
    latencies = [r["latency_ms"] for r in results if r["error"] is None]
    latencies_sorted = sorted(latencies)
    n = len(latencies)
    median_lat = statistics.median(latencies)
    mean_lat = statistics.mean(latencies)
    min_lat = min(latencies)
    max_lat = max(latencies)
    p95_idx = int(0.95 * n)
    p95_lat = latencies_sorted[min(p95_idx, n - 1)]

    # Breakdown by category
    by_category = {}
    for r in results:
        cat = r["category"]
        by_category.setdefault(cat, []).append(r["latency_ms"])

    cat_summary = {}
    for cat, lats in by_category.items():
        cat_summary[cat] = {
            "count": len(lats),
            "median_ms": round(statistics.median(lats), 1),
            "p95_ms": round(sorted(lats)[min(int(0.95 * len(lats)), len(lats) - 1)], 1),
            "min_ms": round(min(lats), 1),
            "max_ms": round(max(lats), 1),
        }

    benchmark_data = {
        "metadata": {
            "date": "2026-11-17",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "provider": settings.llm_provider,
            "model": settings.groq_model,
            "total_turns": n,
            "turns_with_retries": turns_with_retries,
            "machine_context": {
                "os": platform.platform(),
                "python": platform.python_version(),
                "node": platform.node(),
            },
            "pipeline_scope": "Text agent path only (LLM inference + native function tool calls + pgvector knowledge search). Voice pipeline (STT/TTS) is not measured.",
        },
        "summary": {
            "n": n,
            "median_ms": round(median_lat, 1),
            "mean_ms": round(mean_lat, 1),
            "p95_ms": round(p95_lat, 1),
            "min_ms": round(min_lat, 1),
            "max_ms": round(max_lat, 1),
            "turns_with_retries": turns_with_retries,
        },
        "by_category": cat_summary,
        "turns": results,
    }

    out_dir = Path("docs/benchmarks")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "clean_latency_benchmarks_20261117.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(benchmark_data, f, indent=2)

    print("\n" + "=" * 60)
    print("=== CLEAN LATENCY BENCHMARK SUMMARY ===")
    print(f"Turns Measured (n):        {n}")
    print(f"Turns With Retries:        {turns_with_retries}")
    print(f"Median (p50):               {median_lat:.1f} ms")
    print(f"95th Percentile (p95):      {p95_lat:.1f} ms")
    print(f"Minimum:                    {min_lat:.1f} ms")
    print(f"Maximum:                    {max_lat:.1f} ms")
    print(f"Average:                    {mean_lat:.1f} ms")
    print(f"Saved to:                   {out_file}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_clean_latency_benchmark())
