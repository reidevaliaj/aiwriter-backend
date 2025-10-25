#!/bin/bash
# VPS Database Update Script
# Run this on your VPS to update the database

echo "🚀 Updating AIWriter Backend Database..."

# Navigate to backend directory
cd /home/rei/apps/aiwriter-backend

# Activate virtual environment
echo "📦 Activating virtual environment..."
source venv/bin/activate

# Check current migration status
echo "📊 Current migration status:"
alembic current

# Show available migrations
echo "📋 Available migrations:"
alembic history

# Run migrations
echo "🔄 Running database migrations..."
alembic upgrade head

# Check migration status after update
echo "✅ Migration status after update:"
alembic current

# Restart backend service
echo "🔄 Restarting backend service..."
sudo systemctl restart aiwriter

# Check service status
echo "📊 Backend service status:"
sudo systemctl status aiwriter --no-pager

echo "✅ Database update complete!"
echo "🌐 Backend should be running at: http://142.93.161.58"
