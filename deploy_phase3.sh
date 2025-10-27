#!/bin/bash
# Deploy Phase 3 AI Pipeline to VPS

# Configuration
APP_DIR="/home/rei/apps/aiwriter-backend"
SERVICE_NAME="aiwriter"

echo "--- Starting Phase 3 AI Pipeline Deployment ---"

# 1. Navigate to application directory
echo "Navigating to $APP_DIR..."
cd $APP_DIR || { echo "Error: Could not change to $APP_DIR. Exiting."; exit 1; }

# 2. Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate || { echo "Error: Could not activate venv. Exiting."; exit 1; }

# 3. Pull latest changes (if using git)
echo "Pulling latest changes..."
git pull origin main || echo "Warning: Git pull failed or not using git"

# 4. Install/update dependencies
echo "Installing dependencies..."
pip install -r requirements.txt || { echo "Error: Failed to install dependencies. Exiting."; exit 1; }

# 5. Apply Alembic migrations
echo "Applying database migrations..."
alembic upgrade head || { echo "Error: Alembic upgrade failed. Exiting."; exit 1; }

# 6. Check migration status
echo "Checking migration status..."
alembic current || echo "Warning: Could not check current migration"

# 7. Restart the systemd service
echo "Restarting $SERVICE_NAME service..."
sudo systemctl restart $SERVICE_NAME || { echo "Error: Could not restart $SERVICE_NAME. Exiting."; exit 1; }

# 8. Check service status
echo "Checking $SERVICE_NAME service status..."
sudo systemctl status $SERVICE_NAME --no-pager

# 9. Test the API
echo "Testing API health..."
sleep 5  # Wait for service to start
curl -f http://localhost:8080/health || echo "Warning: Health check failed"

echo "--- Phase 3 Deployment Complete ---"
echo "Check logs for any issues: sudo journalctl -u $SERVICE_NAME -f"
echo "Test the API: curl http://142.93.161.58/health"
