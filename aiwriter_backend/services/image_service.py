"""
Image generation service.
"""
import openai
from typing import List, Optional
from aiwriter_backend.core.config import settings


class ImageService:
    """Service for AI image generation."""
    
    def __init__(self):
        self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
    
    async def generate_images(self, topic: str, count: int = 1) -> List[str]:
        """Generate images for an article topic."""
        
        prompt = f"Sachliche, moderne Titelillustration zum Thema „{topic}“, flache Illustration, kein Text, neutraler Hintergrund."
        
        try:
            response = await self.client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                n=count,
                size="1024x1024",
                quality="standard"
            )
            
            return [image.url for image in response.data]
            
        except Exception as e:
            raise Exception(f"Image generation error: {str(e)}")
    
    async def generate_featured_image(self, topic: str) -> Optional[str]:
        """Generate a featured image for an article."""
        images = await self.generate_images(topic, 1)
        return images[0] if images else None
