#!/bin/bash
# Deploy GPT-5 fixes to VPS

# Configuration
APP_DIR="/home/rei/apps/aiwriter-backend"
SERVICE_NAME="aiwriter"

echo "--- Deploying GPT-5 Fixes to VPS ---"

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

# 4. Create a simple test to verify the fix
echo "Creating GPT-5 test script..."
cat > test_gpt5_fix.py << 'EOF'
#!/usr/bin/env python3
import os
import sys
sys.path.append('/home/rei/apps/aiwriter-backend')

from aiwriter_backend.core.config import settings
from aiwriter_backend.core.openai_client import run_text
import asyncio

async def test():
    print(f"Model: {settings.OPENAI_TEXT_MODEL}")
    print(f"API Key: {'SET' if settings.OPENAI_API_KEY else 'NOT SET'}")
    
    if not settings.OPENAI_API_KEY:
        print("ERROR: OpenAI API key not set")
        return
    
    try:
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say hello"}
        ]
        
        response = await run_text(messages)
        print(f"SUCCESS: {response[:50]}...")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(test())
EOF

# 5. Test the fix
echo "Testing GPT-5 fix..."
python test_gpt5_fix.py

# 6. Restart the systemd service
echo "Restarting $SERVICE_NAME service..."
sudo systemctl restart $SERVICE_NAME || { echo "Error: Could not restart $SERVICE_NAME. Exiting."; exit 1; }

# 7. Check service status
echo "Checking $SERVICE_NAME service status..."
sudo systemctl status $SERVICE_NAME --no-pager

echo "--- GPT-5 Fix Deployed ---"
echo "Now try generating an article and check logs:"
echo "sudo journalctl -u $SERVICE_NAME -f"
