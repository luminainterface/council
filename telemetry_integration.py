#!/usr/bin/env python3
"""
Telemetry Integration - Week 3 Strategic Orchestration
=====================================================

Centralized telemetry collection for:
- Chess engine metrics (board_rank, moves_total, merge_events_total)
- Agent SDK metrics (confidence scores, voting rounds, early exits)
- Pattern miner metrics (discovery, merge latency)
- Guard rail alerts and thresholds

Exports to Prometheus and provides health endpoint integration.
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

# Prometheus metrics
try:
    from prometheus_client import (
        Counter, Gauge, Histogram, Summary, 
        CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

logger = logging.getLogger(__name__)

class Week3Metrics:
    """Centralized metrics for Week 3 components"""
    
    def __init__(self):
        # Use custom registry to avoid conflicts
        self.registry = CollectorRegistry()
        
        if PROMETHEUS_AVAILABLE:
            # Chess Engine Metrics
            self.board_rank = Gauge(
                'board_rank', 
                'Current chess board complexity rank',
                registry=self.registry
            )
            
            self.moves_total = Counter(
                'moves_total',
                'Total moves made on chess board',
                ['move_type'],
                registry=self.registry
            )
            
            self.merge_events_total = Counter(
                'merge_events_total',
                'Total merge events completed',
                registry=self.registry
            )
            
            # Agent SDK Metrics
            self.agent_confidence_score = Gauge(
                'agent_confidence_score',
                'Current agent confidence scores',
                ['agent_id', 'agent_type'],
                registry=self.registry
            )
            
            self.agent_voting_rounds = Histogram(
                'agent_voting_rounds',
                'Number of voting rounds to reach consensus',
                registry=self.registry
            )
            
            self.agent_early_exit_total = Counter(
                'agent_early_exit_total',
                'Total early consensus exits',
                registry=self.registry
            )
            
            self.agent_proposal_latency_ms = Histogram(
                'agent_proposal_latency_ms',
                'Agent proposal generation latency in milliseconds',
                registry=self.registry
            )
            
            # Pattern Miner Metrics
            self.pattern_discovery_total = Counter(
                'pattern_discovery_total',
                'Total patterns discovered',
                registry=self.registry
            )
            
            self.pattern_merge_latency_ms = Histogram(
                'pattern_merge_latency_ms',
                'Pattern merge operation latency in milliseconds',
                registry=self.registry
            )
            
            self.pattern_cluster_count = Gauge(
                'pattern_cluster_count',
                'Current number of pattern clusters',
                registry=self.registry
            )
            
            # vLLM Integration Metrics
            self.vllm_inflight_pct = Gauge(
                'vllm_inflight_pct',
                'Percentage of vLLM inflight requests vs max',
                registry=self.registry
            )
            
            self.mixtral_generation_seconds_total = Counter(
                'mixtral_generation_seconds_total',
                'Total time spent in Mixtral generation',
                ['board_rank_range'],
                registry=self.registry
            )
            
            # System Health Metrics
            self.week3_component_health = Gauge(
                'week3_component_health',
                'Health status of Week 3 components (1=healthy, 0=unhealthy)',
                ['component'],
                registry=self.registry
            )
            
            logger.info("✅ Week 3 metrics initialized with Prometheus")
        else:
            logger.warning("⚠️ Prometheus not available - using mock metrics")
            self._init_mock_metrics()
    
    def _init_mock_metrics(self):
        """Initialize mock metrics for development"""
        class MockMetric:
            def __init__(self, name):
                self.name = name
                self.value = 0
            
            def inc(self, amount=1):
                self.value += amount
            
            def set(self, value):
                self.value = value
            
            def observe(self, value):
                self.value = value
            
            def labels(self, **kwargs):
                return self
        
        # Create mock versions of all metrics
        for attr_name in dir(self):
            if not attr_name.startswith('_') and attr_name not in ['registry']:
                attr = getattr(self, attr_name)
                if hasattr(attr, 'inc') or hasattr(attr, 'set') or hasattr(attr, 'observe'):
                    setattr(self, attr_name, MockMetric(attr_name))
    
    def update_chess_metrics(self, board_state: Dict):
        """Update chess engine metrics"""
        try:
            if 'board_rank' in board_state:
                self.board_rank.set(board_state['board_rank'])
            
            if 'metrics' in board_state:
                metrics = board_state['metrics']
                
                # Update move counters (increment by difference)
                if 'moves_total' in metrics:
                    current_moves = getattr(self.moves_total, '_value', {})
                    new_total = metrics['moves_total']
                    diff = new_total - sum(current_moves.values()) if current_moves else new_total
                    if diff > 0:
                        self.moves_total.labels(move_type='general').inc(diff)
                
                if 'merges_total' in metrics:
                    current_merges = getattr(self.merge_events_total, '_value', 0)
                    new_total = metrics['merges_total']
                    diff = new_total - current_merges if hasattr(self.merge_events_total, '_value') else new_total
                    if diff > 0:
                        self.merge_events_total.inc(diff)
            
        except Exception as e:
            logger.warning(f"⚠️ Chess metrics update failed: {e}")
    
    def update_agent_metrics(self, agent_stats: Dict):
        """Update agent SDK metrics"""
        try:
            for agent_id, stats in agent_stats.get('agents', {}).items():
                confidence = stats.get('average_confidence', 0.0)
                agent_type = stats.get('type', 'unknown')
                
                self.agent_confidence_score.labels(
                    agent_id=agent_id,
                    agent_type=agent_type
                ).set(confidence)
            
            # Update voting efficiency
            if 'voting_rounds_avg' in agent_stats:
                self.agent_voting_rounds.observe(agent_stats['voting_rounds_avg'])
            
        except Exception as e:
            logger.warning(f"⚠️ Agent metrics update failed: {e}")
    
    def update_pattern_metrics(self, pattern_count: int, discovery_count: int = 0):
        """Update pattern miner metrics"""
        try:
            self.pattern_cluster_count.set(pattern_count)
            
            if discovery_count > 0:
                self.pattern_discovery_total.inc(discovery_count)
                
        except Exception as e:
            logger.warning(f"⚠️ Pattern metrics update failed: {e}")
    
    def update_vllm_metrics(self, inflight_pct: float, generation_time: float = 0, board_rank: int = 0):
        """Update vLLM integration metrics"""
        try:
            self.vllm_inflight_pct.set(inflight_pct)
            
            if generation_time > 0:
                rank_range = '<16' if board_rank < 16 else '>=16'
                self.mixtral_generation_seconds_total.labels(
                    board_rank_range=rank_range
                ).inc(generation_time)
                
        except Exception as e:
            logger.warning(f"⚠️ vLLM metrics update failed: {e}")
    
    def record_component_health(self, component: str, healthy: bool):
        """Record component health status"""
        try:
            self.week3_component_health.labels(component=component).set(1 if healthy else 0)
        except Exception as e:
            logger.warning(f"⚠️ Health metric update failed for {component}: {e}")
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get current metrics summary"""
        summary = {
            'timestamp': datetime.now().isoformat(),
            'chess_engine': {
                'board_rank': getattr(self.board_rank, '_value', 0),
                'total_moves': sum(getattr(self.moves_total, '_value', {}).values()),
                'merge_events': getattr(self.merge_events_total, '_value', 0)
            },
            'pattern_miner': {
                'cluster_count': getattr(self.pattern_cluster_count, '_value', 0),
                'discovery_total': getattr(self.pattern_discovery_total, '_value', 0)
            },
            'vllm': {
                'inflight_pct': getattr(self.vllm_inflight_pct, '_value', 0.0)
            }
        }
        
        # Calculate derived metrics
        chess = summary['chess_engine']
        if chess['total_moves'] > 0:
            summary['derived'] = {
                'merge_efficiency': chess['merge_events'] / chess['total_moves'],
                'moves_per_rank': chess['total_moves'] / max(1, chess['board_rank'])
            }
        
        return summary
    
    def export_prometheus_metrics(self) -> str:
        """Export metrics in Prometheus format"""
        if PROMETHEUS_AVAILABLE:
            return generate_latest(self.registry).decode('utf-8')
        else:
            # Mock Prometheus format
            lines = []
            for attr_name in dir(self):
                if not attr_name.startswith('_') and hasattr(getattr(self, attr_name), 'value'):
                    metric = getattr(self, attr_name)
                    lines.append(f"# TYPE {attr_name} gauge")
                    lines.append(f"{attr_name} {getattr(metric, 'value', 0)}")
            return '\n'.join(lines)

