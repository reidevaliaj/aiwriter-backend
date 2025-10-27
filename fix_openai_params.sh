#!/bin/bash
# Fix OpenAI API parameter compatibility

# Configuration
APP_DIR="/home/rei/apps/aiwriter-backend"
SERVICE_NAME="aiwriter"

echo "--- Fixing OpenAI API Parameters ---"

# 1. Navigate to application directory
echo "Navigating to $APP_DIR..."
cd $APP_DIR || { echo "Error: Could not change to $APP_DIR. Exiting."; exit 1; }

# 2. Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate || { echo "Error: Could not activate venv. Exiting."; exit 1; }

# 3. Set environment variables for better models
echo "Setting environment variables..."
export OPENAI_TEXT_MODEL="gpt-4o"
export OPENAI_IMAGE_MODEL="dall-e-3"

# 4. Restart the systemd service
echo "Restarting $SERVICE_NAME service..."
sudo systemctl restart $SERVICE_NAME || { echo "Error: Could not restart $SERVICE_NAME. Exiting."; exit 1; }

# 5. Check service status
echo "Checking $SERVICE_NAME service status..."
sudo systemctl status $SERVICE_NAME --no-pager

echo "--- OpenAI API Fix Complete ---"
echo "Now using GPT-4o for text and DALL-E 3 for images"
echo "Try generating an article and check logs:"
echo "sudo journalctl -u $SERVICE_NAME -f"
