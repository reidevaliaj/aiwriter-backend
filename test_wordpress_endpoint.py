#!/usr/bin/env python3
"""
Test script to verify WordPress endpoint is accessible.
"""
import requests
import json

def test_wordpress_endpoint():
    """Test if WordPress endpoint is accessible."""
    
    # Test URL
    webhook_url = "https://aiwriter.code-studio.eu/wp-json/aiwriter/v1/publish"
    
    # Test payload
    payload = {
        "site_id": 1,
        "job_id": 999,
        "article_data": {
            "title": "Test Article",
            "content_html": "<p>This is a test article.</p>",
            "meta_title": "Test Article - Meta Title",
            "meta_description": "Test article meta description",
            "faq_schema": "{}",
            "featured_image_url": None
        },
        "signature": "test-signature"
    }
    
    print(f"Testing WordPress endpoint: {webhook_url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        print(f"Response Status: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Body: {response.text}")
        
        if response.status_code == 200:
            print("✅ WordPress endpoint is working!")
            return True
        else:
            print(f"❌ WordPress endpoint error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing WordPress endpoint: {e}")
        return False

if __name__ == "__main__":
    test_wordpress_endpoint()
