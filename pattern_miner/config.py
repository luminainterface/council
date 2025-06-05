# swarm/api/pattern_miner/config.py
from datetime import timedelta

REDIS_PROMPT_KEY = "prompt_queue"          # list → pushes every /orchestrate hit
REDIS_CLUSTER_PREFIX = "pattern:"          # hash → cluster-id
REDIS_CLUSTER_META = "pattern_meta"        # hash(cluster_id) → {samples, centroid}

EMBED_MODEL_NAME = "thenlper/gte-small"    # 110 MB, ~6 ms/token on CPU
MIN_PROMPTS_PER_RUN = 2_000                # skip run if not enough new data
RUN_INTERVAL = timedelta(hours=6)          # background loop sleep
MAX_ROUTE_LATENCY_MS = 50                  # guard-rail for /orchestrate 