"""
Base database models - Simplified schema for v1.
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from aiwriter_backend.db.session import Base


class Plan(Base):
    """Subscription plan model."""
    __tablename__ = "plans"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    monthly_limit = Column(Integer, nullable=False)  # articles per month
    max_images_per_article = Column(Integer, default=0)
    price_eur = Column(Integer, nullable=False)  # Price in cents
    
    # Relationships
    licenses = relationship("License", back_populates="plan")


class License(Base):
    """License model."""
    __tablename__ = "licenses"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True, nullable=False)
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=False)
    status = Column(String, default="active")  # active, inactive, expired
    reset_day = Column(Integer, default=1)  # Day of month to reset usage
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    plan = relationship("Plan", back_populates="licenses")
    sites = relationship("Site", back_populates="license")


class Site(Base):
    """WordPress site model."""
    __tablename__ = "sites"
    
    id = Column(Integer, primary_key=True, index=True)
    license_id = Column(Integer, ForeignKey("licenses.id"), nullable=False)
    domain = Column(String, nullable=False)
    site_secret = Column(String, nullable=False)  # HMAC secret for this site
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    license = relationship("License", back_populates="sites")
    jobs = relationship("Job", back_populates="site")
    usage = relationship("Usage", back_populates="site")


class Job(Base):
    """Article generation job model."""
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    topic = Column(String, nullable=False)
    length = Column(String, default="medium")  # short, medium, long
    images = Column(Boolean, default=False)  # whether to generate images
    status = Column(String, default="pending")  # pending, processing, completed, failed
    error = Column(Text, nullable=True)  # error message if failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    site = relationship("Site", back_populates="jobs")


class Usage(Base):
    """Usage tracking model."""
    __tablename__ = "usage"
    
    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    year_month = Column(String, nullable=False)  # YYYY-MM format
    articles_generated = Column(Integer, default=0)
    
    # Relationships
    site = relationship("Site", back_populates="usage")
