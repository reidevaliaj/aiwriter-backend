#!/usr/bin/env python3
"""
Test OpenAI client compatibility on VPS.
"""
import os
import sys

# Add the backend directory to Python path
sys.path.append('/home/rei/apps/aiwriter-backend')

def test_openai_client():
    """Test OpenAI client initialization."""
    print("=== OpenAI Client Compatibility Test ===")
    
    try:
        # Check environment
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            print("❌ OPENAI_API_KEY not set")
            return False
        
        print(f"✅ OPENAI_API_KEY is set")
        
        # Test OpenAI client import
        from openai import OpenAI
        print(f"✅ OpenAI import successful")
        
        # Test client initialization
        try:
            client = OpenAI(api_key=api_key, timeout=60)
            print("✅ OpenAI client with timeout parameter works")
        except TypeError as e:
            if "unexpected keyword argument" in str(e):
                print("⚠️ Timeout parameter not supported, trying without...")
                client = OpenAI(api_key=api_key)
                print("✅ OpenAI client without timeout parameter works")
            else:
                raise
        
        # Test API call
        print("Testing API call...")
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Say hello"}],
            max_tokens=10
        )
        
        print(f"✅ API call successful: {response.choices[0].message.content}")
        return True
        
    except Exception as e:
        print(f"❌ OpenAI client test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_our_client():
    """Test our OpenAI client wrapper."""
    print("\n=== Our OpenAI Client Test ===")
    
    try:
        from aiwriter_backend.core.openai_client import get_openai
        client = get_openai()
        print("✅ Our OpenAI client wrapper works")
        return True
        
    except Exception as e:
        print(f"❌ Our OpenAI client wrapper failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("OpenAI SDK Compatibility Test")
    print("=" * 50)
    
    basic_test = test_openai_client()
    wrapper_test = test_our_client()
    
    print("\n=== Results ===")
    print(f"Basic OpenAI client: {'✅ PASS' if basic_test else '❌ FAIL'}")
    print(f"Our wrapper: {'✅ PASS' if wrapper_test else '❌ FAIL'}")
    
    if basic_test and wrapper_test:
        print("\n🎉 All tests passed! OpenAI should work now.")
    else:
        print("\n⚠️ Some tests failed. Check the errors above.")
