#!/usr/bin/env python3
"""
Fix Alembic revision chain by cleaning up duplicate entries in alembic_version table.
This script checks what migrations have actually been applied and sets the correct version.
"""
import sys
from sqlalchemy import create_engine, text, inspect
from aiwriter_backend.core.config import settings

def fix_alembic_revisions():
    """Clean up alembic_version table and set correct version based on actual schema."""
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        # Check all current versions (might be duplicates)
        result = conn.execute(text("SELECT version_num FROM alembic_version"))
        all_versions = [row[0] for row in result]
        
        print(f"Current versions in alembic_version table: {all_versions}")
        
        # Check what's actually in the database schema
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        has_articles = 'articles' in tables
        has_jobs_context = False
        
        if 'jobs' in tables:
            columns = [col['name'] for col in inspector.get_columns('jobs')]
            has_jobs_context = 'context' in columns
        
        # Determine correct version based on schema
        if has_jobs_context:
            correct_version = '004_phase35_job_fields'
            print("✅ Database has Phase 3.5 fields (context, user_images, etc.)")
        elif has_articles:
            correct_version = '003_phase3_article_fields'
            print("✅ Database has articles table (Phase 3)")
        elif 'callback_url' in [col['name'] for col in inspector.get_columns('sites')]:
            correct_version = '002_add_callback_url'
            print("✅ Database has callback_url (Phase 2)")
        else:
            correct_version = '001_initial_schema'
            print("✅ Database has initial schema only")
        
        print(f"\n📌 Setting Alembic version to: {correct_version}")
        
        # Delete all existing entries
        conn.execute(text("DELETE FROM alembic_version"))
        
        # Insert the correct version
        conn.execute(text("INSERT INTO alembic_version (version_num) VALUES (:version)"), {"version": correct_version})
        conn.commit()
        
        print(f"✅ Fixed! Alembic version is now: {correct_version}")
        
        # Verify
        result = conn.execute(text("SELECT version_num FROM alembic_version"))
        final_version = result.scalar()
        print(f"✅ Verified final version: {final_version}")
    
    return True

if __name__ == '__main__':
    try:
        if fix_alembic_revisions():
            print("\n✅ Alembic revisions fixed! You can now run 'alembic upgrade head'")
            sys.exit(0)
        else:
            print("\n❌ Failed to fix revisions. Please check manually.")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

