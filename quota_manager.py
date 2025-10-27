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

def show_plans():
    """Show all available plans."""
    db = next(get_db())
    
    plans = db.query(Plan).all()
    
    print("=== Available Plans ===")
    print(f"{'Plan ID':<8} {'Name':<10} {'Monthly Limit':<13} {'Max Images':<11} {'Price (EUR)':<12}")
    print("-" * 60)
    
    for plan in plans:
        price_eur = plan.price_eur / 100 if plan.price_eur else 0
        print(f"{plan.id:<8} {plan.name:<10} {plan.monthly_limit:<13} {plan.max_images_per_article:<11} {price_eur:<12}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("AIWriter Quota Management Tool")
        print("=" * 40)
        print("Usage:")
        print("  python quota_manager.py show                    # Show current usage")
        print("  python quota_manager.py plans                   # Show available plans")
        print("  python quota_manager.py reset <site_id>         # Reset site usage")
        print("  python quota_manager.py increase <plan_id> <limit> # Increase plan limit")
        print("  python quota_manager.py add <site_id> <articles>  # Add usage (testing)")
        print("")
        print("Examples:")
        print("  python quota_manager.py show")
        print("  python quota_manager.py reset 1")
        print("  python quota_manager.py increase 1 50")
        sys.exit(1)
    
    command = sys.argv[1]
    
    try:
        if command == "show":
            show_usage()
        elif command == "plans":
            show_plans()
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
            print("Use 'python quota_manager.py' without arguments to see usage")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
