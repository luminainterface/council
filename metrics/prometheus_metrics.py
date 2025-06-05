#!/usr/bin/env python3
"""
Phase-2 Bridge Plan - Observability Metrics
==========================================

Prometheus metrics for Intent → Action pipeline monitoring:
- intent_latency_seconds{stage=intent} histogram
- action_route_accuracy gauge (good / total)
- stub_detections_total counter
- cloud_calls_total with cost labels
"""

from prometheus_client import Counter, Histogram, Gauge, Summary
import time
from typing import Dict, Any, Optional

# Intent processing latency metrics
intent_latency_seconds = Histogram(
    'intent_latency_seconds',
    'Time spent in intent processing stages',
    ['stage'],  # agent0, specialist, fusion, etc.
    buckets=(0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0)
)

# Action routing accuracy 
action_route_accuracy = Gauge(
    'action_route_accuracy',
    'Percentage of successful action routing (good / total)',
    ['time_window']  # 1h, 24h, 7d
)

# Stub detection counter
stub_detections_total = Counter(
    'stub_detections_total',
    'Total number of stub responses detected and filtered',
    ['stub_type', 'location']  # template/todo/custom_function, response/query
)

# Cloud model usage tracking
cloud_calls_total = Counter(
    'cloud_calls_total',
    'Total cloud model API calls with cost tracking',
    ['model', 'provider', 'reason']  # gpt-4o, openai, fallback
)

# Cloud spend tracking
cloud_spend_usd = Counter(
    'cloud_spend_usd_total',
    'Total USD spent on cloud models',
    ['model', 'provider']
)

# Local model performance
local_model_latency = Histogram(
    'local_model_latency_seconds',
    'Local model inference latency',
    ['model_name', 'device'],
    buckets=(0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0)
)

# Memory and resource usage
gpu_memory_usage_bytes = Gauge(
    'gpu_memory_usage_bytes',
    'Current GPU memory usage',
    ['device_id']
)

# System health indicators
system_health_score = Gauge(
    'system_health_score',
    'Overall system health (0.0 to 1.0)',
    ['component']  # routing, models, memory, etc.
)

# Agent-0 confidence distribution
agent0_confidence = Histogram(
    'agent0_confidence_score',
    'Distribution of Agent-0 confidence scores',
    ['query_type'],
    buckets=(0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
)

# Specialist escalation patterns
specialist_escalations = Counter(
    'specialist_escalations_total',
    'Number of escalations to specialists',
    ['specialist_type', 'trigger_reason']  # math/code/logic, low_confidence/flag
)

class MetricsCollector:
    """Centralized metrics collection for the bridge plan pipeline"""
    
    def __init__(self):
        self.start_times: Dict[str, float] = {}
        self.daily_budget_usd = 1.00  # From bridge plan budget guard
        self.per_request_budget_usd = 0.05
        
    def start_timer(self, operation_id: str) -> None:
        """Start timing an operation"""
        self.start_times[operation_id] = time.time()
    
    def end_timer(self, operation_id: str, stage: str) -> float:
        """End timing and record metric"""
        if operation_id not in self.start_times:
            return 0.0
        
        duration = time.time() - self.start_times[operation_id]
        intent_latency_seconds.labels(stage=stage).observe(duration)
        del self.start_times[operation_id]
        return duration
    
    def record_stub_detection(self, stub_type: str, location: str) -> None:
        """Record stub detection event"""
        stub_detections_total.labels(
            stub_type=stub_type,
            location=location
        ).inc()
    
    def record_cloud_call(self, model: str, provider: str, reason: str, cost_usd: float = 0.0) -> None:
        """Record cloud model usage and cost"""
        cloud_calls_total.labels(
            model=model,
            provider=provider,
            reason=reason
        ).inc()
        
        if cost_usd > 0:
            cloud_spend_usd.labels(
                model=model,
                provider=provider
            ).inc(cost_usd)
    
    def record_agent0_confidence(self, confidence: float, query_type: str = "general") -> None:
        """Record Agent-0 confidence score"""
        agent0_confidence.labels(query_type=query_type).observe(confidence)
    
    def record_specialist_escalation(self, specialist: str, reason: str) -> None:
        """Record specialist escalation"""
        specialist_escalations.labels(
            specialist_type=specialist,
            trigger_reason=reason
        ).inc()
    
    def record_local_model_latency(self, model_name: str, device: str, latency: float) -> None:
        """Record local model performance"""
        local_model_latency.labels(
            model_name=model_name,
            device=device
        ).observe(latency)
    
    def update_system_health(self, component: str, health_score: float) -> None:
        """Update system health indicators"""
        system_health_score.labels(component=component).set(health_score)
    
    def check_budget_limits(self, request_cost: float) -> bool:
        """Check if request is within budget limits"""
        if request_cost > self.per_request_budget_usd:
            return False
        
        # Note: Daily budget checking would require persistent storage
        # For now, just check per-request limit
        return True
    
    def get_daily_burn_rate(self) -> float:
        """Get current daily burn rate (would need time-series data)"""
        # Placeholder - in production this would query time-series metrics
        return 0.0

# Global metrics collector instance
metrics = MetricsCollector()

# Context managers for easy timing
class timer_context:
    """Context manager for timing operations"""
    
    def __init__(self, stage: str, operation_id: Optional[str] = None):
        self.stage = stage
        self.operation_id = operation_id or f"{stage}_{int(time.time() * 1000)}"
    
    def __enter__(self):
        metrics.start_timer(self.operation_id)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        metrics.end_timer(self.operation_id, self.stage)

# Utility functions for common metrics patterns
def record_query_metrics(query: str, confidence: float, specialists_used: list, latency_ms: float) -> None:
    """Record metrics for a complete query processing cycle"""
    # Classify query type
    query_type = "general"
    if any(word in query.lower() for word in ["math", "calculate", "+", "-", "*", "/"]):
        query_type = "math"
    elif any(word in query.lower() for word in ["code", "function", "python", "javascript"]):
        query_type = "code"
    elif any(word in query.lower() for word in ["logic", "proof", "reasoning"]):
        query_type = "logic"
    
    # Record core metrics
    metrics.record_agent0_confidence(confidence, query_type)
    
    # Record specialist usage
    for specialist in specialists_used:
        metrics.record_specialist_escalation(specialist, "agent0_escalation")
    
    # Record overall latency
    intent_latency_seconds.labels(stage="total").observe(latency_ms / 1000.0)

def record_stub_event(candidate: Dict[str, Any]) -> None:
    """Record stub detection from a candidate response"""
    if candidate.get("stub_detected"):
        stub_type = candidate.get("stub_detected", "unknown")
        location = candidate.get("stub_location", "unknown")
        metrics.record_stub_detection(stub_type, location) 