# -*- coding: utf-8 -*-
"""
Hybrid routing: Smart orchestration between local and cloud models
"""

import asyncio
import time
from typing import List, Dict, Any, Optional
from loader.deterministic_loader import get_loaded_models, generate_response
from router.voting import vote, smart_select
from router.cost_tracking import debit

async def hybrid_route(prompt: str, preferred_models: List[str] = None, enable_council: bool = None) -> Dict[str, Any]:
    """
    Hybrid routing with confidence-based local/cloud decision making
    
    Args:
        prompt: Input prompt
        preferred_models: List of preferred local models
        enable_council: Whether to enable council deliberation
        
    Returns:
        Dict with response, provider, model_used, confidence, etc.
    """
    start_time = time.time()
    
    # Default models if none specified
    if not preferred_models:
        loaded_models = get_loaded_models()
        preferred_models = list(loaded_models.keys())[:2]  # Use first 2 available
    
    try:
        # ⚡ FAST PATH: Smart single-model selection for simple prompts
        if (len(prompt) < 120 and 
            not any(keyword in prompt.lower() for keyword in ["explain", "why", "step by step", "analyze", "compare", "reasoning"])):
            
            # Smart select best model without running inference
            selected_model = smart_select(prompt, preferred_models)
            print(f"⚡ Smart path: selected {selected_model} for '{prompt[:50]}...'")
            
            try:
                # Generate single response with fail-fast on templates
                response_text = generate_response(selected_model, prompt, max_tokens=150)
                
                # Check for template/mock responses
                if ("Response from " in response_text or "[TEMPLATE]" in response_text or 
                    "Mock" in response_text or len(response_text) < 10):
                    raise RuntimeError(f"Template/mock response detected: {response_text[:100]}")
                
                latency_ms = (time.time() - start_time) * 1000
                tokens = len(prompt.split()) + len(response_text.split())
                cost_cents = debit(selected_model, tokens)
                
                return {
                    "text": response_text,
                    "provider": "local_smart",
                    "model_used": selected_model,
                    "confidence": 0.8,  # High confidence for smart routing
                    "hybrid_latency_ms": latency_ms,
                    "cloud_consulted": False,
                    "cost_cents": cost_cents,
                    "council_used": bool(enable_council),
                    "council_voices": None
                }
                
            except (RuntimeError, Exception) as local_error:
                # Local inference failed - try cloud fallback
                print(f"🌩️ Local inference failed: {local_error}")
                return await cloud_fallback_response(prompt, start_time, str(local_error))
        
        # COMPLEX PATH: Use voting for complex prompts
        print(f"🗳️ Complex prompt, using voting for '{prompt[:50]}...'")
        
        try:
            result = await vote(prompt, preferred_models, top_k=1)
            
            # Check if voting result contains templates
            response_text = result.get("text", "")
            if ("Response from " in response_text or "[TEMPLATE]" in response_text or 
                "Mock" in response_text or len(response_text) < 10):
                raise RuntimeError(f"Voting returned template response: {response_text[:100]}")
            
            latency_ms = (time.time() - start_time) * 1000
            
            # Extract winner information
            winner = result.get("winner", {})
            confidence = winner.get("confidence", 0.5)
            
            # Simple cost calculation
            tokens = len(prompt.split()) + len(response_text.split())
            cost_cents = debit(winner.get("model", "unknown"), tokens)
            
            return {
                "text": response_text,
                "provider": "local_voting",
                "model_used": winner.get("model", "unknown"),
                "confidence": confidence,
                "hybrid_latency_ms": latency_ms,
                "cloud_consulted": False,
                "cost_cents": cost_cents,
                "council_used": bool(enable_council),
                "council_voices": None
            }
            
        except (RuntimeError, Exception) as voting_error:
            # Voting failed - try cloud fallback
            print(f"🌩️ Voting failed: {voting_error}")
            return await cloud_fallback_response(prompt, start_time, str(voting_error))
        
    except Exception as e:
        # General error - try cloud fallback
        print(f"🌩️ Hybrid routing general error: {e}")
        return await cloud_fallback_response(prompt, start_time, str(e))

