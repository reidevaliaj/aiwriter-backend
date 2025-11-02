"""
Job management endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from aiwriter_backend.db.session import get_db
from aiwriter_backend.db.base import Job, Article
from aiwriter_backend.schemas.job import JobCreate, JobResponse, JobStatus
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
    print(f"[JOB_ROUTER] - Context: {getattr(request, 'context', None) or 'None'}")
    print(f"[JOB_ROUTER] - User Images: {len(getattr(request, 'user_images', []) or [])} images")
    print(f"[JOB_ROUTER] - Include FAQ: {getattr(request, 'include_faq', True)}")
    print(f"[JOB_ROUTER] - Include CTA: {getattr(request, 'include_cta', False)}")
    print(f"[JOB_ROUTER] - Category: {getattr(request, 'category', None) or 'None'}")
    print(f"[JOB_ROUTER] - Tags: {getattr(request, 'tags', None) or 'None'}")
    print(f"[JOB_ROUTER] - Signature: {x_signature[:10]}...")
    
    service = JobService(db)
    result = await service.create_job(
        site_id=x_site_id,
        topic=request.topic,
        length=request.length,
        include_images=request.include_images,
        language=getattr(request, 'language', 'de'),
        context=getattr(request, 'context', None),
        user_images=getattr(request, 'user_images', None),
        include_faq=getattr(request, 'include_faq', True),
        include_cta=getattr(request, 'include_cta', False),
        cta_url=getattr(request, 'cta_url', None),
        category=getattr(request, 'category', None),
        tags=getattr(request, 'tags', None)
    )
    
    print(f"[JOB_ROUTER] Job creation result: {result.success}, Message: {result.message}")
    return result


@router.get("/{job_id}/status", response_model=JobStatus)
async def get_job_status(
    job_id: int,
    x_site_id: int = Header(..., alias="X-Site-ID"),
    x_signature: str = Header(..., alias="X-Signature"),
    db: Session = Depends(get_db)
):
    """Get job status."""
    # Verify site exists
    service = JobService(db)
    # Basic validation - in production, verify signature
    
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Get article if exists to retrieve WordPress post ID
    article = db.query(Article).filter(Article.job_id == job_id).first()
    wordpress_post_id = None
    if article and article.outline_json and isinstance(article.outline_json, dict):
        wordpress_post_id = article.outline_json.get("wordpress_post_id")
    
    # Return job status with post_id if available
    return JobStatus(
        job_id=job.id,
        status=job.status,
        topic=job.topic,
        created_at=job.created_at,
        finished_at=job.finished_at,
        error=job.error,
        wordpress_post_id=wordpress_post_id
    )
