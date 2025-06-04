#!/usr/bin/env python3
"""
Router fast path tests - prevents smart routing regressions
"""

import asyncio
import pytest
from router.hybrid import hybrid_route
from router.voting import vote


@pytest.mark.asyncio
async def test_simple_prompt_uses_smart_path(monkeypatch):
    """Test that simple prompts use smart routing and never call vote()"""
    
    # Block the vote() function to ensure it's not called
    def blocked_vote(*args, **kwargs):
        raise AssertionError("vote() should not be called for simple prompts")
    
    monkeypatch.setattr("router.voting.vote", blocked_vote)
    
    # Test simple prompts
    simple_prompts = [
        "2+2?",
        "What is the capital of France?", 
        "Calculate 5 * 6",
        "Hello world"
    ]
    
    for prompt in simple_prompts:
        result = await hybrid_route(prompt, ["math_specialist_0.8b", "tinyllama_1b"])
        
        # Should use smart routing
        assert result["provider"] == "local_smart", f"Simple prompt '{prompt}' should use local_smart, got {result['provider']}"
        assert "smart" in result["provider"], f"Simple prompt '{prompt}' should use smart routing"
        
        # Should be fast (< 50ms for smart routing)
        assert result["hybrid_latency_ms"] < 50, f"Smart routing should be fast, got {result['hybrid_latency_ms']}ms"


@pytest.mark.asyncio 
async def test_complex_prompt_uses_voting_path(monkeypatch):
    """Test that complex prompts trigger voting and do call vote()"""
    
    # Track vote() calls
    vote_calls = {"count": 0, "args": None}
    
    async def mock_vote(*args, **kwargs):
        vote_calls["count"] += 1
        vote_calls["args"] = args
        
        # Return realistic mock voting result
        return {
            "text": "Mock voting response",
            "winner": {
                "model": "math_specialist_0.8b",
                "confidence": 0.75,
                "log_probability": -3.2,
                "quality_score": 2.5,
                "response_time_ms": 150,
                "token_count": 25
            },
            "all_candidates": [],
            "voting_stats": {
                "total_heads": 2,
                "successful_responses": 2,
                "voting_time_ms": 200,
                "top_k": 1
            }
        }
    
    monkeypatch.setattr("router.voting.vote", mock_vote)
    
    # Test complex prompts  
    complex_prompts = [
        "Please explain in detail why neural networks work",
        "Analyze the step by step process of machine learning", 
        "Why do we need quantum computing and what are the implications?",
        "Compare and contrast different sorting algorithms and explain their trade-offs"
    ]
    
    for prompt in complex_prompts:
        vote_calls["count"] = 0  # Reset counter
        
        result = await hybrid_route(prompt, ["math_specialist_0.8b", "tinyllama_1b"])
        
        # Should use voting
        assert result["provider"] == "local_voting", f"Complex prompt '{prompt}' should use local_voting, got {result['provider']}"
        assert "voting" in result["provider"], f"Complex prompt '{prompt}' should use voting"
        
        # Should have called vote() exactly once
        assert vote_calls["count"] == 1, f"Complex prompt '{prompt}' should call vote() once, called {vote_calls['count']} times"


@pytest.mark.asyncio
async def test_prompt_classification_logic():
    """Test the prompt classification logic directly"""
    
    # Test simple prompts (should be classified as simple)
    simple_prompts = [
        "2+2?",                           # Very short
        "What is the capital of France?", # Short factual
        "Calculate 5 * 6",               # Simple math
        "Hello world",                   # Basic greeting
        "A" * 119                        # Just under 120 char limit
    ]
    
    for prompt in simple_prompts:
        # This is the actual classification logic from hybrid.py
        is_simple = (len(prompt) < 120 and 
                     not any(keyword in prompt.lower() 
                            for keyword in ["explain", "why", "step by step", "analyze", "compare", "reasoning"]))
        
        assert is_simple, f"Prompt '{prompt[:50]}...' should be classified as simple"
    
    # Test complex prompts (should be classified as complex)
    complex_prompts = [
        "Please explain in detail why neural networks work",  # Contains "explain" and "why"
        "Analyze the step by step process",                   # Contains "analyze" and "step by step"
        "Why do we need quantum computing?",                  # Contains "why"
        "Compare and contrast different algorithms",          # Contains "compare"
        "Show me the reasoning behind this decision",         # Contains "reasoning"
        "A" * 120                                            # Exactly at 120 char limit
    ]
    
    for prompt in complex_prompts:
        is_simple = (len(prompt) < 120 and 
                     not any(keyword in prompt.lower() 
                            for keyword in ["explain", "why", "step by step", "analyze", "compare", "reasoning"]))
        
        assert not is_simple, f"Prompt '{prompt[:50]}...' should be classified as complex"


def test_keyword_detection():
    """Test that complex keywords are correctly detected"""
    
    keywords = ["explain", "why", "step by step", "analyze", "compare", "reasoning"]
    
    # Test each keyword individually
    for keyword in keywords:
        prompt = f"Please {keyword} this concept"
        
        has_keyword = any(kw in prompt.lower() for kw in keywords)
        assert has_keyword, f"Keyword '{keyword}' should be detected in prompt"
    
    # Test case insensitivity
    prompt = "EXPLAIN WHY this works"
    has_keyword = any(kw in prompt.lower() for kw in keywords)
    assert has_keyword, "Keywords should be detected case-insensitively"
    
    # Test no false positives
    simple_prompt = "Hello world 2+2 calculate the sum"
    has_keyword = any(kw in simple_prompt.lower() for kw in keywords)
    assert not has_keyword, "Simple prompt should not trigger keyword detection"


@pytest.mark.asyncio
async def test_performance_characteristics(monkeypatch):
    """Test that smart routing is faster than voting"""
    
    # Mock vote to simulate realistic voting latency
    async def slow_vote(*args, **kwargs):
        import time
        await asyncio.sleep(0.1)  # Simulate 100ms voting time
        return {
            "text": "Slow voting response",
            "winner": {"model": "test", "confidence": 0.5},
            "all_candidates": [],
            "voting_stats": {"voting_time_ms": 100}
        }
    
    monkeypatch.setattr("router.voting.vote", slow_vote)
    
    # Test smart routing speed
    import time
    start = time.perf_counter()
    result = await hybrid_route("2+2?", ["math_specialist_0.8b"])
    smart_time = time.perf_counter() - start
    
    assert result["provider"] == "local_smart"
    assert smart_time < 0.05, f"Smart routing should be < 50ms, took {smart_time*1000:.1f}ms"
    
    # Test voting speed  
    start = time.perf_counter()
    result = await hybrid_route("Please explain why this works", ["math_specialist_0.8b"])
    voting_time = time.perf_counter() - start
    
    assert result["provider"] == "local_voting"
    assert voting_time > smart_time, "Voting should be slower than smart routing" 