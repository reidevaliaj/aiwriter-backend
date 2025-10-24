"""
Script to seed subscription plans.
"""
from sqlalchemy.orm import Session
from aiwriter_backend.db.session import SessionLocal
from aiwriter_backend.db.base import Plan


def seed_plans():
    """Seed the database with subscription plans."""
    db = SessionLocal()
    try:
        # Check if plans already exist
        existing_plans = db.query(Plan).count()
        if existing_plans > 0:
            print("Plans already exist, skipping seed")
            return
        
        # Create plans
        plans = [
            Plan(
                name="Free",
                monthly_limit=10,
                max_images_per_article=0,
                price_eur=0
            ),
            Plan(
                name="Starter",
                monthly_limit=30,
                max_images_per_article=1,
                price_eur=1900  # €19.00 in cents
            ),
            Plan(
                name="Pro",
                monthly_limit=100,
                max_images_per_article=2,
                price_eur=4900  # €49.00 in cents
            )
        ]
        
        for plan in plans:
            db.add(plan)
        
        db.commit()
        print("Plans seeded successfully")
        
    finally:
        db.close()


if __name__ == "__main__":
    seed_plans()
