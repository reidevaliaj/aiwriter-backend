#!/bin/bash
# Deploy GPT-5 configuration with correct parameters

# Configuration
APP_DIR="/home/rei/apps/aiwriter-backend"
SERVICE_NAME="aiwriter"

echo "--- Deploying GPT-5 Configuration ---"

# 1. Navigate to application directory
echo "Navigating to $APP_DIR..."
cd $APP_DIR || { echo "Error: Could not change to $APP_DIR. Exiting."; exit 1; }

# 2. Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate || { echo "Error: Could not activate venv. Exiting."; exit 1; }

# 3. Set GPT-5 environment variables
echo "Setting GPT-5 environment variables..."
export OPENAI_TEXT_MODEL="gpt-5"
export OPENAI_IMAGE_MODEL="dall-e-3"
export OPENAI_MAX_TOKENS_TEXT="2200"
export OPENAI_TEMPERATURE="0.4"

# 4. Restart the systemd service
echo "Restarting $SERVICE_NAME service..."
sudo systemctl restart $SERVICE_NAME || { echo "Error: Could not restart $SERVICE_NAME. Exiting."; exit 1; }

# 5. Check service status
echo "Checking $SERVICE_NAME service status..."
sudo systemctl status $SERVICE_NAME --no-pager

echo "--- GPT-5 Configuration Deployed ---"
echo "Now using GPT-5 with max_completion_tokens, verbosity, and reasoning_effort"
echo "Try generating an article and check logs:"
echo "sudo journalctl -u $SERVICE_NAME -f"
