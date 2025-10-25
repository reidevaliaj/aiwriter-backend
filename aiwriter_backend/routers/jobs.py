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
    print(f"[JOB_ROUTER] Received job request:")
    print(f"[JOB_ROUTER] - Site ID: {x_site_id}")
    print(f"[JOB_ROUTER] - Topic: {request.topic}")
    print(f"[JOB_ROUTER] - Length: {request.length}")
    print(f"[JOB_ROUTER] - Include Images: {request.include_images}")
    print(f"[JOB_ROUTER] - Signature: {x_signature[:10]}...")
    
    service = JobService(db)
    result = await service.create_job(
        site_id=x_site_id,
        topic=request.topic,
        length=request.length,
        include_images=request.include_images
    )
    
    print(f"[JOB_ROUTER] Job creation result: {result.success}, Message: {result.message}")
    return result
