#!/usr/bin/env python3
"""
Test script to verify WordPress REST API endpoints.
"""
import requests
import json

def test_wordpress_rest():
    """Test WordPress REST API endpoints."""
    
    base_url = "https://aiwriter.code-studio.eu"
    
    # Test 1: Check if WordPress REST API is working
    print("=== Test 1: WordPress REST API ===")
    try:
        response = requests.get(f"{base_url}/wp-json/", timeout=10)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print("✅ WordPress REST API is working")
        else:
            print(f"❌ WordPress REST API error: {response.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 2: Check if our plugin endpoint is registered
    print("\n=== Test 2: AIWriter Test Endpoint ===")
    try:
        response = requests.get(f"{base_url}/wp-json/aiwriter/v1/test", timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        if response.status_code == 200:
            print("✅ AIWriter REST endpoint is working")
        else:
            print(f"❌ AIWriter REST endpoint error: {response.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 3: Check available REST routes
    print("\n=== Test 3: Available REST Routes ===")
    try:
        response = requests.get(f"{base_url}/wp-json/", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'namespaces' in data:
                print("Available namespaces:")
                for namespace in data['namespaces']:
                    print(f"  - {namespace}")
            if 'routes' in data:
                print("Available routes:")
                for route, info in data['routes'].items():
                    if 'aiwriter' in route:
                        print(f"  - {route}: {info}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_wordpress_rest()
