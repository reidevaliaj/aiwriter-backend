"""
FastAPI main application for AIWriter backend.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aiwriter_backend.core.config import settings
from aiwriter_backend.db.init_db import init_db
from aiwriter_backend.routers import license, jobs, webhook

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

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    init_db()

@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "AIWriter Backend API", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
