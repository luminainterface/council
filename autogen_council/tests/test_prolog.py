#!/usr/bin/env python3
"""Test Prolog Logic Skill"""

import asyncio
import sys
import os

# Add the skills directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'skills'))

from prolog_logic import solve_logic

async def test_prolog():
    # Test spatial reasoning
    result = await solve_logic("If A is south of B and B south of C, where is A?")
    print(f"Spatial test: {result}")
    print(f"Answer: {result['answer']}")
    print(f"Steps: {result['reasoning_steps']}")
    print()
    
    # Test family reasoning
    result = await solve_logic("Is John the parent of Mary?")
    print(f"Family test: {result}")
    print(f"Answer: {result['answer']}")
    print(f"Steps: {result['reasoning_steps']}")

if __name__ == "__main__":
    asyncio.run(test_prolog()) 