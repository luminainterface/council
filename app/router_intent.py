# -*- coding: utf-8 -*-
"""
Router intent handling for SwarmAI
Manages routing requests to appropriate model heads
"""

import time
import random
from typing import List, Dict, Any, Optional
from loader.deterministic_loader import get_loaded_models, generate_response

async def route(prompt: str, heads: List[str]) -> str:
    """
    Route a prompt to the specified heads using round-robin or intelligent routing
    
    Args:
        prompt: The input prompt to process
        heads: List of model head names to use for processing
        
    Returns:
        Generated response text
    """
    
    loaded_models = get_loaded_models()
    
    # Validate requested heads are loaded
    available_heads = []
    for head in heads:
        if head in loaded_models:
            available_heads.append(head)
        else:
            print(f"⚠️ Requested head '{head}' not loaded, skipping")
    
    if not available_heads:
        raise ValueError(f"No requested heads are loaded. Available: {list(loaded_models.keys())}")
    
    # Simple round-robin selection (enhance this with smarter routing later)
    selected_head = random.choice(available_heads)
    
    # Get model info for latency simulation
    model_info = loaded_models[selected_head]
    backend = model_info.get('backend', 'mock')
    
    # Different latency characteristics per backend
    if backend == "vllm":
        base_latency = 0.08  # vLLM has higher startup cost but better batching
    elif backend == "llama_cpp":
        base_latency = 0.04  # llama.cpp is faster for single requests
    else:  # mock
        base_latency = 0.05  # Original mock latency
    
    # Add variability based on model size
    size_factor = model_info['vram_mb'] / 1000
    processing_time = base_latency + (size_factor * 0.01)
    
    # Add some randomness to simulate real inference variance
    processing_time += random.uniform(0, 0.02)
    
    # Simulate the processing time
    await asyncio_sleep(processing_time)
    
    # Generate actual response using the real inference system
    try:
        response = generate_response(selected_head, prompt, max_tokens=150)
        signature = f" [via {selected_head}]"
        full_response = response + signature
        
        print(f"🎯 Routed to {selected_head}: '{prompt[:50]}...' -> '{response[:50]}...' (backend: {backend})")
        
        return full_response
        
    except Exception as e:
        print(f"⚠️ Error with {selected_head}: {e}")
        # Fallback to mock response
        fallback_response = generate_mock_response(prompt, selected_head, model_info)
        signature = f" [via {selected_head} - fallback]"
        return fallback_response + signature

async def asyncio_sleep(duration: float):
    """Async sleep wrapper"""
    import asyncio
    await asyncio.sleep(duration)

def generate_mock_response(prompt: str, head_name: str, model_info: Dict[str, Any]) -> str:
    """
    Generate a mock response for fallback scenarios
    """
    
    # Different response styles based on model type
    if "math" in head_name.lower():
        responses = [
            "The mathematical solution is 4.",
            "Calculating step by step: 2 + 2 = 4",
            "Using arithmetic: 2 + 2 equals 4"
        ]
    elif "code" in head_name.lower():
        responses = [
            "```python\nresult = 2 + 2\nprint(result)  # Output: 4\n```",
            "Here's the code solution:\n```\nsum = a + b\n```",
            "def add(a, b): return a + b  # Returns 4 for add(2,2)"
        ]
    elif "safety" in head_name.lower():
        responses = [
            "This is a safe mathematical query. Result: 4",
            "Content approved. Answer: 2 + 2 = 4",
            "Safe response: The sum is 4"
        ]
    else:
        responses = [
            f"Processed by {head_name}: The answer is 4.",
            f"Using {model_info.get('type', 'unknown')} model: 2 + 2 = 4",
            f"Response from {head_name}: Four is the result of 2 + 2."
        ]
    
    base_response = random.choice(responses)
    return base_response

async def health_check() -> Dict[str, Any]:
    """Health check for the router"""
    loaded_models = get_loaded_models()
    
    # Analyze backend distribution
    backends = {}
    for model_info in loaded_models.values():
        backend = model_info.get('backend', 'unknown')
        backends[backend] = backends.get(backend, 0) + 1
    
    return {
        "status": "healthy",
        "loaded_models": len(loaded_models),
        "available_heads": list(loaded_models.keys()),
        "backends": backends,
        "timestamp": time.time()
    } 