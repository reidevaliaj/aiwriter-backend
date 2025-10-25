"""
Simple article generation service for testing.
"""
import requests
import json
from datetime import datetime
from sqlalchemy.orm import Session
from aiwriter_backend.db.base import Job, Site
from aiwriter_backend.core.security import create_hmac_signature


class ArticleGenerator:
    """Simple article generator for testing."""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def generate_article(self, job_id: int):
        """Generate a simple article for testing."""
        try:
            print(f"[ARTICLE_GENERATOR] Starting article generation for job {job_id}")
            
            # Get job details
            job = self.db.query(Job).filter(Job.id == job_id).first()
            if not job:
                print(f"[ARTICLE_GENERATOR] ERROR: Job {job_id} not found")
                return False
            
            # Get site details
            site = self.db.query(Site).filter(Site.id == job.site_id).first()
            if not site:
                print(f"[ARTICLE_GENERATOR] ERROR: Site not found for job {job_id}")
                return False
            
            print(f"[ARTICLE_GENERATOR] Generating article for topic: {job.topic}")
            
            # Create a simple mock article
            article_data = self._create_mock_article(job.topic, job.length)
            
            # Update job status
            job.status = "completed"
            job.finished_at = datetime.now()
            self.db.commit()
            
            print(f"[ARTICLE_GENERATOR] Article generated successfully")
            
            # Send to WordPress
            success = await self._send_to_wordpress(site, job_id, article_data)
            
            if success:
                print(f"[ARTICLE_GENERATOR] Article sent to WordPress successfully")
            else:
                print(f"[ARTICLE_GENERATOR] Failed to send article to WordPress")
                job.status = "failed"
                job.error = "Failed to send to WordPress"
                self.db.commit()
            
            return success
            
        except Exception as e:
            print(f"[ARTICLE_GENERATOR] ERROR: {str(e)}")
            # Update job status
            job = self.db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = "failed"
                job.error = str(e)
                self.db.commit()
            return False
    
    def _create_mock_article(self, topic: str, length: str) -> dict:
        """Create a simple mock article."""
        word_count = {
            "short": 500,
            "medium": 800,
            "long": 1200
        }.get(length, 800)
        
        # Create a simple article structure
        title = f"Complete Guide to {topic.title()}"
        
        content = f"""
        <h2>Introduction to {topic}</h2>
        <p>Welcome to our comprehensive guide about {topic}. This article will provide you with all the essential information you need to understand and master this topic.</p>
        
        <h2>What is {topic}?</h2>
        <p>{topic} is an important subject that many people are interested in learning about. In this section, we'll explore the fundamental concepts and principles.</p>
        
        <h2>Key Benefits of {topic}</h2>
        <p>There are several advantages to understanding {topic}:</p>
        <ul>
            <li>Improved knowledge and understanding</li>
            <li>Better decision-making capabilities</li>
            <li>Enhanced problem-solving skills</li>
        </ul>
        
        <h2>How to Get Started with {topic}</h2>
        <p>Getting started with {topic} is easier than you might think. Here are some practical steps:</p>
        <ol>
            <li>Research and gather information</li>
            <li>Practice and apply what you learn</li>
            <li>Seek guidance from experts</li>
        </ol>
        
        <h2>Common Challenges and Solutions</h2>
        <p>When working with {topic}, you might encounter some challenges. Here are common issues and their solutions:</p>
        <p>Challenge 1: Understanding complex concepts<br>
        Solution: Break down information into smaller, manageable parts.</p>
        
        <h2>Conclusion</h2>
        <p>In conclusion, {topic} is a valuable subject that can provide significant benefits. By following the guidelines in this article, you'll be well on your way to mastering this topic.</p>
        """
        
        return {
            "title": title,
            "content_html": content,
            "meta_title": f"{title} - Complete Guide",
            "meta_description": f"Learn everything about {topic} with our comprehensive guide. Get expert tips and practical advice.",
            "faq_schema": json.dumps({
                "@context": "https://schema.org",
                "@type": "FAQPage",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": f"What is {topic}?",
                        "acceptedAnswer": {
                            "@type": "Answer",
                            "text": f"{topic} is an important subject that provides valuable knowledge and skills."
                        }
                    }
                ]
            }),
            "featured_image_url": None
        }
    
    async def _send_to_wordpress(self, site: Site, job_id: int, article_data: dict) -> bool:
        """Send article to WordPress via webhook."""
        try:
            # Create HMAC signature
            signature = create_hmac_signature(site.site_secret, json.dumps(article_data))
            
            # WordPress webhook URL (this would be configured in the plugin)
            webhook_url = f"https://{site.domain}/wp-json/aiwriter/v1/publish"
            
            payload = {
                "site_id": site.id,
                "job_id": job_id,
                "article_data": article_data,
                "signature": signature
            }
            
            print(f"[ARTICLE_GENERATOR] Sending to WordPress: {webhook_url}")
            
            response = requests.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                print(f"[ARTICLE_GENERATOR] WordPress response: {response.json()}")
                return True
            else:
                print(f"[ARTICLE_GENERATOR] WordPress error: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"[ARTICLE_GENERATOR] Error sending to WordPress: {str(e)}")
            return False
