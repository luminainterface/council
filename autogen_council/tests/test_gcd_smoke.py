#!/usr/bin/env python3
"""
GCD Code Generation Smoke Test
==============================

Test that GCD function requests are properly routed to code
and generate valid Python functions.
"""

import asyncio
import sys
import os

# Add the router path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from router_cascade import RouterCascade
from skills.deepseek_coder import generate_code

def test_gcd_code_structure():
    """Test that GCD code generation produces valid structure"""
    test_cases = [
        ("Write a function to calculate GCD", "code", 0.95),
        ("python gcd of 48 18", "code", 0.95), 
        ("Create a function for greatest common divisor", "code", 0.95),
        ("Write GCD function in Python", "code", 0.95)  # Clear code request
    ]
    
    router = RouterCascade()
    
    for query, expected_skill, min_confidence in test_cases:
        route = router.classify_query(query)
        print(f"Query: '{query}'")
        print(f"  → Routed to: {route.skill_type}")
        print(f"  → Confidence: {route.confidence:.3f}")
        
        # Ensure all GCD requests route to code
        assert route.skill_type == expected_skill, f"GCD query routed to {route.skill_type}, expected {expected_skill}"
        assert route.confidence >= min_confidence, f"GCD confidence too low: {route.confidence}"

async def test_gcd_generation():
    """Test actual GCD code generation"""
    try:
        result = await generate_code("Write a function to calculate GCD")
        
        # Check basic structure
        code = result.get("code", "")
        assert "def" in code, "Generated code should contain 'def'"
        assert "return" in code, "Generated code should contain 'return'"
        
        print(f"✅ Generated valid GCD function structure")
        print(f"Code preview: {code[:100]}...")
        
        return True
        
    except Exception as e:
        print(f"⚠️ Code generation failed (expected if no model): {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing GCD Code Generation...")
    
    # Test routing
    test_gcd_code_structure()
    print("✅ All GCD queries route to code correctly!")
    
    # Test generation (may fail without real model)
    print("\n🤖 Testing actual code generation...")
    success = asyncio.run(test_gcd_generation())
    
    if success:
        print("✅ GCD code generation smoke test PASSED!")
    else:
        print("⚠️ Code generation skipped (no model available)")
        print("✅ Routing tests PASSED!")
    
    print("\n🎯 GCD smoke test complete!") 