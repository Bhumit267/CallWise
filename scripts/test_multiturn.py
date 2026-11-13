import os
import sys
import time
import uuid
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from callwise.db.session import get_sync_session
from callwise.db.models import Business
from callwise.agent.prompt import build_system_prompt
from openai import OpenAI

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)

business_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
with get_sync_session() as db:
    business = db.get(Business, business_id)
    assert business is not None, "Business not found"
    system_prompt = build_system_prompt(business)

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.getenv("GROQ_API_KEY"),
    timeout=20.0,
)
model = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_business_hours",
            "description": "Check operating hours for a specific day or today",
            "parameters": {
                "type": "object",
                "properties": {"day_of_week": {"type": "string", "description": "e.g. monday, tuesday"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_services",
            "description": "List all dental services and their prices",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "Search clinic policies, insurance coverage, and FAQs",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Check available appointment slots for a service on a given date",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_name": {"type": "string"},
                    "date_str": {"type": "string"},
                },
                "required": ["service_name", "date_str"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Book a confirmed appointment with customer details",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_name": {"type": "string"},
                    "slot_time": {"type": "string"},
                    "customer_name": {"type": "string"},
                    "customer_phone": {"type": "string"},
                },
                "required": ["service_name", "slot_time", "customer_name", "customer_phone"],
            },
        },
    },
]

simulated_tool_responses = {
    "get_business_hours": json.dumps({"hours": "Monday: 8:00 AM - 5:00 PM", "status": "open"}),
    "list_services": json.dumps([
        {"name": "Routine Cleaning", "price": "$120", "duration": "45m"},
        {"name": "Teeth Whitening", "price": "$250", "duration": "60m"},
        {"name": "Dental Exam & X-Rays", "price": "$150", "duration": "30m"}
    ]),
    "search_knowledge": json.dumps({"result": "Yes, we accept Delta Dental, Cigna, MetLife, and Guardian PPO plans."}),
    "check_availability": json.dumps({"openings": ["9:00 AM", "11:30 AM", "2:00 PM"]}),
    "book_appointment": json.dumps({"booking_code": "BK-7F9", "confirmed": True, "details": "Routine Cleaning on Monday at 11:30 AM"}),
}

# 5 Realistic Caller Questions
questions = [
    "What are your office hours on Monday?",
    "What services do you offer and what do they cost?",
    "Do you accept Delta Dental insurance?",
    "Can I schedule an appointment for routine cleaning next Monday at 11:30 AM?",
    "Yes, Monday at 11:30 AM works. My name is Alex Smith and my number is 555-123-4567.",
]

messages = [{"role": "system", "content": system_prompt}]

print("\n" + "=" * 70, flush=True)
print(f"🚀 LIVE 5-QUESTION AGENT TEST ON GROQ ({model})", flush=True)
print(f"🏢 Tenant: Apex Dental Care | Local Time: Monday 09:00 AM", flush=True)
print("=" * 70 + "\n", flush=True)

for i, q in enumerate(questions, 1):
    now_q = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print("═" * 70, flush=True)
    print(f"🕒 [{now_q}] 👤 CALLER QUESTION {i}:", flush=True)
    print(f"   \"{q}\"", flush=True)
    print("─" * 70, flush=True)

    messages.append({"role": "user", "content": q})
    window = [messages[0]] + messages[-6:] if len(messages) > 7 else messages

    start_time = time.perf_counter()
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=window,
            tools=tools,
            tool_choice="auto",
            max_tokens=150,
            temperature=0.3,
        )
        latency_1 = int((time.perf_counter() - start_time) * 1000)
        choice = resp.choices[0]

        if choice.message.tool_calls:
            tc = choice.message.tool_calls[0]
            print(f"🛠️  TOOL CALLED: {tc.function.name}({tc.function.arguments})", flush=True)

            messages.append(choice.message)
            tool_result = simulated_tool_responses.get(tc.function.name, json.dumps({"status": "success"}))
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": tool_result})

            # Follow-up generation to produce the spoken answer
            f_start = time.perf_counter()
            f_resp = client.chat.completions.create(
                model=model,
                messages=[messages[0]] + messages[-6:],
                max_tokens=120,
                temperature=0.3,
            )
            latency_2 = int((time.perf_counter() - f_start) * 1000)
            total_latency = latency_1 + latency_2
            answer = f_resp.choices[0].message.content.strip()

            now_a = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"🕒 [{now_a}] 🤖 AGENT ANSWER (⏱️ Latency: {total_latency}ms):", flush=True)
            print(f"   \"{answer}\"", flush=True)
            print(f"📊 Usage: Prompt={resp.usage.prompt_tokens} tokens | Output={f_resp.usage.completion_tokens} tokens", flush=True)
            messages.append({"role": "assistant", "content": answer})
        else:
            answer = choice.message.content.strip()
            now_a = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"🕒 [{now_a}] 🤖 AGENT ANSWER (⏱️ Latency: {latency_1}ms):", flush=True)
            print(f"   \"{answer}\"", flush=True)
            print(f"📊 Usage: Prompt={resp.usage.prompt_tokens} tokens | Output={resp.usage.completion_tokens} tokens", flush=True)
            messages.append({"role": "assistant", "content": answer})

        print("═" * 70 + "\n", flush=True)

    except Exception as e:
        print(f"❌ Error on Question {i}: {e}", flush=True)
        break

    # Realistic caller speech gap
    time.sleep(1.5)

print("✅ ALL 5 QUESTIONS COMPLETED SUCCESSFULLY!", flush=True)
