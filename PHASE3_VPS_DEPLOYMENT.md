# Phase 3 VPS Deployment Guide

## Issue
The VPS is missing the new database columns (`requested_images`, `language`) and the `articles` table from Phase 3.

## Error
```
column "requested_images" of relation "jobs" does not exist
```

## Solution

### Option 1: Quick Migration (Recommended)
```bash
# SSH into your VPS
ssh rei@142.93.161.58

# Navigate to the app directory
cd /home/rei/apps/aiwriter-backend

# Activate virtual environment
source venv/bin/activate

# Apply the migration
alembic upgrade head

# Restart the service
sudo systemctl restart aiwriter

# Check status
sudo systemctl status aiwriter
```

### Option 2: Use Deployment Script
```bash
# Upload the migration script to VPS
scp backend/migrate_phase3.sh rei@142.93.161.58:/home/rei/

# SSH into VPS
ssh rei@142.93.161.58

# Make script executable and run
chmod +x migrate_phase3.sh
./migrate_phase3.sh
```

### Option 3: Full Phase 3 Deployment
```bash
# Upload the full deployment script
scp backend/deploy_phase3.sh rei@142.93.161.58:/home/rei/

# SSH into VPS
ssh rei@142.93.161.58

# Make script executable and run
chmod +x deploy_phase3.sh
./deploy_phase3.sh
```

## What the Migration Does

The `003_phase3_article_fields.py` migration will:

1. **Create `articles` table** with:
   - `id`, `job_id`, `license_id`, `topic`, `language`
   - `outline_json`, `article_html`, `meta_title`, `meta_description`
   - `faq_json`, `schema_json`, `image_urls_json`
   - `tokens_input`, `tokens_output`, `image_cost_cents`
   - `status`, `created_at`, `updated_at`

2. **Update `jobs` table** with:
   - `requested_images` (INTEGER, default 0)
   - `language` (VARCHAR, default 'de')

3. **Add indexes** for performance:
   - `ix_articles_job_id`
   - `ix_articles_license_id`
   - `ix_articles_created_at`
   - `ix_articles_license_created`

## Verification

After migration, test the API:
```bash
# Health check
curl http://142.93.161.58/health

# Test job creation (this should work now)
curl -X POST http://142.93.161.58/v1/jobs/generate \
  -H "Content-Type: application/json" \
  -H "X-Site-ID: 1" \
  -H "X-Signature: test" \
  -d '{"topic": "test article", "length": "short", "include_images": false}'
```

## Environment Variables

Make sure your VPS has the OpenAI API key set:
```bash
# Add to your VPS environment
export OPENAI_API_KEY="your_openai_api_key_here"
export OPENAI_TEXT_MODEL="gpt-5"
export OPENAI_IMAGE_MODEL="gpt-image-1"
```

## Next Steps

After successful migration:
1. ✅ Database schema updated
2. ✅ Service restarted
3. 🔄 Test article generation
4. 🔄 Verify WordPress integration
