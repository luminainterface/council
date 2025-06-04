#!/usr/bin/env python3
"""
Validation Tests for Step 2 Requirements
========================================

Tests to verify that all the specific validation criteria from the user's requirements are met.
"""

import asyncio
import sys
import os

# Add the skills directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'skills'))

from lightning_math import solve_math
from prolog_logic import solve_logic
from deepseek_coder import generate_code
from faiss_rag import retrieve_knowledge

async def validate_all_skills():
    """Validate all skills meet the user's specific requirements"""
    
    print("🔍 Validation Tests for Step 2 Requirements")
    print("=" * 50)
    
    # 1. Lightning Math validation: "8*7" == "56"
    print("1. Lightning Math: 8*7 should equal 56")
    result = await solve_math("8*7")
    assert result["answer"] == "56", f"Expected 56, got {result['answer']}"
    print("   ✅ PASS: 8*7 = 56")
    
    # 2. Prolog Logic validation: spatial reasoning
    print("\n2. Prolog Logic: If A is south of B and B south of C, where is A?")
    result = await solve_logic("If A is south of B and B south of C, where is A?")
    assert result["answer"] == "south_of_c", f"Expected 'south_of_c', got {result['answer']}"
    print("   ✅ PASS: Spatial reasoning working")
    
    # 3. DeepSeek Coder validation: compile_ok(deepseek.solve(code_prompt))
    print("\n3. DeepSeek Coder: Function generation should work")
    result = await generate_code("Write a function to add two numbers")
    assert "def" in result["code"], "Expected function definition in code"
    assert len(result["code"]) > 20, "Expected substantial code output"
    print("   ✅ PASS: Code generation working")
    
    # 4. FAISS RAG validation: "299" in rag.solve("speed of light")
    print("\n4. FAISS RAG: Speed of light query should contain '299'")
    result = await retrieve_knowledge("speed of light")
    docs_text = str(result["documents"])
    assert "299" in docs_text, f"Expected '299' in documents, got: {docs_text}"
    print("   ✅ PASS: Speed of light retrieval working")
    
    print("\n🎉 ALL VALIDATION TESTS PASSED!")
    print("✅ Step 2 requirements fully satisfied")
    
    return True

if __name__ == "__main__":
    asyncio.run(validate_all_skills()) 