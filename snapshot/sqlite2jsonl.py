# snapshot/sqlite2jsonl.py
"""SQLite to JSONL converter for training data generation"""

import argparse
import json
import random
import sqlite3
import hashlib
import redis
from pattern_miner.config import REDIS_CLUSTER_PREFIX

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--out-train", required=True)
    parser.add_argument("--out-holdout", required=True)
    args = parser.parse_args()

    # Connect to Redis for pattern lookups
    try:
        r = redis.from_url("redis://redis:6379/0", decode_responses=True)
    except:
        r = None
        print("⚠️ Redis unavailable, cluster IDs will be None")

    # Connect to SQLite database
    conn = sqlite3.connect(args.db)
    cur = conn.cursor()

    train_count = 0
    holdout_count = 0

    with open(args.out_train, "w") as f_train, open(args.out_holdout, "w") as f_hold:
        for row in cur.execute("SELECT id, text FROM prompts"):
            pid, prompt = row
            
            # Fetch cluster ID from Redis patterns
            cid = None
            if r:
                try:
                    prompt_hash = hashlib.sha1(prompt.encode()).hexdigest()
                    cid = r.get(REDIS_CLUSTER_PREFIX + prompt_hash)
                except:
                    pass
            
            # Create training item
            item = {
                "id": pid, 
                "prompt": prompt, 
                "cluster_id": cid
            }

            # Safety filters
            if len(prompt) > 4000:
                continue
            if "forbidden" in prompt.lower():
                continue
            if len(prompt.strip()) < 10:
                continue

            # Split train/holdout (90/10)
            if random.random() < 0.1:
                f_hold.write(json.dumps(item) + "\n")
                holdout_count += 1
            else:
                f_train.write(json.dumps(item) + "\n")
                train_count += 1

    conn.close()
    
    print(f"✅ Generated {train_count} training examples")
    print(f"✅ Generated {holdout_count} holdout examples")
    print(f"📊 Holdout ratio: {holdout_count/(train_count+holdout_count)*100:.1f}%")

if __name__ == "__main__":
    main() 