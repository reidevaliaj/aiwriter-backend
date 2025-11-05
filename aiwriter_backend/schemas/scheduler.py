"""
Scheduler-related Pydantic schemas for Option 2 - AutoPilot Scheduler.
"""
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class GeneratePlanRequest(BaseModel):
    """Request schema for generating article titles."""
    context: str  # Website context/niche description
    goal: Optional[str] = None  # Goal: contact page, newsletter, shop, etc.
    count: int = 30  # Number of titles to generate


class ScheduleItem(BaseModel):
    """Schema for a single schedule item."""
    title: str
    description: Optional[str] = None
    publish_date: str  # ISO format datetime string
    user_images: Optional[List[str]] = None
    generate_images: bool = False
    context: Optional[str] = None
    goal: Optional[str] = None


class SavePlanRequest(BaseModel):
    """Request schema for saving a schedule plan."""
    schedule: List[ScheduleItem]


class SchedulerResponse(BaseModel):
    """Generic scheduler response."""
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None


class GeneratePlanResponse(BaseModel):
    """Response schema for title generation."""
    success: bool
    titles: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None


class ScheduledJobResponse(BaseModel):
    """Response schema for a scheduled job."""
    id: int
    title: str
    description: Optional[str] = None
    publish_date: datetime
    status: str
    generate_images: bool
    wordpress_post_id: Optional[int] = None
    error: Optional[str] = None


class ScheduledJobsListResponse(BaseModel):
    """Response schema for list of scheduled jobs."""
    success: bool
    jobs: List[ScheduledJobResponse]
    error: Optional[str] = None

