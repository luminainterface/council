#!/usr/bin/env python3
"""
Metrics Collection for Enhanced Router with Flag Support
=======================================================

Centralized Prometheus metrics for flag routing, execution tracking,
and performance monitoring.
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Prometheus imports with fallback
try:
    from prometheus_client import (
        Counter, Gauge, Histogram, Summary,
        CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("Prometheus client not available - using mock metrics")

# Shared registry to avoid conflicts
registry = CollectorRegistry()

class RouterMetrics:
    """Centralized metrics for router and flag processing"""
    
    def __init__(self):
        if PROMETHEUS_AVAILABLE:
            # Flag routing metrics with consistent labelsets
            self.flag_counter = Counter(
                "swarm_router_flag_total",
                "Total flag routing hits",
                ["flag", "executor"],
                registry=registry
            )
            
            self.flag_processing_duration = Histogram(
                "swarm_flag_processing_duration_seconds",
                "Time spent processing flagged requests",
                ["flag_type", "executor"],
                registry=registry
            )
            
            # Router performance metrics
            self.routing_latency = Histogram(
                "swarm_routing_latency_ms",
                "Router decision latency in milliseconds", 
                registry=registry
            )
            
            self.executor_queue_size = Gauge(
                "swarm_executor_queue_size",
                "Current executor queue sizes",
                ["queue_name"],
                registry=registry
            )
            
            # Execution metrics with consistent labels
            self.execution_success_total = Counter(
                "swarm_execution_success_total",
                "Total successful executions",
                ["executor", "flag_type"],
                registry=registry
            )
            
            self.execution_error_total = Counter(
                "swarm_execution_error_total", 
                "Total execution errors",
                ["executor", "error_type"],
                registry=registry
            )
            
            # Week 3 strategic metrics with shared registry and board_rank filter
            self.merge_efficiency = Gauge(
                "merge_efficiency",
                "Chess merge efficiency ratio",
                ["board_rank"],
                registry=registry
            )
            
            self.pattern_clusters_total = Counter(
                "pattern_clusters_total",
                "Total pattern clusters discovered",
                registry=registry
            )
            
            self.agent_consensus_rounds = Histogram(
                "agent_consensus_rounds", 
                "Voting rounds to reach consensus",
                registry=registry
            )
            
            logger.info("✅ Router metrics initialized with shared registry")
        else:
            self._init_mock_metrics()
    
    def _init_mock_metrics(self):
        """Initialize mock metrics for development"""
        class MockMetric:
            def __init__(self, name):
                self.name = name
                self._value = 0
            
            def inc(self, amount=1):
                self._value += amount
            
            def set(self, value):
                self._value = value
            
            def observe(self, value):
                self._value = value
            
            def labels(self, **kwargs):
                return self
        
        # Create mock versions
        for attr_name in [
            'flag_counter', 'flag_processing_duration', 'routing_latency',
            'executor_queue_size', 'execution_success_total', 'execution_error_total',
            'merge_efficiency', 'pattern_clusters_total', 'agent_consensus_rounds'
        ]:
            setattr(self, attr_name, MockMetric(attr_name))
    
    def record_flag_hit(self, flag: str, executor: str):
        """Record a flag routing hit"""
        try:
            self.flag_counter.labels(flag=flag, executor=executor).inc()
        except Exception as e:
            logger.warning(f"Failed to record flag hit: {e}")
    
    def record_routing_latency(self, latency_ms: float):
        """Record routing decision latency"""
        try:
            self.routing_latency.observe(latency_ms)
        except Exception as e:
            logger.warning(f"Failed to record routing latency: {e}")
    
    def record_execution_success(self, executor: str, flag_type: str = "unknown"):
        """Record successful execution"""
        try:
            self.execution_success_total.labels(
                executor=executor, 
                flag_type=flag_type
            ).inc()
        except Exception as e:
            logger.warning(f"Failed to record execution success: {e}")
    
    def record_execution_error(self, executor: str, error_type: str):
        """Record execution error"""
        try:
            self.execution_error_total.labels(
                executor=executor,
                error_type=error_type
            ).inc()
        except Exception as e:
            logger.warning(f"Failed to record execution error: {e}")
    
    def update_queue_size(self, queue_name: str, size: int):
        """Update executor queue size"""
        try:
            self.executor_queue_size.labels(queue_name=queue_name).set(size)
        except Exception as e:
            logger.warning(f"Failed to update queue size: {e}")
    
    def record_flag_processing_time(self, flag_type: str, executor: str, duration_seconds: float):
        """Record flag processing duration"""
        try:
            self.flag_processing_duration.labels(
                flag_type=flag_type,
                executor=executor
            ).observe(duration_seconds)
        except Exception as e:
            logger.warning(f"Failed to record processing time: {e}")
    
    # Week 3 integration methods
    def update_merge_efficiency(self, ratio: float, board_rank: int = 0):
        """Update chess merge efficiency"""
        try:
            rank_label = str(board_rank) if board_rank > 0 else "unknown"
            self.merge_efficiency.labels(board_rank=rank_label).set(ratio)
        except Exception as e:
            logger.warning(f"Failed to update merge efficiency: {e}")
    
    def record_pattern_discovery(self, count: int = 1):
        """Record pattern cluster discovery"""
        try:
            self.pattern_clusters_total.inc(count)
        except Exception as e:
            logger.warning(f"Failed to record pattern discovery: {e}")
    
    def record_consensus_rounds(self, rounds: int):
        """Record agent consensus voting rounds"""
        try:
            self.agent_consensus_rounds.observe(rounds)
        except Exception as e:
            logger.warning(f"Failed to record consensus rounds: {e}")
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get current metrics summary"""
        summary = {
            'flag_routing': {
                'total_hits': getattr(self.flag_counter, '_value', 0),
                'avg_latency_ms': getattr(self.routing_latency, '_value', 0)
            },
            'execution': {
                'success_total': getattr(self.execution_success_total, '_value', 0),
                'error_total': getattr(self.execution_error_total, '_value', 0)
            },
            'week3_integration': {
                'merge_efficiency': getattr(self.merge_efficiency, '_value', 0),
                'pattern_clusters': getattr(self.pattern_clusters_total, '_value', 0)
            }
        }
        
        # Calculate derived metrics
        exec_data = summary['execution']
        if exec_data['success_total'] > 0:
            total_exec = exec_data['success_total'] + exec_data['error_total']
            summary['derived'] = {
                'success_rate': exec_data['success_total'] / total_exec,
                'error_rate': exec_data['error_total'] / total_exec
            }
        
        return summary
    
    def export_prometheus_metrics(self) -> str:
        """Export metrics in Prometheus format"""
        if PROMETHEUS_AVAILABLE:
            return generate_latest(registry).decode('utf-8')
        else:
            # Mock Prometheus format
            lines = []
            for attr_name in dir(self):
                if not attr_name.startswith('_') and hasattr(getattr(self, attr_name), '_value'):
                    metric = getattr(self, attr_name)
                    lines.append(f"# TYPE {attr_name} gauge")
                    lines.append(f"{attr_name} {getattr(metric, '_value', 0)}")
            return '\n'.join(lines)

