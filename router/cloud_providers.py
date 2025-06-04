# -*- coding: utf-8 -*-
"""
Cloud Providers Module for SwarmAI Router
"""

import os
import asyncio
import aiohttp
from typing import Dict, Any, Optional, List


async def ask_cloud_council(prompt: str, model_name: str = "mistral_medium_cloud") -> Dict[str, Any]:
    """
    Route requests to cloud-based AI providers for council deliberation
    
    Args:
        prompt: The prompt to send to cloud provider
        model_name: The cloud model to use
        
    Returns:
        Dict with response data from cloud provider
    """
    # Default response structure
    response_data = {
        "response": "",
        "model_used": model_name,
        "latency_ms": 0.0,
        "cost_dollars": 0.0,
        "provider": "local_fallback",
        "error": None
    }
    
    try:
        # Check if we have cloud credentials
        openai_key = os.getenv("OPENAI_API_KEY")
        mistral_key = os.getenv("MISTRAL_API_KEY")
        
        if not openai_key and not mistral_key:
            # Fallback to local processing
            response_data["response"] = f"[Cloud unavailable - local fallback] {prompt[:100]}..."
            response_data["provider"] = "local_fallback"
            response_data["latency_ms"] = 50.0  # Simulated fast local response
            return response_data
        
        # Route to appropriate cloud provider based on model name
        if "openai" in model_name.lower() or "gpt" in model_name.lower():
            return await _ask_openai(prompt, model_name, openai_key)
        elif "mistral" in model_name.lower():
            return await _ask_mistral(prompt, model_name, mistral_key)
        else:
            # Default to local fallback for unknown models
            response_data["response"] = f"[Unknown cloud model - local fallback] Processing: {prompt[:50]}..."
            response_data["provider"] = "local_fallback"
            response_data["latency_ms"] = 75.0
            return response_data
            
    except Exception as e:
        response_data["error"] = str(e)
        response_data["response"] = f"[Cloud error - local fallback] {str(e)[:50]}..."
        response_data["provider"] = "error_fallback"
        response_data["latency_ms"] = 100.0
        return response_data


async def _ask_openai(prompt: str, model_name: str, api_key: str) -> Dict[str, Any]:
    """Call OpenAI API"""
    if not api_key:
        return {
            "response": "[OpenAI API key not available]",
            "model_used": model_name,
            "latency_ms": 0.0,
            "cost_dollars": 0.0,
            "provider": "openai_unavailable",
            "error": "No API key"
        }
    
    import time
    start_time = time.time()
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Map model names to actual OpenAI models
    model_mapping = {
        "gpt4_cloud": "gpt-4",
        "gpt35_cloud": "gpt-3.5-turbo",
        "gpt4_turbo_cloud": "gpt-4-turbo-preview"
    }
    actual_model = model_mapping.get(model_name, "gpt-3.5-turbo")
    
    payload = {
        "model": actual_model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 500,
        "temperature": 0.7
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                data = await response.json()
                
                if response.status == 200:
                    latency_ms = (time.time() - start_time) * 1000
                    response_text = data["choices"][0]["message"]["content"]
                    
                    # Estimate cost (rough approximation)
                    tokens_used = data.get("usage", {}).get("total_tokens", 100)
                    cost_dollars = (tokens_used / 1000) * 0.002  # Rough GPT-3.5 pricing
                    
                    return {
                        "response": response_text,
                        "model_used": actual_model,
                        "latency_ms": latency_ms,
                        "cost_dollars": cost_dollars,
                        "provider": "openai",
                        "error": None
                    }
                else:
                    return {
                        "response": f"[OpenAI API error: {response.status}]",
                        "model_used": actual_model,
                        "latency_ms": (time.time() - start_time) * 1000,
                        "cost_dollars": 0.0,
                        "provider": "openai_error",
                        "error": f"HTTP {response.status}"
                    }
                    
    except Exception as e:
        return {
            "response": f"[OpenAI connection error: {str(e)[:50]}]",
            "model_used": actual_model,
            "latency_ms": (time.time() - start_time) * 1000,
            "cost_dollars": 0.0,
            "provider": "openai_error",
            "error": str(e)
        }


async def _ask_mistral(prompt: str, model_name: str, api_key: str) -> Dict[str, Any]:
    """Call Mistral AI API"""
    if not api_key:
        return {
            "response": "[Mistral API key not available]",
            "model_used": model_name,
            "latency_ms": 0.0,
            "cost_dollars": 0.0,
            "provider": "mistral_unavailable",
            "error": "No API key"
        }
    
    import time
    start_time = time.time()
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Map model names to actual Mistral models
    model_mapping = {
        "mistral_medium_cloud": "mistral-medium",
        "mistral_large_cloud": "mistral-large",
        "mistral_small_cloud": "mistral-small"
    }
    actual_model = model_mapping.get(model_name, "mistral-medium")
    
    payload = {
        "model": actual_model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 500,
        "temperature": 0.7
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.mistral.ai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                data = await response.json()
                
                if response.status == 200:
                    latency_ms = (time.time() - start_time) * 1000
                    response_text = data["choices"][0]["message"]["content"]
                    
                    # Estimate cost (rough approximation)
                    tokens_used = data.get("usage", {}).get("total_tokens", 100)
                    cost_dollars = (tokens_used / 1000) * 0.003  # Rough Mistral pricing
                    
                    return {
                        "response": response_text,
                        "model_used": actual_model,
                        "latency_ms": latency_ms,
                        "cost_dollars": cost_dollars,
                        "provider": "mistral",
                        "error": None
                    }
                else:
                    return {
                        "response": f"[Mistral API error: {response.status}]",
                        "model_used": actual_model,
                        "latency_ms": (time.time() - start_time) * 1000,
                        "cost_dollars": 0.0,
                        "provider": "mistral_error",
                        "error": f"HTTP {response.status}"
                    }
                    
    except Exception as e:
        return {
            "response": f"[Mistral connection error: {str(e)[:50]}]",
            "model_used": actual_model,
            "latency_ms": (time.time() - start_time) * 1000,
            "cost_dollars": 0.0,
            "provider": "mistral_error",
            "error": str(e)
        }


def get_available_cloud_models() -> List[str]:
    """Get list of available cloud models"""
    return [
        "gpt4_cloud",
        "gpt35_cloud", 
        "gpt4_turbo_cloud",
        "mistral_medium_cloud",
        "mistral_large_cloud",
        "mistral_small_cloud"
    ]


def get_cloud_provider_status() -> Dict[str, Any]:
    """Get status of cloud providers"""
    return {
        "openai": {
            "available": bool(os.getenv("OPENAI_API_KEY")),
            "models": ["gpt4_cloud", "gpt35_cloud", "gpt4_turbo_cloud"]
        },
        "mistral": {
            "available": bool(os.getenv("MISTRAL_API_KEY")),
            "models": ["mistral_medium_cloud", "mistral_large_cloud", "mistral_small_cloud"]
        }
    } 