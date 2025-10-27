#!/usr/bin/env python3
"""
Debug script to check Phase 3 issues on VPS.
"""
import os
import sys
import asyncio
from sqlalchemy.orm import Session

# Add the backend directory to Python path
sys.path.append('/home/rei/apps/aiwriter-backend')

def check_environment():
    """Check environment variables."""
    print("=== Environment Check ===")
    print(f"OPENAI_API_KEY: {'SET' if os.getenv('OPENAI_API_KEY') else 'NOT SET'}")
    print(f"OPENAI_TEXT_MODEL: {os.getenv('OPENAI_TEXT_MODEL', 'NOT SET')}")
    print(f"OPENAI_IMAGE_MODEL: {os.getenv('OPENAI_IMAGE_MODEL', 'NOT SET')}")
    
    if not os.getenv('OPENAI_API_KEY'):
        print("❌ OPENAI_API_KEY is not set!")
        return False
    
    print("✅ Environment looks good")
    return True

def check_imports():
    """Check if all imports work."""
    print("\n=== Import Check ===")
    
    try:
        from aiwriter_backend.core.openai_client import get_openai
        print("✅ OpenAI client import OK")
    except Exception as e:
        print(f"❌ OpenAI client import failed: {e}")
        return False
    
    try:
        from aiwriter_backend.services.article_generator import ArticleGenerator
        print("✅ ArticleGenerator import OK")
    except Exception as e:
        print(f"❌ ArticleGenerator import failed: {e}")
        return False
    
    try:
        from aiwriter_backend.db.session import get_db
        print("✅ Database session import OK")
    except Exception as e:
        print(f"❌ Database session import failed: {e}")
        return False
    
    return True

def check_database():
    """Check database connection and schema."""
    print("\n=== Database Check ===")
    
    try:
        db = next(get_db())
        
        # Check if articles table exists
        from aiwriter_backend.db.base import Article, Job
        article_count = db.query(Article).count()
        job_count = db.query(Job).count()
        
        print(f"✅ Database connection OK")
        print(f"✅ Articles table exists: {article_count} articles")
        print(f"✅ Jobs table exists: {job_count} jobs")
        
        # Check latest job
        latest_job = db.query(Job).order_by(Job.id.desc()).first()
        if latest_job:
            print(f"✅ Latest job: ID {latest_job.id}, Status: {latest_job.status}, Topic: {latest_job.topic}")
        
        return True
        
    except Exception as e:
        print(f"❌ Database check failed: {e}")
        return False

async def test_openai_client():
    """Test OpenAI client."""
    print("\n=== OpenAI Client Test ===")
    
    try:
        from aiwriter_backend.core.openai_client import get_openai, run_text
        
        client = get_openai()
        print("✅ OpenAI client created")
        
        # Test with a simple message
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say 'Hello World'"}
        ]
        
        response = await run_text(messages)
        print(f"✅ OpenAI response: {response[:50]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ OpenAI client test failed: {e}")
        return False

async def test_article_generation():
    """Test article generation with latest job."""
    print("\n=== Article Generation Test ===")
    
    try:
        from aiwriter_backend.db.session import get_db
        from aiwriter_backend.db.base import Job, Article
        from aiwriter_backend.services.article_generator import ArticleGenerator
        
        db = next(get_db())
        
        # Find the latest pending job
        latest_job = db.query(Job).filter(Job.status == "pending").order_by(Job.id.desc()).first()
        
        if not latest_job:
            print("❌ No pending jobs found")
            return False
        
        print(f"✅ Found pending job: ID {latest_job.id}, Topic: {latest_job.topic}")
        
        # Try to generate article
        generator = ArticleGenerator(db)
        success = await generator.generate_article(latest_job.id)
        
        if success:
            print("✅ Article generation successful!")
            
            # Check if article was created
            article = db.query(Article).filter(Article.job_id == latest_job.id).first()
            if article:
                print(f"✅ Article created: ID {article.id}, Status: {article.status}")
                print(f"✅ HTML length: {len(article.article_html or '')}")
            else:
                print("❌ No article found after generation")
        else:
            print("❌ Article generation failed")
        
        return success
        
    except Exception as e:
        print(f"❌ Article generation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all checks."""
    print("Phase 3 VPS Debug Script")
    print("=" * 50)
    
    # Run checks
    env_ok = check_environment()
    imports_ok = check_imports()
    db_ok = check_database()
    
    if not (env_ok and imports_ok and db_ok):
        print("\n❌ Basic checks failed. Fix these issues first.")
        return
    
    # Test OpenAI
    openai_ok = await test_openai_client()
    
    if not openai_ok:
        print("\n❌ OpenAI test failed. Check API key and network.")
        return
    
    # Test article generation
    generation_ok = await test_article_generation()
    
    print("\n=== Summary ===")
    print(f"Environment: {'✅' if env_ok else '❌'}")
    print(f"Imports: {'✅' if imports_ok else '❌'}")
    print(f"Database: {'✅' if db_ok else '❌'}")
    print(f"OpenAI: {'✅' if openai_ok else '❌'}")
    print(f"Generation: {'✅' if generation_ok else '❌'}")
    
    if all([env_ok, imports_ok, db_ok, openai_ok, generation_ok]):
        print("\n🎉 All tests passed! Phase 3 should be working.")
    else:
        print("\n⚠️ Some tests failed. Check the errors above.")

if __name__ == "__main__":
    asyncio.run(main())
