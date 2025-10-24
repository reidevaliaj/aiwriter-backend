"""
Script to create an admin user.
"""
import asyncio
from sqlalchemy.orm import Session
from aiwriter_backend.db.session import SessionLocal
from aiwriter_backend.db.base import User


def create_admin_user(email: str):
    """Create an admin user."""
    db = SessionLocal()
    try:
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            print(f"User with email {email} already exists")
            return
        
        # Create new user
        user = User(email=email, is_active=True)
        db.add(user)
        db.commit()
        print(f"Admin user created: {email}")
        
    finally:
        db.close()


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python create_admin.py <email>")
        sys.exit(1)
    
    create_admin_user(sys.argv[1])
