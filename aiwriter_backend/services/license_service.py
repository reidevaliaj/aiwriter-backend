"""
License management service.
"""
import secrets
from sqlalchemy.orm import Session
from aiwriter_backend.db.base import License, Plan, Site
from aiwriter_backend.schemas.license import LicenseActivateResponse, LicenseValidateResponse


class LicenseService:
    """Service for license management."""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def activate_license(self, license_key: str, domain: str) -> LicenseActivateResponse:
        """Activate a license for a WordPress site."""
        try:
            # Find the license
            license_obj = self.db.query(License).filter(License.key == license_key).first()
            
            if not license_obj:
                return LicenseActivateResponse(
                    success=False,
                    message="Invalid license key"
                )
            
            if license_obj.status != "active":
                return LicenseActivateResponse(
                    success=False,
                    message="License is not active"
                )
            
            # Check if site already exists for this domain
            existing_site = self.db.query(Site).filter(
                Site.license_id == license_obj.id,
                Site.domain == domain
            ).first()
            
            if existing_site:
                return LicenseActivateResponse(
                    success=True,
                    site_id=existing_site.id,
                    secret=existing_site.site_secret,
                    message="Site already activated"
                )
            
            # Create new site
            site_secret = secrets.token_urlsafe(32)
            site = Site(
                license_id=license_obj.id,
                domain=domain,
                site_secret=site_secret,
                callback_url=request.callback_url
            )
            
            self.db.add(site)
            self.db.commit()
            self.db.refresh(site)
            
            return LicenseActivateResponse(
                success=True,
                site_id=site.id,
                secret=site.site_secret,
                message="License activated successfully"
            )
            
        except Exception as e:
            self.db.rollback()
            return LicenseActivateResponse(
                success=False,
                message=f"Activation failed: {str(e)}"
            )
    
    async def validate_license(self, license_key: str) -> LicenseValidateResponse:
        """Validate a license key."""
        try:
            license_obj = self.db.query(License).filter(License.key == license_key).first()
            
            if not license_obj:
                return LicenseValidateResponse(
                    valid=False,
                    message="Invalid license key"
                )
            
            if license_obj.status != "active":
                return LicenseValidateResponse(
                    valid=False,
                    message="License is not active"
                )
            
            # Get plan details
            plan = self.db.query(Plan).filter(Plan.id == license_obj.plan_id).first()
            
            return LicenseValidateResponse(
                valid=True,
                plan_name=plan.name,
                monthly_limit=plan.monthly_limit,
                max_images=plan.max_images_per_article,
                message="License is valid"
            )
            
        except Exception as e:
            return LicenseValidateResponse(
                valid=False,
                message=f"Validation failed: {str(e)}"
            )
