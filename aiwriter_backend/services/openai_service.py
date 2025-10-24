"""
OpenAI service for article generation.
"""
import openai
from typing import Dict, Any
from aiwriter_backend.core.config import settings


class OpenAIService:
    """Service for OpenAI API interactions."""
    
    def __init__(self):
        self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
    
    async def generate_article(self, topic: str, length: str = "medium") -> Dict[str, Any]:
        """Generate a complete article using OpenAI."""
        
        # System prompt for German SEO articles
        system_prompt = """Du bist ein deutscher SEO-Redakteur. Schreibe faktenbasierte, klare Artikel in professionellem Ton.
Verwende H2/H3-Überschriften, kurze Absätze (max. 120 Wörter) und Listen, wenn sinnvoll.
Vermeide Wiederholungen und übertriebene Sprache.

Struktur:
1. OUTLINE - Gliederung mit H2/H3-Überschriften
2. ARTICLE_HTML - Vollständiger HTML-Artikel
3. META - Meta-Title (≤60 Zeichen) und Meta-Description (≤155 Zeichen)
4. FAQ - 3-5 häufige Fragen mit präzisen Antworten
5. SCHEMA - JSON-LD Schema für FAQ"""

        user_prompt = f"""
Thema: {topic}
Ziel: Informationsartikel für Laien
Länge: {length}
Struktur: H2-Überschriften für Hauptpunkte, H3 für Details
"""

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=4000
            )
            
            content = response.choices[0].message.content
            return self._parse_article_content(content)
            
        except Exception as e:
            raise Exception(f"OpenAI API error: {str(e)}")
    
    def _parse_article_content(self, content: str) -> Dict[str, Any]:
        """Parse the generated content into structured format."""
        # This would parse the content into the required sections
        # For now, return a basic structure
        return {
            "outline": "Parsed outline",
            "html": content,
            "meta": {
                "title": "Generated title",
                "description": "Generated description"
            },
            "faq": [],
            "schema": {}
        }
