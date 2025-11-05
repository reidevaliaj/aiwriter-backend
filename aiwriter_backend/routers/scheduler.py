"""
Scheduler endpoints for Option 2 - AutoPilot Scheduler.
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from aiwriter_backend.db.session import get_db
from aiwriter_backend.services.scheduler_service import SchedulerService
from aiwriter_backend.schemas.scheduler import (
    GeneratePlanRequest,
    GeneratePlanResponse,
    SavePlanRequest,
    SchedulerResponse,
    ScheduledJobsListResponse,
    ScheduledJobResponse,
    ScheduleItem
)
from typing import List

router = APIRouter()


@router.post("/generate_plan", response_model=GeneratePlanResponse)
async def generate_plan(
    request: GeneratePlanRequest,
    x_site_id: int = Header(..., alias="X-Site-ID"),
    x_signature: str = Header(..., alias="X-Signature"),
    db: Session = Depends(get_db)
):
    """Generate article titles for scheduling."""
    service = SchedulerService(db)
    result = await service.generate_plan(
        site_id=x_site_id,
        context=request.context,
        goal=request.goal,
        count=request.count
    )
    
    if result.get("success"):
        return GeneratePlanResponse(
            success=True,
            titles=result.get("titles", [])
        )
    else:
        return GeneratePlanResponse(
            success=False,
            error=result.get("error", "Failed to generate titles")
        )


@router.post("/save_plan", response_model=SchedulerResponse)
async def save_plan(
    request: SavePlanRequest,
    x_site_id: int = Header(..., alias="X-Site-ID"),
    x_signature: str = Header(..., alias="X-Signature"),
    db: Session = Depends(get_db)
):
    """Save a schedule plan to the database."""
    service = SchedulerService(db)
    
    # Convert schedule items to dict format
    schedule_data = []
    for item in request.schedule:
        schedule_data.append({
            "title": item.title,
            "description": item.description,
            "publish_date": item.publish_date,
            "user_images": item.user_images,
            "generate_images": item.generate_images,
            "context": item.context,
            "goal": item.goal
        })
    
    result = await service.save_plan(
        site_id=x_site_id,
        schedule_data=schedule_data
    )
    
    if result.get("success"):
        return SchedulerResponse(
            success=True,
            message=f"Saved {result.get('saved_count', 0)} scheduled posts"
        )
    else:
        return SchedulerResponse(
            success=False,
            error=result.get("error", "Failed to save schedule")
        )


@router.get("/list", response_model=ScheduledJobsListResponse)
async def list_scheduled(
    days: int = 7,
    x_site_id: int = Header(..., alias="X-Site-ID"),
    x_signature: str = Header(..., alias="X-Signature"),
    db: Session = Depends(get_db)
):
    """Get upcoming scheduled jobs."""
    service = SchedulerService(db)
    jobs = await service.get_upcoming(site_id=x_site_id, days=days)
    
    job_responses = [
        ScheduledJobResponse(
            id=job["id"],
            title=job["title"],
            description=job.get("description"),
            publish_date=datetime.fromisoformat(job["publish_date"]),
            status=job["status"],
            generate_images=job["generate_images"],
            wordpress_post_id=job.get("wordpress_post_id"),
            error=job.get("error")
        )
        for job in jobs
    ]
    
    return ScheduledJobsListResponse(
        success=True,
        jobs=job_responses
    )


@router.put("/update/{job_id}", response_model=SchedulerResponse)
async def update_scheduled(
    job_id: int,
    updates: dict,
    x_site_id: int = Header(..., alias="X-Site-ID"),
    x_signature: str = Header(..., alias="X-Signature"),
    db: Session = Depends(get_db)
):
    """Update a scheduled job."""
    service = SchedulerService(db)
    result = await service.update_scheduled_job(job_id=job_id, updates=updates)
    
    if result.get("success"):
        return SchedulerResponse(
            success=True,
            message=result.get("message", "Updated successfully")
        )
    else:
        return SchedulerResponse(
            success=False,
            error=result.get("error", "Failed to update")
        )


@router.delete("/delete/{job_id}", response_model=SchedulerResponse)
async def delete_scheduled(
    job_id: int,
    x_site_id: int = Header(..., alias="X-Site-ID"),
    x_signature: str = Header(..., alias="X-Signature"),
    db: Session = Depends(get_db)
):
    """Delete a scheduled job."""
    service = SchedulerService(db)
    result = await service.delete_scheduled_job(job_id=job_id)
    
    if result.get("success"):
        return SchedulerResponse(
            success=True,
            message=result.get("message", "Deleted successfully")
        )
    else:
        return SchedulerResponse(
            success=False,
            error=result.get("error", "Failed to delete")
        )


@router.post("/run_daily", response_model=SchedulerResponse)
async def run_daily(
    db: Session = Depends(get_db)
):
    """
    Internal endpoint to process due scheduled jobs.
    This is called by APScheduler daily.
    """
    service = SchedulerService(db)
    result = await service.process_due_jobs()
    
    if result.get("success"):
        return SchedulerResponse(
            success=True,
            message=f"Processed {result.get('processed', 0)} jobs, {result.get('failed', 0)} failed"
        )
    else:
        return SchedulerResponse(
            success=False,
            error=result.get("error", "Failed to process jobs")
        )

