#!/usr/bin/env python3
"""
Pattern Miner α-Launch - Week 3 Strategic Orchestration
======================================================

Batch embed + HDBSCAN every 6h to discover task patterns.
Writes pattern:{sha} into Redis for router cache optimization.

Key Features:
- HDBSCAN clustering on sentence embeddings  
- Pattern discovery and merging
- Redis caching for fast lookups
- Prometheus metrics integration
"""

import asyncio
import hashlib
import json
import logging
import time
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict

import numpy as np
import redis

# Optional dependencies for production
try:
    import hdbscan
    from sentence_transformers import SentenceTransformer
    CLUSTERING_AVAILABLE = True
except ImportError:
    CLUSTERING_AVAILABLE = False

# Prometheus metrics
try:
    from prometheus_client import Counter, Gauge, Histogram
    PATTERN_MERGE_TOTAL = Counter("pattern_merge_total", "Total pattern merges")
    PATTERN_DISCOVERY_TOTAL = Counter("pattern_discovery_total", "Total patterns discovered")
    PATTERN_CACHE_HITS = Counter("pattern_cache_hits_total", "Pattern cache hits")
    PATTERN_EMBEDDINGS_TOTAL = Counter("pattern_embeddings_total", "Total embeddings computed")
    PATTERN_MERGE_LATENCY = Histogram("pattern_merge_latency_ms", "Pattern merge latency")
    PATTERN_CLUSTER_COUNT = Gauge("pattern_cluster_count", "Current number of clusters")
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

logger = logging.getLogger(__name__)

@dataclass
class TaskPattern:
    """Represents a discovered task pattern"""
    pattern_id: str
    pattern_type: str
    intent_signature: str
    example_tasks: List[str]
    embedding_centroid: List[float]
    confidence: float
    cluster_size: int
    discovered_at: datetime
    merge_count: int = 0

    def to_redis_value(self) -> str:
        """Serialize for Redis storage"""
        data = asdict(self)
        data['discovered_at'] = self.discovered_at.isoformat()
        return json.dumps(data)
    
    @classmethod
    def from_redis_value(cls, value: str) -> 'TaskPattern':
        """Deserialize from Redis"""
        data = json.loads(value)
        data['discovered_at'] = datetime.fromisoformat(data['discovered_at'])
        return cls(**data)

