"""
Job management service.
"""
import asyncio
from sqlalchemy.orm import Session
from aiwriter_backend.db.base import Job, Site, License, Plan, Usage
from aiwriter_backend.schemas.job import JobResponse
from datetime import datetime
import calendar


class JobService:
    """Service for job management."""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def create_job(
        self,
        site_id: int,
        topic: str,
        length: str = "medium",
        include_images: bool = False,
        language: str = "de",
        context: str = None,
        user_images: list = None,
        include_faq: bool = True,
        include_cta: bool = False,
        cta_url: str = None,
        category: int = None,
        tags: str = None
    ) -> JobResponse:
        """Create a new article generation job."""
        try:
            print(f"[JOB_SERVICE] Creating job - Site ID: {site_id}, Topic: {topic}, Length: {length}, Include Images: {include_images}")
            
            # Get site and license info
            site = self.db.query(Site).filter(Site.id == site_id).first()
            if not site:
                print(f"[JOB_SERVICE] ERROR: Site not found for ID {site_id}")
                return JobResponse(
                    success=False,
                    message="Site not found"
                )
            
            print(f"[JOB_SERVICE] Site found: {site.domain}")
            
            license_obj = self.db.query(License).filter(License.id == site.license_id).first()
            if not license_obj or license_obj.status != "active":
                print(f"[JOB_SERVICE] ERROR: License not active for site {site_id}")
                return JobResponse(
                    success=False,
                    message="License not active"
                )
            
            print(f"[JOB_SERVICE] License found: {license_obj.key}")
            
            # Check quota
            quota_check = await self._check_quota(site_id, license_obj.plan_id)
            print(f"[JOB_SERVICE] Quota check: {quota_check}")
            if not quota_check["allowed"]:
                return JobResponse(
                    success=False,
                    message=f"Quota exceeded. {quota_check['message']}"
                )
            
            # Check image quota ONLY if requesting images
            if include_images:
                print(f"[JOB_SERVICE] Checking image quota for plan {license_obj.plan_id}")
                plan = self.db.query(Plan).filter(Plan.id == license_obj.plan_id).first()
                if not plan:
                    print(f"[JOB_SERVICE] ERROR: Plan not found for ID {license_obj.plan_id}")
                    return JobResponse(
                        success=False,
                        message="Plan information missing"
                    )

                allowance = plan.max_images_per_article if plan.max_images_per_article is not None else 0
                if allowance <= 0:
                    print(f"[JOB_SERVICE] ERROR: Image generation not available in plan {plan.name}")
                    return JobResponse(
                        success=False,
                        message="Image generation not available in your plan"
                    )

                print(f"[JOB_SERVICE] Image generation allowed: {allowance} images per article")
            else:
                print(f"[JOB_SERVICE] No image generation requested, skipping image quota check")
            
            # Determine number of images to request
            requested_images = 0
            if include_images:
                plan = plan or self.db.query(Plan).filter(Plan.id == license_obj.plan_id).first()
                allowance = 0
                if plan:
                    allowance = plan.max_images_per_article if plan.max_images_per_article is not None else 0
                requested_images = min(max(allowance, 0), 1)
            
            # Create job with Phase 3.5 fields
            # Store category/tags in template/style_preset fields temporarily (repurposed)
            job = Job(
                site_id=site_id,
                topic=topic,
                length=length,
                images=include_images,
                requested_images=requested_images,
                language=language,
                context=context,
                user_images=user_images if user_images else None,
                include_faq=include_faq,
                include_cta=include_cta,
                cta_url=cta_url,
                template=str(category) if category else None,  # Store category ID as string
                style_preset=tags if tags else None,  # Store tags
                status="pending"
            )
            
            print(f"[JOB_SERVICE] Creating job record: {job.topic}")
            self.db.add(job)
            self.db.commit()
            self.db.refresh(job)
            
            print(f"[JOB_SERVICE] Job created successfully with ID: {job.id}")
            
            # DON'T update usage immediately - wait for success
            # await self.update_usage(site_id)
            # print(f"[JOB_SERVICE] Usage updated for site {site_id}")
            
            # Start article generation in background (non-blocking)
            asyncio.create_task(self._start_article_generation(job.id))
            print(f"[JOB_SERVICE] Article generation started in background for job {job.id}")
            
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
            print(f"[JOB_SERVICE] Checking quota for site {site_id}, plan {plan_id}, month {current_month}")
            
            # Get plan limits
            plan = self.db.query(Plan).filter(Plan.id == plan_id).first()
            if not plan:
                print(f"[JOB_SERVICE] ERROR: Plan not found for ID {plan_id}")
                return {
                    "allowed": False,
                    "message": "Plan not found"
                }
            
            monthly_limit = plan.monthly_limit
            print(f"[JOB_SERVICE] Plan: {plan.name}, Monthly limit: {monthly_limit}")
            
            # Get current usage
            usage = self.db.query(Usage).filter(
                Usage.site_id == site_id,
                Usage.year_month == current_month
            ).first()
            
            articles_generated = usage.articles_generated if usage else 0
            print(f"[JOB_SERVICE] Current usage: {articles_generated}/{monthly_limit}")
            
            if articles_generated >= monthly_limit:
                print(f"[JOB_SERVICE] Quota exceeded: {articles_generated} >= {monthly_limit}")
                return {
                    "allowed": False,
                    "message": f"Monthly limit of {monthly_limit} articles reached"
                }
            
            remaining = monthly_limit - articles_generated
            print(f"[JOB_SERVICE] Quota check passed: {remaining} articles remaining")
            return {
                "allowed": True,
                "message": f"{remaining} articles remaining this month"
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
    
    async def _start_article_generation(self, job_id: int):
        """Start article generation for a job."""
        try:
            print(f"[JOB_SERVICE] Starting article generation for job {job_id}")
            from aiwriter_backend.services.article_generator import ArticleGenerator
            print(f"[JOB_SERVICE] ArticleGenerator imported successfully")
            
            generator = ArticleGenerator(self.db)
            print(f"[JOB_SERVICE] ArticleGenerator instance created")
            
            result = await generator.generate_article(job_id)
            print(f"[JOB_SERVICE] Article generation completed with result: {result}")
            
            # Update usage only on success
            if result:
                job = self.db.query(Job).filter(Job.id == job_id).first()
                if job:
                    await self.update_usage(job.site_id)
                    print(f"[JOB_SERVICE] Usage updated for site {job.site_id} after successful generation")
            
        except Exception as e:
            print(f"[JOB_SERVICE] Error starting article generation: {e}")
            import traceback
            traceback.print_exc()
