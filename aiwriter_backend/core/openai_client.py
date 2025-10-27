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
    
    # Use correct token parameter based on model
    if settings.OPENAI_TEXT_MODEL == "gpt-5":
        # GPT-5 uses max_completion_tokens and supports new parameters
        options["max_completion_tokens"] = settings.OPENAI_MAX_TOKENS_TEXT
        options["verbosity"] = "minimal"  # GPT-5 specific parameter
        options["reasoning_effort"] = "medium"  # GPT-5 specific parameter
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
        
    except ValueError:
        # Retry with JSON-only prompt
        logger.info(f"Retrying with JSON-only prompt for {context}")
        
        retry_messages = messages + [
            {
                "role": "user",
                "content": "Return valid JSON only. No commentary."
            }
        ]
        
        content = await run_text(retry_messages)
        return validate_json_response(content, f"{context} (retry)")
