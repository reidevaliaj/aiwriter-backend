#!/usr/bin/env python3
"""
Test OpenAI API parameters compatibility.
"""
import os
import sys
import asyncio

# Add the backend directory to Python path
sys.path.append('/home/rei/apps/aiwriter-backend')

async def test_openai_params():
    """Test OpenAI API with correct parameters."""
    print("=== OpenAI API Parameters Test ===")
    
    try:
        from aiwriter_backend.core.openai_client import run_text
        
        # Test with GPT-4o (should use max_completion_tokens)
        print("Testing GPT-4o with max_completion_tokens...")
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Write a short paragraph about camping."}
        ]
        
        response = await run_text(messages)
        print(f"✅ GPT-4o response: {response[:100]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ OpenAI API test failed: {e}")
        return False

async def test_image_generation():
    """Test DALL-E image generation."""
    print("\n=== DALL-E Image Generation Test ===")
    
    try:
        from aiwriter_backend.core.openai_client import gen_image
        
        print("Testing DALL-E 3 image generation...")
        image_url = await gen_image("A simple camping tent in a forest")
        print(f"✅ DALL-E 3 image generated: {image_url}")
        
        return True
        
    except Exception as e:
        print(f"❌ DALL-E test failed: {e}")
        return False

async def main():
    """Run all tests."""
    print("OpenAI API Parameters Compatibility Test")
    print("=" * 50)
    
    # Check environment
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ OPENAI_API_KEY not set")
        return
    
    print(f"✅ OPENAI_API_KEY is set")
    print(f"Model: {os.getenv('OPENAI_TEXT_MODEL', 'gpt-4o')}")
    print(f"Image Model: {os.getenv('OPENAI_IMAGE_MODEL', 'dall-e-3')}")
    
    # Test text generation
    text_test = await test_openai_params()
    
    # Test image generation
    image_test = await test_image_generation()
    
    print("\n=== Results ===")
    print(f"Text Generation: {'✅ PASS' if text_test else '❌ FAIL'}")
    print(f"Image Generation: {'✅ PASS' if image_test else '❌ FAIL'}")
    
    if text_test and image_test:
        print("\n🎉 All tests passed! OpenAI API should work now.")
    else:
        print("\n⚠️ Some tests failed. Check the errors above.")

if __name__ == "__main__":
    asyncio.run(main())
