"""
Webhook endpoints for WordPress communication.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from aiwriter_backend.db.session import get_db
from aiwriter_backend.schemas.webhook import PublishRequest, PublishResponse
from aiwriter_backend.services.webhook_service import WebhookService

router = APIRouter()


@router.post("/publish", response_model=PublishResponse)
async def publish_article(
    request: PublishRequest,
    db: Session = Depends(get_db)
):
    """Publish an article to WordPress."""
    service = WebhookService(db)
    return await service.publish_article(
        site_id=request.site_id,
        job_id=request.job_id,
        article_data=request.article_data,
        signature=request.signature
    )