# Global metrics instance
_router_metrics = None

def get_router_metrics() -> RouterMetrics:
    """Get global router metrics instance"""
    global _router_metrics
    if _router_metrics is None:
        _router_metrics = RouterMetrics()
    return _router_metrics

# Derived metrics calculator (for telemetry/derived.py)
class DerivedMetricsCalculator:
    """Calculates derived metrics to avoid PromQL complexity"""
    
    def __init__(self):
        self.metrics = get_router_metrics()
        
        if PROMETHEUS_AVAILABLE:
            # Derived metrics gauges
            self.merge_efficiency_ratio = Gauge(
                "merge_efficiency_ratio",
                "Calculated merge events / moves ratio",
                registry=registry
            )
            
            self.flag_success_rate = Gauge(
                "flag_success_rate", 
                "Success rate for flagged executions",
                ["flag_type"],
                registry=registry
            )
            
            self.routing_efficiency = Gauge(
                "routing_efficiency",
                "Router decision efficiency score", 
                registry=registry
            )
    
    def calculate_all_derived_metrics(self):
        """Calculate all derived metrics"""
        if not PROMETHEUS_AVAILABLE:
            return
        
        try:
            # Calculate merge efficiency ratio
            # Note: In real implementation, these would come from actual counters
            merge_events = getattr(self.metrics.pattern_clusters_total, '_value', 0)
            total_moves = 10  # Mock data - would come from chess engine
            
            if total_moves > 0:
                ratio = merge_events / total_moves
                self.merge_efficiency_ratio.set(ratio)
            
            # Calculate flag success rate
            success = getattr(self.metrics.execution_success_total, '_value', 0)
            errors = getattr(self.metrics.execution_error_total, '_value', 0)
            total = success + errors
            
            if total > 0:
                success_rate = success / total
                self.flag_success_rate.labels(flag_type="all").set(success_rate)
            
            # Calculate routing efficiency
            avg_latency = getattr(self.metrics.routing_latency, '_value', 1.0)
            efficiency = 1.0 / (1.0 + avg_latency / 1000.0)  # Normalize to 0-1
            self.routing_efficiency.set(efficiency)
            
        except Exception as e:
            logger.error(f"❌ Derived metrics calculation failed: {e}")

# Test function
def test_metrics():
    """Test metrics collection"""
    print("📊 Testing Router Metrics")
    print("=" * 40)
    
    metrics = get_router_metrics()
    
    # Simulate some metric updates
    metrics.record_flag_hit("FLAG_MATH", "math_specialist")
    metrics.record_flag_hit("FLAG_SYSCALL", "os_executor")
    metrics.record_routing_latency(15.5)
    metrics.record_execution_success("math_specialist", "FLAG_MATH")
    metrics.update_merge_efficiency(0.25, board_rank=8)
    
    # Get summary
    summary = metrics.get_metrics_summary()
    print(f"Flag routing hits: {summary['flag_routing']['total_hits']}")
    print(f"Execution successes: {summary['execution']['success_total']}")
    print(f"Merge efficiency: {summary['week3_integration']['merge_efficiency']}")
    
    if 'derived' in summary:
        print(f"Success rate: {summary['derived']['success_rate']:.1%}")
    
    # Test derived metrics
    calculator = DerivedMetricsCalculator()
    calculator.calculate_all_derived_metrics()
    
    print("✅ Metrics test completed")

if __name__ == "__main__":
    test_metrics() 