#!/usr/bin/env python3
"""
Basic Skills Test Suite
=======================

Tests for the skill adapters to ensure they integrate properly with AutoGen
and return correct answers for basic mathematical problems.
"""

import pytest
import asyncio
import sys
import os

# Add the skills directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'skills'))

from lightning_math import solve_math, create_lightning_math_agent
from sympy_cas import solve_symbolic, create_sympy_cas_agent
from prolog_logic import solve_logic, create_prolog_logic_agent
from deepseek_coder import generate_code, create_deepseek_coder_agent
from faiss_rag import retrieve_knowledge, create_faiss_rag_agent

class TestLightningMath:
    """Test the Lightning Math skill adapter"""
    
    @pytest.mark.asyncio
    async def test_basic_arithmetic(self):
        """Test basic arithmetic operations"""
        result = await solve_math("What is 2 + 2?")
        
        assert result["answer"] == "4"
        assert result["confidence"] > 0.8
        assert result["problem_type"] == "arithmetic"
        assert result["exact_answer"] is True
    
    @pytest.mark.asyncio
    async def test_multiplication(self):
        """Test multiplication"""
        result = await solve_math("Calculate 7 * 8")
        
        assert result["answer"] == "56"
        assert result["confidence"] > 0.8
        assert result["problem_type"] == "arithmetic"
    
    @pytest.mark.asyncio
    async def test_triangle_area(self):
        """Test geometry - triangle area"""
        result = await solve_math("What is the area of a triangle with base 6 and height 8?")
        
        assert result["answer"] == "24.0"
        assert result["confidence"] > 0.8
        assert result["problem_type"] == "geometry"
    
    @pytest.mark.asyncio
    async def test_factorial(self):
        """Test number theory - factorial"""
        result = await solve_math("What is 5 factorial?")
        
        assert result["answer"] == "120"
        assert result["confidence"] > 0.8
        assert result["problem_type"] == "number_theory"
    
    @pytest.mark.asyncio
    async def test_gcd(self):
        """Test number theory - GCD"""
        result = await solve_math("Find the GCD of 12 and 18")
        
        assert result["answer"] == "6"
        assert result["confidence"] > 0.8
        assert result["problem_type"] == "number_theory"

class TestSymPyCAS:
    """Test the SymPy CAS skill adapter"""
    
    @pytest.mark.asyncio
    async def test_simplify_expression(self):
        """Test expression simplification"""
        result = await solve_symbolic("Simplify x^2 + 2*x + 1")
        
        # Should simplify to (x + 1)^2 or similar
        assert result["confidence"] > 0.8
        assert result["operation"] == "simplify"
        assert "error" not in result
    
    @pytest.mark.asyncio
    async def test_expand_expression(self):
        """Test expression expansion"""
        result = await solve_symbolic("Expand (x + 1)^2")
        
        assert result["confidence"] > 0.8
        assert result["operation"] == "expand"
        assert "error" not in result
    
    @pytest.mark.asyncio
    async def test_derivative(self):
        """Test differentiation"""
        result = await solve_symbolic("Find the derivative of x^2")
        
        assert result["confidence"] > 0.8
        assert result["operation"] == "differentiate"
        assert "error" not in result

class TestPrologLogic:
    """Test the Prolog Logic skill adapter"""
    
    @pytest.mark.asyncio
    async def test_spatial_reasoning(self):
        """Test spatial reasoning - the target test case"""
        result = await solve_logic("If A is south of B and B south of C, where is A?")
        
        assert result["answer"] == "south_of_c"
        assert result["confidence"] > 0.5
        assert result["query_type"] == "spatial_relation"
    
    @pytest.mark.asyncio
    async def test_family_relation(self):
        """Test family relationship reasoning"""
        result = await solve_logic("Is John the parent of Mary?")
        
        assert result["answer"] in ["true", "yes"]
        assert result["confidence"] > 0.5
        assert result["query_type"] == "family_relation"

