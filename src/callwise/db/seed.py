"""Seed script creating 2 realistic demo businesses (Dental Clinic and Hair Salon)."""

import json
from typing import Any, Dict, List
import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session

from callwise.db.models import Business, Service
from callwise.db.session import get_sync_session

# Stable UUIDs for consistent test and eval references
DENTAL_CLINIC_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
SALON_SPA_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")

DEMO_SERVICES: Dict[uuid.UUID, List[Dict[str, Any]]] = {
    DENTAL_CLINIC_ID: [
        {
            "name": "Routine Cleaning & Exam",
            "duration_minutes": 60,
            "price": 120.0,
            "description": "Comprehensive dental checkup, routine cleaning, and digital bitewing x-rays.",
        },
        {
            "name": "Zoom In-Office Teeth Whitening",
            "duration_minutes": 60,
            "price": 350.0,
            "description": "Professional laser teeth whitening for a visibly brighter smile.",
        },
        {
            "name": "Porcelain Dental Crown",
            "duration_minutes": 90,
            "price": 950.0,
            "description": "Custom-fitted porcelain crown consultation and placement.",
        },
        {
            "name": "Emergency Dental Exam",
            "duration_minutes": 30,
            "price": 85.0,
            "description": "Same-day urgent exam for severe tooth pain, chips, or trauma.",
        },
    ],
    SALON_SPA_ID: [
        {
            "name": "Women's Haircut & Blowout",
            "duration_minutes": 45,
            "price": 75.0,
            "description": "Precision haircut, luxury wash, blowout, and style.",
        },
        {
            "name": "Full Custom Balayage",
            "duration_minutes": 120,
            "price": 220.0,
            "description": "Hand-painted dimensional highlights with custom toner and gloss.",
        },
        {
            "name": "Keratin Smoothing Treatment",
            "duration_minutes": 90,
            "price": 275.0,
            "description": "Anti-frizz smoothing treatment for sleek, long-lasting shine.",
        },
        {
            "name": "Signature Glow Facial",
            "duration_minutes": 60,
            "price": 110.0,
            "description": "Restorative deep cleansing, gentle exfoliation, and hydration facial.",
        },
    ],
}

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
        "transfer_number": "+1-617-555-0100",
        "notification_email": "frontdesk@brightsmilefamilydental.com",
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
        "transfer_number": "+1-310-555-0200",
        "notification_email": "reception@luxeglowsalon.com",
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
    """Seed or update demo businesses and services idempotently."""
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
            existing.transfer_number = data.get("transfer_number")
            existing.notification_email = data.get("notification_email")
            biz = existing
        else:
            biz = Business(
                id=data["id"],
                name=data["name"],
                business_type=data["business_type"],
                greeting=data["greeting"],
                tone=data["tone"],
                timezone=data["timezone"],
                hours=data["hours"],
                transfer_number=data.get("transfer_number"),
                notification_email=data.get("notification_email"),
            )
            session.add(biz)

        session.flush()

        # Seed services for this business
        services_data = DEMO_SERVICES.get(data["id"], [])
        for s_data in services_data:
            s_stmt = select(Service).where(
                Service.business_id == data["id"],
                Service.name == s_data["name"],
            )
            existing_service = session.scalar(s_stmt)
            if existing_service:
                existing_service.duration_minutes = s_data["duration_minutes"]
                existing_service.price = s_data["price"]
                existing_service.description = s_data.get("description")
                existing_service.is_active = True
            else:
                svc = Service(
                    business_id=data["id"],
                    name=s_data["name"],
                    duration_minutes=s_data["duration_minutes"],
                    price=s_data["price"],
                    description=s_data.get("description"),
                    is_active=True,
                )
                session.add(svc)

        created_or_updated.append(biz)

    session.flush()
    return created_or_updated


def run_seed() -> List[Business]:
    """Run the seed process within a database session."""
    with get_sync_session() as session:
        return seed_businesses(session)
