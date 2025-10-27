-- AIWriter Quota Management SQL Script
-- Run these commands in PostgreSQL: sudo -u postgres psql -d aiwriter

-- 1. Show current usage for all sites
SELECT 
    s.id as site_id,
    s.domain,
    p.name as plan_name,
    p.monthly_limit,
    COALESCE(u.articles_generated, 0) as articles_used,
    (p.monthly_limit - COALESCE(u.articles_generated, 0)) as articles_remaining,
    u.year_month
FROM sites s
JOIN licenses l ON s.license_id = l.id
JOIN plans p ON l.plan_id = p.id
LEFT JOIN usage u ON s.id = u.site_id AND u.year_month = '2025-10'
ORDER BY s.id;

-- 2. Reset usage for site ID 1 (your current site)
UPDATE usage 
SET articles_generated = 0 
WHERE site_id = 1 AND year_month = '2025-10';

-- 3. Increase Free plan limit to 50 articles/month
UPDATE plans 
SET monthly_limit = 50 
WHERE id = 1 AND name = 'Free';

-- 4. Allow 1 image per article for Free plan
UPDATE plans 
SET max_images_per_article = 1 
WHERE id = 1 AND name = 'Free';

-- 5. Set usage to test quota (e.g., 9 articles used)
UPDATE usage 
SET articles_generated = 9 
WHERE site_id = 1 AND year_month = '2025-10';

-- 6. Delete usage record entirely (resets to 0)
DELETE FROM usage 
WHERE site_id = 1 AND year_month = '2025-10';

-- 7. Show all plans
SELECT id, name, monthly_limit, max_images_per_article, price_eur 
FROM plans 
ORDER BY id;

-- 8. Reset all usage for current month (nuclear option)
UPDATE usage 
SET articles_generated = 0 
WHERE year_month = '2025-10';

-- 9. Check specific site details
SELECT 
    s.id,
    s.domain,
    l.key as license_key,
    p.name as plan_name,
    p.monthly_limit,
    p.max_images_per_article,
    COALESCE(u.articles_generated, 0) as articles_used
FROM sites s
JOIN licenses l ON s.license_id = l.id
JOIN plans p ON l.plan_id = p.id
LEFT JOIN usage u ON s.id = u.site_id AND u.year_month = '2025-10'
WHERE s.id = 1;
