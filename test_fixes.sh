#!/bin/bash

# Test script to verify timeout and JSON parsing fixes
echo "🧪 Testing AIWriter fixes..."

# Test 1: Check Nginx timeout settings
echo "1. Checking Nginx timeout settings..."
timeout_settings=$(grep -E "(proxy_|client_|keepalive_)timeout" /etc/nginx/sites-available/aiwriter)
if [ -n "$timeout_settings" ]; then
    echo "✅ Nginx timeout settings found:"
    echo "$timeout_settings"
else
    echo "❌ Nginx timeout settings not found"
fi

# Test 2: Check backend service status
echo ""
echo "2. Checking backend service status..."
sudo systemctl is-active aiwriter
if [ $? -eq 0 ]; then
    echo "✅ Backend service is running"
else
    echo "❌ Backend service is not running"
fi

# Test 3: Test API endpoint
echo ""
echo "3. Testing API endpoint..."
response=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8080/)
if [ "$response" = "200" ]; then
    echo "✅ API endpoint responding (HTTP $response)"
else
    echo "❌ API endpoint not responding (HTTP $response)"
fi

# Test 4: Check recent logs for errors
echo ""
echo "4. Checking recent logs for errors..."
recent_errors=$(sudo journalctl -u aiwriter --since "5 minutes ago" | grep -i "error\|failed\|timeout" | tail -5)
if [ -n "$recent_errors" ]; then
    echo "⚠️  Recent errors found:"
    echo "$recent_errors"
else
    echo "✅ No recent errors found"
fi

echo ""
echo "🎯 Summary:"
echo "- Nginx timeouts: $(if [ -n "$timeout_settings" ]; then echo "✅ Fixed"; else echo "❌ Not fixed"; fi)"
echo "- Backend service: $(if sudo systemctl is-active aiwriter >/dev/null 2>&1; then echo "✅ Running"; else echo "❌ Not running"; fi)"
echo "- API endpoint: $(if [ "$response" = "200" ]; then echo "✅ Responding"; else echo "❌ Not responding"; fi)"
echo ""
echo "🚀 Ready to test article generation from WordPress!"
