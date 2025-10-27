#!/usr/bin/env python3
"""
Test script for Phase 3 AI Pipeline.
"""
import asyncio
import os
import sys
from sqlalchemy.orm import Session

# Add the backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from aiwriter_backend.db.session import get_db
from aiwriter_backend.services.article_generator import ArticleGenerator
from aiwriter_backend.core.config import settings

async def test_openai_client():
    """Test OpenAI client functionality."""
    print("=== Testing OpenAI Client ===")
    
    try:
        from aiwriter_backend.core.openai_client import get_openai, run_text, gen_image
        
        # Test text generation
        print("Testing text generation...")
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Write a short paragraph about AI."}
        ]
        
        response = await run_text(messages)
        print(f"Text response: {response[:100]}...")
        
        # Test image generation
        print("Testing image generation...")
        image_url = await gen_image("A simple test image")
        print(f"Image URL: {image_url}")
        
        print("✅ OpenAI client tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ OpenAI client test failed: {e}")
        return False

async def test_article_generator():
    """Test article generator with a mock job."""
    print("\n=== Testing Article Generator ===")
    
    try:
        # Get database session
        db = next(get_db())
        
        # Create a test job
        from aiwriter_backend.db.base import Job, Site, License, Plan
        
        # Check if we have test data
        site = db.query(Site).first()
        if not site:
            print("❌ No test site found. Please run setup_db.py first.")
            return False
        
        # Create a test job
        job = Job(
            site_id=site.id,
            topic="Test Article Topic",
            length="short",
            images=False,
            requested_images=0,
            language="de",
            status="pending"
        )
        
        db.add(job)
        db.commit()
        db.refresh(job)
        
        print(f"Created test job: {job.id}")
        
        # Test article generation
        generator = ArticleGenerator(db)
        success = await generator.generate_article(job.id)
        
        if success:
            print("✅ Article generation test passed!")
            
            # Check the generated article
            from aiwriter_backend.db.base import Article
            article = db.query(Article).filter(Article.job_id == job.id).first()
            if article:
                print(f"Article created: {article.id}")
                print(f"Status: {article.status}")
                print(f"HTML length: {len(article.article_html or '')}")
                print(f"Meta title: {article.meta_title}")
        else:
            print("❌ Article generation test failed!")
        
        # Clean up
        db.delete(job)
        if 'article' in locals():
            db.delete(article)
        db.commit()
        
        return success
        
    except Exception as e:
        print(f"❌ Article generator test failed: {e}")
        return False

async def main():
    """Run all tests."""
    print("Phase 3 AI Pipeline Test")
    print("=" * 50)
    
    # Check if OpenAI API key is set
    if not settings.OPENAI_API_KEY:
        print("❌ OPENAI_API_KEY not set in environment variables")
        print("Please set your OpenAI API key in the .env file")
        return
    
    print(f"Using OpenAI models:")
    print(f"- Text: {settings.OPENAI_TEXT_MODEL}")
    print(f"- Image: {settings.OPENAI_IMAGE_MODEL}")
    print(f"- Max tokens: {settings.OPENAI_MAX_TOKENS_TEXT}")
    print(f"- Temperature: {settings.OPENAI_TEMPERATURE}")
    
    # Run tests
    client_test = await test_openai_client()
    generator_test = await test_article_generator()
    
    print("\n=== Test Results ===")
    print(f"OpenAI Client: {'✅ PASS' if client_test else '❌ FAIL'}")
    print(f"Article Generator: {'✅ PASS' if generator_test else '❌ FAIL'}")
    
    if client_test and generator_test:
        print("\n🎉 All tests passed! Phase 3 AI Pipeline is working!")
    else:
        print("\n⚠️ Some tests failed. Check the errors above.")

if __name__ == "__main__":
    asyncio.run(main())
