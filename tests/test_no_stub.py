"""
Test for stub marker detection to ensure template responses are properly caught
"""
import pytest
import asyncio
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from router_cascade import RouterCascade


@pytest.mark.asyncio
class TestStubDetection:
    """Test that stub markers properly detect template code"""
    
    @pytest.fixture
    def router(self):
        """Create router instance for testing"""
        return RouterCascade()
    
    async def test_custom_function_stub(self, router):
        """Test that 'custom_function' triggers stub detection"""
        result = await router.route_query("def custom_function():")
        
        # Should return confidence 0 for stub code
        assert result["confidence"] == 0.0, f"Expected confidence 0, got {result['confidence']}"
        assert "custom_function" in result.get("text", "").lower() or "stub" in result.get("text", "").lower()
    
    async def test_todo_stub(self, router):
        """Test that 'TODO' triggers stub detection"""
        result = await router.route_query("# TODO: implement this function")
        
        # Should return confidence 0 for stub code
        assert result["confidence"] == 0.0, f"Expected confidence 0, got {result['confidence']}"
    
    async def test_template_stub(self, router):
        """Test that 'template' triggers stub detection"""
        result = await router.route_query("This is a template response")
        
        # Should return confidence 0 for stub code
        assert result["confidence"] == 0.0, f"Expected confidence 0, got {result['confidence']}"
    
    async def test_valid_code_not_stub(self, router):
        """Test that real code doesn't trigger stub detection"""
        result = await router.route_query("def factorial(n): return 1 if n <= 1 else n * factorial(n-1)")
        
        # Should return normal confidence for real code
        assert result["confidence"] > 0.0, f"Expected confidence > 0, got {result['confidence']}"
    
    async def test_math_query_not_stub(self, router):
        """Test that math queries don't trigger stub detection"""
        result = await router.route_query("What is 2 + 2?")
        
        # Should return normal confidence for math
        assert result["confidence"] > 0.0, f"Expected confidence > 0, got {result['confidence']}"


if __name__ == "__main__":
    # Run tests directly
    async def run_tests():
        router = RouterCascade()
        
        # Test cases from the checklist
        test_cases = [
            ("def custom_function()", "Should detect stub"),
            ("# TODO: implement", "Should detect stub"),
            ("template response", "Should detect stub"),
            ("What is 2+2?", "Should be normal"),
        ]
        
        print("🧪 Running stub detection tests...")
        for query, description in test_cases:
            result = await router.route_query(query)
            confidence = result.get("confidence", -1)
            print(f"  Query: '{query}' -> Confidence: {confidence} ({description})")
            
            if "stub" in description.lower() and confidence != 0.0:
                print(f"    ❌ FAIL: Expected confidence 0, got {confidence}")
            elif "normal" in description.lower() and confidence <= 0.0:
                print(f"    ❌ FAIL: Expected confidence > 0, got {confidence}")
            else:
                print(f"    ✅ PASS")
    
    asyncio.run(run_tests()) 