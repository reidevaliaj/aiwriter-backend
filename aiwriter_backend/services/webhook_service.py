"""
Webhook service for WordPress communication.
"""
import requests
import json
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from typing import Optional

from aiwriter_backend.db.base import Site, Job, Article, ArticleStatus
from aiwriter_backend.schemas.webhook import PublishResponse
from aiwriter_backend.core.security import verify_hmac_signature

logger = logging.getLogger(__name__)


class WebhookService:
    """Service for webhook handling."""
    
    def __init__(self, db: Session):
        self.db = db
    
    @staticmethod
    def _coerce_json(value, default):
        """Return JSON-like value as native Python, handling str/list/dict."""
        if value is None:
            return default
        if isinstance(value, (list, dict)):
            return value
        try:
            return json.loads(value)
        except Exception:  # noqa: BLE001
            return default
    
    async def send_article_to_wordpress(self, article_id: int, payload_override: Optional[dict] = None) -> bool:
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
            
            # Prepare article data, preferring freshly generated payload if provided
            article_data = self._build_article_payload(article, payload_override)
            
            # Image URLs are already handled in _build_article_payload
            
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
                post_id = result.get("post_id")
                logger.info(f"Article {article_id} sent to WordPress successfully, post_id: {post_id}")
                
                # Store WordPress post ID in article's outline_json
                if post_id:
                    if article.outline_json and isinstance(article.outline_json, dict):
                        article.outline_json["wordpress_post_id"] = post_id
                    else:
                        article.outline_json = {"wordpress_post_id": post_id}
                
                # Update article status
                article.status = ArticleStatus.READY
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

    def _build_article_payload(self, article: Article, payload_override: Optional[dict]) -> dict:
        payload = payload_override or {}

        # Title
        title = payload.get("title") or article.topic or "Untitled Article"

        # Content (fallback order)
        content = (
            payload.get("article_html")
            or payload.get("content")
            or payload.get("content_html")
            or article.article_html
            or ""
        )

        # Meta
        meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
        meta_title = meta.get("title") or payload.get("meta_title") or article.meta_title or title[:60]
        meta_description = (
            meta.get("description")
            or payload.get("meta_description")
            or article.meta_description
            or f"Erfahren Sie mehr über {title}."[:155]
        )

        # FAQ & schema
        faq_payload = payload.get("faq") if isinstance(payload.get("faq"), list) else None
        schema_payload = payload.get("schema") or payload.get("schema_data")

        faq = faq_payload if faq_payload is not None else self._coerce_json(article.faq_json, default=[])
        schema = (
            schema_payload
            if isinstance(schema_payload, (dict, list))
            else self._coerce_json(article.schema_json, default={})
        )

        # Featured image and content images (prefer override)
        featured_image = payload.get("featured_image") or None
        content_image_urls = payload.get("image_urls") or []
        
        # Ensure content_image_urls doesn't include the featured image
        if featured_image and content_image_urls:
            content_image_urls = [url for url in content_image_urls if url != featured_image]
        
        if featured_image is None:
            image_urls = self._coerce_json(article.image_urls_json, default=[])
            if len(image_urls) == 1:
                # Single image: featured only
                featured_image = image_urls[0]
                content_image_urls = []
            elif len(image_urls) > 1:
                # Multiple images: first featured, rest in content
                featured_image = image_urls[0]
                content_image_urls = [url for url in image_urls[1:] if url != featured_image]  # Explicitly exclude featured

        # Category and tags (from payload override)
        category = payload.get("category")
        tags = payload.get("tags")
        
        # Include FAQ flag
        include_faq = payload.get("include_faq", True)  # Default to True for backwards compatibility
        
        return {
            "title": title,
            "content": content,
            "meta_title": meta_title,
            "meta_description": meta_description,
            "faq": faq,
            "schema_data": schema,
            "featured_image": featured_image,
            "image_urls": content_image_urls,  # Images to include in content
            "category": category,  # WordPress category ID
            "tags": tags,  # WordPress tags (comma-separated)
            "include_faq": include_faq,  # Whether FAQ was requested
        }

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
                post_id = result.get("post_id")
                
                # Store WordPress post ID in article
                article = self.db.query(Article).filter(Article.job_id == job_id).first()
                if article and post_id:
                    # Store as JSON in a metadata field (or add column later)
                    # For now, we'll add it to article metadata or store in job
                    # Since we don't have wordpress_post_id column, store in article's outline_json temporarily
                    if article.outline_json and isinstance(article.outline_json, dict):
                        article.outline_json["wordpress_post_id"] = post_id
                    else:
                        article.outline_json = {"wordpress_post_id": post_id}
                    self.db.commit()
                
                # Update job status
                job.status = "completed"
                job.finished_at = datetime.now()
                self.db.commit()
                
                return PublishResponse(
                    success=True,
                    post_id=post_id,
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
