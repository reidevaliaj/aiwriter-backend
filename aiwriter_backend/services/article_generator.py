"""
Article generation service leveraging the gpt-4o JSON workflow from
`simple_article_cli.py`.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

from sqlalchemy.orm import Session

from aiwriter_backend.core.config import settings
from aiwriter_backend.core.openai_client import run_text, run_text_structured, gen_image
from aiwriter_backend.db.base import Article, ArticleStatus, Job, License, Site
from aiwriter_backend.services.webhook_service import WebhookService

logger = logging.getLogger(__name__)


ARTICLE_SYSTEM_PROMPT_DE = (
    "Du bist ein deutscher SEO-Redakteur. Der Artikel muss als sauberes HTML "
    "mit H2/H3-Struktur, kurzen Absätzen (≤120 Wörter) und sinnvollen Listen "
    "verfasst sein. Nutze einen professionellen Ton, verzichte auf "
    "übertriebene Sprache sowie Inline-CSS oder Skripte. Antworte "
    "ausschließlich als gültiges JSON-Objekt ohne zusätzliche Erklärungen."
)


ARTICLE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["article_html"],
    "properties": {
        "title": {"type": "string"},
        "article_html": {"type": "string"},
        "meta": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
            },
        },
        "faq": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["q", "a"],
                "properties": {
                    "q": {"type": "string"},
                    "a": {"type": "string"},
                },
            },
        },
        "schema": {"type": "object"},
    },
}


def _length_hint(length: str) -> str:
    mapping = {
        "short": "3–4 H2-Abschnitte, 600–800 Wörter",
        "medium": "5–6 H2-Abschnitte, 900–1.300 Wörter",
        "long": "7–8 H2-Abschnitte, 1.400–1.800 Wörter",
    }
    return mapping.get(length, mapping["medium"])


def _extract_first_heading(html: str) -> Optional[str]:
    if not isinstance(html, str):
        return None

    match = re.search(r"<h1[^>]*>(.*?)</h1>", html, flags=re.I | re.S)
    if not match:
        match = re.search(r"<h2[^>]*>(.*?)</h2>", html, flags=re.I | re.S)
    if not match:
        return None

    text = re.sub(r"<[^>]+>", "", match.group(1)).strip()
    return text or None


def _extract_outline(html: str) -> Dict[str, Any]:
    sections: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None

    for match in re.finditer(r"<(h[23])[^>]*>(.*?)</\1>", html, flags=re.I | re.S):
        level = match.group(1).lower()
        text = re.sub(r"<[^>]+>", "", match.group(2)).strip()
        if not text:
            continue

        if level == "h2":
            current = {"h2": text, "h3s": []}
            sections.append(current)
        elif level == "h3" and current is not None:
            current.setdefault("h3s", []).append(text)

    return {"sections": sections}


def _normalize_result(raw: Dict[str, Any], topic_fallback: str, language: str) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("Model did not return a JSON object.")

    candidate = raw
    for wrap in ("article", "result", "data", "payload", "content"):
        if isinstance(candidate.get(wrap), dict):
            candidate = candidate[wrap]
            break

    lower_map = {k.lower(): k for k in candidate.keys()}

    def get_ci(*names: str) -> Optional[Any]:
        for name in names:
            key = lower_map.get(name.lower())
            if key is not None:
                return candidate[key]
        return None

    title = get_ci("title", "titel", "headline")
    article_html = get_ci("article_html", "html", "content")

    if not isinstance(article_html, str) or not article_html.strip():
        raise ValueError("Missing or invalid 'article_html'.")

    if not title:
        title = _extract_first_heading(article_html) or topic_fallback

    meta_obj = get_ci("meta", "metadata")
    if not isinstance(meta_obj, dict):
        meta_obj = {}

    meta_title = meta_obj.get("title") or title[:60]
    meta_description = meta_obj.get("description") or f"Erfahren Sie alles über {title}."
    meta = {"title": meta_title[:60], "description": meta_description[:155]}

    faq = get_ci("faq", "faqs")
    if not isinstance(faq, list):
        faq = []  # Will be set to empty if include_faq=False

    schema = get_ci("schema", "jsonld")
    if not isinstance(schema, dict):
        schema = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": title,
            "datePublished": datetime.now(timezone.utc).isoformat(),
            "inLanguage": language,
        }

    outline = _extract_outline(article_html)

    return {
        "title": title,
        "article_html": article_html,
        "meta": meta,
        "faq": faq,
        "schema": schema,
        "outline": outline,
    }


def _build_messages(topic: str, language: str, length: str, context: str = None, include_faq: bool = True) -> List[Dict[str, str]]:
    guidance = _length_hint(length)
    published = datetime.now(timezone.utc).isoformat()
    
    context_section = ""
    if context and context.strip():
        context_section = f"\nZusätzlicher Kontext: {context.strip()}"

    faq_section = ""
    if include_faq:
        faq_section = ',\n  "faq": [\n    {{"q": "string", "a": "string (80–100 Wörter)"}}\n  ]'

    user_prompt = f"""
