# swarm/api/pattern_miner/worker.py
import hashlib, json, time, asyncio, logging
from datetime import datetime, timedelta
import redis.asyncio as redis
import numpy as np
from hdbscan import HDBSCAN
from sentence_transformers import SentenceTransformer
from .config import *

log = logging.getLogger("pattern_miner")

class PatternMiner:
    def __init__(self, redis_url: str = "redis://redis:6379/0"):
        self.r = redis.from_url(redis_url, decode_responses=True)
        self.model = SentenceTransformer(EMBED_MODEL_NAME)

    async def run_forever(self):
        log.info("Pattern-Miner started ✅")
        while True:
            await self._maybe_cluster()
            await asyncio.sleep(RUN_INTERVAL.total_seconds())

    async def _maybe_cluster(self):
        size = await self.r.llen(REDIS_PROMPT_KEY)
        if size < MIN_PROMPTS_PER_RUN:
            log.info("Not enough prompts yet (%s), skipping clustering", size)
            return

        # pop the whole queue atomically
        pipe = self.r.pipeline()
        pipe.lrange(REDIS_PROMPT_KEY, 0, -1)
        pipe.delete(REDIS_PROMPT_KEY)
        prompts, _ = await pipe.execute()

        embeds = self.model.encode(prompts, convert_to_numpy=True,
                                   batch_size=64, show_progress_bar=False)

        # HDBSCAN with cosine metric
        clusterer = HDBSCAN(min_cluster_size=15, metric="euclidean")
        labels = clusterer.fit_predict(embeds)

        # iterate clusters
        for idx, lbl in enumerate(labels):
            if lbl == -1:
                continue                                    # outliers → ignore
            text = prompts[idx]
            cluster_id = f"c{lbl}"
            hash_key = REDIS_CLUSTER_PREFIX + sha1(text)
            await self.r.set(hash_key, cluster_id)

        await self._update_meta(clusterer, prompts, embeds)
        log.info("Clustered %s prompts into %s clusters", len(prompts),
                 clusterer.labels_.max() + 1)

    async def _update_meta(self, clusterer, prompts, embeds):
        """Record centroid & sample count per cluster (optional analytic)."""
        centroids = {}
        for lbl in set(clusterer.labels_):
            if lbl == -1:
                continue
            mask = clusterer.labels_ == lbl
            centroid = embeds[mask].mean(axis=0)
            centroids[f"c{lbl}"] = {
                "samples": int(mask.sum()),
                "centroid": centroid.tolist()
            }
        if centroids:
            await self.r.hset(REDIS_CLUSTER_META, mapping={
                k: json.dumps(v) for k, v in centroids.items()
            })

def sha1(txt: str) -> str:
    return hashlib.sha1(txt.encode()).hexdigest() 