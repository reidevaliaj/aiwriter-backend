"""
Webhook-related Pydantic schemas.
"""
from pydantic import BaseModel
from typing import Optional, Dict, Any


class PublishRequest(BaseModel):
    """Request schema for article publishing."""
    site_id: int
    job_id: int
    article_data: Dict[str, Any]
    signature: str


class PublishResponse(BaseModel):
    """Response schema for article publishing."""
    success: bool
    post_id: Optional[int] = None
    message: str
