#!/usr/bin/env python3
"""
Test GPT-5 API with correct parameters.
"""
import os
import sys
import asyncio

# Add the backend directory to Python path
sys.path.append('/home/rei/apps/aiwriter-backend')

async def test_gpt5():
    """Test GPT-5 with correct parameters."""
    print("=== GPT-5 API Test ===")
    
    try:
        from aiwriter_backend.core.openai_client import run_text
        
        # Test with GPT-5 specific parameters
        print("Testing GPT-5 with max_completion_tokens, verbosity, and reasoning_effort...")
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Write a short paragraph about camping tools."}
        ]
        
        response = await run_text(messages)
        print(f"✅ GPT-5 response: {response[:100]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ GPT-5 test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_gpt5_reasoning():
    """Test GPT-5 reasoning capabilities."""
    print("\n=== GPT-5 Reasoning Test ===")
    
    try:
        from aiwriter_backend.core.openai_client import run_text
        
        # Test with a reasoning task
        print("Testing GPT-5 reasoning capabilities...")
        messages = [
            {"role": "system", "content": "You are a helpful assistant that shows your reasoning process."},
            {"role": "user", "content": "What are the most important factors to consider when choosing camping gear for a forest trip?"}
        ]
        
        response = await run_text(messages)
        print(f"✅ GPT-5 reasoning response: {response[:200]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ GPT-5 reasoning test failed: {e}")
        return False

async def main():
    """Run all GPT-5 tests."""
    print("GPT-5 API Compatibility Test")
    print("=" * 50)
    
    # Check environment
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ OPENAI_API_KEY not set")
        return
    
    print(f"✅ OPENAI_API_KEY is set")
    print(f"Model: {os.getenv('OPENAI_TEXT_MODEL', 'gpt-5')}")
    
    # Test basic GPT-5
    basic_test = await test_gpt5()
    
    # Test GPT-5 reasoning
    reasoning_test = await test_gpt5_reasoning()
    
    print("\n=== Results ===")
    print(f"GPT-5 Basic: {'✅ PASS' if basic_test else '❌ FAIL'}")
    print(f"GPT-5 Reasoning: {'✅ PASS' if reasoning_test else '❌ FAIL'}")
    
    if basic_test and reasoning_test:
        print("\n🎉 All GPT-5 tests passed! The model should work correctly.")
    else:
        print("\n⚠️ Some tests failed. Check the errors above.")

if __name__ == "__main__":
    asyncio.run(main())