class PatternMiner:
    """
    Strategic pattern discovery system for Week 3 orchestration
    
    Discovers task patterns using HDBSCAN clustering and caches them
    in Redis for fast router optimization.
    """
    
    def __init__(self, 
                 redis_url: str = "redis://localhost:6379/0",
                 model_name: str = "all-MiniLM-L6-v2",
                 min_cluster_size: int = 3,
                 batch_interval_hours: int = 6):
        """Initialize the pattern miner"""
        
        self.redis_url = redis_url
        self.model_name = model_name
        self.min_cluster_size = min_cluster_size
        self.batch_interval_hours = batch_interval_hours
        
        # Initialize components
        self.redis_client = None
        self.embedding_model = None
        self.clusterer = None
        
        # State tracking
        self.last_mining_time = None
        self.discovered_patterns: Dict[str, TaskPattern] = {}
        self.running = False
        
        if not CLUSTERING_AVAILABLE:
            logger.warning("⚠️ HDBSCAN/SentenceTransformers not available - using mock patterns")
    
    async def initialize(self):
        """Initialize Redis connection and models"""
        try:
            # Connect to Redis
            self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
            self.redis_client.ping()
            logger.info(f"✅ Pattern Miner connected to Redis: {self.redis_url}")
            
            # Load embedding model
            if CLUSTERING_AVAILABLE:
                self.embedding_model = SentenceTransformer(self.model_name)
                self.clusterer = hdbscan.HDBSCAN(
                    min_cluster_size=self.min_cluster_size,
                    min_samples=2,
                    metric='cosine'
                )
                logger.info(f"✅ Embedding model loaded: {self.model_name}")
            
            # Load existing patterns from Redis
            await self._load_existing_patterns()
            
        except Exception as e:
            logger.error(f"❌ Pattern Miner initialization failed: {e}")
            raise
    
    async def _load_existing_patterns(self):
        """Load existing patterns from Redis cache"""
        try:
            pattern_keys = self.redis_client.keys("pattern:*")
            
            for key in pattern_keys:
                pattern_data = self.redis_client.get(key)
                if pattern_data:
                    pattern = TaskPattern.from_redis_value(pattern_data)
                    self.discovered_patterns[pattern.pattern_id] = pattern
            
            logger.info(f"📊 Loaded {len(self.discovered_patterns)} existing patterns from cache")
            
            if PROMETHEUS_AVAILABLE:
                PATTERN_CLUSTER_COUNT.set(len(self.discovered_patterns))
                
        except Exception as e:
            logger.warning(f"⚠️ Could not load existing patterns: {e}")
    
    async def start_mining_loop(self):
        """Start the 6-hour batch mining loop"""
        if not self.redis_client:
            await self.initialize()
        
        self.running = True
        logger.info("🚀 Pattern Miner α-launch started")
        logger.info(f"   Batch interval: {self.batch_interval_hours}h")
        logger.info(f"   Min cluster size: {self.min_cluster_size}")
        
        while self.running:
            try:
                await self._run_mining_batch()
                
                # Wait for next batch
                sleep_seconds = self.batch_interval_hours * 3600
                logger.info(f"⏰ Next mining batch in {self.batch_interval_hours}h")
                await asyncio.sleep(sleep_seconds)
                
            except Exception as e:
                logger.error(f"❌ Mining batch failed: {e}")
                # Continue with shorter interval on error
                await asyncio.sleep(300)  # 5 minutes
    
    async def _run_mining_batch(self):
        """Run a single pattern mining batch"""
        start_time = time.time()
        logger.info("🔍 Starting pattern mining batch...")
        
        # 1. Collect recent tasks
        tasks = await self._collect_recent_tasks()
        if len(tasks) < self.min_cluster_size:
            logger.info(f"⏳ Only {len(tasks)} tasks collected, skipping batch")
            return
        
        # 2. Generate embeddings
        embeddings = await self._generate_embeddings(tasks)
        
        # 3. Discover patterns via clustering
        new_patterns = await self._discover_patterns(tasks, embeddings)
        
        # 4. Merge with existing patterns
        merged_count = await self._merge_patterns(new_patterns)
        
        # 5. Update Redis cache
        await self._update_pattern_cache()
        
        batch_time = (time.time() - start_time) * 1000
        logger.info(f"✅ Mining batch complete: {len(new_patterns)} new, {merged_count} merged ({batch_time:.1f}ms)")
        
        if PROMETHEUS_AVAILABLE:
            PATTERN_MERGE_LATENCY.observe(batch_time)
            PATTERN_DISCOVERY_TOTAL.inc(len(new_patterns))
            PATTERN_MERGE_TOTAL.inc(merged_count)
    
    async def _collect_recent_tasks(self) -> List[str]:
        """Collect recent tasks from various sources"""
        tasks = []
        
        try:
            # Collect from Redis logs
            log_keys = self.redis_client.keys("swarm:log:*")
            
            for key in log_keys[-100:]:  # Last 100 log entries
                log_data = self.redis_client.get(key)
                if log_data:
                    try:
                        log_entry = json.loads(log_data)
                        if 'prompt' in log_entry:
                            tasks.append(log_entry['prompt'])
                    except json.JSONDecodeError:
                        continue
            
            # Mock tasks for development (remove in production)
            if len(tasks) < 10:
                mock_tasks = [
                    "create file config.json with settings",
                    "install package numpy for data analysis", 
                    "restart nginx service after config change",
                    "write data to output.csv file",
                    "check system status and memory usage",
                    "update package list and install security updates",
                    "create backup of database files",
                    "restart postgresql service",
                    "install pip package requests for API calls",
                    "write log entry to application.log"
                ]
                tasks.extend(mock_tasks)
            
            logger.info(f"📊 Collected {len(tasks)} tasks for pattern analysis")
            return tasks[:100]  # Limit batch size
            
        except Exception as e:
            logger.error(f"❌ Task collection failed: {e}")
            return []
    
    async def _generate_embeddings(self, tasks: List[str]) -> np.ndarray:
        """Generate embeddings for task list"""
        if not CLUSTERING_AVAILABLE:
            # Mock embeddings for development
            return np.random.rand(len(tasks), 384)
        
        try:
            embeddings = self.embedding_model.encode(tasks)
            
            if PROMETHEUS_AVAILABLE:
                PATTERN_EMBEDDINGS_TOTAL.inc(len(tasks))
            
            logger.info(f"🧠 Generated {len(embeddings)} embeddings ({embeddings.shape[1]}D)")
            return embeddings
            
        except Exception as e:
            logger.error(f"❌ Embedding generation failed: {e}")
            return np.random.rand(len(tasks), 384)  # Fallback
    
    async def _discover_patterns(self, tasks: List[str], embeddings: np.ndarray) -> List[TaskPattern]:
        """Discover patterns using HDBSCAN clustering"""
        if not CLUSTERING_AVAILABLE:
            # Mock pattern discovery
            return self._create_mock_patterns(tasks)
        
        try:
            # Run HDBSCAN clustering
            cluster_labels = self.clusterer.fit_predict(embeddings)
            
            patterns = []
            unique_labels = set(cluster_labels)
            
            for label in unique_labels:
                if label == -1:  # Noise cluster
                    continue
                
                # Get tasks in this cluster
                cluster_mask = cluster_labels == label
                cluster_tasks = [tasks[i] for i in range(len(tasks)) if cluster_mask[i]]
                cluster_embeddings = embeddings[cluster_mask]
                
                if len(cluster_tasks) < self.min_cluster_size:
                    continue
                
                # Compute centroid
                centroid = np.mean(cluster_embeddings, axis=0)
                
                # Generate pattern
                pattern = TaskPattern(
                    pattern_id=self._generate_pattern_id(cluster_tasks),
                    pattern_type=self._classify_pattern_type(cluster_tasks),
                    intent_signature=self._extract_intent_signature(cluster_tasks),
                    example_tasks=cluster_tasks[:5],  # Keep top 5 examples
                    embedding_centroid=centroid.tolist(),
                    confidence=self._calculate_pattern_confidence(cluster_tasks, cluster_embeddings),
                    cluster_size=len(cluster_tasks),
                    discovered_at=datetime.now()
                )
                
                patterns.append(pattern)
            
            logger.info(f"🔍 Discovered {len(patterns)} patterns from {len(unique_labels)-1} clusters")
            return patterns
            
        except Exception as e:
            logger.error(f"❌ Pattern discovery failed: {e}")
            return []
    
    def _create_mock_patterns(self, tasks: List[str]) -> List[TaskPattern]:
        """Create mock patterns for development"""
        patterns = []
        
        # File operations pattern
        file_tasks = [t for t in tasks if any(word in t.lower() for word in ['file', 'create', 'write'])]
        if len(file_tasks) >= 2:
            patterns.append(TaskPattern(
                pattern_id="file_ops_001",
                pattern_type="file_operations",
                intent_signature="os_file_*",
                example_tasks=file_tasks[:3],
                embedding_centroid=[0.1] * 384,
                confidence=0.85,
                cluster_size=len(file_tasks),
                discovered_at=datetime.now()
            ))
        
        # Package management pattern  
        pkg_tasks = [t for t in tasks if any(word in t.lower() for word in ['install', 'package', 'pip'])]
        if len(pkg_tasks) >= 2:
            patterns.append(TaskPattern(
                pattern_id="pkg_mgmt_001", 
                pattern_type="package_management",
                intent_signature="package_install",
                example_tasks=pkg_tasks[:3],
                embedding_centroid=[0.2] * 384,
                confidence=0.78,
                cluster_size=len(pkg_tasks),
                discovered_at=datetime.now()
            ))
        
        return patterns
    
    def _generate_pattern_id(self, tasks: List[str]) -> str:
        """Generate unique pattern ID from task content"""
        content = "|".join(sorted(tasks))
        hash_obj = hashlib.sha256(content.encode())
        return f"pattern_{hash_obj.hexdigest()[:12]}"
    
    def _classify_pattern_type(self, tasks: List[str]) -> str:
        """Classify pattern type based on task content"""
        combined = " ".join(tasks).lower()
        
        if any(word in combined for word in ['file', 'create', 'write', 'read']):
            return "file_operations"
        elif any(word in combined for word in ['install', 'package', 'pip', 'apt']):
            return "package_management"
        elif any(word in combined for word in ['restart', 'service', 'systemctl']):
            return "service_management"
        elif any(word in combined for word in ['status', 'check', 'monitor']):
            return "system_monitoring"
        else:
            return "general"
    
    def _extract_intent_signature(self, tasks: List[str]) -> str:
        """Extract intent signature from task cluster"""
        pattern_type = self._classify_pattern_type(tasks)
        
        signatures = {
            "file_operations": "os_file_*",
            "package_management": "package_install", 
            "service_management": "service_restart",
            "system_monitoring": "system_info",
            "general": "general"
        }
        
        return signatures.get(pattern_type, "general")
    
    def _calculate_pattern_confidence(self, tasks: List[str], embeddings: np.ndarray) -> float:
        """Calculate confidence score for pattern"""
        if len(tasks) < 2:
            return 0.5
        
        # Simple confidence based on cluster size and cohesion
        size_score = min(len(tasks) / 10.0, 1.0)
        
        # Compute cohesion (average pairwise similarity)
        if CLUSTERING_AVAILABLE and len(embeddings) > 1:
            from sklearn.metrics.pairwise import cosine_similarity
            similarities = cosine_similarity(embeddings)
            cohesion = np.mean(similarities[np.triu_indices_from(similarities, k=1)])
        else:
            cohesion = 0.7  # Mock cohesion
        
        confidence = (size_score * 0.3) + (cohesion * 0.7)
        return min(confidence, 0.95)
    
    async def _merge_patterns(self, new_patterns: List[TaskPattern]) -> int:
        """Merge new patterns with existing ones"""
        merged_count = 0
        
        for new_pattern in new_patterns:
            # Check for similar existing patterns
            similar_pattern = self._find_similar_pattern(new_pattern)
            
            if similar_pattern:
                # Merge patterns
                await self._merge_pattern_pair(similar_pattern, new_pattern)
                merged_count += 1
            else:
                # Add as new pattern
                self.discovered_patterns[new_pattern.pattern_id] = new_pattern
        
        return merged_count
    
    def _find_similar_pattern(self, pattern: TaskPattern) -> Optional[TaskPattern]:
        """Find similar existing pattern for merging"""
        for existing_pattern in self.discovered_patterns.values():
            # Check type similarity
            if existing_pattern.pattern_type == pattern.pattern_type:
                # Check intent similarity  
                if existing_pattern.intent_signature == pattern.intent_signature:
                    return existing_pattern
        
        return None
    
    async def _merge_pattern_pair(self, existing: TaskPattern, new: TaskPattern):
        """Merge two similar patterns"""
        # Combine example tasks (keep unique)
        combined_tasks = list(set(existing.example_tasks + new.example_tasks))[:10]
        
        # Weighted centroid merge
        total_size = existing.cluster_size + new.cluster_size
        existing_weight = existing.cluster_size / total_size
        new_weight = new.cluster_size / total_size
        
        merged_centroid = [
            existing_weight * existing.embedding_centroid[i] + new_weight * new.embedding_centroid[i]
            for i in range(len(existing.embedding_centroid))
        ]
        
        # Update existing pattern
        existing.example_tasks = combined_tasks
        existing.embedding_centroid = merged_centroid
        existing.cluster_size = total_size
        existing.confidence = max(existing.confidence, new.confidence)
        existing.merge_count += 1
        
        logger.info(f"🔗 Merged patterns: {existing.pattern_id} (confidence: {existing.confidence:.3f})")
    
    async def _update_pattern_cache(self):
        """Update Redis cache with current patterns"""
        try:
            pipe = self.redis_client.pipeline()
            
            for pattern in self.discovered_patterns.values():
                key = f"pattern:{pattern.pattern_id}"
                pipe.set(key, pattern.to_redis_value())
                pipe.expire(key, 86400 * 7)  # 1 week TTL
            
            pipe.execute()
            
            if PROMETHEUS_AVAILABLE:
                PATTERN_CLUSTER_COUNT.set(len(self.discovered_patterns))
            
            logger.info(f"💾 Updated {len(self.discovered_patterns)} patterns in Redis cache")
            
        except Exception as e:
            logger.error(f"❌ Cache update failed: {e}")
    
    async def get_pattern_for_task(self, task: str) -> Optional[TaskPattern]:
        """Get matching pattern for a task (router integration)"""
        if not CLUSTERING_AVAILABLE:
            # Simple keyword matching for development
            task_lower = task.lower()
            
            for pattern in self.discovered_patterns.values():
                if any(word in task_lower for word in pattern.intent_signature.split("_")):
                    if PROMETHEUS_AVAILABLE:
                        PATTERN_CACHE_HITS.inc()
                    return pattern
            
            return None
        
        try:
            # Generate embedding for task
            task_embedding = self.embedding_model.encode([task])[0]
            
            # Find best matching pattern
            best_pattern = None
            best_similarity = 0.0
            
            for pattern in self.discovered_patterns.values():
                centroid = np.array(pattern.embedding_centroid)
                similarity = np.dot(task_embedding, centroid) / (
                    np.linalg.norm(task_embedding) * np.linalg.norm(centroid)
                )
                
                if similarity > best_similarity and similarity > 0.7:  # Similarity threshold
                    best_similarity = similarity
                    best_pattern = pattern
            
            if best_pattern and PROMETHEUS_AVAILABLE:
                PATTERN_CACHE_HITS.inc()
            
            return best_pattern
            
        except Exception as e:
            logger.error(f"❌ Pattern lookup failed: {e}")
            return None
    
    async def stop(self):
        """Stop the pattern miner"""
        self.running = False
        logger.info("🛑 Pattern Miner stopped")

# Global instance for router integration
_pattern_miner = None

async def get_pattern_miner() -> PatternMiner:
    """Get global pattern miner instance"""
    global _pattern_miner
    if _pattern_miner is None:
        _pattern_miner = PatternMiner()
        await _pattern_miner.initialize()
    return _pattern_miner

# CLI interface
async def main():
    """Main CLI interface for pattern miner"""
    print("🔍 Pattern Miner α-Launch - Week 3")
    print("=" * 50)
    
    miner = PatternMiner()
    await miner.initialize()
    
    print(f"📊 Loaded {len(miner.discovered_patterns)} existing patterns")
    
    # Run single batch for testing
    await miner._run_mining_batch()
    
    print(f"✅ Pattern mining complete: {len(miner.discovered_patterns)} total patterns")
    
    # Display patterns
    for pattern in miner.discovered_patterns.values():
        print(f"\n🎯 Pattern: {pattern.pattern_id}")
        print(f"   Type: {pattern.pattern_type}")
        print(f"   Intent: {pattern.intent_signature}")
        print(f"   Confidence: {pattern.confidence:.3f}")
        print(f"   Examples: {pattern.example_tasks[:2]}")

if __name__ == "__main__":
    asyncio.run(main()) 