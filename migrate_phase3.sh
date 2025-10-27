#!/bin/bash
# Apply Phase 3 database migration only

# Configuration
APP_DIR="/home/rei/apps/aiwriter-backend"
SERVICE_NAME="aiwriter"

echo "--- Applying Phase 3 Database Migration ---"

# 1. Navigate to application directory
echo "Navigating to $APP_DIR..."
cd $APP_DIR || { echo "Error: Could not change to $APP_DIR. Exiting."; exit 1; }

# 2. Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate || { echo "Error: Could not activate venv. Exiting."; exit 1; }

# 3. Check current migration status
echo "Current migration status:"
alembic current

# 4. Apply migrations
echo "Applying migrations..."
alembic upgrade head || { echo "Error: Migration failed. Exiting."; exit 1; }

# 5. Verify migration
echo "Migration status after upgrade:"
alembic current

# 6. Restart service
echo "Restarting service..."
sudo systemctl restart $SERVICE_NAME

# 7. Check service status
echo "Service status:"
sudo systemctl status $SERVICE_NAME --no-pager

echo "--- Migration Complete ---"
echo "The database should now have the articles table and updated jobs table."