Sprache: {language}
Thema: {topic}
Länge: {guidance}{context_section}

Gib diese Struktur zurück:
{{
  "title": "string",
  "article_html": "string (vollständiges HTML mit <h2>/<h3>, <p>, <ul>/<ol>)",
  "meta": {{
    "title": "string (≤60 Zeichen)",
    "description": "string (≤155 Zeichen)"
  }}{faq_section},
  "schema": {{
    "@context": "https://schema.org",
    "@type": "Article",
    "headline": "string",
    "datePublished": "{published}",
    "inLanguage": "{language}"
  }}
}}
Regeln:
- Meta-Title ≤ 60 Zeichen, Meta-Description ≤ 155 Zeichen.
{"- FAQ-Einträge: 3–5 Einträge." if include_faq else "- Keine FAQ erforderlich."}
- Kein Markdown, keine Codeblöcke, nur JSON-Inhalt.
"""

    return [
        {"role": "system", "content": ARTICLE_SYSTEM_PROMPT_DE},
        {"role": "user", "content": user_prompt},
    ]


async def get_image_topic_from_openai(topic: str) -> str:
    """Derive a short descriptive phrase for image search."""
    messages = [
        {
            "role": "system",
            "content": (
                "You are a content assistant. Given an article topic, respond with a short, "
                "descriptive phrase that best represents a good photo for this topic. Respond with only the phrase."
            ),
        },
        {"role": "user", "content": topic},
    ]

    try:
        response = await run_text(
            messages,
            model="gpt-4o",
            temperature=0.4,
            max_completion_tokens=48,
        )
        return response.strip().strip('"').strip("'")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Falling back to original topic for image", extra={"topic": topic, "error": str(exc)})
        return topic


def get_image_from_pexels(keyword: str) -> Optional[str]:
    """Fetch a representative image URL from Pexels."""
    api_key = "36l3lUAEJNu26bMbOrvXxplQPn8HffWIViMvjdTOcVqL7HNeMkfyrvvz"
    url = "https://api.pexels.com/v1/search"
    params = {"query": keyword, "per_page": 1}
    headers = {"Authorization": api_key}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code != 200:
            logger.warning(
                "Pexels request failed",
                extra={"keyword": keyword, "status": response.status_code, "body": response.text[:200]},
            )
            return None

        data = response.json()
        photos = data.get("photos") or []
        if not photos:
            logger.info("Pexels returned no photos", extra={"keyword": keyword})
            return None

        src = photos[0].get("src", {})
        return src.get("large") or src.get("medium") or src.get("original")

    except Exception as exc:  # noqa: BLE001
        logger.warning("Error fetching image from Pexels", extra={"keyword": keyword, "error": str(exc)})
        return None


class ArticleGenerator:
    """OpenAI-powered generator aligned with `simple_article_cli.py`."""

    def __init__(self, db: Session):
        self.db = db
        self.webhook_service = WebhookService(db)

    async def generate_article(self, job_id: int) -> bool:
        try:
            logger.info("[ARTICLE_GENERATOR] Starting article generation", extra={"job_id": job_id})

            if not settings.OPENAI_API_KEY:
                logger.error("OpenAI API key not configured")
                return False

            job = self.db.query(Job).filter(Job.id == job_id).first()
            if not job:
                logger.error("Job not found", extra={"job_id": job_id})
                return False

            site = self.db.query(Site).filter(Site.id == job.site_id).first()
            if not site:
                logger.error("Site not found for job", extra={"job_id": job_id})
                return False

            license_obj = self.db.query(License).filter(License.id == site.license_id).first()
            if not license_obj:
                logger.error("License not found for job", extra={"job_id": job_id})
                return False

            job.status = "processing"
            self.db.commit()

            article = Article(
                job_id=job.id,
                license_id=license_obj.id,
                topic=job.topic,
                language=job.language or "de",
                status=ArticleStatus.DRAFT,
            )
            self.db.add(article)
            self.db.commit()
            self.db.refresh(article)

            payload = await self._generate_payload(
                topic=job.topic,
                language=job.language or "de",
                length=job.length or "medium",
                context=job.context,
                include_faq=job.include_faq,
            )

            article.topic = payload["title"]
            article.article_html = payload["article_html"]
            article.meta_title = payload["meta"]["title"]
            article.meta_description = payload["meta"]["description"]
            # Only include FAQ if requested
            if job.include_faq:
                article.faq_json = payload["faq"]
            else:
                article.faq_json = []
            
            article.schema_json = payload["schema"]
            article.outline_json = payload.get("outline")
            
            # Add CTA to article HTML if requested
            if job.include_cta and job.cta_url:
                cta_html = f'<div class="aiwriter-cta" style="margin: 30px 0; padding: 20px; background: #f5f5f5; border-radius: 5px; text-align: center;"><a href="{job.cta_url}" class="button" style="display: inline-block; padding: 12px 24px; background: #0073aa; color: white; text-decoration: none; border-radius: 3px;">Jetzt kontaktieren</a></div>'
                payload["article_html"] = payload["article_html"] + "\n\n" + cta_html
            
            # Store category and tags (passed from job)
            if job.template:
                try:
                    payload["category"] = int(job.template)
                except (ValueError, TypeError):
                    payload["category"] = None
            else:
                payload["category"] = None
            
            payload["tags"] = job.style_preset if job.style_preset else None

            # Handle images: user-provided OR AI-generated
            image_urls: List[str] = []
            
            # First, use user-provided images if available
            if job.user_images and isinstance(job.user_images, list) and len(job.user_images) > 0:
                image_urls = job.user_images
                article.image_urls_json = image_urls
                article.image_cost_cents = 0  # User images are free
                logger.info(f"Using {len(image_urls)} user-provided images", extra={"job_id": job_id})
            # Otherwise, generate AI images if requested
            elif job.images and job.requested_images and job.requested_images > 0:
                image_urls = await self.generate_images(job.topic, job.requested_images)
                article.image_urls_json = image_urls
                article.image_cost_cents = len(image_urls) * 4
                logger.info(f"Generated {len(image_urls)} AI images", extra={"job_id": job_id})
            else:
                article.image_urls_json = []
                article.image_cost_cents = 0

            # Image handling logic:
            # - If 1 image: Set as featured only (not in content)
            # - If 2+ images: First as featured, remaining in content
            if len(image_urls) == 1:
                # Single image: featured only
                payload["featured_image"] = image_urls[0]
                payload["image_urls"] = []  # No images in content
                logger.info(f"Single image: set as featured only", extra={"job_id": job_id, "featured": image_urls[0]})
            elif len(image_urls) > 1:
                # Multiple images: first featured, rest in content
                featured = image_urls[0]
                content_images = image_urls[1:]  # Explicitly exclude first image
                payload["featured_image"] = featured
                payload["image_urls"] = content_images  # Only remaining images for content
                logger.info(
                    f"Multiple images: first as featured, {len(content_images)} in content",
                    extra={"job_id": job_id, "featured": featured, "content_images": content_images}
                )
            else:
                payload["featured_image"] = None
                payload["image_urls"] = []
                logger.info(f"No images", extra={"job_id": job_id})

            article.status = ArticleStatus.READY
            article.updated_at = datetime.now(timezone.utc)

            job.status = "completed"
            job.finished_at = datetime.now(timezone.utc)

            self.db.commit()

            logger.info(
                "[ARTICLE_GENERATOR] Article generated successfully",
                extra={"job_id": job_id, "article_id": article.id},
            )

            await self.webhook_service.send_article_to_wordpress(article.id, payload_override=payload)

            return True

        except Exception as exc:  # noqa: BLE001
            logger.exception("Article generation failed", extra={"job_id": job_id})
            self.db.rollback()

            job = self.db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = "failed"
                job.error = str(exc)
                job.finished_at = datetime.now(timezone.utc)
                self.db.commit()

            article = self.db.query(Article).filter(Article.job_id == job_id).first()
            if article:
                article.status = ArticleStatus.FAILED
                article.updated_at = datetime.now(timezone.utc)
                self.db.commit()

            return False

    async def _generate_payload(self, *, topic: str, language: str, length: str, context: str = None, include_faq: bool = True) -> Dict[str, Any]:
        messages = _build_messages(topic, language, length, context, include_faq)
        logger.info(
            "Calling OpenAI for article payload",
            extra={"model": settings.OPENAI_TEXT_MODEL, "topic": topic},
        )

        raw = await run_text_structured(
            messages,
            ARTICLE_SCHEMA,
            model=settings.OPENAI_TEXT_MODEL,
            temperature=settings.OPENAI_TEMPERATURE,
            max_completion_tokens=settings.OPENAI_MAX_TOKENS_TEXT,
        )

        payload = _normalize_result(raw, topic, language)
        logger.info("Article payload normalized", extra={"topic": topic})
        return payload

    async def generate_images(self, topic: str, requested_images: int) -> List[str]:
        if requested_images <= 0:
            return []

        urls: List[str] = []

        image_topic = await get_image_topic_from_openai(topic)
        logger.info("Derived image topic", extra={"topic": topic, "image_topic": image_topic})

        pexels_url = await asyncio.to_thread(get_image_from_pexels, image_topic)
        if pexels_url:
            logger.info("Fetched image from Pexels", extra={"topic": topic, "image_topic": image_topic})
            urls.append(pexels_url)
            return urls[:1]

        prompt = (
            f"Sachliche, moderne Titelillustration zum Thema „{topic}“, flache "
            "Illustration, kein Text, neutraler Hintergrund."
        )

        try:
            url = await gen_image(prompt=prompt, size="1024x1024", quality="high")
            if url:
                urls.append(url)
                logger.info("Generated fallback image with OpenAI", extra={"topic": topic})
            else:
                logger.warning("OpenAI image generation returned no URL", extra={"topic": topic})
        except Exception as image_error:  # noqa: BLE001
            logger.warning(
                "Image generation failed after Pexels fallback",
                extra={"topic": topic, "error": str(image_error)},
            )

        return urls[:1]

