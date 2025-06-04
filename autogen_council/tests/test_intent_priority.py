#!/usr/bin/env python3
"""
Intent Priority Regression Tests
================================

Tests to ensure math queries override generic knowledge queries
and prevent regression of the routing priority bug.
"""

import pytest
import sys
import os

# Add the router path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from router_cascade import RouterCascade

class TestIntentPriority:
    """Test intent classification priority"""
    
    def test_math_overrides_knowledge(self):
        """Math queries should route to math, not knowledge"""
        router = RouterCascade()
        
        # The critical test case that was broken
        route = router.classify_query("What is the square root of 64?")
        assert route.skill_type == "math", f"Expected math, got {route.skill_type}"
        assert route.confidence > 0.1, f"Math confidence too low: {route.confidence}"
    
    def test_specific_math_patterns(self):
        """Specific math patterns should all route to math"""
        router = RouterCascade()
        
        math_queries = [
            "What is the square root of 64?",
            "Calculate 8 factorial", 
            "Find the GCD of 12 and 18",
            "What is 2 + 2?",
            "Solve x^2 - 5x + 6 = 0",
            "What is log base 10 of 1000?"
        ]
        
        for query in math_queries:
            route = router.classify_query(query)
            assert route.skill_type == "math", f"Query '{query}' routed to {route.skill_type}, expected math"
    
    def test_knowledge_still_works(self):
        """Knowledge queries should still route to knowledge"""
        router = RouterCascade()
        
        knowledge_queries = [
            "What is DNA?",
            "Explain quantum entanglement",
            "Describe photosynthesis",
            "What is the speed of light?"
        ]
        
        for query in knowledge_queries:
            route = router.classify_query(query)
            assert route.skill_type == "knowledge", f"Query '{query}' routed to {route.skill_type}, expected knowledge"
    
    def test_no_ambiguous_routing(self):
        """Math-like queries should never route to knowledge"""
        router = RouterCascade()
        
        # These should NEVER go to knowledge
        math_disguised_queries = [
            "What is the factorial of 5?",
            "What is sqrt(16)?", 
            "What is 2^3?",
            "What is the GCD of 6 and 9?"
        ]
        
        for query in math_disguised_queries:
            route = router.classify_query(query)
            assert route.skill_type != "knowledge", f"Query '{query}' incorrectly routed to knowledge"
    
    def test_logic_priority(self):
        """⚡ FIX: Logic queries should route to logic with weighted patterns"""
        router = RouterCascade()
        
        # The target test case from user request
        route = router.classify_query("If all A are B and all B are C, where is A?")
        assert route.skill_type == "logic", f"Expected logic, got {route.skill_type}"
        assert route.confidence >= 0.85, f"Logic confidence too low: {route.confidence}"
        
        # Additional logic queries that should have high confidence
        logic_queries = [
            "If all A are B and all B are C, where is A?",
            "Therefore, the conclusion is true",
            "Either it rains or it shines",
            "This is a syllogism with two premises",
            "If John is taller than Mary, and Mary is taller than Bob, who is tallest?"
        ]
        
        for query in logic_queries:
            route = router.classify_query(query)
            assert route.skill_type == "logic", f"Query '{query}' routed to {route.skill_type}, expected logic"
            
    def test_confidence_hierarchy(self):
        """Math patterns should have reasonable confidence"""
        router = RouterCascade()
        
        # Test the original problematic query
        route = router.classify_query("What is the square root of 64?")
        
        # Should be math with decent confidence
        assert route.skill_type == "math"
        assert route.confidence >= 0.15, f"Math confidence too low: {route.confidence}"
        
        # Should have multiple pattern matches
        assert len(route.patterns_matched) >= 2, f"Should match multiple patterns, got: {route.patterns_matched}"

class TestCodeGeneration:
    """⚡ NEW: Test code generation routing and basic functionality"""
    
    def test_gcd_code_routing(self):
        """GCD function requests should route to code"""
        router = RouterCascade()
        
        gcd_queries = [
            "Write a function to calculate GCD",
            "python gcd of 48 18",
            "Create a function for greatest common divisor",
            "Implement GCD algorithm"
        ]
        
        for query in gcd_queries:
            route = router.classify_query(query)
            assert route.skill_type == "code", f"Query '{query}' routed to {route.skill_type}, expected code"
            assert route.confidence >= 0.7, f"Code confidence too low for '{query}': {route.confidence}"

if __name__ == "__main__":
    # Run basic test
    print("🧪 Testing Intent Priority...")
    
    router = RouterCascade()
    route = router.classify_query("What is the square root of 64?")
    
    print(f"Query: 'What is the square root of 64?'")
    print(f"  → Skill: {route.skill_type}")
    print(f"  → Confidence: {route.confidence:.3f}")
    print(f"  → Patterns: {route.patterns_matched}")
    
    if route.skill_type == "math" and route.confidence > 0.1:
        print("✅ Intent priority test PASSED!")
    else:
        print("❌ Intent priority test FAILED!")
        exit(1)
        
    # Test logic priority
    route = router.classify_query("If all A are B and all B are C, where is A?")
    print(f"\nQuery: 'If all A are B and all B are C, where is A?'")
    print(f"  → Skill: {route.skill_type}")
    print(f"  → Confidence: {route.confidence:.3f}")
    print(f"  → Patterns: {route.patterns_matched}")
    
    if route.skill_type == "logic" and route.confidence >= 0.85:
        print("✅ Logic priority test PASSED!")
    else:
        print("❌ Logic priority test FAILED!")
        exit(1)
        
    # Test GCD code routing
    route = router.classify_query("Write a function to calculate GCD")
    print(f"\nQuery: 'Write a function to calculate GCD'")
    print(f"  → Skill: {route.skill_type}")
    print(f"  → Confidence: {route.confidence:.3f}")
    print(f"  → Patterns: {route.patterns_matched}")
    
    if route.skill_type == "code" and route.confidence >= 0.7:
        print("✅ GCD code routing test PASSED!")
    else:
        print("❌ GCD code routing test FAILED!")
        exit(1) 