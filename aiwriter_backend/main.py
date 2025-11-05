"""
FastAPI main application for AIWriter backend.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import asyncio
import logging

from aiwriter_backend.core.config import settings
from aiwriter_backend.db.init_db import init_db
from aiwriter_backend.db.session import SessionLocal
from aiwriter_backend.routers import license, jobs, webhook, scheduler
from aiwriter_backend.services.scheduler_service import SchedulerService

logger = logging.getLogger(__name__)

# Initialize APScheduler (renamed to avoid conflict with scheduler router module)
job_scheduler = AsyncIOScheduler()

app = FastAPI(
    title="AIWriter Backend API",
    description="Backend API for AIWriter WordPress plugin",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(license.router, prefix="/v1/license", tags=["license"])
app.include_router(jobs.router, prefix="/v1/jobs", tags=["jobs"])
app.include_router(webhook.router, prefix="/v1/sites", tags=["webhook"])
app.include_router(scheduler.router, prefix="/v1/scheduler", tags=["scheduler"])

async def process_due_scheduled_jobs():
    """Background task to process due scheduled jobs."""
    try:
        db = SessionLocal()
        try:
            service = SchedulerService(db)
            result = await service.process_due_jobs()
            logger.info(f"Processed scheduled jobs: {result}")
        finally:
            db.close()
    except Exception as e:
        logger.exception(f"Error processing scheduled jobs: {e}")


@app.on_event("startup")
async def startup_event():
    """Initialize database and scheduler on startup."""
    init_db()
    
    # Schedule daily job processing at 2 AM UTC
    job_scheduler.add_job(
        process_due_scheduled_jobs,
        trigger=CronTrigger(hour=2, minute=0),  # Run daily at 2 AM UTC
        id="process_scheduled_jobs",
        name="Process due scheduled jobs",
        replace_existing=True
    )
    
    job_scheduler.start()
    logger.info("APScheduler started - scheduled jobs will be processed daily at 2 AM UTC")


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown scheduler on application shutdown."""
    job_scheduler.shutdown(wait=False)
    logger.info("APScheduler stopped")

@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "AIWriter Backend API", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
