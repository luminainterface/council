"""
📊 Metrics - Prometheus metrics for feedback system
#201 Feedback-Ingest monitoring and alerting
"""

from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry
import time
import logging

logger = logging.getLogger(__name__)

# Create custom registry for feedback metrics
feedback_registry = CollectorRegistry()

# Core feedback metrics
feedback_ingest_total = Counter(
    "feedback_ingest_total",
    "Total feedback items ingested",
    registry=feedback_registry
)

feedback_latency_seconds = Histogram(
    "feedback_latency_seconds", 
    "Time spent writing feedback to Redis",
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25],
    registry=feedback_registry
)

# Feedback score distribution
feedback_score_total = Counter(
    "feedback_score_total",
    "Total feedback by score value",
    ["score"],  # Labels: -1, 0, 1
    registry=feedback_registry
)

# Feedback rate gauge (updated periodically)
feedback_rate_ratio = Gauge(
    "feedback_rate_ratio",
    "Ratio of feedback submissions to total requests",
    registry=feedback_registry
)

# Redis health for feedback storage
feedback_redis_errors_total = Counter(
    "feedback_redis_errors_total",
    "Redis errors during feedback storage",
    registry=feedback_registry
)

# Request processing time for feedback endpoints
feedback_request_duration_seconds = Histogram(
    "feedback_request_duration_seconds",
    "Time spent processing feedback requests",
    ["endpoint"],  # Labels: submit, stats, lookup
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1],
    registry=feedback_registry
)


def record_feedback_score(score: int):
    """Record feedback score in metrics"""
    try:
        score_label = str(score)  # -1, 0, or 1
        feedback_score_total.labels(score=score_label).inc()
    except Exception as e:
        logger.warning(f"Failed to record feedback score metric: {e}")


def record_feedback_latency(latency_seconds: float):
    """Record feedback storage latency"""
    try:
        feedback_latency_seconds.observe(latency_seconds)
    except Exception as e:
        logger.warning(f"Failed to record feedback latency: {e}")


def record_redis_error():
    """Record Redis error"""
    try:
        feedback_redis_errors_total.inc()
    except Exception as e:
        logger.warning(f"Failed to record Redis error: {e}")


def update_feedback_rate(feedback_count: int, request_count: int):
    """Update the feedback rate ratio"""
    try:
        if request_count > 0:
            rate = feedback_count / request_count
            feedback_rate_ratio.set(rate)
        else:
            feedback_rate_ratio.set(0.0)
    except Exception as e:
        logger.warning(f"Failed to update feedback rate: {e}")


def get_metrics_summary():
    """Get a summary of current feedback metrics"""
    try:
        from prometheus_client import generate_latest
        return generate_latest(feedback_registry).decode('utf-8')
    except Exception as e:
        logger.error(f"Failed to generate metrics: {e}")
        return "# Metrics unavailable\n"


class FeedbackMetricsCollector:
    """Async metrics collection for feedback system"""
    
    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        self.last_update = 0
        self.update_interval = 60  # Update every minute
        
    async def update_metrics(self):
        """Update feedback metrics from Redis data"""
        now = time.time()
        if now - self.last_update < self.update_interval:
            return
            
        try:
            if not self.redis_client:
                return
                
            # Get feedback count from Redis
            feedback_keys = await self.redis_client.keys("feedback:*")
            feedback_count = len(feedback_keys)
            
            # This would ideally get request count from your main API
            # For now, we'll estimate based on feedback keys
            estimated_requests = feedback_count * 4  # Assume 25% feedback rate
            
            # Update rate metric
            update_feedback_rate(feedback_count, estimated_requests)
            
            self.last_update = now
            logger.debug(f"Updated feedback metrics: {feedback_count} feedback items")
            
        except Exception as e:
            logger.error(f"Failed to update feedback metrics: {e}")


# Export metrics for use in other modules
__all__ = [
    'feedback_ingest_total',
    'feedback_latency_seconds', 
    'feedback_score_total',
    'feedback_rate_ratio',
    'feedback_redis_errors_total',
    'feedback_request_duration_seconds',
    'record_feedback_score',
    'record_feedback_latency',
    'record_redis_error',
    'update_feedback_rate',
    'get_metrics_summary',
    'FeedbackMetricsCollector'
] 