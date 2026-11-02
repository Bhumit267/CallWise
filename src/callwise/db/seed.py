"""Seed script creating 2 realistic demo businesses (Dental Clinic and Hair Salon)."""

import json
from typing import Any, Dict, List
import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session

from callwise.db.models import Business
from callwise.db.session import get_sync_session

# Stable UUIDs for consistent test and eval references
DENTAL_CLINIC_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
SALON_SPA_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")

DEMO_BUSINESSES: List[Dict[str, Any]] = [
    {
        "id": DENTAL_CLINIC_ID,
        "name": "BrightSmile Family Dental",
        "business_type": "Dental Clinic",
        "greeting": (
            "Thank you for calling BrightSmile Family Dental. "
            "How can I assist you with your oral care today?"
        ),
        "tone": "Warm, compassionate, and reassuring",
        "timezone": "America/New_York",
        "hours": {
            "monday": {"open": "08:00", "close": "17:00", "closed": False},
            "tuesday": {"open": "08:00", "close": "17:00", "closed": False},
            "wednesday": {"open": "08:00", "close": "17:00", "closed": False},
            "thursday": {"open": "08:00", "close": "17:00", "closed": False},
            "friday": {"open": "08:00", "close": "13:00", "closed": False},
            "saturday": {"open": None, "close": None, "closed": True},
            "sunday": {"open": None, "close": None, "closed": True},
        },
    },
    {
        "id": SALON_SPA_ID,
        "name": "Luxe Glow Salon & Spa",
        "business_type": "Hair Salon & Spa",
        "greeting": (
            "Welcome to Luxe Glow Salon and Spa! "
            "How can I help you book your next look or treatment?"
        ),
        "tone": "Upbeat, chic, and polite",
        "timezone": "America/Los_Angeles",
        "hours": {
            "monday": {"open": None, "close": None, "closed": True},
            "tuesday": {"open": "10:00", "close": "19:00", "closed": False},
            "wednesday": {"open": "10:00", "close": "19:00", "closed": False},
            "thursday": {"open": "10:00", "close": "19:00", "closed": False},
            "friday": {"open": "10:00", "close": "20:00", "closed": False},
            "saturday": {"open": "09:00", "close": "18:00", "closed": False},
            "sunday": {"open": "11:00", "close": "16:00", "closed": False},
        },
    },
]


def seed_businesses(session: Session) -> List[Business]:
    """Seed or update demo businesses idempotently."""
    created_or_updated: List[Business] = []

    for data in DEMO_BUSINESSES:
        stmt = select(Business).where(Business.id == data["id"])
        existing = session.scalar(stmt)

        if existing:
            existing.name = data["name"]
            existing.business_type = data["business_type"]
            existing.greeting = data["greeting"]
            existing.tone = data["tone"]
            existing.timezone = data["timezone"]
            existing.hours = data["hours"]
            created_or_updated.append(existing)
        else:
            business = Business(
                id=data["id"],
                name=data["name"],
                business_type=data["business_type"],
                greeting=data["greeting"],
                tone=data["tone"],
                timezone=data["timezone"],
                hours=data["hours"],
            )
            session.add(business)
            created_or_updated.append(business)

    session.flush()
    return created_or_updated


def run_seed() -> List[Business]:
    """Run the seed process within a database session."""
    with get_sync_session() as session:
        return seed_businesses(session)
