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
    print(f"[JOB_ROUTER] - Context: {getattr(request, 'context', None) or 'None'}")
    print(f"[JOB_ROUTER] - User Images: {len(getattr(request, 'user_images', []) or [])} images")
    print(f"[JOB_ROUTER] - Include FAQ: {getattr(request, 'include_faq', True)}")
    print(f"[JOB_ROUTER] - Include CTA: {getattr(request, 'include_cta', False)}")
    print(f"[JOB_ROUTER] - Template: {getattr(request, 'template', 'classic')}")
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
        template=getattr(request, 'template', 'classic'),
        style_preset=getattr(request, 'style_preset', 'default')
    )
    
    print(f"[JOB_ROUTER] Job creation result: {result.success}, Message: {result.message}")
    return result
