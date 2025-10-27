"""
Article generation service with OpenAI integration.
"""
import json
import logging
import re
from typing import Dict, List, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from aiwriter_backend.db.base import Job, Article, ArticleStatus, Site, License
from aiwriter_backend.core.openai_client import run_text, gen_image, retry_with_json_prompt
from aiwriter_backend.services.webhook_service import WebhookService

logger = logging.getLogger(__name__)

# German SEO system prompt
SYSTEM_PROMPT_DE = (
    "Du bist ein deutscher SEO-Redakteur. Schreibe faktenbasierte, klare Artikel in professionellem Ton. "
    "Verwende H2/H3-Überschriften, kurze Absätze (max. 120 Wörter) und Listen, wenn sinnvoll. "
    "Vermeide Wiederholungen und übertriebene Sprache. Antworte ausschließlich in HTML, ohne Markdown."
)


class ArticleGenerator:
    """Real OpenAI-powered article generator."""
    
    def __init__(self, db: Session):
        self.db = db
        self.webhook_service = WebhookService(db)
    
    async def generate_article(self, job_id: int) -> bool:
        """
        Generate a complete article using OpenAI.
        
        Args:
            job_id: Job ID to process
            
        Returns:
            True if successful, False otherwise
        """
        try:
            print(f"[ARTICLE_GENERATOR] Starting article generation for job {job_id}")
            
            # Check OpenAI API key
            from aiwriter_backend.core.config import settings
            if not settings.OPENAI_API_KEY:
                print(f"[ARTICLE_GENERATOR] ERROR: OpenAI API key not set")
                return False
            
            print(f"[ARTICLE_GENERATOR] OpenAI API key is set, using model: {settings.OPENAI_TEXT_MODEL}")
            
            # Get job and related data
            job = self.db.query(Job).filter(Job.id == job_id).first()
            if not job:
                logger.error(f"Job {job_id} not found")
                return False
            
            site = self.db.query(Site).filter(Site.id == job.site_id).first()
            if not site:
                logger.error(f"Site for job {job_id} not found")
                return False
            
            license_obj = self.db.query(License).filter(License.id == site.license_id).first()
            if not license_obj:
                logger.error(f"License for job {job_id} not found")
                return False
            
            logger.info(f"Starting article generation for job {job_id}: {job.topic}")
            
            # Update job status
            job.status = "processing"
            self.db.commit()
            
            # Create article record
            article = Article(
                job_id=job_id,
                license_id=license_obj.id,
                topic=job.topic,
                language=job.language or "de",
                status=ArticleStatus.DRAFT
            )
            self.db.add(article)
            self.db.commit()
            self.db.refresh(article)
            
            # Generate article components
            context = {
                "topic": job.topic,
                "length": job.length,
                "language": job.language or "de",
                "article_id": article.id
            }
            
            # Step 1: Create outline
            logger.info(f"Creating outline for article {article.id}")
            outline = await self.create_outline(**context)
            article.outline_json = outline
            
            # Step 2: Write sections
            logger.info(f"Writing sections for article {article.id}")
            sections_html = await self.write_sections(outline, **context)
            
            # Step 3: Write intro and conclusion
            logger.info(f"Writing intro/conclusion for article {article.id}")
            intro_html = await self.write_intro_and_conclusion(outline, **context)
            
            # Step 4: Generate FAQ
            logger.info(f"Generating FAQ for article {article.id}")
            faq_data = await self.generate_faq(outline, **context)
            article.faq_json = faq_data
            
            # Step 5: Generate meta
            logger.info(f"Generating meta for article {article.id}")
            meta_data = await self.generate_meta(outline, **context)
            article.meta_title = meta_data["title"]
            article.meta_description = meta_data["description"]
            
            # Step 6: Generate schema
            logger.info(f"Generating schema for article {article.id}")
            schema_data = await self.generate_schema(outline, faq_data, **context)
            article.schema_json = schema_data
            
            # Step 7: Assemble HTML
            logger.info(f"Assembling HTML for article {article.id}")
            full_html = await self.assemble_html(intro_html, sections_html, **context)
            article.article_html = full_html
            
            # Step 8: Generate images (if requested)
            if job.requested_images and job.requested_images > 0:
                logger.info(f"Generating {job.requested_images} images for article {article.id}")
                image_urls = await self.generate_images(job.topic, job.requested_images)
                article.image_urls_json = image_urls
                # Calculate image cost (assuming $0.04 per image for DALL-E 3)
                article.image_cost_cents = len(image_urls) * 4
            
            # Update article status
            article.status = ArticleStatus.READY
            article.updated_at = datetime.utcnow()
            
            # Update job status
            job.status = "completed"
            job.finished_at = datetime.utcnow()
            
            self.db.commit()
            
            logger.info(f"Article {article.id} generated successfully")
            
            # Send to WordPress
            await self.webhook_service.send_article_to_wordpress(article.id)
            
            return True
            
        except Exception as e:
            logger.error(f"Article generation failed for job {job_id}: {str(e)}")
            
            # Update job status
            job = self.db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = "failed"
                job.error = str(e)
                job.finished_at = datetime.utcnow()
                self.db.commit()
            
            # Update article status if it exists
            article = self.db.query(Article).filter(Article.job_id == job_id).first()
            if article:
                article.status = ArticleStatus.FAILED
                article.updated_at = datetime.utcnow()
                self.db.commit()
            
            return False
    
    async def create_outline(self, topic: str, length: str, language: str, **kwargs) -> Dict[str, Any]:
        """Create article outline with H2/H3 structure."""
        length_guidance = {
            "short": "3-4 H2 sections",
            "medium": "5-6 H2 sections", 
            "long": "7-8 H2 sections"
        }
        
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT_DE},
            {
                "role": "user", 
                "content": f"""Erstelle eine detaillierte Gliederung für einen Artikel zum Thema "{topic}".

Länge: {length_guidance.get(length, "5-6 H2 sections")}

Antworte mit einem JSON-Objekt:
{{
  "title": "Artikel-Titel",
  "sections": [
    {{
      "h2": "Hauptüberschrift",
      "h3s": ["Unterüberschrift 1", "Unterüberschrift 2"]
    }}
  ]
}}

Stelle sicher, dass die Gliederung SEO-optimiert und strukturiert ist."""
            }
        ]
        
        result = await retry_with_json_prompt(messages, "outline")
        return result
    
    async def write_sections(self, outline: Dict[str, Any], topic: str, length: str, language: str, **kwargs) -> str:
        """Write article sections based on outline."""
        sections_html = []
        
        for section in outline.get("sections", []):
            h2 = section.get("h2", "")
            h3s = section.get("h3s", [])
            
            # Generate content for this section
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT_DE},
                {
                    "role": "user",
                    "content": f"""Schreibe den Inhalt für den Abschnitt "{h2}" des Artikels zum Thema "{topic}".

Unterüberschriften: {', '.join(h3s) if h3s else 'Keine'}

Antworte in reinem HTML mit:
- <h2>{h2}</h2>
- <h3>Unterüberschrift</h3> für jede Unterüberschrift
- <p>Absätze</p> mit max. 120 Wörtern
- <ul><li>Listen</li></ul> oder <ol><li>Nummerierte Listen</li></ol> wenn sinnvoll

Verwende keine Inline-CSS oder andere Formatierung."""
                }
            ]
            
            content = await run_text(messages)
            sections_html.append(content)
        
        return "\n\n".join(sections_html)
    
    async def write_intro_and_conclusion(self, outline: Dict[str, Any], topic: str, length: str, language: str, **kwargs) -> str:
        """Write introduction and conclusion paragraphs."""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT_DE},
            {
                "role": "user",
                "content": f"""Schreibe eine Einleitung und einen Schluss für den Artikel zum Thema "{topic}".

Antworte in reinem HTML:
- <p>Einleitungsparagraph (max. 120 Wörter)</p>
- <p>Schlussparagraph (max. 120 Wörter)</p>

Die Einleitung soll das Thema einführen und den Leser fesseln.
Der Schluss soll die wichtigsten Punkte zusammenfassen."""
            }
        ]
        
        content = await run_text(messages)
        return content
    
    async def generate_faq(self, outline: Dict[str, Any], topic: str, length: str, language: str, **kwargs) -> List[Dict[str, str]]:
        """Generate FAQ questions and answers."""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT_DE},
            {
                "role": "user",
                "content": f"""Erstelle 3-5 häufig gestellte Fragen zum Thema "{topic}".

Antworte mit einem JSON-Array:
[
  {{"q": "Frage", "a": "Antwort (max. 80-100 Wörter)"}},
  {{"q": "Frage", "a": "Antwort (max. 80-100 Wörter)"}}
]

Die Fragen sollen relevant und die Antworten präzise sein."""
            }
        ]
        
        result = await retry_with_json_prompt(messages, "FAQ")
        return result
    
    async def generate_meta(self, outline: Dict[str, Any], topic: str, length: str, language: str, **kwargs) -> Dict[str, str]:
        """Generate meta title and description."""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT_DE},
            {
                "role": "user",
                "content": f"""Erstelle Meta-Titel und Meta-Beschreibung für den Artikel zum Thema "{topic}".

Antworte mit einem JSON-Objekt:
{{
  "title": "Meta-Titel (max. 60 Zeichen)",
  "description": "Meta-Beschreibung (max. 155 Zeichen)"
}}

Beide sollen SEO-optimiert und ansprechend sein."""
            }
        ]
        
        result = await retry_with_json_prompt(messages, "meta")
        return result
    
    async def generate_schema(self, outline: Dict[str, Any], faq_data: List[Dict[str, str]], topic: str, length: str, language: str, **kwargs) -> Dict[str, Any]:
        """Generate structured data schema."""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT_DE},
            {
                "role": "user",
                "content": f"""Erstelle strukturierte Daten (Schema.org) für den Artikel zum Thema "{topic}".

Antworte mit einem JSON-Objekt:
{{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "Artikel-Titel",
  "datePublished": "{datetime.now().isoformat()}",
  "inLanguage": "{language}",
  "mainEntityOfPage": {{
    "@type": "WebPage",
    "@id": "https://example.com/article"
  }},
  "author": {{
    "@type": "Organization",
    "name": "AIWriter"
  }},
  "publisher": {{
    "@type": "Organization",
    "name": "AIWriter"
  }}
}}

Falls FAQ vorhanden sind, füge auch ein FAQPage-Schema hinzu."""
            }
        ]
        
        result = await retry_with_json_prompt(messages, "schema")
        
        # Add FAQ schema if we have FAQ data
        if faq_data:
            faq_schema = {
                "@context": "https://schema.org",
                "@type": "FAQPage",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": item["q"],
                        "acceptedAnswer": {
                            "@type": "Answer",
                            "text": item["a"]
                        }
                    }
                    for item in faq_data
                ]
            }
            result["faq"] = faq_schema
        
        return result
    
    async def assemble_html(self, intro_html: str, sections_html: str, topic: str, length: str, language: str, **kwargs) -> str:
        """Assemble final HTML article."""
        # Combine intro, sections, and conclusion
        full_html = f"{intro_html}\n\n{sections_html}"
        
        # Clean up HTML
        full_html = self._clean_html(full_html)
        
        return full_html
    
    async def generate_images(self, topic: str, requested_images: int) -> List[str]:
        """Generate images for the article."""
        if requested_images <= 0:
            return []
        
        image_urls = []
        
        for i in range(requested_images):
            try:
                prompt = f"Sachliche, moderne Titelillustration zum Thema „{topic}“, flache Illustration, kein Text, neutraler Hintergrund."
                
                image_url = await gen_image(
                    prompt=prompt,
                    size="1024x1024",
                    quality="high"
                )
                
                image_urls.append(image_url)
                logger.info(f"Generated image {i+1}/{requested_images}: {image_url}")
                
            except Exception as e:
                logger.error(f"Image generation failed for image {i+1}: {str(e)}")
                # Continue with other images
                continue
        
        return image_urls
    
    def _clean_html(self, html: str) -> str:
        """Clean and sanitize HTML content."""
        # Remove any inline CSS
        html = re.sub(r'style="[^"]*"', '', html)
        
        # Ensure proper heading hierarchy
        html = re.sub(r'<h([1-6])>', lambda m: f'<h{int(m.group(1)) + 1}>', html)
        
        # Remove any risky tags
        risky_tags = ['script', 'iframe', 'object', 'embed']
        for tag in risky_tags:
            html = re.sub(f'<{tag}[^>]*>.*?</{tag}>', '', html, flags=re.IGNORECASE | re.DOTALL)
        
        return html.strip()