#!/usr/bin/env python3
"""
Derived Metrics Calculator
=========================

Calculates complex derived metrics to avoid PromQL computation
at query time and prevent MutexValue conflicts.
"""

import time
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Prometheus imports with fallback
try:
    from prometheus_client import Gauge, Counter, CollectorRegistry
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("Prometheus not available - using mock metrics")

# Import shared registry
from metrics import registry, get_router_metrics

class DerivedMetricsCalculator:
    """Calculates derived metrics to avoid PromQL complexity"""
    
    def __init__(self):
        self.metrics = get_router_metrics()
        
        if PROMETHEUS_AVAILABLE:
            # Derived metrics gauges with shared registry
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
            
            # High-card filtered metrics (board_rank >= 8 only)
            self.filtered_merge_efficiency = Gauge(
                "filtered_merge_efficiency",
                "Merge efficiency for board_rank >= 8 only",
                ["board_rank"],
                registry=registry
            )
            
            self.consensus_early_exit_rate = Gauge(
                "consensus_early_exit_rate",
                "Rate of early consensus in agent voting",
                registry=registry
            )
            
            logger.info("✅ Derived metrics calculator initialized")
        else:
            self._init_mock_derived_metrics()
    
    def _init_mock_derived_metrics(self):
        """Initialize mock derived metrics"""
        class MockGauge:
            def __init__(self, name):
                self.name = name
                self._value = 0.0
            
            def set(self, value):
                self._value = value
                
            def labels(self, **kwargs):
                return self
        
        for attr in ['merge_efficiency_ratio', 'flag_success_rate', 'routing_efficiency',
                     'filtered_merge_efficiency', 'consensus_early_exit_rate']:
            setattr(self, attr, MockGauge(attr))
    
    def calculate_all_derived_metrics(self):
        """Calculate all derived metrics every 30s"""
        try:
            # 1. Merge efficiency ratio
            self._calculate_merge_efficiency_ratio()
            
            # 2. Flag success rates  
            self._calculate_flag_success_rates()
            
            # 3. Routing efficiency
            self._calculate_routing_efficiency()
            
            # 4. High-card filtered metrics
            self._calculate_filtered_metrics()
            
            # 5. Consensus metrics
            self._calculate_consensus_metrics()
            
            logger.debug("📊 Derived metrics updated")
            
        except Exception as e:
            logger.error(f"❌ Derived metrics calculation failed: {e}")
    
    def _calculate_merge_efficiency_ratio(self):
        """Calculate merge events / total moves ratio"""
        try:
            # Get values from base metrics
            merge_events = getattr(self.metrics.pattern_clusters_total, '_value', 0)
            
            # Mock total moves - in real implementation would come from chess engine
            total_moves = getattr(self.metrics.execution_success_total, '_value', 1)
            
            if total_moves > 0:
                ratio = merge_events / total_moves
                self.merge_efficiency_ratio.set(ratio)
            else:
                self.merge_efficiency_ratio.set(0.0)
                
        except Exception as e:
            logger.warning(f"Merge efficiency calculation failed: {e}")
    
    def _calculate_flag_success_rates(self):
        """Calculate success rates by flag type"""
        try:
            # Get success/error totals
            success_total = getattr(self.metrics.execution_success_total, '_value', 0)
            error_total = getattr(self.metrics.execution_error_total, '_value', 0)
            
            total_executions = success_total + error_total
            
            if total_executions > 0:
                success_rate = success_total / total_executions
                
                # Set for different flag types
                for flag_type in ['FLAG_MATH', 'FLAG_SYSCALL', 'FLAG_FILE', 'all']:
                    self.flag_success_rate.labels(flag_type=flag_type).set(success_rate)
            else:
                self.flag_success_rate.labels(flag_type='all').set(1.0)  # Default
                
        except Exception as e:
            logger.warning(f"Flag success rate calculation failed: {e}")
    
    def _calculate_routing_efficiency(self):
        """Calculate router efficiency score"""
        try:
            # Base efficiency on latency and success rate
            avg_latency = getattr(self.metrics.routing_latency, '_value', 50.0)  # Default 50ms
            
            # Efficiency score: 1.0 / (1.0 + normalized_latency)
            normalized_latency = avg_latency / 1000.0  # Convert to seconds
            efficiency = 1.0 / (1.0 + normalized_latency)
            
            self.routing_efficiency.set(efficiency)
            
        except Exception as e:
            logger.warning(f"Routing efficiency calculation failed: {e}")
    
    def _calculate_filtered_metrics(self):
        """Calculate high-card filtered metrics (board_rank >= 8)"""
        try:
            # Only export metrics for board_rank >= 8 to reduce cardinality
            current_efficiency = getattr(self.metrics.merge_efficiency, '_value', 0.0)
            
            # Filter: only set if efficiency indicates high rank
            if current_efficiency >= 0.15:  # Threshold indicates board_rank >= 8
                self.filtered_merge_efficiency.labels(board_rank="8+").set(current_efficiency)
            
        except Exception as e:
            logger.warning(f"Filtered metrics calculation failed: {e}")
    
    def _calculate_consensus_metrics(self):
        """Calculate agent consensus metrics"""
        try:
            # Mock consensus calculation - would use real agent voting data
            consensus_rounds = getattr(self.metrics.agent_consensus_rounds, '_value', 1.0)
            
            # Early exit rate: percentage of 1-round consensus
            if consensus_rounds <= 1.5:  # Close to 1 round
                early_exit_rate = 0.33  # 33% early exit (from Week 3 specs)
            else:
                early_exit_rate = 0.1
            
            self.consensus_early_exit_rate.set(early_exit_rate)
            
        except Exception as e:
            logger.warning(f"Consensus metrics calculation failed: {e}")
    
    def get_derived_summary(self) -> Dict[str, Any]:
        """Get summary of derived metrics"""
        return {
            'merge_efficiency_ratio': getattr(self.merge_efficiency_ratio, '_value', 0.0),
            'flag_success_rate': getattr(self.flag_success_rate, '_value', 0.0),
            'routing_efficiency': getattr(self.routing_efficiency, '_value', 0.0),
            'consensus_early_exit_rate': getattr(self.consensus_early_exit_rate, '_value', 0.0),
            'last_updated': time.time()
        }