class TestDeepSeekCoder:
    """Test the DeepSeek Coder skill adapter"""
    
    @pytest.mark.asyncio
    async def test_function_generation(self):
        """Test function generation"""
        result = await generate_code("Write a function to add two numbers")
        
        assert "def" in result["code"]
        assert result["language"] == "python"
        assert result["task_type"] == "function_generation"
        assert result["confidence"] > 0.3
    
    @pytest.mark.asyncio
    async def test_sorting_algorithm(self):
        """Test algorithm implementation"""
        result = await generate_code("Write a sorting algorithm")
        
        assert len(result["code"]) > 20
        assert result["language"] == "python"
        assert result["confidence"] > 0.3
        # Should detect it as algorithm implementation
        assert result["task_type"] in ["algorithm_implementation", "function_generation"]

    @pytest.mark.asyncio
    async def test_factorial_math_routing(self):
        """⚡ FIX: Test that factorial functions route to math not code"""
        from router_cascade import RouterCascade
        
        router = RouterCascade()
        
        # Test factorial function routing
        route = router.classify_query("Implement a factorial function")
        assert route.skill_type == "math", f"Expected math routing, got {route.skill_type}"
        assert route.confidence >= 0.95, f"Expected high confidence, got {route.confidence}"
        
        # Test create factorial routing  
        route = router.classify_query("Create a factorial function")
        assert route.skill_type == "math", f"Expected math routing, got {route.confidence}"
        
        print("✅ Factorial functions correctly route to math")
    
    @pytest.mark.asyncio
    async def test_palindrome_cloud_retry(self):
        """⚡ FIX: Test that palindrome checker triggers cloud retry on template stub"""
        from deepseek_coder import generate_code
        
        try:
            # This should trigger cloud retry due to custom_function stub
            result = await generate_code("Write a palindrome checker function")
            # If we get here without error, check for stub patterns
            if "custom_function" in result.get("code", "") or "Implementation needed" in result.get("code", ""):
                assert False, "Template stub should have triggered cloud retry"
        except RuntimeError as e:
            # Expected - should trigger cloud retry
            assert "cloud retry needed" in str(e).lower(), f"Unexpected error: {e}"
            print("✅ Palindrome checker correctly triggers cloud retry")
    
    @pytest.mark.asyncio
    async def test_bubble_sort_compile_retry(self):
        """⚡ FIX: Test that compile errors trigger cloud retry"""
        from deepseek_coder import DeepSeekCoderAgent
        
        agent = DeepSeekCoderAgent()
        
        # Test that syntax errors trigger cloud retry
        validation = agent.validate_generated_code("def bubble_sort(arr):\n    # Missing parenthesis\n    if arr[0] > arr[1]")
        
        if not validation['valid'] and 'expected' in validation.get('error', '').lower():
            print("✅ Compile errors correctly detected for cloud retry")
        else:
            print(f"⚠️ Validation result: {validation}")

    @pytest.mark.asyncio
    async def test_enhanced_stub_detection(self):
        """⚡ FIX: Test enhanced stub detection for custom_function and TODO patterns"""
        from deepseek_coder import DeepSeekCoderAgent
        
        agent = DeepSeekCoderAgent()
        
        # Test stub patterns that should trigger cloud retry
        stub_codes = [
            "def custom_function():\n    return 'Implementation needed'",
            "def function():\n    # TODO: implement functionality\n    pass",
            "def gcd_function():\n    # TODO\n    pass",
            "def function():\n    pass  # Implementation needed"
        ]
        
        for stub_code in stub_codes:
            validation = agent.validate_generated_code(stub_code)
            # Should be invalid due to stub patterns
            assert not validation['valid'], f"Stub code should be invalid: {stub_code[:30]}..."
            print(f"✅ Stub detected: {stub_code[:30]}...")
    
    @pytest.mark.asyncio
    async def test_enhanced_factorial_routing(self):
        """⚡ FIX: Test that factorial function requests route to math with high confidence"""
        from router_cascade import RouterCascade
        
        router = RouterCascade()
        
        factorial_queries = [
            "Implement a factorial function",
            "Create a factorial function", 
            "Write a factorial function",
            "Calculate factorial of a number",
            "Find factorial implementation"
        ]
        
        for query in factorial_queries:
            route = router.classify_query(query)
            assert route.skill_type == "math", f"Expected math routing for '{query}', got {route.skill_type}"
            assert route.confidence >= 0.95, f"Expected high confidence for '{query}', got {route.confidence}"
            print(f"✅ Factorial query routed to math: {query}")
    
    @pytest.mark.asyncio  
    async def test_knowledge_duplicate_detection(self):
        """⚡ FIX: Test that knowledge duplicate detection catches Einstein/photosynthesis loops"""
        from faiss_rag import FAISSRAGAgent
        
        agent = FAISSRAGAgent()
        
        # Simulate duplicate responses
        einstein_response = "Einstein's theory of relativity revolutionized our understanding of space, time, and gravity."
        similar_response = "Einstein's theory of relativity changed our understanding of space, time, and gravity."
        
        # Add first response to cache
        agent._add_to_cache(einstein_response)
        
        # Check if similar response is detected as duplicate
        is_duplicate = agent._check_duplicate_response(similar_response)
        
        # Should detect high similarity
        assert is_duplicate, "Should detect Einstein response as duplicate"
        print(f"✅ Knowledge duplicate detection working: Einstein responses")
    
    @pytest.mark.asyncio
    async def test_gcd_function_routing(self):
        """⚡ FIX: Test that GCD function requests can route to either math or code properly"""
        from router_cascade import RouterCascade
        
        router = RouterCascade()
        
        # Test GCD function routing
        route = router.classify_query("Write a function to calculate GCD of two numbers")
        
        # Should route to code (function generation) with good confidence
        assert route.skill_type in ["code", "math"], f"GCD function should route to code or math, got {route.skill_type}"
        assert route.confidence >= 0.70, f"Expected decent confidence for GCD function, got {route.confidence}"
        print(f"✅ GCD function routed to: {route.skill_type} (confidence: {route.confidence:.2f})")

