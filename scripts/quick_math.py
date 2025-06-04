#!/usr/bin/env python3
"""
Quick Math Sanity Test
======================

Single-shot real inference test to verify models are working
without falling back to mocks.
"""

import sys
import os
import asyncio
import time

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'fork', 'swarm_autogen'))

from router_cascade import RouterCascade, MockResponseError

async def test_math_computation(expression: str):
    """Test a single math computation and verify it's real"""
    print(f"🧮 Testing: {expression}")
    
    router = RouterCascade()
    
    try:
        start_time = time.time()
        result = await router.route_query(f"Calculate {expression}")
        latency_ms = (time.time() - start_time) * 1000
        
        print(f"✅ Answer: {result['text']}")
        print(f"⚡ Latency: {latency_ms:.1f}ms")
        print(f"🎯 Skill: {result['skill_type']}")
        print(f"🤖 Model: {result.get('model', 'unknown')}")
        print(f"📊 Confidence: {result.get('confidence', 0.0):.2f}")
        
        # Verify it's not a mock response
        if "not sure" in result['text'].lower():
            print("❌ MOCK DETECTED: Router fallback")
            return False
        
        if result.get('model') == 'unknown':
            print("⚠️ WARNING: Model unknown - possibly mock")
            return False
            
        return True
        
    except MockResponseError as e:
        print(f"❌ MOCK DETECTED: {e}")
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

async def main():
    """Run quick math tests"""
    print("🚀 Quick Math Sanity Test")
    print("=" * 40)
    
    test_cases = [
        "2 + 2",
        "12 * (7 - 2)",  # Your suggested test case
        "8 factorial",
        "square root of 64"
    ]
    
    success_count = 0
    total_tests = len(test_cases)
    
    for expression in test_cases:
        print()
        success = await test_math_computation(expression)
        if success:
            success_count += 1
        print("-" * 40)
    
    print()
    print(f"📊 RESULTS: {success_count}/{total_tests} tests passed")
    
    if success_count == total_tests:
        print("🎉 ALL TESTS PASSED - Real AI generation working!")
        sys.exit(0)
    elif success_count > 0:
        print("⚠️ PARTIAL SUCCESS - Some real generation working")
        sys.exit(1)
    else:
        print("❌ ALL TESTS FAILED - Only mock responses")
        sys.exit(2)

if __name__ == "__main__":
    asyncio.run(main()) 