"""
Database setup script - creates tables and seeds initial data.
"""
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from aiwriter_backend.db.base import Base
from aiwriter_backend.db.session import engine, SessionLocal
from aiwriter_backend.db.base import Plan


def create_tables():
    """Create all database tables."""
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully")


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


def main():
    """Main setup function."""
    print("Setting up AIWriter database...")
    
    try:
        # Create tables
        create_tables()
        
        # Seed initial data
        seed_plans()
        
        print("Database setup completed successfully!")
        print("\nNext steps:")
        print("1. Start the backend: uvicorn aiwriter_backend.main:app --reload")
        print("2. Start the frontend: cd ../frontend && npm run dev")
        
    except Exception as e:
        print(f"Database setup failed: {e}")
        print("\nMake sure PostgreSQL is running and accessible.")
        print("You can start it with: docker-compose up -d postgres")


if __name__ == "__main__":
    main()
