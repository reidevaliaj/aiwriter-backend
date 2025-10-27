"""
Webhook service for WordPress communication.
"""
import requests
import json
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from aiwriter_backend.db.base import Site, Job, Article, ArticleStatus
from aiwriter_backend.schemas.webhook import PublishResponse
from aiwriter_backend.core.security import verify_hmac_signature

logger = logging.getLogger(__name__)


class WebhookService:
    """Service for webhook handling."""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def send_article_to_wordpress(self, article_id: int) -> bool:
        """Send article to WordPress via webhook."""
        try:
            # Get article and related data
            article = self.db.query(Article).filter(Article.id == article_id).first()
            if not article:
                logger.error(f"Article {article_id} not found")
                return False
            
            job = self.db.query(Job).filter(Job.id == article.job_id).first()
            if not job:
                logger.error(f"Job for article {article_id} not found")
                return False
            
            site = self.db.query(Site).filter(Site.id == job.site_id).first()
            if not site:
                logger.error(f"Site for job {job.id} not found")
                return False
            
            # Prepare article data
            article_data = {
                "title": article.topic,
                "content": article.article_html,
                "meta_title": article.meta_title,
                "meta_description": article.meta_description,
                "faq": json.loads(article.faq_json) if article.faq_json else [],
                "schema_data": json.loads(article.schema_json) if article.schema_json else {},
                "featured_image": None
            }
            
            # Add featured image if available
            if article.image_urls_json:
                image_urls = json.loads(article.image_urls_json)
                if image_urls:
                    article_data["featured_image"] = image_urls[0]
            
            # Create HMAC signature
            payload_str = json.dumps(article_data, sort_keys=True)
            signature = self._create_hmac_signature(payload_str, site.site_secret)
            
            # Send to WordPress
            wp_url = site.callback_url or f"https://{site.domain}/wp-json/aiwriter/v1/publish"
            logger.info(f"Sending article to WordPress: {wp_url}")
            
            wp_payload = {
                "payload": article_data,
                "signature": signature
            }
            
            response = requests.post(
                wp_url,
                json=wp_payload,
                headers={"Content-Type": "application/json"},
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Article {article_id} sent to WordPress successfully")
                
                # Update article status
                article.status = ArticleStatus.PUBLISHED
                article.updated_at = datetime.utcnow()
                self.db.commit()
                
                return True
            else:
                logger.error(f"WordPress publishing failed: {response.status_code} - {response.text}")
                
                # Update article status
                article.status = ArticleStatus.FAILED
                article.updated_at = datetime.utcnow()
                self.db.commit()
                
                return False
                
        except Exception as e:
            logger.error(f"Error sending article {article_id} to WordPress: {str(e)}")
            
            # Update article status
            if 'article' in locals():
                article.status = ArticleStatus.FAILED
                article.updated_at = datetime.utcnow()
                self.db.commit()
            
            return False
    
    def _create_hmac_signature(self, payload: str, secret: str) -> str:
        """Create HMAC signature for payload."""
        import hmac
        import hashlib
        
        signature = hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature

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
