"""Seed script creating 2 realistic demo businesses (Dental Clinic and Hair Salon)."""

import json
from typing import Any, Dict, List
import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session

from callwise.db.models import Business, Chunk, Document, Service
from callwise.db.session import get_sync_session
from callwise.providers.embeddings import get_embedding_provider

# Stable UUIDs for consistent test and eval references
DENTAL_CLINIC_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
SALON_SPA_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
INDIAN_CLINIC_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")

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


# ============================================================================
# Option 5: 1-Click Indian Demo Clinic Seed Data (Bengaluru, Karnataka)
# ============================================================================

INDIAN_CLINIC_DATA: Dict[str, Any] = {
    "id": INDIAN_CLINIC_ID,
    "name": "Aarav Health & Dental Clinic",
    "business_type": "dental clinic",
    "greeting": "Namaste! Thank you for calling Aarav Health & Dental Clinic, Indiranagar. How can I assist you with your dental care today?",
    "tone": "warm, respectful, polite, and reassuring",
    "timezone": "Asia/Kolkata",
    "transfer_number": "+918025251122",
    "notification_email": "contact@aaravdental.in",
    "hours": {
        "monday": {"open": "10:00", "close": "20:00", "closed": False},
        "tuesday": {"open": "10:00", "close": "20:00", "closed": False},
        "wednesday": {"open": "10:00", "close": "20:00", "closed": False},
        "thursday": {"open": "10:00", "close": "20:00", "closed": False},
        "friday": {"open": "10:00", "close": "20:00", "closed": False},
        "saturday": {"open": "10:00", "close": "20:00", "closed": False},
        "sunday": {"open": "10:00", "close": "14:00", "closed": False},
    },
}

INDIAN_SERVICES: List[Dict[str, Any]] = [
    {
        "name": "Root Canal Treatment (Single Sitting)",
        "duration_minutes": 60,
        "price": 4500.0,
        "description": "Specialist rotary endodontic root canal treatment by Dr. Aarav Sharma with digital x-rays.",
    },
    {
        "name": "Zoom Laser Teeth Whitening",
        "duration_minutes": 60,
        "price": 3500.0,
        "description": "In-clinic professional enamel-safe laser teeth whitening for instant 4-6 shade brightness.",
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
    {
        "name": "Emergency Toothache & Broken Tooth Relief",
        "duration_minutes": 30,
        "price": 600.0,
        "description": "Immediate same-day pain management, temporary dressing, and emergency evaluation.",
    },
]

INDIAN_KNOWLEDGE_FAQS: List[tuple[str, str]] = [
    (
        "Payment Methods and UPI Options",
        "What payment options and UPI methods do you accept at Aarav Dental Clinic?\n\n"
        "We accept all major UPI apps including Google Pay (GPay), PhonePe, and Paytm QR code payments at our reception desk. "
        "We also accept all major Indian and international debit/credit cards (Visa, MasterCard, RuPay), net banking, and cash. "
        "No-cost EMI payment plans are available on credit cards for procedures above ₹5,000.",
    ),
    (
        "Clinic Location, Metro, and Directions",
        "Where is Aarav Health & Dental Clinic located and how do I reach by metro?\n\n"
        "We are conveniently located at #42, 100 Feet Road, HAL 2nd Stage, Indiranagar, Bengaluru, Karnataka 560038. "
        "The nearest landmark is near the 12th Main junction, directly opposite Starbucks. "
        "By Namma Metro: Take the Purple Line to Indiranagar Metro Station (Exit A). The clinic is an easy 600-meter walk (about 7 minutes) from the station.",
    ),
    (
        "Parking Facilities",
        "Is parking available at the clinic in Indiranagar?\n\n"
        "Yes! We provide dedicated two-wheeler parking directly in front of the clinic. "
        "For four-wheelers, complimentary valet parking is provided during clinic operating hours from 10:00 AM to 8:00 PM.",
    ),
    (
        "Health Insurance and Cashless Dental Claims",
        "Does Aarav Dental accept health insurance and cashless claims?\n\n"
        "Yes, we support cashless corporate dental insurance claims with leading providers including Star Health, "
        "ICICI Lombard, HDFC ERGO, and Bajaj Allianz. For all reimbursement policies, our front desk provides complete itemized GST tax invoices, "
        "prescriptions, and diagnostic digital x-ray records immediately after treatment.",
    ),
    (
        "Specialist Doctors and Qualifications",
        "Who are the doctors practicing at Aarav Health & Dental Clinic?\n\n"
        "Our clinical team is led by Dr. Aarav Sharma, BDS, MDS (Endodontics and Conservative Dentistry) with over 12 years of clinical experience specializing in painless root canal treatments. "
        "Our periodontics and implant surgery department is headed by Dr. Priya Nair, BDS, MDS (Periodontics and Oral Implantology).",
    ),
]


def seed_indian_business(session: Session) -> Business:
    """Seed or update Aarav Health & Dental Clinic, services, and FAQ knowledge idempotently."""
    data = INDIAN_CLINIC_DATA
    stmt = select(Business).where(Business.id == data["id"])
    existing = session.scalar(stmt)

    if existing:
        existing.name = data["name"]
        existing.business_type = data["business_type"]
        existing.greeting = data["greeting"]
        existing.tone = data["tone"]
        existing.timezone = data["timezone"]
        existing.hours = data["hours"]
        existing.transfer_number = data["transfer_number"]
        existing.notification_email = data["notification_email"]
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
            transfer_number=data["transfer_number"],
            notification_email=data["notification_email"],
        )
        session.add(biz)

    session.flush()

    # Seed INR Services
    for s_data in INDIAN_SERVICES:
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

    session.flush()

    # Seed Knowledge Base FAQs with Vector Embeddings
    embedding_provider = get_embedding_provider()
    for title, content in INDIAN_KNOWLEDGE_FAQS:
        doc_stmt = select(Document).where(
            Document.business_id == data["id"],
            Document.title == title,
        )
        existing_doc = session.scalar(doc_stmt)
        if not existing_doc:
            doc = Document(
                business_id=data["id"],
                title=title,
                source_type="faq",
                source_uri=f"faq://{title.lower().replace(' ', '_')}",
            )
            session.add(doc)
            session.flush()

            embeddings = embedding_provider.embed_batch([content])
            chunk = Chunk(
                business_id=data["id"],
                document_id=doc.id,
                content=content,
                embedding=embeddings[0],
                chunk_index=0,
            )
            session.add(chunk)

    session.flush()
    return biz


def run_seed_india() -> Business:
    """Run the Indian clinic seed process within a database session."""
    with get_sync_session() as session:
        return seed_indian_business(session)
