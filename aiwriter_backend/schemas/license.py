"""
License-related Pydantic schemas.
"""
from pydantic import BaseModel
from typing import Optional


class LicenseActivate(BaseModel):
    """Request schema for license activation."""
    license_key: str
    domain: str
    callback_url: Optional[str] = None


class LicenseActivateResponse(BaseModel):
    """Response schema for license activation."""
    success: bool
    site_id: Optional[int] = None
    secret: Optional[str] = None
    message: str


class LicenseValidate(BaseModel):
    """Request schema for license validation."""
    license_key: str


class LicenseValidateResponse(BaseModel):
    """Response schema for license validation."""
    valid: bool
    plan_name: Optional[str] = None
    monthly_limit: Optional[int] = None
    max_images: Optional[int] = None
    message: str
