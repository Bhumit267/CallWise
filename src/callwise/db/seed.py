"""Seed script creating exactly 2 realistic demo businesses (Indian Dental Clinic and Hair Salon & Spa)."""

import json
from typing import Any, Dict, List
import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session

from callwise.db.models import Business, Chunk, Document, Service
from callwise.db.session import get_sync_session
from callwise.providers.embeddings import get_embedding_provider

# Stable UUIDs for consistent test and eval references
INDIAN_CLINIC_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
SALON_SPA_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
# Alias pointing to Indian clinic for backward-compatibility in tests
DENTAL_CLINIC_ID = INDIAN_CLINIC_ID

DEMO_SERVICES: Dict[uuid.UUID, List[Dict[str, Any]]] = {
    INDIAN_CLINIC_ID: [
        {
            "name": "Root Canal Treatment (Single Sitting)",
            "duration_minutes": 60,
            "price": 4500.0,
            "description": "Specialist rotary endodontic root canal procedure with digital diagnostic imaging.",
        },
        {
            "name": "Zoom Laser Teeth Whitening",
            "duration_minutes": 60,
            "price": 3500.0,
            "description": "In-clinic professional enamel-safe laser teeth whitening for instant shade brightness.",
        },
        {
            "name": "Routine Scaling & Ultrasonic Polishing",
            "duration_minutes": 45,
            "price": 1500.0,
            "description": "Deep plaque and tartar removal with gentle ultrasonic scaling and airflow stain removal.",
        },
        {
            "name": "Dental Implant Consultation & 3D CBCT Scan",
            "duration_minutes": 45,
            "price": 800.0,
            "description": "Comprehensive implant planning with bone density assessment by senior implantologist.",
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
        "id": INDIAN_CLINIC_ID,
        "name": "Aarav Health & Dental Clinic",
        "business_type": "Dental Clinic",
        "greeting": (
            "Namaste! Thank you for calling Aarav Health & Dental Clinic, Indiranagar. "
            "How can I assist you with your dental care today?"
        ),
        "tone": "Warm, respectful, polite, and reassuring",
        "timezone": "Asia/Kolkata",
        "transfer_number": "+91-80-25251122",
        "notification_email": "contact@aaravdental.test",
        "hours": {
            "monday": {"open": "10:00", "close": "20:00", "closed": False},
            "tuesday": {"open": "10:00", "close": "20:00", "closed": False},
            "wednesday": {"open": "10:00", "close": "20:00", "closed": False},
            "thursday": {"open": "10:00", "close": "20:00", "closed": False},
            "friday": {"open": "10:00", "close": "20:00", "closed": False},
            "saturday": {"open": "10:00", "close": "20:00", "closed": False},
            "sunday": {"open": "10:00", "close": "14:00", "closed": False},
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
        "notification_email": "reception@luxeglowsalon.test",
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

INDIAN_KNOWLEDGE_FAQS: List[tuple[str, str]] = [
    (
        "Payment Methods and UPI Options",
        "What payment options and UPI methods do you accept at Aarav Dental Clinic?\n\n"
        "We accept all major UPI applications (including QR code scan-and-pay), standard debit and credit cards, net banking, and cash at our reception desk. "
        "No-cost installment plans are available on supported credit cards for procedures above ₹5,000.",
    ),
    (
        "Clinic Location, Metro, and Directions",
        "Where is Aarav Health & Dental Clinic located and how do I reach by metro?\n\n"
        "We are located on 100 Feet Road, HAL 2nd Stage, Indiranagar, Bengaluru, Karnataka 560038, near the 12th Main junction. "
        "By Namma Metro: Take the Purple Line to Indiranagar Metro Station (Exit A). The clinic is an easy 600-meter walk from the station.",
    ),
    (
        "Parking Facilities",
        "Is parking available at the clinic in Indiranagar?\n\n"
        "Yes! Dedicated two-wheeler parking is available in front of the clinic. "
        "Complimentary valet parking is provided for four-wheelers during clinic operating hours from 10:00 AM to 8:00 PM.",
    ),
    (
        "Health Insurance and Cashless Dental Claims",
        "Does Aarav Dental accept health insurance and cashless claims?\n\n"
        "Yes, we support cashless corporate dental insurance claims with major health insurance providers. "
        "For all reimbursement policies, our front desk provides complete itemized tax invoices, treatment summaries, and diagnostic digital x-ray records.",
    ),
    (
        "Specialist Doctors and Qualifications",
        "Who are the doctors practicing at Aarav Health & Dental Clinic?\n\n"
        "Our clinical team is led by senior specialist dental surgeons, BDS, MDS in Endodontics and Conservative Dentistry with over a decade of clinical experience in painless procedures. "
        "Our periodontics and implant surgery department is headed by senior specialists in Periodontics and Oral Implantology.",
    ),
]

SALON_KNOWLEDGE_FAQS: List[tuple[str, str]] = [
    (
        "Salon Services and Booking Policies",
        "What services and policies does Luxe Glow Salon & Spa provide?\n\n"
        "Luxe Glow Salon & Spa offers precision haircuts, custom balayage, keratin treatments, and signature glow facials. "
        "Appointments can be scheduled online or by phone. Cancellations must be made at least 24 hours in advance to avoid a cancellation fee.",
    ),
]


def seed_businesses(session: Session) -> List[Business]:
    """Seed or update demo businesses, services, and FAQ knowledge idempotently."""
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

    # Seed FAQ Knowledge with Vector Embeddings
    faqs_map = {
        INDIAN_CLINIC_ID: INDIAN_KNOWLEDGE_FAQS,
        SALON_SPA_ID: SALON_KNOWLEDGE_FAQS,
    }
    embedding_provider = get_embedding_provider()

    for biz_id, faqs in faqs_map.items():
        for title, content in faqs:
            doc_stmt = select(Document).where(
                Document.business_id == biz_id,
                Document.title == title,
            )
            existing_doc = session.scalar(doc_stmt)
            if not existing_doc:
                doc = Document(
                    business_id=biz_id,
                    title=title,
                    source_type="faq",
                    source_uri=f"faq://{title.lower().replace(' ', '_')}",
                )
                session.add(doc)
                session.flush()

                embeddings = embedding_provider.embed_batch([content])
                chunk = Chunk(
                    business_id=biz_id,
                    document_id=doc.id,
                    content=content,
                    embedding=embeddings[0],
                    chunk_index=0,
                )
                session.add(chunk)

    session.flush()
    return created_or_updated


def run_seed() -> List[Business]:
    """Run the seed process within a database session."""
    with get_sync_session() as session:
        return seed_businesses(session)


def seed_indian_business(session: Session) -> Business:
    """Seed or update Aarav Health & Dental Clinic idempotently."""
    businesses = seed_businesses(session)
    return next(b for b in businesses if b.id == INDIAN_CLINIC_ID)


def run_seed_india() -> Business:
    """Run the Indian clinic seed process within a database session."""
    with get_sync_session() as session:
        return seed_indian_business(session)
