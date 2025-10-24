"""
Test script for API endpoints.
"""
import requests
import json
import secrets
from sqlalchemy.orm import Session
from aiwriter_backend.db.session import SessionLocal
from aiwriter_backend.db.base import License, Plan

# API base URL
API_BASE = "http://localhost:8000"

def create_test_license():
    """Create a test license in the database."""
    db = SessionLocal()
    try:
        # Get the Free plan
        plan = db.query(Plan).filter(Plan.name == "Free").first()
        if not plan:
            print("No Free plan found. Please run seed_plans.py first.")
            return None
        
        # Create a test license
        license_key = f"TEST-{secrets.token_hex(8).upper()}"
        license_obj = License(
            key=license_key,
            plan_id=plan.id,
            status="active"
        )
        
        db.add(license_obj)
        db.commit()
        db.refresh(license_obj)
        
        print(f"Created test license: {license_key}")
        return license_key
        
    finally:
        db.close()

def test_license_activation():
    """Test license activation endpoint."""
    print("\n=== Testing License Activation ===")
    
    # Create test license
    license_key = create_test_license()
    if not license_key:
        return
    
    # Test activation
    url = f"{API_BASE}/v1/license/activate"
    data = {
        "license_key": license_key,
        "domain": "example.com"
    }
    
    try:
        response = requests.post(url, json=data)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            result = response.json()
            if result["success"]:
                print(f"SUCCESS: License activated! Site ID: {result['site_id']}")
                return result["site_id"], result["secret"]
            else:
                print(f"FAILED: Activation failed: {result['message']}")
        else:
            print(f"ERROR: HTTP Error: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Request failed: {e}")
    
    return None, None

def test_license_validation():
    """Test license validation endpoint."""
    print("\n=== Testing License Validation ===")
    
    # Create test license
    license_key = create_test_license()
    if not license_key:
        return
    
    url = f"{API_BASE}/v1/license/validate"
    data = {
        "license_key": license_key
    }
    
    try:
        response = requests.post(url, json=data)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            result = response.json()
            if result["valid"]:
                print(f"SUCCESS: License is valid! Plan: {result['plan_name']}")
            else:
                print(f"FAILED: License invalid: {result['message']}")
        else:
            print(f"ERROR: HTTP Error: {response.status_code}")
            
    except Exception as e:
        print(f"ERROR: Request failed: {e}")

def test_job_creation(site_id, secret):
    """Test job creation endpoint."""
    print("\n=== Testing Job Creation ===")
    
    url = f"{API_BASE}/v1/jobs/generate"
    data = {
        "topic": "Test Article Topic",
        "length": "medium",
        "include_images": False
    }
    
    headers = {
        "X-Site-ID": str(site_id),
        "X-Signature": "test-signature",  # In real implementation, this would be HMAC
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, json=data, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            result = response.json()
            if result["success"]:
                print(f"SUCCESS: Job created! Job ID: {result['job_id']}")
            else:
                print(f"FAILED: Job creation failed: {result['message']}")
        else:
            print(f"ERROR: HTTP Error: {response.status_code}")
            
    except Exception as e:
        print(f"ERROR: Request failed: {e}")

def test_health_check():
    """Test health check endpoint."""
    print("\n=== Testing Health Check ===")
    
    try:
        response = requests.get(f"{API_BASE}/health")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            print("SUCCESS: Health check passed!")
        else:
            print(f"ERROR: Health check failed: {response.status_code}")
            
    except Exception as e:
        print(f"ERROR: Health check failed: {e}")

def main():
    """Run all tests."""
    print("Starting API Tests")
    print("=" * 50)
    
    # Test health check first
    test_health_check()
    
    # Test license validation
    test_license_validation()
    
    # Test license activation
    site_id, secret = test_license_activation()
    
    # Test job creation if activation succeeded
    if site_id and secret:
        test_job_creation(site_id, secret)
    
    print("\n" + "=" * 50)
    print("SUCCESS: API Tests Completed!")

if __name__ == "__main__":
    main()
