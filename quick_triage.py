#!/usr/bin/env python3
"""
Fast triage script to check for template/stub leaks
Based on the user's debug checklist
"""

import json
import requests
import sys
import re

def test_endpoint(endpoint_url: str):
    """Test the Router endpoint for stub leaks"""
    tests = [
        "hi", 
        "2+2", 
        "Write a python factorial", 
        "Unsupported edge case",
        "def custom_function(): pass",
        "Hello! I can help you with anything"
    ]
    
    print(f"🔍 Testing endpoint: {endpoint_url}")
    print("=" * 80)
    
    for q in tests:
        try:
            # Try both /hybrid and /vote endpoints
            for endpoint in ["/hybrid", "/vote"]:
                url = f"{endpoint_url}{endpoint}"
                print(f"\n📤 Query: {q[:20]:<25}")
                
                try:
                    if endpoint == "/vote":
                        payload = {"prompt": q, "session_id": "test_session"}
                    else:
                        payload = {"query": q}
                    
                    r = requests.post(url, json=payload, timeout=10.0)
                    
                    if r.status_code == 200:
                        result = r.json()
                        txt = result.get("text", "")[:120]
                        skill_type = result.get("skill_type", result.get("specialist", "unknown"))
                        confidence = result.get("confidence", 0.0)
                        
                        # Check for stubs
                        stub_patterns = [
                            "todo", "template", "custom_function", "placeholder",
                            "def function():", "pass", "not implemented",
                            "hello! i can help", "i am an ai", "how can i assist"
                        ]
                        
                        stub = any(p in txt.lower() for p in stub_patterns)
                        
                        print(f"   {endpoint}: {skill_type} | conf={confidence:.2f} | stub={stub}")
                        print(f"   Text: {txt}")
                        
                        if stub:
                            print(f"   🚨 STUB DETECTED! Check patterns in Router")
                    else:
                        print(f"   {endpoint}: ERROR {r.status_code} - {r.text[:50]}")
                        
                except requests.exceptions.RequestException as e:
                    print(f"   {endpoint}: CONNECTION ERROR - {str(e)[:50]}")
                    
        except Exception as e:
            print(f"   ERROR: {e}")
    
    print("\n" + "=" * 80)
    print("🎯 Expected results:")
    print("   - Agent-0 for 'hi', '2+2'")
    print("   - code_specialist (real answer) for factorial")
    print("   - Cloud fallback or UNSURE for unknown edge")
    print("   - CloudRetry for any stub==True")

if __name__ == "__main__":
    # Test localhost first
    base_url = "http://localhost:8000"
    test_endpoint(base_url) 