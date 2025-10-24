"""
Initialize database tables.
"""
from sqlalchemy.orm import Session
from aiwriter_backend.db.session import engine, Base
from aiwriter_backend.db.base import Base  # Import all models


def init_db() -> None:
    """Initialize database tables."""
    # Create all tables
    Base.metadata.create_all(bind=engine)
