"""
Base database models - Simplified schema for v1.
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, JSON, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from aiwriter_backend.db.session import Base
import enum


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
    callback_url = Column(String, nullable=True)  # WordPress callback URL
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    license = relationship("License", back_populates="sites")
    jobs = relationship("Job", back_populates="site")
    usage = relationship("Usage", back_populates="site")
    scheduled_jobs = relationship("ScheduledJob", back_populates="site")


class Job(Base):
    """Article generation job model."""
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    topic = Column(String, nullable=False)
    length = Column(String, default="medium")  # short, medium, long
    images = Column(Boolean, default=False)  # whether to generate images
    requested_images = Column(Integer, default=0)  # number of images requested
    language = Column(String, default="de")  # article language
    status = Column(String, default="pending")  # pending, processing, completed, failed
    error = Column(Text, nullable=True)  # error message if failed
    # Phase 3.5 fields
    context = Column(Text, nullable=True)  # Additional context/keywords
    user_images = Column(JSON, nullable=True)  # User-uploaded image URLs
    include_faq = Column(Boolean, default=True)  # Include FAQ section
    include_cta = Column(Boolean, default=False)  # Include call-to-action
    cta_url = Column(String, nullable=True)  # CTA URL
    template = Column(String, default="classic")  # Article template
    style_preset = Column(String, default="default")  # Style preset
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    site = relationship("Site", back_populates="jobs")
    articles = relationship("Article", back_populates="job")


class ArticleStatus(enum.Enum):
    """Article status enum."""
    DRAFT = "draft"
    READY = "ready"
    FAILED = "failed"


class Article(Base):
    """Generated article model."""
    __tablename__ = "articles"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    license_id = Column(Integer, ForeignKey("licenses.id"), nullable=False)
    topic = Column(Text, nullable=False)
    language = Column(String, nullable=False, default="de")
    outline_json = Column(JSON, nullable=True)
    article_html = Column(Text, nullable=True)
    meta_title = Column(String(160), nullable=True)
    meta_description = Column(String(180), nullable=True)
    faq_json = Column(JSON, nullable=True)
    schema_json = Column(JSON, nullable=True)
    image_urls_json = Column(JSON, nullable=True, default=[])
    tokens_input = Column(Integer, nullable=True)
    tokens_output = Column(Integer, nullable=True)
    image_cost_cents = Column(Integer, nullable=True, default=0)
    status = Column(Enum(ArticleStatus), nullable=False, default=ArticleStatus.READY)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    job = relationship("Job", back_populates="articles")
    license = relationship("License")


class Usage(Base):
    """Usage tracking model."""
    __tablename__ = "usage"
    
    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    year_month = Column(String, nullable=False)  # YYYY-MM format
    articles_generated = Column(Integer, default=0)
    
    # Relationships
    site = relationship("Site", back_populates="usage")


class ScheduledJob(Base):
    """Scheduled article job model for Option 2 - AutoPilot Scheduler."""
    __tablename__ = "scheduled_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    license_id = Column(Integer, ForeignKey("licenses.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)  # Short description
    context = Column(Text, nullable=True)  # Website context for AI generation
    goal = Column(String, nullable=True)  # Goal: contact page, newsletter, shop, etc.
    publish_date = Column(DateTime(timezone=True), nullable=False)  # When to publish
    user_images = Column(JSON, nullable=True)  # Optional per-article images
    generate_images = Column(Boolean, default=False)  # Whether to generate AI images
    status = Column(String, default="pending")  # pending, processing, completed, failed
    error = Column(Text, nullable=True)  # Error message if failed
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True)  # Link to generated job
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=True)  # Link to generated article
    wordpress_post_id = Column(Integer, nullable=True)  # WordPress post ID after publishing
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    site = relationship("Site", back_populates="scheduled_jobs")
    license = relationship("License")
    job = relationship("Job")
    article = relationship("Article")
