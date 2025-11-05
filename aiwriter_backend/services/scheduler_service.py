"""
Scheduler service for Option 2 - AutoPilot Scheduler.
Handles title generation, schedule management, and automated publishing.
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_
from aiwriter_backend.db.base import ScheduledJob, Site, License, Job, Article
from aiwriter_backend.core.openai_client import run_text_structured
from aiwriter_backend.services.article_generator import ArticleGenerator
from aiwriter_backend.services.job_service import JobService
import json

logger = logging.getLogger(__name__)

# Schema for title generation response
TITLE_GENERATION_SCHEMA = {
    "type": "object",
    "properties": {
        "titles": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "keywords": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["title", "description"]
            }
        }
    },
    "required": ["titles"]
}


class SchedulerService:
    """Service for managing scheduled article jobs."""
    
    def __init__(self, db: Session):
        self.db = db
        self.article_generator = ArticleGenerator(db)
        self.job_service = JobService(db)
    
    async def generate_plan(
        self,
        site_id: int,
        context: str,
        goal: Optional[str] = None,
        count: int = 30
    ) -> Dict[str, Any]:
        """
        Generate a list of article titles using GPT-4o.
        
        Args:
            site_id: Site ID
            context: Website context/niche description
            goal: Goal (contact page, newsletter, shop, etc.)
            count: Number of titles to generate (default 30)
        
        Returns:
            Dict with list of titles, descriptions, and keywords
        """
        try:
            # Get site info for context
            site = self.db.query(Site).filter(Site.id == site_id).first()
            if not site:
                raise ValueError("Site not found")
            
            # Build prompt for title generation
            goal_text = f"\nZiel: {goal}" if goal else ""
            prompt = f"""Du bist ein Content-Strategist für eine Website. Basierend auf dem folgenden Kontext erstelle {count} Artikel-Titel für ein regelmäßiges Blog-Publishing-Programm.

Website-Kontext:
{context}{goal_text}

Erstelle {count} SEO-optimierte, ansprechende Artikel-Titel in deutscher Sprache. Jeder Titel sollte:
- 50-60 Zeichen lang sein
- Klar und präzise sein
- Neugier wecken
- Zum Klicken einladen
- Zum Website-Kontext passen

Gib für jeden Titel auch eine kurze Beschreibung (1-2 Sätze) und 3-5 relevante Keywords an.

