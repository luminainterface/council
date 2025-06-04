# -*- coding: utf-8 -*-
"""
SwarmAI FastAPI Main Application
"""

import os
import time
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from prometheus_client import Histogram, Counter, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from loader.deterministic_loader import boot_models, get_loaded_models
from app.router_intent import route, health_check
from router.voting import vote
from router.cost_tracking import debit, get_budget_status, get_cost_breakdown, downgrade_route
from router.hybrid import hybrid_route, smart_orchestrate
from router.council import council_route  # 🌌 Council integration
from router.traffic_controller import traffic_controller  # 🚦 Traffic controller

# Prometheus metrics
REQUEST_LATENCY = Histogram(
    "swarm_router_request_latency", 
    "Router request latency in seconds",
    buckets=(0.05, 0.1, 0.2, 0.5, 1, 2, 5)
)

ROUTER_REQUESTS = Counter(
    "swarm_router_requests_total",
    "Total router requests"
)

# Pydantic models for API
class OrchestrateRequest(BaseModel):
    prompt: str
    route: List[str]

class OrchestrateResponse(BaseModel):
    text: str
    model_used: str
    latency_ms: float
    cost_cents: float

class VotingRequest(BaseModel):
    prompt: str
    candidates: List[str]
    top_k: int = 2

class VotingResponse(BaseModel):
    text: str
    winner: Dict[str, Any]
    all_candidates: List[Dict[str, Any]]
    voting_stats: Dict[str, Any]
    total_cost_cents: float

class BudgetResponse(BaseModel):
    budget_status: Dict[str, float]
    cost_breakdown: Dict[str, float]

class HybridRequest(BaseModel):
    prompt: str
    preferred_models: List[str] = []
    enable_council: Optional[bool] = None  # 🌌 Council toggle
    force_council: Optional[bool] = False  # 🌌 Force council deliberation

class HybridResponse(BaseModel):
    text: str
    provider: str
    model_used: str
    confidence: float
    hybrid_latency_ms: float
    cloud_consulted: bool
    cost_cents: float
    council_used: Optional[bool] = False  # 🌌 Council usage indicator
    council_voices: Optional[Dict[str, Any]] = None  # 🌌 Council voice breakdown

class VoteRequest(BaseModel):
    prompt: str
    heads: List[str]
    top_k: Optional[int] = 2

class CouncilRequest(BaseModel):
    prompt: str
    force_council: Optional[bool] = False

class CouncilResponse(BaseModel):
    text: str
    council_used: bool
    voice_responses: Dict[str, Any]
    total_latency_ms: float
    total_cost_dollars: float
    consensus_achieved: bool
    risk_flags: List[str]

