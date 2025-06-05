#!/usr/bin/env python3
"""
Exports a drift_score gauge every 30 s.

• Reads two snapshots from /snapshots:  current.json & previous.json
• Each snapshot = {"concept_id": embedding_vector}
• Computes average cosine drift across all concepts.
"""

import json, os, time, math
from prometheus_client import start_http_server, Gauge

PORT = int(os.getenv("PORT", 9105))
SNAP_DIR = os.getenv("SNAP_DIR", "/snapshots")
DRIFT = Gauge("drift_score", "Average semantic drift (0 = identical, 1 = orthogonal)")

def cosine(a, b):
    dot = sum(x*y for x, y in zip(a, b))
    na = math.sqrt(sum(x*x for x in a))
    nb = math.sqrt(sum(y*y for y in b))
    return 1 - dot / (na * nb + 1e-9)

def compute_drift():
    try:
        cur = json.load(open(f"{SNAP_DIR}/current.json"))
        prev = json.load(open(f"{SNAP_DIR}/previous.json"))
    except FileNotFoundError:
        return 0
    common = cur.keys() & prev.keys()
    if not common:
        return 0
    return sum(cosine(cur[k], prev[k]) for k in common) / len(common)

if __name__ == "__main__":
    start_http_server(PORT)
    while True:
        DRIFT.set(compute_drift())
        time.sleep(30) 