Antworte im folgenden JSON-Format:
{{
  "titles": [
    {{
      "title": "Artikel-Titel",
      "description": "Kurze Beschreibung des Artikels",
      "keywords": ["keyword1", "keyword2", "keyword3"]
    }}
  ]
}}"""

            messages = [
                {
                    "role": "system",
                    "content": "Du bist ein erfahrener Content-Strategist und SEO-Experte. Du erstellst professionelle, ansprechende Artikel-Titel für deutsche Websites."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
            
            logger.info(f"Generating {count} titles for site {site_id}")
            
            # Call OpenAI with structured output
            from aiwriter_backend.core.openai_client import run_text_structured
            
            result = await run_text_structured(
                messages,
                TITLE_GENERATION_SCHEMA,
                model="gpt-4o",
                temperature=0.7,
                max_completion_tokens=2000
            )
            
            # Parse and validate response
            if isinstance(result, dict) and "titles" in result:
                titles = result["titles"][:count]  # Limit to requested count
                logger.info(f"Generated {len(titles)} titles for site {site_id}")
                return {"success": True, "titles": titles}
            else:
                logger.error(f"Invalid response format from OpenAI: {result}")
                return {"success": False, "error": "Invalid response format"}
                
        except Exception as e:
            logger.exception(f"Error generating titles: {e}")
            return {"success": False, "error": str(e)}
    
    async def save_plan(
        self,
        site_id: int,
        schedule_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Save a schedule plan to the database.
        
        Args:
            site_id: Site ID
            schedule_data: List of schedule items with title, description, publish_date, etc.
        
        Returns:
            Dict with success status and saved schedule IDs
        """
        try:
            site = self.db.query(Site).filter(Site.id == site_id).first()
            if not site:
                return {"success": False, "error": "Site not found"}
            
            saved_ids = []
            
            for item in schedule_data:
                # Validate publish_date
                publish_date_str = item.get("publish_date")
                if not publish_date_str:
                    continue
                
                # Parse date
                try:
                    if isinstance(publish_date_str, str):
                        publish_date = datetime.fromisoformat(publish_date_str.replace('Z', '+00:00'))
                    else:
                        publish_date = publish_date_str
                    
                    # Ensure date is timezone-aware
                    if publish_date.tzinfo is None:
                        publish_date = publish_date.replace(tzinfo=timezone.utc)
                except Exception as e:
                    logger.error(f"Error parsing date {publish_date_str}: {e}")
                    continue
                
                # Validate date is in the future
                if publish_date <= datetime.now(timezone.utc):
                    logger.warning(f"Skipping past date: {publish_date}")
                    continue
                
                # Create scheduled job
                scheduled_job = ScheduledJob(
                    site_id=site_id,
                    license_id=site.license_id,
                    title=item.get("title", ""),
                    description=item.get("description", ""),
                    context=item.get("context", ""),
                    goal=item.get("goal", ""),
                    publish_date=publish_date,
                    user_images=item.get("user_images"),
                    generate_images=item.get("generate_images", False),
                    status="pending"
                )
                
                self.db.add(scheduled_job)
                saved_ids.append(scheduled_job.id)
            
            self.db.commit()
            
            logger.info(f"Saved {len(saved_ids)} scheduled jobs for site {site_id}")
            return {"success": True, "saved_count": len(saved_ids), "ids": saved_ids}
            
        except Exception as e:
            logger.exception(f"Error saving schedule: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}
    
    async def get_upcoming(
        self,
        site_id: int,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """Get upcoming scheduled jobs for a site."""
        try:
            cutoff_date = datetime.now(timezone.utc) + timedelta(days=days)
            
            scheduled_jobs = self.db.query(ScheduledJob).filter(
                and_(
                    ScheduledJob.site_id == site_id,
                    ScheduledJob.publish_date >= datetime.now(timezone.utc),
                    ScheduledJob.publish_date <= cutoff_date
                )
            ).order_by(ScheduledJob.publish_date).all()
            
            result = []
            for job in scheduled_jobs:
                result.append({
                    "id": job.id,
                    "title": job.title,
                    "description": job.description,
                    "publish_date": job.publish_date.isoformat(),
                    "status": job.status,
                    "generate_images": job.generate_images,
                    "wordpress_post_id": job.wordpress_post_id,
                    "error": job.error
                })
            
            return result
            
        except Exception as e:
            logger.exception(f"Error getting upcoming jobs: {e}")
            return []
    
    async def update_scheduled_job(
        self,
        job_id: int,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update a scheduled job."""
        try:
            scheduled_job = self.db.query(ScheduledJob).filter(ScheduledJob.id == job_id).first()
            if not scheduled_job:
                return {"success": False, "error": "Scheduled job not found"}
            
            # Update fields
            if "title" in updates:
                scheduled_job.title = updates["title"]
            if "description" in updates:
                scheduled_job.description = updates["description"]
            if "publish_date" in updates:
                publish_date_str = updates["publish_date"]
                try:
                    if isinstance(publish_date_str, str):
                        publish_date = datetime.fromisoformat(publish_date_str.replace('Z', '+00:00'))
                    else:
                        publish_date = publish_date_str
                    if publish_date.tzinfo is None:
                        publish_date = publish_date.replace(tzinfo=timezone.utc)
                    scheduled_job.publish_date = publish_date
                except Exception as e:
                    return {"success": False, "error": f"Invalid date format: {e}"}
            if "user_images" in updates:
                scheduled_job.user_images = updates["user_images"]
            if "generate_images" in updates:
                scheduled_job.generate_images = updates["generate_images"]
            
            scheduled_job.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            
            return {"success": True, "message": "Scheduled job updated"}
            
        except Exception as e:
            logger.exception(f"Error updating scheduled job: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}
    
    async def delete_scheduled_job(self, job_id: int) -> Dict[str, Any]:
        """Delete a scheduled job."""
        try:
            scheduled_job = self.db.query(ScheduledJob).filter(ScheduledJob.id == job_id).first()
            if not scheduled_job:
                return {"success": False, "error": "Scheduled job not found"}
            
            # Only allow deletion if not already processing or completed
            if scheduled_job.status in ["processing", "completed"]:
                return {"success": False, "error": "Cannot delete job that is processing or completed"}
            
            self.db.delete(scheduled_job)
            self.db.commit()
            
            return {"success": True, "message": "Scheduled job deleted"}
            
        except Exception as e:
            logger.exception(f"Error deleting scheduled job: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}
    
    async def process_due_jobs(self) -> Dict[str, Any]:
        """
        Process all scheduled jobs that are due to be published.
        This is called by APScheduler daily.
        """
        try:
            now = datetime.now(timezone.utc)
            
            # Find all pending jobs where publish_date is in the past
            due_jobs = self.db.query(ScheduledJob).filter(
                and_(
                    ScheduledJob.status == "pending",
                    ScheduledJob.publish_date <= now
                )
            ).all()
            
            logger.info(f"Found {len(due_jobs)} scheduled jobs due for publishing")
            
            processed = 0
            failed = 0
            
            for scheduled_job in due_jobs:
                try:
                    # Mark as processing
                    scheduled_job.status = "processing"
                    self.db.commit()
                    
                    # Create a regular job using the existing article generation flow
                    # Use the scheduled job's title as topic, and include context
                    job_response = await self.job_service.create_job(
                        site_id=scheduled_job.site_id,
                        topic=scheduled_job.title,
                        length="medium",  # Default length for scheduled posts
                        include_images=scheduled_job.generate_images,
                        language="de",
                        context=scheduled_job.context,
                        user_images=scheduled_job.user_images,
                        include_faq=True,  # Default for scheduled posts
                        include_cta=False,
                        category=None,
                        tags=None
                    )
                    
                    if job_response.success and job_response.job_id:
                        # Link the job to the scheduled job
                        scheduled_job.job_id = job_response.job_id
                        
                        # Wait for article generation to complete
                        # The article will be published via webhook automatically
                        # We'll update the scheduled_job status when we get the WordPress post ID
                        
                        # For now, mark as completed (the webhook will update wordpress_post_id)
                        scheduled_job.status = "completed"
                        self.db.commit()
                        processed += 1
                        
                        logger.info(f"Processed scheduled job {scheduled_job.id} -> job {job_response.job_id}")
                    else:
                        scheduled_job.status = "failed"
                        scheduled_job.error = job_response.message
                        self.db.commit()
                        failed += 1
                        
                except Exception as e:
                    logger.exception(f"Error processing scheduled job {scheduled_job.id}: {e}")
                    scheduled_job.status = "failed"
                    scheduled_job.error = str(e)
                    self.db.commit()
                    failed += 1
            
            return {
                "success": True,
                "processed": processed,
                "failed": failed,
                "total": len(due_jobs)
            }
            
        except Exception as e:
            logger.exception(f"Error processing due jobs: {e}")
            return {"success": False, "error": str(e)}

