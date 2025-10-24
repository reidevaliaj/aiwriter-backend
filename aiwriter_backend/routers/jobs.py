"""
Job management endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from aiwriter_backend.db.session import get_db
from aiwriter_backend.schemas.job import JobCreate, JobResponse
from aiwriter_backend.services.job_service import JobService

router = APIRouter()


@router.post("/generate", response_model=JobResponse)
async def create_job(
    request: JobCreate,
    x_site_id: int = Header(..., alias="X-Site-ID"),
    x_signature: str = Header(..., alias="X-Signature"),
    db: Session = Depends(get_db)
):
    """Create a new article generation job."""
    service = JobService(db)
    return await service.create_job(
        site_id=x_site_id,
        topic=request.topic,
        length=request.length,
        include_images=request.include_images
    )
