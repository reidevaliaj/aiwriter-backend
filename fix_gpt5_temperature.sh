#!/bin/bash

# Quick fix for GPT-5 temperature parameter issue
echo "🔧 Fixing GPT-5 temperature parameter..."

cd /home/rei/apps/aiwriter-backend

# Backup current files
cp aiwriter_backend/core/config.py aiwriter_backend/core/config.py.backup.temp
cp aiwriter_backend/core/openai_client.py aiwriter_backend/core/openai_client.py.backup.temp

echo "✅ Backups created"

# Fix config.py - set temperature to 1.0 for GPT-5
echo "🔧 Updating config.py..."
sed -i 's/OPENAI_TEMPERATURE: float = 0.4/OPENAI_TEMPERATURE: float = 1.0/' aiwriter_backend/core/config.py

# Fix openai_client.py - remove temperature for GPT-5
echo "🔧 Updating openai_client.py..."
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


async def run_text_structured(messages: List[Dict[str, str]], schema: Dict[str, Any], **opts) -> Dict[str, Any]:
    """
    Generate structured JSON using OpenAI chat completions with JSON schema.
    
    Args:
        messages: List of message dicts with 'role' and 'content'
        schema: JSON schema for structured output
        **opts: Additional options (model, temperature, etc.)
    
    Returns:
        Parsed JSON dict
    """
    client = get_openai()
    
    # Default options with compatibility for newer models
    options = {
        "model": settings.OPENAI_TEXT_MODEL,
        "temperature": settings.OPENAI_TEMPERATURE,
        "messages": messages,
        "response_format": {"type": "json_object"}
    }
    
    # Use correct parameters based on model
    if settings.OPENAI_TEXT_MODEL == "gpt-5":
        # GPT-5 uses max_completion_tokens (never max_tokens)
        options["max_completion_tokens"] = settings.OPENAI_MAX_TOKENS_TEXT
        # GPT-5 only supports temperature=1 (default), remove temperature parameter
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
        logger.info(f"Calling OpenAI with structured JSON output for model: {options['model']}")
        
        response = client.chat.completions.create(**options)
        
        content = response.choices[0].message.content
        logger.info(f"OpenAI structured response received, length: {len(content) if content else 0}")
        
        # Parse JSON directly (no cleaning needed with structured output)
        result = json.loads(content)
        logger.info(f"Structured JSON parsing successful")
        return result
        
    except json.JSONDecodeError as e:
        logger.error(f"Structured JSON parsing failed: {str(e)}")
        logger.error(f"Content: {content[:200]}...")
        raise ValueError(f"Invalid structured JSON response: {str(e)}")
    except Exception as e:
        logger.error(f"OpenAI structured text generation failed: {str(e)}")
        raise


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
        # GPT-5 uses max_completion_tokens (never max_tokens)
        options["max_completion_tokens"] = settings.OPENAI_MAX_TOKENS_TEXT
        # GPT-5 only supports temperature=1 (default), remove temperature parameter
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
            logger.info(f"GPT-5 parameters: temperature removed (only supports default 1.0)")
        
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

echo "✅ OpenAI client updated with correct GPT-5 temperature handling"

# Restart the backend service
echo "🔄 Restarting backend service..."
sudo systemctl restart aiwriter

# Check service status
echo "📊 Checking service status..."
sleep 3
sudo systemctl status aiwriter --no-pager

echo ""
echo "✅ GPT-5 temperature fix deployed successfully!"
echo ""
echo "🔍 What was fixed:"
echo "- GPT-5 temperature parameter removed (only supports default 1.0)"
echo "- Config updated to use temperature 1.0"
echo "- OpenAI client updated to handle GPT-5 correctly"
echo ""
echo "🧪 Test article generation again - should work now!"
echo "📝 Monitor logs with: sudo journalctl -u aiwriter -f"
