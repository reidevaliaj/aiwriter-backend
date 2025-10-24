"""
License management endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from aiwriter_backend.db.session import get_db
from aiwriter_backend.schemas.license import (
    LicenseActivate, 
    LicenseActivateResponse,
    LicenseValidate, 
    LicenseValidateResponse
)
from aiwriter_backend.services.license_service import LicenseService

router = APIRouter()


@router.post("/activate", response_model=LicenseActivateResponse)
async def activate_license(
    request: LicenseActivate,
    db: Session = Depends(get_db)
):
    """Activate a license for a WordPress site."""
    service = LicenseService(db)
    return await service.activate_license(request.license_key, request.domain)


@router.post("/validate", response_model=LicenseValidateResponse)
async def validate_license(
    request: LicenseValidate,
    db: Session = Depends(get_db)
):
    """Validate a license key."""
    service = LicenseService(db)
    return await service.validate_license(request.license_key)