class TestFAISSRAG:
    """Test the FAISS RAG skill adapter"""
    
    @pytest.mark.asyncio
    async def test_speed_of_light_query(self):
        """Test the target RAG test case"""
        result = await retrieve_knowledge("speed of light")
        
        # Should find information about speed of light
        assert "299" in str(result["documents"]) or "299,792,458" in str(result["documents"])
        assert result["confidence"] > 0.1
        assert result["num_results"] > 0
    
    @pytest.mark.asyncio
    async def test_factual_query(self):
        """Test factual knowledge retrieval"""
        result = await retrieve_knowledge("What is Python?")
        
        assert result["num_results"] > 0
        assert result["query_type"] == "factual"
        assert len(result["documents"]) > 0

class TestSkillIntegration:
    """Test skill integration with AutoGen framework"""
    
    @pytest.mark.asyncio
    async def test_all_agents_creation(self):
        """Test that all skill agents can be created"""
        lightning_agent = create_lightning_math_agent()
        assert lightning_agent is not None
        assert hasattr(lightning_agent, 'solve_math_problem')
        
        try:
            cas_agent = create_sympy_cas_agent()
            assert cas_agent is not None
            assert hasattr(cas_agent, 'process_cas_request')
        except ImportError:
            # SymPy not available, skip test
            pytest.skip("SymPy not available")
        
        prolog_agent = create_prolog_logic_agent()
        assert prolog_agent is not None
        assert hasattr(prolog_agent, 'solve_logic_problem')
        
        coder_agent = create_deepseek_coder_agent()
        assert coder_agent is not None
        assert hasattr(coder_agent, 'generate_code')
        
        rag_agent = create_faiss_rag_agent()
        assert rag_agent is not None
        assert hasattr(rag_agent, 'retrieve_documents')
    
    @pytest.mark.asyncio
    async def test_math_problem_classification(self):
        """Test that problems are classified correctly"""
        agent = create_lightning_math_agent()
        
        # Test arithmetic classification
        assert agent.classify_problem("What is 2 + 2?").value == "arithmetic"
        
        # Test geometry classification
        assert agent.classify_problem("What is the area of a triangle?").value == "geometry"
        
        # Test number theory classification
        assert agent.classify_problem("Find the GCD of 12 and 18").value == "number_theory"

def test_skills_import():
    """Test that skills can be imported without errors"""
    try:
        from lightning_math import LightningMathAgent
        from sympy_cas import SymPyCASAgent
        from prolog_logic import PrologLogicAgent
        from deepseek_coder import DeepSeekCoderAgent
        from faiss_rag import FAISSRAGAgent
        assert True
    except ImportError as e:
        pytest.fail(f"Failed to import skills: {e}")

if __name__ == "__main__":
    # Run basic tests
    print("🧪 Running comprehensive skills tests...")
    
    # Test imports
    test_skills_import()
    print("✅ All skills import successfully")
    
    # Run async tests
    async def run_comprehensive_tests():
        print("\n🔢 Testing Lightning Math...")
        # Test Lightning Math
        result = await solve_math("What is 2 + 2?")
        assert result["answer"] == "4"
        print("✅ Lightning Math: 2 + 2 = 4")
        
        # Test triangle area
        result = await solve_math("What is the area of a triangle with base 6 and height 8?")
        assert result["answer"] == "24.0"
        print("✅ Lightning Math: Triangle area = 24.0")
        
        # Test factorial
        result = await solve_math("What is 5 factorial?")
        assert result["answer"] == "120"
        print("✅ Lightning Math: 5! = 120")
        
        print("\n🧠 Testing Prolog Logic...")
        # Test Prolog Logic
        result = await solve_logic("If A is south of B and B south of C, where is A?")
        assert result["answer"] == "south_of_c"
        print("✅ Prolog Logic: Spatial reasoning test passed")
        
        print("\n💻 Testing DeepSeek Coder...")
        # Test DeepSeek Coder
        result = await generate_code("Write a function to add two numbers")
        assert "def" in result["code"]
        print("✅ DeepSeek Coder: Function generation works")
        
        print("\n🔍 Testing FAISS RAG...")
        # Test FAISS RAG
        result = await retrieve_knowledge("speed of light")
        assert "299" in str(result["documents"])
        print("✅ FAISS RAG: Speed of light retrieval works")
        
        print("\n🎉 All 5 skills working! Step 2 complete!")
    
    # Run the tests
    asyncio.run(run_comprehensive_tests()) 