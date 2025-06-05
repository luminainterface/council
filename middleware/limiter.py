#!/usr/bin/env python3
"""
Admission Control Middleware - Week 2 Final Push
===============================================

Token bucket rate limiting to prevent vLLM overload.
Implements backpressure with 429 responses when capacity exceeded.
"""

import asyncio
import os
import time
import logging
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional

logger = logging.getLogger(__name__)

# Global semaphore for admission control
bucket: Optional[asyncio.Semaphore] = None

def init_admission_control():
    """Initialize admission control semaphore"""
    global bucket
    max_inflight = int(os.getenv("MAX_INFLIGHT_PROMPTS", "16"))
    bucket = asyncio.Semaphore(max_inflight)
    logger.info(f"🚦 Admission control initialized: {max_inflight} max inflight prompts")

async def backpressure_middleware(request: Request, call_next):
    """
    Admission control middleware - implements token bucket pattern
    
    Returns 429 when vLLM is at capacity to prevent queue buildup.
    """
    global bucket
    
    if bucket is None:
        init_admission_control()
    
    # Only apply to vLLM endpoints
    vllm_paths = ["/draft", "/chat", "/completions", "/v1/completions", "/v1/chat/completions"]
    
    if not any(request.url.path.startswith(path) for path in vllm_paths):
        # Not a vLLM endpoint, pass through
        return await call_next(request)
    
    # Check if we have capacity
    if bucket.locked():
        # At capacity - return 429
        logger.warning(f"🚦 Admission control: 429 - bucket full ({request.url.path})")
        
        # Update Prometheus metrics
        try:
            from prometheus_client import Counter
            bucket_denied = Counter("vllm_bucket_denied_total", "Requests denied due to bucket full")
            bucket_denied.inc()
        except:
            pass
        
        return JSONResponse(
            status_code=429,
            content={
                "error": "Service temporarily busy",
                "retry_after": 1,
                "queue_full": True
            }
        )
    
    # Acquire token and process request
    async with bucket:
        start_time = time.time()
        try:
            response = await call_next(request)
            
            # Update success metrics
            duration = time.time() - start_time
            logger.debug(f"🚦 Request processed: {request.url.path} ({duration:.3f}s)")
            
            return response
            
        except Exception as e:
            logger.error(f"🚦 Request failed: {request.url.path} - {e}")
            raise

def get_bucket_utilization() -> float:
    """Get current bucket utilization (0.0 - 1.0)"""
    global bucket
    if bucket is None:
        return 0.0
    
    max_capacity = bucket._initial_value
    current_available = bucket._value
    utilized = max_capacity - current_available
    
    return utilized / max_capacity if max_capacity > 0 else 0.0

def update_prometheus_metrics():
    """Update Prometheus metrics for bucket utilization"""
    try:
        from prometheus_client import Gauge
        
        # Create or get existing gauge
        bucket_gauge = Gauge("vllm_inflight_pct", "vLLM inflight requests percentage")
        bucket_gauge.set(get_bucket_utilization())
        
    except ImportError:
        pass  # Prometheus not available
    except Exception as e:
        logger.warning(f"Failed to update bucket metrics: {e}")

# Periodic metrics updater
async def metrics_updater():
    """Background task to update metrics every 5 seconds"""
    while True:
        try:
            update_prometheus_metrics()
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Metrics updater error: {e}")
            await asyncio.sleep(5)

def start_metrics_updater():
    """Start the metrics updater background task"""
    task = asyncio.create_task(metrics_updater())
    logger.info("🚦 Bucket metrics updater started")
    return task 