#!/usr/bin/env python3
"""Direct API test for stub detection"""

import requests
import json

BASE_URL = "http://localhost:8001"

def test_stub_api(prompt):
    """Test a single prompt via API"""
    try:
        response = requests.post(
            f"{BASE_URL}/hybrid",
            json={"prompt": prompt},
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            return {
                "success": True,
                "confidence": result.get("confidence", -1),
                "text": result.get("text", ""),
                "full_response": result
            }
        else:
            return {
                "success": False,
                "error": f"HTTP {response.status_code}: {response.text[:100]}"
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# Test cases
test_cases = [
    "template this needs custom_function",
    "todo: implement unsupported number theory",
    "hello world normal query"
]

print("🔧 Direct API Stub Detection Test")
print("=" * 50)

for i, prompt in enumerate(test_cases):
    print(f"\nTest {i+1}: '{prompt}'")
    result = test_stub_api(prompt)
    
    if result["success"]:
        confidence = result["confidence"]
        text = result["text"][:50]
        print(f"  ✅ Success: confidence={confidence:.2f}")
        print(f"  Response: {text}...")
        
        if "template" in prompt or "todo" in prompt:
            if confidence <= 0.1:
                print(f"  ✅ Stub detection WORKING (conf≤0.1)")
            else:
                print(f"  ❌ Stub detection FAILED (conf={confidence:.2f})")
        else:
            print(f"  ℹ️ Normal query (expected high confidence)")
    else:
        print(f"  ❌ Failed: {result['error']}") 