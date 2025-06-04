#!/usr/bin/env python3
"""
Smoke test: Smart routing vs voting behavior
Ensures simple prompts use smart routing and complex prompts use voting
"""

import requests
import time
import json
import sys
import os

API = os.getenv("SWARM_API", "http://localhost:8000")

def call(prompt):
    """Make a hybrid API call and return timing and routing info"""
    t0 = time.perf_counter()
    try:
        r = requests.post(
            f"{API}/hybrid",
            json={"prompt": prompt, "preferred_models": []}, 
            timeout=10
        )
        r.raise_for_status()
        latency = (time.perf_counter() - t0) * 1000
        
        result = r.json()
        provider = result.get("provider", "unknown")
        model_used = result.get("model_used", "unknown")
        
        print(f"{prompt[:30]:30s} | model={model_used:20s} | "
              f"provider={provider:15s} | {latency:6.1f} ms")
        
        return provider
        
    except Exception as e:
        print(f"ERROR calling API: {e}")
        sys.exit(1)

def main():
    """Run smoke tests for smart routing behavior"""
    print("🧪 Smart Routing Smoke Test")
    print("=" * 60)
    
    # Test 1: Simple prompts should use smart routing (local_smart)
    print("\n📊 SIMPLE PROMPTS (should use local_smart):")
    simple_prompts = [
        "2+2?",
        "What is the capital of France?",
        "Calculate 5 * 6",
        "Hello world"
    ]
    
    for prompt in simple_prompts:
        provider = call(prompt)
        if provider != "local_smart":
            print(f"❌ FAIL: Simple prompt '{prompt}' used {provider}, expected local_smart")
            sys.exit(1)
    
    print("✅ All simple prompts correctly used smart routing")
    
    # Test 2: Complex prompts should use voting (local_voting)
    print("\n🧠 COMPLEX PROMPTS (should use local_voting):")
    complex_prompts = [
        "Please explain in detail why neural networks work",
        "Analyze the step by step process of machine learning",
        "Why do we need quantum computing and what are the implications?",
        "Compare and contrast different sorting algorithms and explain their trade-offs"
    ]
    
    for prompt in complex_prompts:
        provider = call(prompt)
        if provider != "local_voting":
            print(f"❌ FAIL: Complex prompt '{prompt}' used {provider}, expected local_voting")
            sys.exit(1)
    
    print("✅ All complex prompts correctly used voting")
    
    # Test 3: Performance characteristics
    print("\n⚡ PERFORMANCE VERIFICATION:")
    
    # Simple prompt should be very fast
    t0 = time.perf_counter()
    call("2+2?")
    simple_latency = (time.perf_counter() - t0) * 1000
    
    # Complex prompt should be slower (due to voting)
    t0 = time.perf_counter()
    call("Explain why the sky is blue step by step")
    complex_latency = (time.perf_counter() - t0) * 1000
    
    print(f"Simple routing latency: {simple_latency:.1f}ms")
    print(f"Voting routing latency: {complex_latency:.1f}ms")
    
    if simple_latency > 100:  # Simple should be < 100ms
        print(f"⚠️ WARNING: Simple routing took {simple_latency:.1f}ms (expected < 100ms)")
    
    if complex_latency < simple_latency:
        print(f"⚠️ WARNING: Voting was faster than smart routing (unexpected)")
    
    print("\n✅ Smart routing smoke test PASSED!")
    print("🎯 All routing decisions are working correctly")

if __name__ == "__main__":
    main() 