# Global variable to track model loading status
model_loading_summary = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - startup and shutdown"""
    global model_loading_summary
    
    # Startup
    echo("[STARTUP] SwarmAI FastAPI starting up...")
    profile = os.environ.get("SWARM_GPU_PROFILE", "rtx_4070")
    echo(f"[PROFILE] Using GPU profile: {profile}")
    
    try:
        model_loading_summary = boot_models(profile=profile)
        echo(f"[OK] Model loading complete: {model_loading_summary}")
    except Exception as e:
        echo(f"[ERROR] Model loading failed: {e}")
        model_loading_summary = {"error": str(e)}
    
    print("🌌 Council-in-the-Loop: Initialized")
    print("🎯 Router 2.0 ready for requests")
    
    yield
    
    # Shutdown
    echo("[SHUTDOWN] SwarmAI FastAPI shutting down...")

# Create FastAPI app with lifespan management
app = FastAPI(
    title="SwarmAI Router 2.0",
    description="Intelligent AI model routing, orchestration, and confidence-weighted voting with cost tracking",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware to handle browser preflight requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods including OPTIONS
    allow_headers=["*"],  # Allow all headers
)

def echo(msg: str):
    """Safe logging function with ASCII-only output"""
    # Replace problematic emojis with ASCII equivalents
    safe_msg = msg.replace('🗳️', '[VOTE]').replace('🏆', '[WIN]').replace('💰', '[COST]').replace('❌', '[ERROR]').replace('⚠️', '[WARN]').replace('🎯', '[ROUTE]').replace('🌌', '[COUNCIL]')
    print(time.strftime('%H:%M:%S'), safe_msg, flush=True)

@app.post("/orchestrate", response_model=OrchestrateResponse)
async def orchestrate(request: OrchestrateRequest):
    """Route a prompt to specified model heads with cost tracking"""
    
    start_time = time.time()
    
    try:
        ROUTER_REQUESTS.inc()
        
        # Apply budget-aware routing
        cost_optimized_route = downgrade_route(request.route)
        if cost_optimized_route != request.route:
            echo(f"💰 Budget-aware routing: {request.route} -> {cost_optimized_route}")
        
        with REQUEST_LATENCY.time():
            result = await route(request.prompt, cost_optimized_route)
        
        # Calculate latency
        latency_ms = (time.time() - start_time) * 1000
        
        # Determine which model was actually used (simplified)
        loaded_models = get_loaded_models()
        available_heads = [h for h in cost_optimized_route if h in loaded_models]
        model_used = available_heads[0] if available_heads else "unknown"
        
        # Track cost
        tokens = len(result.split())  # Simple token estimate
        cost_cents = debit(model_used, tokens)
        
        return OrchestrateResponse(
            text=result,
            model_used=model_used,
            latency_ms=latency_ms,
            cost_cents=cost_cents
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/vote", response_model=VotingResponse)
async def vote_endpoint(request: VotingRequest):
    """Router 2.0: Confidence-weighted voting across multiple model heads with cost tracking"""
    
    start_time = time.time()
    
    try:
        ROUTER_REQUESTS.inc()
        
        # Apply budget-aware candidate selection
        cost_optimized_candidates = downgrade_route(request.candidates)
        if cost_optimized_candidates != request.candidates:
            echo(f"💰 Budget-aware voting: {request.candidates} -> {cost_optimized_candidates}")
        
        with REQUEST_LATENCY.time():
            result = await vote(request.prompt, cost_optimized_candidates, request.top_k)
        
        # Track costs for all candidates that responded
        total_cost_cents = 0.0
        for candidate in result["all_candidates"]:
            # Safely estimate tokens from response snippet
            response_text = candidate.get("response_snippet", "")
            if isinstance(response_text, str):
                tokens = len(response_text.split())
                cost = debit(candidate["model"], tokens)
                total_cost_cents += cost
        
        return VotingResponse(
            text=result["text"],
            winner=result["winner"],
            all_candidates=result["all_candidates"],
            voting_stats=result["voting_stats"],
            total_cost_cents=total_cost_cents
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/budget", response_model=BudgetResponse)
async def budget():
    """Get current budget status and cost breakdown"""
    try:
        return BudgetResponse(
            budget_status=get_budget_status(),
            cost_breakdown=get_cost_breakdown()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Budget check failed: {e}")

@app.get("/health")
async def health():
    """Health check endpoint"""
    try:
        result = await health_check()
        
        # Add council-specific health info
        council_status = traffic_controller.get_status()
        
        return {
            **result,
            "council": {
                "enabled": council_status["council_enabled"],
                "traffic_percent": council_status["traffic_percent"],
                "controller_active": council_status["controller_active"]
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {e}")

@app.get("/healthz")
async def healthz():
    """Load balancer health check with QPS metrics"""
    try:
        # Get basic health
        health_result = await health_check()
        
        # Add QPS metrics for load balancer
        return {
            "status": "healthy" if health_result.get("status") == "healthy" else "unhealthy",
            "local_qps": REQUEST_LATENCY._total._value if hasattr(REQUEST_LATENCY, '_total') else 0,
            "council_qps": COUNCIL_REQUESTS_TOTAL._value._value if 'COUNCIL_REQUESTS_TOTAL' in globals() else 0,
            "council_traffic_percent": traffic_controller.traffic_percent,
            "timestamp": time.time()
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

@app.get("/models")
async def models():
    """Get currently loaded models"""
    try:
        loaded_models = get_loaded_models()
        
        models_info = {}
        for name, info in loaded_models.items():
            models_info[name] = {
                "backend": info.get("backend", "unknown"),
                "type": info.get("type", "unknown"),
                "vram_mb": info.get("vram_mb", 0),
                "loaded_at": info.get("loaded_at", 0)
            }
        
        return {
            "total_models": len(loaded_models),
            "loaded_models": models_info,  # Include this field for test compatibility
            "models": models_info,  # Keep this too for new API
            "loading_summary": model_loading_summary
        }
    except Exception as e:
        echo(f"❌ Models endpoint error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get models: {e}")

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/hybrid", response_model=HybridResponse)
async def hybrid_endpoint(request: HybridRequest):
    """Enhanced hybrid local+cloud+council routing endpoint"""
    
    start_time = time.time()
    
    try:
        ROUTER_REQUESTS.inc()
        
        # 🌌 Council integration logic
        council_result = None
        council_used = False
        
        # Check if council should be used
        if request.force_council or request.enable_council:
            echo(f"🌌 Council requested for: '{request.prompt[:50]}...'")
            
            # Temporarily enable council if requested
            original_enabled = os.environ.get("SWARM_COUNCIL_ENABLED", "false")
            if request.enable_council or request.force_council:
                os.environ["SWARM_COUNCIL_ENABLED"] = "true"
            
            try:
                with REQUEST_LATENCY.time():
                    council_result = await council_route(request.prompt)
                
                if council_result.get("council_used", False):
                    council_used = True
                    echo(f"🌌 Council deliberation completed")
                
                # Restore original setting
                os.environ["SWARM_COUNCIL_ENABLED"] = original_enabled
                
            except Exception as e:
                echo(f"🌌 Council failed, falling back to hybrid: {e}")
                os.environ["SWARM_COUNCIL_ENABLED"] = original_enabled
                council_result = None
        
        # If council succeeded, use its result
        if council_used and council_result:
            cost_cents = council_result.get("total_cost_cents", 0.0)
            
            return HybridResponse(
                text=council_result["text"],
                provider="council",
                model_used="five_voice_council",
                confidence=council_result.get("consensus_confidence", 0.9),
                hybrid_latency_ms=council_result.get("total_latency_ms", 0.0),
                cloud_consulted=council_result.get("cloud_consulted", False),
                cost_cents=cost_cents,
                council_used=True,
                council_voices=council_result.get("voice_summary", {})
            )
        
        # Fall back to standard hybrid routing
        with REQUEST_LATENCY.time():
            result = await hybrid_route(request.prompt, request.preferred_models or None)
        
        # Extract cost information
        cost_cents = 0.0
        
        if result.get("provider") == "local":
            # Local cost tracking
            tokens = len(result["text"].split())
            model_used = result.get("model_used", "unknown")
            cost_cents = debit(model_used, tokens)
        elif "cost_cents" in result:
            # Cloud cost already calculated
            cost_cents = result["cost_cents"]
        
        return HybridResponse(
            text=result["text"],
            provider=result.get("provider", "unknown"),
            model_used=result.get("model_used", "unknown"),
            confidence=result.get("confidence", 0.0),
            hybrid_latency_ms=result.get("hybrid_latency_ms", 0.0),
            cloud_consulted=result.get("cloud_consulted", False),
            cost_cents=cost_cents,
            council_used=False,
            council_voices=None
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/council", response_model=CouncilResponse)
async def council_endpoint(request: CouncilRequest):
    """🌌 Dedicated Council-in-the-Loop deliberation endpoint"""
    
    start_time = time.time()
    
    try:
        echo(f"🌌 Council deliberation: '{request.prompt[:50]}...'")
        
        # Force council if requested
        if request.force_council:
            original_enabled = os.environ.get("SWARM_COUNCIL_ENABLED", "false")
            os.environ["SWARM_COUNCIL_ENABLED"] = "true"
            
            # Lower token threshold for forced council
            original_tokens = os.environ.get("COUNCIL_MIN_TOKENS", "20")
            os.environ["COUNCIL_MIN_TOKENS"] = "1"
            
            try:
                result = await council_route(request.prompt)
                
                # Restore settings
                os.environ["SWARM_COUNCIL_ENABLED"] = original_enabled
                os.environ["COUNCIL_MIN_TOKENS"] = original_tokens
                
            except Exception as e:
                # Restore settings on error
                os.environ["SWARM_COUNCIL_ENABLED"] = original_enabled
                os.environ["COUNCIL_MIN_TOKENS"] = original_tokens
                raise e
        else:
            result = await council_route(request.prompt)
        
        return CouncilResponse(
            text=result["text"],
            council_used=result.get("council_used", False),
            voice_responses=result.get("voice_responses", {}),
            total_latency_ms=result.get("total_latency_ms", 0.0),
            total_cost_dollars=result.get("total_cost_dollars", 0.0),
            consensus_achieved=result.get("consensus_achieved", False),
            risk_flags=result.get("risk_flags", [])
        )
        
    except Exception as e:
        echo(f"❌ Council error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/council/status")
async def council_status():
    """🌌 Get council configuration and status"""
    try:
        from router.council import council_router
        
        return {
            "council_enabled": council_router.council_enabled,
            "voice_models": {voice.value: model for voice, model in council_router.voice_models.items()},
            "budget_limits": {
                "max_cost_per_request": council_router.max_council_cost_per_request,
                "daily_budget": council_router.daily_council_budget
            },
            "trigger_config": {
                "min_tokens": council_router.min_tokens_for_council,
                "keywords": council_router.council_trigger_keywords
            },
            "performance_targets": {
                "p95_latency_ms": council_router.target_p95_latency_ms
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 