"""
Webhook service for WordPress communication.
"""
import requests
import json
from datetime import datetime
from sqlalchemy.orm import Session
from aiwriter_backend.db.base import Site, Job
from aiwriter_backend.schemas.webhook import PublishResponse
from aiwriter_backend.core.security import verify_hmac_signature


class WebhookService:
    """Service for webhook handling."""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def publish_article(self, site_id: int, job_id: int, article_data: dict, signature: str) -> PublishResponse:
        """Publish an article to WordPress."""
        try:
            # Get site info
            site = self.db.query(Site).filter(Site.id == site_id).first()
            if not site:
                return PublishResponse(
                    success=False,
                    message="Site not found"
                )
            
            # Verify HMAC signature
            payload_str = json.dumps(article_data, sort_keys=True)
            if not verify_hmac_signature(payload_str, signature, site.site_secret):
                return PublishResponse(
                    success=False,
                    message="Invalid signature"
                )
            
            # Get job info
            job = self.db.query(Job).filter(Job.id == job_id).first()
            if not job:
                return PublishResponse(
                    success=False,
                    message="Job not found"
                )
            
            # Prepare payload for WordPress
            wp_payload = {
                "payload": {
                    "title": article_data.get("title", ""),
                    "content": article_data.get("content", ""),
                    "meta": {
                        "title": article_data.get("meta_title", ""),
                        "description": article_data.get("meta_description", "")
                    },
                    "featured_image": article_data.get("featured_image"),
                    "faq": article_data.get("faq", []),
                    "schema": article_data.get("schema_data", {})
                },
                "signature": signature
            }
            
            # Send to WordPress
            wp_url = f"https://{site.domain}/wp-json/aiwriter/v1/publish"
            response = requests.post(
                wp_url,
                json=wp_payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Update job status
                job.status = "completed"
                job.finished_at = datetime.now()
                self.db.commit()
                
                return PublishResponse(
                    success=True,
                    post_id=result.get("post_id"),
                    message="Article published successfully"
                )
            else:
                # Update job with error
                job.status = "failed"
                job.error = f"WordPress error: {response.status_code}"
                job.finished_at = datetime.now()
                self.db.commit()
                
                return PublishResponse(
                    success=False,
                    message=f"WordPress publishing failed: {response.status_code}"
                )
                
        except Exception as e:
            # Update job with error
            job = self.db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = "failed"
                job.error = str(e)
                job.finished_at = datetime.now()
                self.db.commit()
            
            return PublishResponse(
                success=False,
                message=f"Publishing failed: {str(e)}"
            )
