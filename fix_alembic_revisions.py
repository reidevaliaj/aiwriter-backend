#!/usr/bin/env python3
"""
Fix Alembic revision chain by updating the alembic_version table.
This script checks the current state and updates revision IDs to match the new naming.
"""
import sys
from sqlalchemy import create_engine, text
from aiwriter_backend.core.config import settings

def fix_alembic_revisions():
    """Update alembic_version table to match new revision IDs."""
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        # Check current version
        result = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
        current_version = result.scalar()
        
        print(f"Current Alembic version in database: {current_version}")
        
        # Mapping of old IDs to new IDs
        revision_map = {
            '001': '001_initial_schema',
            '002': '002_add_callback_url',
            '003': '003_phase3_article_fields',  # In case it was created with just '003'
        }
        
        # Update if needed
        if current_version in revision_map:
            new_version = revision_map[current_version]
            print(f"Updating revision from '{current_version}' to '{new_version}'")
            conn.execute(text("UPDATE alembic_version SET version_num = :new_version"), {"new_version": new_version})
            conn.commit()
            print(f"✅ Updated to: {new_version}")
        elif current_version in revision_map.values():
            print(f"✅ Version already correct: {current_version}")
        else:
            print(f"⚠️  Unknown version '{current_version}'. Please check manually.")
            print("Expected values: 001_initial_schema, 002_add_callback_url, 003_phase3_article_fields, 004_phase35_job_fields")
            return False
    
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

