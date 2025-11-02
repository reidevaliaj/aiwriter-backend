#!/usr/bin/env python3
"""
Check for blocking queries/locks on the jobs table.
"""
from sqlalchemy import create_engine, text
from aiwriter_backend.core.config import settings

def check_locks():
    """Check for locks on jobs table."""
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        # Check for blocking queries
        result = conn.execute(text("""
            SELECT 
                blocked_locks.pid AS blocked_pid,
                blocking_locks.pid AS blocking_pid,
                blocked_activity.usename AS blocked_user,
                blocking_activity.usename AS blocking_user,
                blocked_activity.query AS blocked_statement,
                blocking_activity.query AS blocking_statement
            FROM pg_catalog.pg_locks blocked_locks
            JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
            JOIN pg_catalog.pg_locks blocking_locks 
                ON blocking_locks.locktype = blocked_locks.locktype
                AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
                AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
                AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
                AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
                AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
                AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
                AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
                AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
                AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
                AND blocking_locks.pid != blocked_locks.pid
            JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
            WHERE NOT blocked_locks.granted
        """))
        
        blocks = list(result)
        if blocks:
            print("🚨 BLOCKING QUERIES DETECTED:")
            for row in blocks:
                print(f"\nBlocked PID: {row[0]}")
                print(f"Blocking PID: {row[1]}")
                print(f"Blocked Query: {row[4][:200]}...")
                print(f"Blocking Query: {row[5][:200]}...")
        else:
            print("✅ No blocking queries detected")
        
        # Check for locks on jobs table
        result = conn.execute(text("""
            SELECT 
                l.locktype,
                l.relation::regclass,
                l.mode,
                l.granted,
                a.usename,
                a.query,
                a.query_start
            FROM pg_locks l
            JOIN pg_stat_activity a ON l.pid = a.pid
            WHERE l.relation = 'jobs'::regclass::oid
               OR l.relation::text LIKE '%jobs%'
            ORDER BY a.query_start
        """))
        
        locks = list(result)
        if locks:
            print("\n🔒 LOCKS ON JOBS TABLE:")
            for row in locks:
                granted = "✅ GRANTED" if row[3] else "⏳ WAITING"
                print(f"{granted} - {row[4]} - {row[5][:100]}...")
        else:
            print("\n✅ No locks on jobs table")

if __name__ == '__main__':
    check_locks()