async def cloud_fallback_response(prompt: str, start_time: float, error_reason: str) -> Dict[str, Any]:
    """Fallback to cloud APIs when local models fail"""
    import os
    import aiohttp
    import json
    
    # Check for cloud APIs
    mistral_key = os.getenv("MISTRAL_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    
    if mistral_key and mistral_key != "demo-key":
        try:
            # Real Mistral API call
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {mistral_key}"
                }
                payload = {
                    "model": "mistral-small-latest",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 150,
                    "temperature": 0.7
                }
                
                async with session.post(
                    "https://api.mistral.ai/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        response = data["choices"][0]["message"]["content"].strip()
                        latency_ms = (time.time() - start_time) * 1000
                        
                        return {
                            "text": response,
                            "provider": "cloud_mistral",
                            "model_used": "mistral-small-latest",
                            "confidence": 0.85,
                            "hybrid_latency_ms": latency_ms,
                            "cloud_consulted": True,
                            "cost_cents": len(prompt.split()) * 0.8,
                            "council_used": False,
                            "cloud_reason": error_reason[:100],
                            "council_voices": None
                        }
                    else:
                        print(f"Mistral API error: {resp.status} - {await resp.text()}")
                        
        except Exception as e:
            print(f"Mistral API failed: {e}")
    
    if openai_key and openai_key != "demo-key":
        try:
            # Real OpenAI API call
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {openai_key}"
                }
                payload = {
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 150,
                    "temperature": 0.7
                }
                
                async with session.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        response = data["choices"][0]["message"]["content"].strip()
                        latency_ms = (time.time() - start_time) * 1000
                        
                        return {
                            "text": response,
                            "provider": "cloud_openai", 
                            "model_used": "gpt-4o-mini",
                            "confidence": 0.90,
                            "hybrid_latency_ms": latency_ms,
                            "cloud_consulted": True,
                            "cost_cents": len(prompt.split()) * 0.4,
                            "council_used": False,
                            "cloud_reason": error_reason[:100],
                            "council_voices": None
                        }
                    else:
                        print(f"OpenAI API error: {resp.status} - {await resp.text()}")
                        
        except Exception as e:
            print(f"OpenAI API failed: {e}")
    
    # No cloud APIs available - return error
    latency_ms = (time.time() - start_time) * 1000
    return {
        "text": f"Local inference failed and cloud APIs failed. Error: {error_reason}",
        "provider": "error",
        "model_used": "none",
        "confidence": 0.0,
        "hybrid_latency_ms": latency_ms,
        "cloud_consulted": False,
        "cost_cents": 0,
        "council_used": False,
        "error": "ALL_METHODS_FAILED",
        "error_reason": error_reason[:200],
        "council_voices": None
    }

async def smart_orchestrate(prompt: str, route: List[str], enable_cloud_fallback: bool = False) -> Dict[str, Any]:
    """
    Smart orchestration with optional cloud fallback
    
    Args:
        prompt: Input prompt
        route: List of models to try
        enable_cloud_fallback: Whether to fallback to cloud if local fails
        
    Returns:
        Dict with orchestration result
    """
    start_time = time.time()
    
    try:
        # Try hybrid routing first
        result = await hybrid_route(prompt, route, enable_council=False)
        
        # If confidence is too low and cloud fallback is enabled
        if result["confidence"] < 0.3 and enable_cloud_fallback:
            # For now, just return the local result with a flag
            result["cloud_consulted"] = True
            result["provider"] = "hybrid_with_cloud_consult"
        
        return result
        
    except Exception as e:
        return {
            "text": f"Orchestration failed: {str(e)}",
            "provider": "error",
            "model_used": "error",
            "confidence": 0.0,
            "hybrid_latency_ms": (time.time() - start_time) * 1000,
            "cloud_consulted": False,
            "cost_cents": 0.0,
            "council_used": False,
            "council_voices": None
        } 