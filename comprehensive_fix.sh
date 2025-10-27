#!/bin/bash

# Comprehensive fix for AIWriter timeout and JSON parsing issues
# This script fixes both the missing webhook method and GPT-5 JSON parsing problems

echo "🔧 Applying comprehensive AIWriter fixes..."

# 1. Update Nginx configuration for longer timeouts
echo "📝 Updating Nginx configuration..."
sudo tee /etc/nginx/sites-available/aiwriter > /dev/null << 'EOF'
server {
    listen 80 default_server;
    server_name _;

    # Increase proxy timeouts for AI requests
    proxy_connect_timeout 300s;
    proxy_send_timeout 300s;
    proxy_read_timeout 300s;

    # Increase client timeouts
    client_body_timeout 300s;
    client_header_timeout 300s;

    # Increase keepalive timeout
    keepalive_timeout 300s;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

# 2. Test Nginx configuration
echo "🧪 Testing Nginx configuration..."
sudo nginx -t

if [ $? -eq 0 ]; then
    echo "✅ Nginx configuration is valid"
    # Reload Nginx
    sudo systemctl reload nginx
    echo "🔄 Nginx reloaded with new timeout settings"
else
    echo "❌ Nginx configuration error"
    exit 1
fi

# 3. Update the backend code
echo "📦 Updating backend code..."
cd /home/rei/apps/aiwriter-backend

# Backup current files
cp aiwriter_backend/core/openai_client.py aiwriter_backend/core/openai_client.py.backup
cp aiwriter_backend/services/webhook_service.py aiwriter_backend/services/webhook_service.py.backup

# Update webhook service with missing method
echo "🔗 Fixing WebhookService..."
cat > aiwriter_backend/services/webhook_service.py << 'EOF'
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
EOF

# Update OpenAI client with improved JSON parsing
echo "🤖 Fixing OpenAI client JSON parsing..."
cat > aiwriter_backend/core/openai_client.py << 'EOF'
"""
OpenAI client singleton and helper functions.
"""
import json
import logging
from typing import List, Dict, Any, Optional
from openai import OpenAI
from .config import settings

logger = logging.getLogger(__name__)

# Singleton instance
_openai_client: Optional[OpenAI] = None


def get_openai() -> OpenAI:
    """Get OpenAI client singleton."""
    global _openai_client
    
    if _openai_client is None:
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required but not set")
        
        # Initialize OpenAI client with compatibility check
        try:
            _openai_client = OpenAI(
                api_key=settings.OPENAI_API_KEY,
                timeout=settings.OPENAI_TIMEOUT_S
            )
        except TypeError as e:
            if "unexpected keyword argument" in str(e):
                # Fallback for older OpenAI SDK versions
                logger.warning("Using fallback OpenAI client initialization (older SDK version)")
                _openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
            else:
                raise
        logger.info(f"OpenAI client initialized with model: {settings.OPENAI_TEXT_MODEL}")
    
    return _openai_client


async def run_text(messages: List[Dict[str, str]], **opts) -> str:
    """
    Generate text using OpenAI chat completions.
    
    Args:
        messages: List of message dicts with 'role' and 'content'
        **opts: Additional options (model, temperature, max_tokens, etc.)
    
    Returns:
        Generated text content
    """
    client = get_openai()
    
    # Default options with compatibility for newer models
    options = {
        "model": settings.OPENAI_TEXT_MODEL,
        "temperature": settings.OPENAI_TEMPERATURE,
        "messages": messages
    }
    
    # Use correct parameters based on model
    if settings.OPENAI_TEXT_MODEL == "gpt-5":
        # GPT-5 uses max_completion_tokens and supports new parameters
        options["max_completion_tokens"] = settings.OPENAI_MAX_TOKENS_TEXT
        options["verbosity"] = "low"  # GPT-5 specific parameter
        options["reasoning_effort"] = "medium"  # GPT-5 specific parameter
        # Remove temperature for GPT-5 as it's not supported
        options.pop("temperature", None)
    elif settings.OPENAI_TEXT_MODEL in ["gpt-4o", "gpt-4o-mini"]:
        # GPT-4o models use max_completion_tokens
        options["max_completion_tokens"] = settings.OPENAI_MAX_TOKENS_TEXT
    else:
        # Older models use max_tokens
        options["max_tokens"] = settings.OPENAI_MAX_TOKENS_TEXT
    
    # Override with any provided options
    options.update(opts)
    
    try:
        logger.info(f"Calling OpenAI with model: {options['model']}")
        logger.info(f"Using token parameter: {'max_completion_tokens' if 'max_completion_tokens' in options else 'max_tokens'}")
        if settings.OPENAI_TEXT_MODEL == "gpt-5":
            logger.info(f"GPT-5 parameters: verbosity={options.get('verbosity')}, reasoning_effort={options.get('reasoning_effort')}")
            logger.info(f"GPT-5: temperature removed (not supported)")
        
        response = client.chat.completions.create(**options)
        
        content = response.choices[0].message.content
        logger.info(f"OpenAI response received, length: {len(content) if content else 0}")
        
        return content or ""
        
    except Exception as e:
        logger.error(f"OpenAI text generation failed: {str(e)}")
        raise


async def gen_image(prompt: str, size: str = "1024x1024", quality: str = "high") -> str:
    """
    Generate image using OpenAI DALL-E.
    
    Args:
        prompt: Image generation prompt
        size: Image size (1024x1024, 1792x1024, 1024x1792)
        quality: Image quality (standard, hd)
    
    Returns:
        Image URL
    """
    client = get_openai()
    
    try:
        logger.info(f"Generating image with prompt: {prompt[:100]}...")
        response = client.images.generate(
            model=settings.OPENAI_IMAGE_MODEL,
            prompt=prompt,
            size=size,
            quality=quality,
            n=1
        )
        
        image_url = response.data[0].url
        logger.info(f"Image generated successfully: {image_url}")
        
        return image_url
        
    except Exception as e:
        logger.error(f"OpenAI image generation failed: {str(e)}")
        raise


def validate_json_response(content: str, context: str = "") -> Dict[str, Any]:
    """
    Validate and parse JSON response from OpenAI.
    
    Args:
        content: Raw content from OpenAI
        context: Context for error messages
    
    Returns:
        Parsed JSON dict
    
    Raises:
        ValueError: If JSON is invalid
    """
    try:
        # Try to find JSON in the content
        content = content.strip()
        
        # Look for JSON block markers
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            if end != -1:
                content = content[start:end].strip()
        elif "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            if end != -1:
                content = content[start:end].strip()
        elif "<pre>" in content:
            # Handle <pre> tags (GPT-5 sometimes uses these)
            start = content.find("<pre>") + 5
            end = content.find("</pre>", start)
            if end != -1:
                content = content[start:end].strip()
        
        # Clean up any remaining HTML tags or extra whitespace
        content = content.replace('<pre>', '').replace('</pre>', '').strip()
        
        # Remove any leading/trailing whitespace and newlines
        content = content.strip()
        
        # If content is empty after cleaning, raise an error
        if not content:
            raise ValueError(f"Empty content after cleaning for {context}")
        
        # Try to find JSON object boundaries if content is malformed
        if not content.startswith('{') and not content.startswith('['):
            # Look for first { or [
            start_idx = max(content.find('{'), content.find('['))
            if start_idx != -1:
                content = content[start_idx:]
        
        # Try to find the end of the JSON object
        if content.startswith('{'):
            # Count braces to find the end
            brace_count = 0
            end_idx = -1
            for i, char in enumerate(content):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i + 1
                        break
            if end_idx != -1:
                content = content[:end_idx]
        
        # Parse JSON
        result = json.loads(content)
        logger.info(f"JSON validation successful for {context}")
        return result
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON validation failed for {context}: {str(e)}")
        logger.error(f"Content: {content[:200]}...")
        raise ValueError(f"Invalid JSON response for {context}: {str(e)}")


async def retry_with_json_prompt(messages: List[Dict[str, str]], context: str = "") -> Dict[str, Any]:
    """
    Retry OpenAI call with JSON-only prompt if first attempt fails.
    
    Args:
        messages: Original messages
        context: Context for error messages
    
    Returns:
        Parsed JSON dict
    """
    try:
        # First attempt
        content = await run_text(messages)
        return validate_json_response(content, context)
        
    except ValueError as e:
        # Retry with JSON-only prompt
        logger.info(f"Retrying with JSON-only prompt for {context}: {str(e)}")
        
        retry_messages = messages + [
            {
                "role": "user",
                "content": "Return valid JSON only. No commentary, no HTML tags, no explanations. Just the JSON object."
            }
        ]
        
        try:
            content = await run_text(retry_messages)
            return validate_json_response(content, f"{context} (retry)")
        except Exception as retry_error:
            logger.error(f"Retry failed for {context}: {str(retry_error)}")
            
            # Final attempt with even more explicit instructions
            logger.info(f"Final attempt with explicit JSON instructions for {context}")
            final_messages = [
                {
                    "role": "system",
                    "content": "You must respond with valid JSON only. No text before or after the JSON. No explanations. No HTML tags. Just the JSON object."
                },
                {
                    "role": "user",
                    "content": "Return valid JSON only. No commentary, no HTML tags, no explanations. Just the JSON object."
                }
            ]
            
            try:
                content = await run_text(final_messages)
                return validate_json_response(content, f"{context} (final)")
            except Exception as final_error:
                logger.error(f"Final attempt failed for {context}: {str(final_error)}")
                raise ValueError(f"Failed to get valid JSON for {context} after all attempts: {str(final_error)}")
EOF

# 4. Restart the backend service
echo "🔄 Restarting backend service..."
sudo systemctl restart aiwriter

# 5. Check service status
echo "📊 Checking service status..."
sleep 3
sudo systemctl status aiwriter --no-pager

echo ""
echo "✅ Comprehensive fixes applied successfully!"
echo ""
echo "🔍 What was fixed:"
echo "1. ✅ Nginx timeout increased from 60s to 300s (5 minutes)"
echo "2. ✅ Added missing send_article_to_wordpress method to WebhookService"
echo "3. ✅ Improved JSON parsing for GPT-5 responses"
echo "4. ✅ Added 3-tier retry logic for JSON parsing"
echo "5. ✅ Better handling of malformed JSON responses"
echo "6. ✅ Enhanced error handling and logging"
echo ""
echo "🧪 Test the fix by generating an article from WordPress!"
echo "📝 Monitor logs with: sudo journalctl -u aiwriter -f"
echo ""
echo "🎯 Expected results:"
echo "- No more 'WebhookService' object has no attribute 'send_article_to_wordpress' errors"
echo "- Better JSON parsing success rate"
echo "- Articles should be generated and sent to WordPress successfully"
