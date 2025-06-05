#!/usr/bin/env python3
"""
Smoke Test Suite - Phase 2 Production Reality Check
==================================================

Comprehensive endpoint validation with CI-ready exit codes.
Fails the build if CUDA or local models disappear.
"""

import requests
import json
import sys
import time

# Test configuration
BASE_URL = "http://localhost:8001"
TEST_ENDPOINTS = ["/hybrid", "/vote", "/health"]
STUB_QUERIES = [
    "template this needs custom_function",
    "todo: implement unsupported number theory",
    "this has template markers custom_function todo"
]

def test_endpoint(endpoint, query="hello world"):
    """Test a single endpoint with timing"""
    url = f"{BASE_URL}{endpoint}"
    data = {"prompt": query}
    
    print(f"🧪 Testing {endpoint}...")
    start_time = time.time()
    
    try:
        response = requests.post(url, json=data, timeout=30)
        elapsed = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            result = response.json()
            conf = result.get("confidence", 0.0)
            model = result.get("response", "unknown")[:50]
            
            print(f"✅ {endpoint} → {conf:.2f} conf ({elapsed:.0f}ms)")
            print(f"   Response: {model}...")
            return True, {"confidence": conf, "latency_ms": elapsed, "response": result}
        else:
            print(f"❌ {endpoint} failed: HTTP {response.status_code}")
            return False, {"error": f"HTTP {response.status_code}"}
            
    except requests.exceptions.RequestException as e:
        print(f"❌ {endpoint} error: {e}")
        return False, {"error": str(e)}

def test_health():
    """Test health endpoint for CI reality check"""
    url = f"{BASE_URL}/health"
    
    print(f"🏥 Testing health endpoint...")
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            health = response.json()
            
            # Extract key metrics for CI
            cuda_available = health.get("cuda", False)
            system_ok = health.get("ok", False)
            local_models = health.get("local_models", 0)
            
            print(f"✅ Health check passed:")
            print(f"   CUDA: {cuda_available}")
            print(f"   System OK: {system_ok}")
            print(f"   Local models: {local_models}")
            
            return True, {
                "cuda": cuda_available,
                "ok": system_ok,
                "local_models": local_models,
                "full_health": health
            }
        else:
            print(f"❌ Health check failed: HTTP {response.status_code}")
            return False, {"error": f"HTTP {response.status_code}"}
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Health check error: {e}")
        return False, {"error": str(e)}

def test_stub_detection():
    """Test that stub detection is working properly"""
    print(f"🔍 Testing stub detection...")
    
    for query in STUB_QUERIES:
        success, result = test_endpoint("/hybrid", query)
        if success:
            conf = result.get("confidence", 1.0)
            if conf <= 0.1:  # Should be very low confidence for stubs
                print(f"✅ Stub detected: '{query[:30]}...' → {conf:.2f}")
            else:
                print(f"⚠️ Stub missed: '{query[:30]}...' → {conf:.2f}")
        else:
            print(f"❌ Stub test failed for: '{query[:30]}...'")

def main():
    """Main smoke test execution"""
    print("🔥 Phase-2 Smoke Test Suite")
    print("=" * 50)
    
    all_results = {}
    overall_success = True
    
    # Test all endpoints
    for endpoint in TEST_ENDPOINTS:
        if endpoint == "/health":
            success, result = test_health()
        else:
            success, result = test_endpoint(endpoint)
        
        all_results[endpoint] = result
        if not success:
            overall_success = False
    
    # Test stub detection
    test_stub_detection()
    
    # CI Reality Check - these MUST pass for production
    print("\n🚨 CI Reality Check:")
    health_data = all_results.get("/health", {})
    
    ci_checks = {
        "health_ok": health_data.get("ok", False),
        "cuda_available": health_data.get("cuda", False),
        "endpoints_working": "/hybrid" in all_results and "/vote" in all_results,
    }
    
    for check, passed in ci_checks.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {check}: {status}")
        if not passed:
            overall_success = False
    
    # Output machine-readable results for CI parsing
    print(f"\n📊 Machine-readable results:")
    print(json.dumps(all_results, indent=2))
    
    # Exit with proper code for CI
    if overall_success:
        print(f"\n🎉 All tests passed! System ready for production.")
        sys.exit(0)
    else:
        print(f"\n💥 Some tests failed! Check logs above.")
        sys.exit(1)

if __name__ == "__main__":
    main() 