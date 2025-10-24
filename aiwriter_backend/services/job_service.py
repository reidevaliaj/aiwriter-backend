"""
Job management service.
"""
from sqlalchemy.orm import Session
from aiwriter_backend.db.base import Job, Site, License, Plan, Usage
from aiwriter_backend.schemas.job import JobResponse
from datetime import datetime
import calendar


class JobService:
    """Service for job management."""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def create_job(self, site_id: int, topic: str, length: str = "medium", include_images: bool = False) -> JobResponse:
        """Create a new article generation job."""
        try:
            # Get site and license info
            site = self.db.query(Site).filter(Site.id == site_id).first()
            if not site:
                return JobResponse(
                    success=False,
                    message="Site not found"
                )
            
            license_obj = self.db.query(License).filter(License.id == site.license_id).first()
            if not license_obj or license_obj.status != "active":
                return JobResponse(
                    success=False,
                    message="License not active"
                )
            
            # Check quota
            quota_check = await self._check_quota(site_id, license_obj.plan_id)
            if not quota_check["allowed"]:
                return JobResponse(
                    success=False,
                    message=f"Quota exceeded. {quota_check['message']}"
                )
            
            # Check image quota if requesting images
            if include_images:
                plan = self.db.query(Plan).filter(Plan.id == license_obj.plan_id).first()
                if plan.max_images_per_article == 0:
                    return JobResponse(
                        success=False,
                        message="Image generation not available in your plan"
                    )
            
            # Create job
            job = Job(
                site_id=site_id,
                topic=topic,
                length=length,
                images=include_images,
                status="pending"
            )
            
            self.db.add(job)
            self.db.commit()
            self.db.refresh(job)
            
            return JobResponse(
                success=True,
                job_id=job.id,
                message="Job created successfully"
            )
            
        except Exception as e:
            self.db.rollback()
            return JobResponse(
                success=False,
                message=f"Job creation failed: {str(e)}"
            )
    
    async def _check_quota(self, site_id: int, plan_id: int) -> dict:
        """Check if site has remaining quota."""
        try:
            # Get current month
            now = datetime.now()
            current_month = f"{now.year}-{now.month:02d}"
            
            # Get plan limits
            plan = self.db.query(Plan).filter(Plan.id == plan_id).first()
            monthly_limit = plan.monthly_limit
            
            # Get current usage
            usage = self.db.query(Usage).filter(
                Usage.site_id == site_id,
                Usage.year_month == current_month
            ).first()
            
            articles_generated = usage.articles_generated if usage else 0
            
            if articles_generated >= monthly_limit:
                return {
                    "allowed": False,
                    "message": f"Monthly limit of {monthly_limit} articles reached"
                }
            
            return {
                "allowed": True,
                "message": f"{monthly_limit - articles_generated} articles remaining this month"
            }
            
        except Exception as e:
            return {
                "allowed": False,
                "message": f"Quota check failed: {str(e)}"
            }
    
    async def update_usage(self, site_id: int):
        """Update usage statistics after job completion."""
        try:
            now = datetime.now()
            current_month = f"{now.year}-{now.month:02d}"
            
            usage = self.db.query(Usage).filter(
                Usage.site_id == site_id,
                Usage.year_month == current_month
            ).first()
            
            if usage:
                usage.articles_generated += 1
            else:
                usage = Usage(
                    site_id=site_id,
                    year_month=current_month,
                    articles_generated=1
                )
                self.db.add(usage)
            
            self.db.commit()
            
        except Exception as e:
            self.db.rollback()
            print(f"Failed to update usage: {e}")
