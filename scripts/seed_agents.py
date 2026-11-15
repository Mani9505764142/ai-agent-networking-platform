"""
Seed Script for AI Agent Networking Platform

Registers the 5 predefined sample AI agents:
1. Swiggy (Food Delivery)
2. PhonePe (FinTech)
3. HDFC Bank (Banking)
4. Bajaj Auto (Automobile)
5. Google Pay (Digital Payments)

Idempotent: checks for existing agents by company_name to prevent duplicates.
"""

import sys
import uuid
from pathlib import Path

# Ensure project root is in sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from app.database.connection import SessionLocal, init_db
from app.database.repository import AgentRepository
from app.models.agent import Agent

SAMPLE_AGENTS = [
    {
        "company_name": "Swiggy",
        "industry_category": "Food Delivery",
        "interest_manifesto": (
            "Food delivery offers, restaurant promotions, discounts, festivals."
        ),
        "webhook_url": "https://api.swiggy.com/agent/v1/webhook",
        "trust_score": 1.0,
    },
    {
        "company_name": "PhonePe",
        "industry_category": "FinTech",
        "interest_manifesto": (
            "UPI payments, cashback offers, digital payments, merchant partnerships."
        ),
        "webhook_url": "https://api.phonepe.com/agent/v1/webhook",
        "trust_score": 1.0,
    },
    {
        "company_name": "HDFC Bank",
        "industry_category": "Banking",
        "interest_manifesto": (
            "Credit cards, banking offers, payment partnerships, financial services."
        ),
        "webhook_url": "https://api.hdfcbank.com/agent/v1/webhook",
        "trust_score": 1.0,
    },
    {
        "company_name": "Bajaj Auto",
        "industry_category": "Automobile",
        "interest_manifesto": (
            "Motorcycles, vehicle launches, automobile promotions, automotive finance."
        ),
        "webhook_url": "https://api.bajajauto.com/agent/v1/webhook",
        "trust_score": 1.0,
    },
    {
        "company_name": "Google Pay",
        "industry_category": "Digital Payments",
        "interest_manifesto": (
            "UPI, digital payments, cashback, merchant offers."
        ),
        "webhook_url": "https://pay.google.com/agent/v1/webhook",
        "trust_score": 1.0,
    },
]


def seed_agents() -> dict:
    """Register the sample agents, skipping any that already exist."""
    print("=" * 60)
    print("AI Agent Networking Platform - Database Seeder")
    print("=" * 60)

    init_db()
    db = SessionLocal()
    repo = AgentRepository(db)

    created_count = 0
    skipped_count = 0

    try:
        for data in SAMPLE_AGENTS:
            existing = repo.get_by_company_name(data["company_name"])
            if existing:
                print(f" [SKIP]    Agent '{data['company_name']}' is already registered (ID: {existing.id})")
                skipped_count += 1
            else:
                agent = Agent(
                    id=str(uuid.uuid4()),
                    company_name=data["company_name"],
                    industry_category=data["industry_category"],
                    webhook_url=data["webhook_url"],
                    interest_manifesto=data["interest_manifesto"],
                    trust_score=data["trust_score"],
                    interest_embedding=None,
                )
                created = repo.create(agent)
                print(f" [CREATED] Agent '{created.company_name}' registered successfully (ID: {created.id})")
                created_count += 1

        all_agents = repo.get_all()
        print("-" * 60)
        print(f"Seeding completed: {created_count} created, {skipped_count} skipped.")
        print(f"Total agents in database: {len(all_agents)}")
        print("=" * 60)

        return {
            "created": created_count,
            "skipped": skipped_count,
            "total": len(all_agents),
        }
    finally:
        db.close()


if __name__ == "__main__":
    seed_agents()
