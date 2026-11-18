"""Re-run only the affected cases: dental-prohib-1 and salon-sched-4."""

import asyncio
import json
from pathlib import Path
import sys
import uuid

sys.path.insert(0, ".")

from sqlalchemy import select

from callwise.config import settings
from callwise.db.models import Business
from callwise.db.session import get_sync_session
from evals.eval_runner import EvalQuestion, run_single_eval

QUESTIONS_FILE = Path("evals/data/questions.json")

async def main():
    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    target_ids = ["dental-prohib-1", "salon-sched-4"]
    target_questions = [EvalQuestion(**item) for item in data if item["id"] in target_ids]

    print(f"=== Re-running affected eval cases ({len(target_questions)}) ===")
    print(f"Provider: {settings.llm_provider.upper()} ({settings.groq_model})")

    with get_sync_session() as session:
        for q in target_questions:
            biz = session.scalar(select(Business).where(Business.id == q.business_id))
            print(f"\nTesting: [{q.id}] ({q.business_name})")
            print(f"Question: \"{q.question}\"")
            result = await run_single_eval(q, biz, provider_name=settings.llm_provider)
            status_str = "[PASS]" if result.passed else "[FAIL]"
            print(f"Status:   {status_str}")
            print(f"Latency:  {result.latency_ms:.1f}ms")
            print(f"Response: {result.response_text}")
            if result.failure_reason:
                print(f"Reason:   {result.failure_reason}")
            # Pause to be gentle with rate limits
            await asyncio.sleep(2.0)

if __name__ == "__main__":
    asyncio.run(main())
