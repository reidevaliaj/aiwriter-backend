# Quota Management Guide

## Overview

The AIWriter system tracks usage per site per month. Quotas are managed through the database and can be adjusted in several ways.

## Current Quota System

### Plans and Limits
- **Free Plan**: 10 articles/month, 0 images
- **Starter Plan**: 30 articles/month, 1 image per article  
- **Pro Plan**: 100 articles/month, 2 images per article

### Database Tables
- `plans` - Plan definitions and limits
- `licenses` - License assignments to plans
- `usage` - Monthly usage tracking per site
- `sites` - WordPress sites with licenses

## Methods to Increase/Reset Quotas

### Method 1: Direct Database Access (Quickest)

**SSH into VPS:**
```bash
ssh rei@142.93.161.58
```

**Access PostgreSQL:**
```bash
sudo -u postgres psql -d aiwriter
```

**Reset usage for a specific site:**
```sql
-- Reset usage for site ID 1 (current month)
UPDATE usage 
SET articles_generated = 0 
WHERE site_id = 1 AND year_month = '2025-10';

-- Or delete the usage record entirely
DELETE FROM usage 
WHERE site_id = 1 AND year_month = '2025-10';
```

**Increase plan limits:**
```sql
-- Increase Free plan to 50 articles/month
UPDATE plans 
SET monthly_limit = 50 
WHERE id = 1;

-- Increase Free plan to allow 1 image per article
UPDATE plans 
SET max_images_per_article = 1 
WHERE id = 1;
```

**Check current usage:**
```sql
-- Check usage for all sites
SELECT s.domain, u.year_month, u.articles_generated, p.monthly_limit, p.name as plan_name
FROM sites s
JOIN licenses l ON s.license_id = l.id
JOIN plans p ON l.plan_id = p.id
LEFT JOIN usage u ON s.id = u.site_id AND u.year_month = '2025-10'
ORDER BY s.id;
```

### Method 2: Python Script (Recommended)

Create a quota management script:

```python
#!/usr/bin/env python3
"""
Quota Management Script for AIWriter
"""
import sys
import os
from datetime import datetime
from sqlalchemy.orm import Session

# Add the backend directory to Python path
sys.path.append('/home/rei/apps/aiwriter-backend')

from aiwriter_backend.db.session import get_db
from aiwriter_backend.db.base import Site, License, Plan, Usage

def show_usage():
    """Show current usage for all sites."""
    db = next(get_db())
    
    current_month = f"{datetime.now().year}-{datetime.now().month:02d}"
    
    sites = db.query(Site).all()
    
    print(f"=== Usage Report for {current_month} ===")
    print(f"{'Site ID':<8} {'Domain':<30} {'Plan':<10} {'Used':<6} {'Limit':<6} {'Remaining':<10}")
    print("-" * 80)
    
    for site in sites:
        license_obj = db.query(License).filter(License.id == site.license_id).first()
        plan = db.query(Plan).filter(Plan.id == license_obj.plan_id).first()
        
        usage = db.query(Usage).filter(
            Usage.site_id == site.id,
            Usage.year_month == current_month
        ).first()
        
        used = usage.articles_generated if usage else 0
        remaining = plan.monthly_limit - used
        
        print(f"{site.id:<8} {site.domain:<30} {plan.name:<10} {used:<6} {plan.monthly_limit:<6} {remaining:<10}")

def reset_site_usage(site_id: int):
    """Reset usage for a specific site."""
    db = next(get_db())
    current_month = f"{datetime.now().year}-{datetime.now().month:02d}"
    
    usage = db.query(Usage).filter(
        Usage.site_id == site_id,
        Usage.year_month == current_month
    ).first()
    
    if usage:
        usage.articles_generated = 0
        print(f"Reset usage for site {site_id} to 0")
    else:
        print(f"No usage record found for site {site_id}")
    
    db.commit()

def increase_plan_limit(plan_id: int, new_limit: int):
    """Increase monthly limit for a plan."""
    db = next(get_db())
    
    plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if plan:
        old_limit = plan.monthly_limit
        plan.monthly_limit = new_limit
        db.commit()
        print(f"Updated {plan.name} plan limit from {old_limit} to {new_limit}")
    else:
        print(f"Plan {plan_id} not found")

def add_usage(site_id: int, articles: int):
    """Add articles to usage (for testing)."""
    db = next(get_db())
    current_month = f"{datetime.now().year}-{datetime.now().month:02d}"
    
    usage = db.query(Usage).filter(
        Usage.site_id == site_id,
        Usage.year_month == current_month
    ).first()
    
    if usage:
        usage.articles_generated += articles
    else:
        usage = Usage(
            site_id=site_id,
            year_month=current_month,
            articles_generated=articles
        )
        db.add(usage)
    
    db.commit()
    print(f"Added {articles} articles to site {site_id} usage")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python quota_manager.py show                    # Show current usage")
        print("  python quota_manager.py reset <site_id>         # Reset site usage")
        print("  python quota_manager.py increase <plan_id> <limit> # Increase plan limit")
        print("  python quota_manager.py add <site_id> <articles>  # Add usage (testing)")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "show":
        show_usage()
    elif command == "reset" and len(sys.argv) == 3:
        site_id = int(sys.argv[2])
        reset_site_usage(site_id)
    elif command == "increase" and len(sys.argv) == 4:
        plan_id = int(sys.argv[2])
        new_limit = int(sys.argv[3])
        increase_plan_limit(plan_id, new_limit)
    elif command == "add" and len(sys.argv) == 4:
        site_id = int(sys.argv[2])
        articles = int(sys.argv[3])
        add_usage(site_id, articles)
    else:
        print("Invalid command or arguments")
```

### Method 3: API Endpoints (Future)

For production, you might want to add admin API endpoints:

```python
@router.post("/admin/reset-usage/{site_id}")
async def reset_site_usage(site_id: int, db: Session = Depends(get_db)):
    """Reset usage for a site (admin only)."""
    # Implementation here
    pass

@router.post("/admin/increase-plan/{plan_id}")
async def increase_plan_limit(plan_id: int, new_limit: int, db: Session = Depends(get_db)):
    """Increase plan limit (admin only)."""
    # Implementation here
    pass
```

## Quick Commands

### Reset Current Site Usage (Site ID 1)
```bash
# SSH into VPS
ssh rei@142.93.161.58

# Access database
sudo -u postgres psql -d aiwriter

# Reset usage
UPDATE usage SET articles_generated = 0 WHERE site_id = 1 AND year_month = '2025-10';
\q
```

### Increase Free Plan Limit
```bash
# In PostgreSQL
UPDATE plans SET monthly_limit = 50 WHERE id = 1;
```

### Check Current Status
```bash
# In PostgreSQL
SELECT s.domain, u.articles_generated, p.monthly_limit, p.name 
FROM sites s 
JOIN licenses l ON s.license_id = l.id 
JOIN plans p ON l.plan_id = p.id 
LEFT JOIN usage u ON s.id = u.site_id AND u.year_month = '2025-10';
```

## Monthly Reset

The system is designed to reset monthly. You can also manually reset all usage:

```sql
-- Reset all usage for current month
UPDATE usage SET articles_generated = 0 WHERE year_month = '2025-10';

-- Or delete all usage records for current month
DELETE FROM usage WHERE year_month = '2025-10';
```

## Testing Quotas

To test quota limits:

```sql
-- Set usage to near limit
UPDATE usage SET articles_generated = 9 WHERE site_id = 1 AND year_month = '2025-10';

-- Or set to exact limit to test blocking
UPDATE usage SET articles_generated = 10 WHERE site_id = 1 AND year_month = '2025-10';
```
