#!/usr/bin/env python3
"""
AutoGen API Shim
================

FastAPI server that exposes the AutoGen skill system as a web API,
compatible with the Titanic Gauntlet benchmark harness.
"""

import asyncio
import time
import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import sys
import os

# Add the AutoGen path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'fork', 'swarm_autogen'))

from router_cascade import RouterCascade, MockResponseError

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AutoGen API Shim",
    description="AutoGen skill system exposed as web API",
    version="2.4.0"
)

class QueryRequest(BaseModel):
    prompt: str

class QueryResponse(BaseModel):
    text: str
    model: str = "autogen-hybrid"
    latency_ms: float
    skill_type: str
    confidence: float
    timestamp: str

# Global router instance
router = None
stats = {
    "requests_total": 0,
    "requests_success": 0,
    "requests_mock_detected": 0,
    "requests_cloud_fallback": 0,
    "avg_latency_ms": 0.0,
    "uptime_start": time.time()
}

async def cloud_fallback(query: str) -> Dict[str, Any]:
    """Cloud fallback when local models fail or return mocks"""
    # For now, return a clearly marked cloud response
    # TODO: Implement actual cloud API calls (OpenAI, Mistral, etc.)
    logger.info("☁️ Cloud fallback triggered")
    stats["requests_cloud_fallback"] += 1
    
    return {
        "text": f"[CLOUD_FALLBACK_NEEDED] Query: {query[:50]}...",
        "model": "cloud-fallback-needed",
        "latency_ms": 100.0,
        "skill_type": "cloud",
        "confidence": 0.3,
        "timestamp": time.time()
    }

@app.on_event("startup")
async def startup_event():
    """Initialize the router on startup"""
    global router
    logger.info("🚀 Starting AutoGen API Shim")
    logger.info("=" * 50)
    logger.info("📡 Endpoints:")
    logger.info("  POST /hybrid - Main AutoGen endpoint")
    logger.info("  GET  /health - Health check")
    logger.info("  GET  /stats  - Service statistics")
    logger.info("  GET  /metrics - Prometheus metrics")
    logger.info("=" * 50)
    logger.info("🌐 Server starting on http://localhost:8000")
    
    try:
        router = RouterCascade()
        logger.info("✅ Router initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize router: {e}")
        raise

@app.post("/hybrid", response_model=QueryResponse)
async def hybrid_endpoint(request: QueryRequest) -> QueryResponse:
    """Main hybrid endpoint compatible with Titanic Gauntlet"""
    start_time = time.time()
    stats["requests_total"] += 1
    
    try:
        # Try local AutoGen processing first
        result = await router.route_query(request.prompt)
        
        stats["requests_success"] += 1
        latency_ms = (time.time() - start_time) * 1000
        
        # Update running average latency
        stats["avg_latency_ms"] = (
            (stats["avg_latency_ms"] * (stats["requests_success"] - 1) + latency_ms) 
            / stats["requests_success"]
        )
        
        return QueryResponse(
            text=result["text"],
            model=result.get("model", "autogen-hybrid"),
            latency_ms=latency_ms,
            skill_type=result.get("skill_type", "unknown"),
            confidence=result.get("confidence", 0.5),
            timestamp=str(result.get("timestamp", time.time()))
        )
        
    except MockResponseError as e:
        # Mock detected - try cloud fallback
        logger.warning(f"🚨 Mock response detected: {e.response_text[:100]}...")
        stats["requests_mock_detected"] += 1
        
        try:
            cloud_result = await cloud_fallback(request.prompt)
            latency_ms = (time.time() - start_time) * 1000
            
            return QueryResponse(
                text=cloud_result["text"],
                model=cloud_result["model"],
                latency_ms=latency_ms,
                skill_type=cloud_result["skill_type"],
                confidence=cloud_result["confidence"],
                timestamp=str(cloud_result["timestamp"])
            )
        except Exception as cloud_error:
            logger.error(f"☁️ Cloud fallback failed: {cloud_error}")
            raise HTTPException(
                status_code=500, 
                detail=f"Local mock detected and cloud fallback failed: {str(cloud_error)}"
            )
    
    except Exception as e:
        logger.error(f"❌ Processing error: {e}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "autogen-api-shim",
        "version": "2.4.0",
        "timestamp": time.time()
    }

@app.get("/stats")
async def get_stats():
    """Service statistics"""
    uptime_seconds = time.time() - stats["uptime_start"]
    
    return {
        "requests_total": stats["requests_total"],
        "requests_success": stats["requests_success"],
        "requests_mock_detected": stats["requests_mock_detected"],
        "requests_cloud_fallback": stats["requests_cloud_fallback"],
        "success_rate": stats["requests_success"] / max(stats["requests_total"], 1),
        "mock_rate": stats["requests_mock_detected"] / max(stats["requests_total"], 1),
        "cloud_fallback_rate": stats["requests_cloud_fallback"] / max(stats["requests_total"], 1),
        "avg_latency_ms": stats["avg_latency_ms"],
        "uptime_seconds": uptime_seconds,
        "timestamp": time.time()
    }

@app.get("/metrics")
async def get_metrics():
    """Prometheus-compatible metrics"""
    uptime_seconds = time.time() - stats["uptime_start"]
    
    metrics = f"""# HELP autogen_requests_total Total number of requests
# TYPE autogen_requests_total counter
autogen_requests_total {stats["requests_total"]}

# HELP autogen_requests_success_total Successful requests
# TYPE autogen_requests_success_total counter
autogen_requests_success_total {stats["requests_success"]}

# HELP autogen_requests_mock_detected_total Mock responses detected
# TYPE autogen_requests_mock_detected_total counter
autogen_requests_mock_detected_total {stats["requests_mock_detected"]}

# HELP autogen_requests_cloud_fallback_total Cloud fallback requests
# TYPE autogen_requests_cloud_fallback_total counter
autogen_requests_cloud_fallback_total {stats["requests_cloud_fallback"]}

# HELP autogen_latency_ms_avg Average latency in milliseconds
# TYPE autogen_latency_ms_avg gauge
autogen_latency_ms_avg {stats["avg_latency_ms"]}

# HELP autogen_uptime_seconds Service uptime in seconds
# TYPE autogen_uptime_seconds gauge
autogen_uptime_seconds {uptime_seconds}
"""
    
    return metrics

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    ) 