"""
Job-related Pydantic schemas.
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class JobCreate(BaseModel):
    """Request schema for job creation."""
    topic: str
    length: str = "medium"  # short, medium, long
    include_images: bool = False
    context: Optional[str] = None  # Additional context/keywords
    user_images: Optional[list[str]] = None  # User-uploaded image URLs
    include_faq: bool = True  # Include FAQ section
    include_cta: bool = False  # Include call-to-action
    cta_url: Optional[str] = None  # CTA URL
    category: Optional[int] = None  # WordPress category ID
    tags: Optional[str] = None  # WordPress tags (comma-separated)


class JobResponse(BaseModel):
    """Response schema for job creation."""
    success: bool
    job_id: Optional[int] = None
    message: str


class JobStatus(BaseModel):
    """Job status response."""
    job_id: int
    status: str  # pending, processing, completed, failed
    topic: str
    created_at: datetime
    finished_at: Optional[datetime] = None
    error: Optional[str] = None
    wordpress_post_id: Optional[int] = None  # WordPress post ID if article is published


class ArticleData(BaseModel):
    """Article data for publishing."""
    title: str
    content: str
    meta_title: str
    meta_description: str
    featured_image: Optional[str] = None
    faq: list = []
    schema_data: dict = {}
