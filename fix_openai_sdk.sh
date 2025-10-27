#!/bin/bash
# Fix OpenAI SDK compatibility on VPS

# Configuration
APP_DIR="/home/rei/apps/aiwriter-backend"
SERVICE_NAME="aiwriter"

echo "--- Fixing OpenAI SDK Compatibility ---"

# 1. Navigate to application directory
echo "Navigating to $APP_DIR..."
cd $APP_DIR || { echo "Error: Could not change to $APP_DIR. Exiting."; exit 1; }

# 2. Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate || { echo "Error: Could not activate venv. Exiting."; exit 1; }

# 3. Check current OpenAI version
echo "Current OpenAI version:"
pip show openai

# 4. Update OpenAI to latest version
echo "Updating OpenAI to latest version..."
pip install --upgrade openai

# 5. Check updated version
echo "Updated OpenAI version:"
pip show openai

# 6. Restart the systemd service
echo "Restarting $SERVICE_NAME service..."
sudo systemctl restart $SERVICE_NAME || { echo "Error: Could not restart $SERVICE_NAME. Exiting."; exit 1; }

# 7. Check service status
echo "Checking $SERVICE_NAME service status..."
sudo systemctl status $SERVICE_NAME --no-pager

echo "--- OpenAI SDK Fix Complete ---"
echo "Now try generating an article and check logs:"
echo "sudo journalctl -u $SERVICE_NAME -f"