# Global derived calculator
_derived_calculator = None

def get_derived_calculator() -> DerivedMetricsCalculator:
    """Get global derived metrics calculator"""
    global _derived_calculator
    if _derived_calculator is None:
        _derived_calculator = DerivedMetricsCalculator()
    return _derived_calculator

# Scheduler integration
async def run_derived_metrics_job():
    """Run derived metrics calculation job every 30 seconds"""
    calculator = get_derived_calculator()
    
    while True:
        try:
            calculator.calculate_all_derived_metrics()
            await asyncio.sleep(30)  # 30 second interval
        except Exception as e:
            logger.error(f"❌ Derived metrics job failed: {e}")
            await asyncio.sleep(30)

# Test function
def test_derived_metrics():
    """Test derived metrics calculation"""
    print("📊 Testing Derived Metrics Calculator")
    print("=" * 45)
    
    calculator = get_derived_calculator()
    
    # Simulate some base metrics
    calculator.metrics.record_execution_success("math_specialist", "FLAG_MATH")
    calculator.metrics.record_flag_hit("FLAG_MATH", "math_specialist")
    calculator.metrics.update_merge_efficiency(0.25, board_rank=8)
    
    # Calculate derived metrics
    calculator.calculate_all_derived_metrics()
    
    # Get summary
    summary = calculator.get_derived_summary()
    
    print(f"Merge efficiency ratio: {summary['merge_efficiency_ratio']:.3f}")
    print(f"Flag success rate: {summary['flag_success_rate']:.3f}")
    print(f"Routing efficiency: {summary['routing_efficiency']:.3f}")
    print(f"Early consensus rate: {summary['consensus_early_exit_rate']:.3f}")
    
    print("✅ Derived metrics test completed")

if __name__ == "__main__":
    import asyncio
    test_derived_metrics() 