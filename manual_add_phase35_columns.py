#!/usr/bin/env python3
"""
Manually add Phase 3.5 columns directly to jobs table without Alembic transaction overhead.
This can be faster if there are lock issues.
"""
import sys
from sqlalchemy import create_engine, text
from aiwriter_backend.core.config import settings

def manual_add_columns():
    """Add Phase 3.5 columns directly using raw SQL."""
    engine = create_engine(settings.DATABASE_URL, isolation_level="AUTOCOMMIT")
    
    try:
        with engine.connect() as conn:
            print("Checking current columns...")
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'jobs' 
                AND column_name IN ('context', 'user_images', 'include_faq', 'include_cta', 'cta_url', 'template', 'style_preset')
            """))
            existing = [row[0] for row in result]
            
            if existing:
                print(f"⚠️  Some columns already exist: {existing}")
                print("Skipping existing columns...")
            
            # Add columns one by one (faster, can be interrupted)
            columns_to_add = {
                'context': "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS context TEXT",
                'user_images': "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS user_images JSONB",
                'include_faq': "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS include_faq BOOLEAN DEFAULT true",
                'include_cta': "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS include_cta BOOLEAN DEFAULT false",
                'cta_url': "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS cta_url VARCHAR",
                'template': "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS template VARCHAR DEFAULT 'classic'",
                'style_preset': "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS style_preset VARCHAR DEFAULT 'default'"
            }
            
            for col_name, sql in columns_to_add.items():
                if col_name not in existing:
                    print(f"Adding column: {col_name}...")
                    conn.execute(text(sql))
                    print(f"✅ Added {col_name}")
                else:
                    print(f"⏭️  Skipped {col_name} (already exists)")
            
            print("\n✅ All columns added!")
            
            # Update Alembic version
            print("\nUpdating Alembic version...")
            conn.execute(text("DELETE FROM alembic_version"))
            conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('004_phase35_job_fields')"))
            print("✅ Alembic version updated to: 004_phase35_job_fields")
            
            return True
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("🔧 Manual Phase 3.5 Column Addition")
    print("=" * 50)
    
    if manual_add_columns():
        print("\n✅ Success! You can now verify with:")
        print("   alembic current")
        sys.exit(0)
    else:
        print("\n❌ Failed. Check errors above.")
        sys.exit(1)