# Global metrics instance
_week3_metrics = None

def get_week3_metrics() -> Week3Metrics:
    """Get global Week 3 metrics instance"""
    global _week3_metrics
    if _week3_metrics is None:
        _week3_metrics = Week3Metrics()
    return _week3_metrics

class TelemetryCollector:
    """Collects telemetry from all Week 3 components"""
    
    def __init__(self):
        self.metrics = get_week3_metrics()
        self.collection_interval = 5.0  # 5 seconds
        self.running = False
        
        # Component health tracking
        self.component_status = {
            'chess_engine': False,
            'agent_router': False,
            'pattern_miner': False,
            'vllm_integration': False
        }
    
    async def start_collection(self):
        """Start continuous telemetry collection"""
        self.running = True
        logger.info("🚀 Starting Week 3 telemetry collection")
        
        while self.running:
            try:
                await self._collect_all_metrics()
                await asyncio.sleep(self.collection_interval)
            except Exception as e:
                logger.error(f"❌ Telemetry collection error: {e}")
                await asyncio.sleep(5.0)  # Back off on error
    
    async def _collect_all_metrics(self):
        """Collect metrics from all components"""
        start_time = time.time()
        
        # Collect from chess engine
        await self._collect_chess_metrics()
        
        # Collect from agent router  
        await self._collect_agent_metrics()
        
        # Collect from pattern miner
        await self._collect_pattern_metrics()
        
        # Collect from vLLM integration
        await self._collect_vllm_metrics()
        
        # Update component health
        for component, healthy in self.component_status.items():
            self.metrics.record_component_health(component, healthy)
        
        collection_time = (time.time() - start_time) * 1000
        logger.debug(f"📊 Telemetry collection completed: {collection_time:.1f}ms")
    
    async def _collect_chess_metrics(self):
        """Collect chess engine metrics"""
        try:
            # In real implementation, this would query the chess engine
            # For now, simulate with mock data
            mock_board_state = {
                'board_rank': 8,
                'metrics': {
                    'moves_total': 15,
                    'merges_total': 3
                }
            }
            
            self.metrics.update_chess_metrics(mock_board_state)
            self.component_status['chess_engine'] = True
            
        except Exception as e:
            logger.warning(f"⚠️ Chess metrics collection failed: {e}")
            self.component_status['chess_engine'] = False
    
    async def _collect_agent_metrics(self):
        """Collect agent router metrics"""
        try:
            # Mock agent stats
            mock_agent_stats = {
                'voting_rounds_avg': 2.3,
                'agents': {
                    'cursor_001': {'average_confidence': 0.85, 'type': 'cursor'},
                    'o3_001': {'average_confidence': 0.92, 'type': 'o3'}
                }
            }
            
            self.metrics.update_agent_metrics(mock_agent_stats)
            self.component_status['agent_router'] = True
            
        except Exception as e:
            logger.warning(f"⚠️ Agent metrics collection failed: {e}")
            self.component_status['agent_router'] = False
    
    async def _collect_pattern_metrics(self):
        """Collect pattern miner metrics"""
        try:
            # Mock pattern data
            self.metrics.update_pattern_metrics(pattern_count=5, discovery_count=1)
            self.component_status['pattern_miner'] = True
            
        except Exception as e:
            logger.warning(f"⚠️ Pattern metrics collection failed: {e}")
            self.component_status['pattern_miner'] = False
    
    async def _collect_vllm_metrics(self):
        """Collect vLLM integration metrics"""
        try:
            # Mock vLLM data
            self.metrics.update_vllm_metrics(inflight_pct=0.65, generation_time=1.2, board_rank=8)
            self.component_status['vllm_integration'] = True
            
        except Exception as e:
            logger.warning(f"⚠️ vLLM metrics collection failed: {e}")
            self.component_status['vllm_integration'] = False
    
    def stop_collection(self):
        """Stop telemetry collection"""
        self.running = False
        logger.info("🛑 Stopped Week 3 telemetry collection")
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status"""
        healthy_count = sum(1 for status in self.component_status.values() if status)
        total_count = len(self.component_status)
        
        return {
            'overall_healthy': healthy_count == total_count,
            'health_score': healthy_count / total_count,
            'components': self.component_status,
            'metrics_summary': self.metrics.get_metrics_summary()
        }

# CLI interface for testing
async def test_telemetry():
    """Test telemetry collection system"""
    print("📊 Testing Week 3 Telemetry Integration")
    print("=" * 50)
    
    collector = TelemetryCollector()
    
    # Run collection for a few cycles
    print("🚀 Starting telemetry collection...")
    collection_task = asyncio.create_task(collector.start_collection())
    
    # Let it run for 10 seconds
    await asyncio.sleep(10)
    
    # Stop collection
    collector.stop_collection()
    collection_task.cancel()
    
    # Get health status
    health = collector.get_health_status()
    print(f"\n📊 Health Status:")
    print(f"   Overall: {'✅ Healthy' if health['overall_healthy'] else '❌ Unhealthy'}")
    print(f"   Score: {health['health_score']:.1%}")
    
    for component, status in health['components'].items():
        print(f"   {component}: {'✅' if status else '❌'}")
    
    # Display metrics summary
    summary = health['metrics_summary']
    print(f"\n📈 Metrics Summary:")
    print(f"   Chess Board Rank: {summary['chess_engine']['board_rank']}")
    print(f"   Total Moves: {summary['chess_engine']['total_moves']}")
    print(f"   Pattern Clusters: {summary['pattern_miner']['cluster_count']}")
    print(f"   vLLM Inflight: {summary['vllm']['inflight_pct']:.1%}")
    
    if 'derived' in summary:
        print(f"   Merge Efficiency: {summary['derived']['merge_efficiency']:.1%}")
    
    # Export Prometheus metrics
    metrics_export = collector.metrics.export_prometheus_metrics()
    print(f"\n📤 Prometheus metrics exported ({len(metrics_export)} bytes)")
    
    print(f"\n🎯 Week 3 Telemetry Ready!")

if __name__ == "__main__":
    asyncio.run(test_telemetry()) 