"""
🛣️ Feedback Routes - #201 Feedback-Ingest
FastAPI endpoints for capturing user feedback on LLM responses
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from redis.asyncio import Redis
import asyncio
import json
import time
import logging
from typing import Optional

# Import schemas and metrics
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from schema.feedback import Feedback, FeedbackResponse, FeedbackStats

# Import metrics (will create if doesn't exist)
try:
    from ..metrics import feedback_ingest_total, feedback_latency_seconds
except ImportError:
    # Create metrics inline if not available
    from prometheus_client import Counter, Histogram
    feedback_ingest_total = Counter("feedback_ingest_total", "Total feedback items ingested")
    feedback_latency_seconds = Histogram(
        "feedback_latency_seconds", 
        "Time spent writing feedback to Redis",
        buckets=[0.001, 0.005, 0.01, 0.025, 0.05]
    )

logger = logging.getLogger(__name__)

# FastAPI router
router = APIRouter(prefix="/feedback", tags=["feedback"])

# Redis connection
redis_client: Optional[Redis] = None

async def get_redis():
    """Get Redis connection with fallback"""
    global redis_client
    if redis_client is None:
        try:
            redis_client = Redis.from_url("redis://redis:6379/0", decode_responses=True)
            # Test connection
            await redis_client.ping()
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")
            redis_client = None
    return redis_client


@router.post("/", status_code=202, response_model=FeedbackResponse)
async def submit_feedback(fb: Feedback, bg: BackgroundTasks, redis: Redis = Depends(get_redis)):
    """
    🎯 Submit user feedback on LLM response
    
    Fire-and-forget async storage for minimal latency impact.
    Target: <10ms p95 latency for feedback submission.
    """
    start_time = time.time()
    
    try:
        # Queue background storage
        bg.add_task(_store_feedback_async, fb, start_time, redis)
        
        # Immediate response to user
        return FeedbackResponse(
            feedback_id=fb.id,
            message=f"Feedback recorded (score: {fb.score})"
        )
        
    except Exception as e:
        logger.error(f"❌ Feedback submission failed: {e}")
        raise HTTPException(status_code=500, detail="Feedback storage error")


async def _store_feedback_async(fb: Feedback, request_start: float, redis: Optional[Redis]):
    """
    🗄️ Async background task to store feedback in Redis
    
    Storage format:
    - Key: feedback:{response_id}
    - Type: Sorted Set (ZADD)
    - Score: feedback.score (-1, 0, 1)
    - Value: JSON-serialized feedback object
    """
    storage_start = time.perf_counter()
    
    try:
        if redis is None:
            logger.warning("Redis unavailable - feedback lost")
            return
            
        # Serialize feedback
        fb_data = fb.dict()
        fb_json = json.dumps(fb_data)
        
        # Store in Redis sorted set (allows duplicate scores, time-ordered)
        redis_key = f"feedback:{fb.id}"
        await redis.zadd(redis_key, {fb_json: fb.timestamp})
        
        # Set expiration (30 days for feedback data)
        await redis.expire(redis_key, 30 * 24 * 3600)
        
        # Update metrics
        feedback_ingest_total.inc()
        storage_latency = time.perf_counter() - storage_start
        feedback_latency_seconds.observe(storage_latency)
        
        logger.info(f"✅ Feedback stored: {fb.id} (score: {fb.score}, latency: {storage_latency:.3f}s)")
        
    except Exception as e:
        logger.error(f"❌ Feedback storage failed: {e}")


@router.get("/stats", response_model=FeedbackStats)
async def get_feedback_stats(redis: Redis = Depends(get_redis)):
    """
    📊 Get aggregated feedback statistics
    Used for monitoring feedback collection rate
    """
    try:
        if redis is None:
            raise HTTPException(status_code=503, detail="Redis unavailable")
            
        # Get all feedback keys
        feedback_keys = await redis.keys("feedback:*")
        
        total_feedback = 0
        score_counts = {"positive": 0, "negative": 0, "neutral": 0}
        score_sum = 0
        
        # Aggregate feedback data
        for key in feedback_keys[:1000]:  # Limit to prevent performance issues
            feedback_items = await redis.zrevrange(key, 0, -1)
            for item in feedback_items:
                try:
                    fb_data = json.loads(item)
                    score = fb_data.get("score", 0)
                    
                    total_feedback += 1
                    score_sum += score
                    
                    if score > 0:
                        score_counts["positive"] += 1
                    elif score < 0:
                        score_counts["negative"] += 1
                    else:
                        score_counts["neutral"] += 1
                        
                except json.JSONDecodeError:
                    continue
        
        # Calculate metrics
        avg_score = score_sum / max(total_feedback, 1)
        
        # Get request rate for feedback rate calculation
        # This would ideally come from your main API metrics
        feedback_rate = 0.0  # TODO: Calculate from request_total metrics
        
        return FeedbackStats(
            total_feedback=total_feedback,
            positive_count=score_counts["positive"],
            negative_count=score_counts["negative"],
            neutral_count=score_counts["neutral"],
            avg_score=avg_score,
            feedback_rate=feedback_rate
        )
        
    except Exception as e:
        logger.error(f"❌ Feedback stats failed: {e}")
        raise HTTPException(status_code=500, detail="Stats calculation error")


@router.get("/{response_id}")
async def get_feedback_for_response(response_id: str, redis: Redis = Depends(get_redis)):
    """
    🔍 Get all feedback for a specific response ID
    Useful for debugging and response quality analysis
    """
    try:
        if redis is None:
            raise HTTPException(status_code=503, detail="Redis unavailable")
            
        redis_key = f"feedback:{response_id}"
        feedback_items = await redis.zrevrange(redis_key, 0, -1, withscores=True)
        
        results = []
        for item, timestamp in feedback_items:
            try:
                fb_data = json.loads(item)
                fb_data["redis_timestamp"] = timestamp
                results.append(fb_data)
            except json.JSONDecodeError:
                continue
        
        return {
            "response_id": response_id,
            "feedback_count": len(results),
            "feedback_items": results
        }
        
    except Exception as e:
        logger.error(f"❌ Feedback lookup failed: {e}")
        raise HTTPException(status_code=500, detail="Feedback lookup error")


# Health check for feedback system
@router.get("/health")
async def feedback_health(redis: Redis = Depends(get_redis)):
    """🏥 Health check for feedback ingestion system"""
    try:
        if redis is None:
            return {"status": "unhealthy", "error": "Redis unavailable"}
            
        # Test Redis operation
        test_key = "feedback:health_check"
        await redis.set(test_key, "ok", ex=10)
        result = await redis.get(test_key)
        
        if result == "ok":
            return {
                "status": "healthy",
                "redis": "connected",
                "timestamp": time.time()
            }
        else:
            return {"status": "unhealthy", "error": "Redis test failed"}
            
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)} 