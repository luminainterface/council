#!/usr/bin/env python3
"""
🎯 Reward Buffer - Ticket #202
Merge prompt snapshot (SQLite) with explicit feedback from Redis
to produce weighted train/holdout JSONL files for LoRA training.

Usage:
    python -m snapshot.weighted_jsonl \
        --db /snap/2025-06-05/traffic.db \
        --out-train /loras/2025-06-05/train.jsonl \
        --out-holdout /loras/2025-06-05/holdout.jsonl
"""

import json
import gzip
import random
import argparse
import sqlite3
import hashlib
import asyncio
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path

# Configuration
REDIS_URL = "redis://redis:6379/0"
TTL_DAYS = 30                    # Disregard feedback older than this
NEUTRAL_WEIGHT = 0.0
POS_WEIGHT = +1.0
NEG_WEIGHT = -1.0
HOLDOUT_RATIO = 0.1              # 10% holdout split

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Generate weighted training data from traffic and feedback")
    parser.add_argument("--db", required=True, help="SQLite traffic database path")
    parser.add_argument("--out-train", required=True, help="Output training JSONL file")
    parser.add_argument("--out-holdout", required=True, help="Output holdout JSONL file")
    parser.add_argument("--dry-run", action="store_true", help="Show stats without writing files")
    return parser.parse_args()

async def get_feedback_for_prompt(redis_client, prompt_id: str, cutoff_timestamp: float):
    """
    Get feedback for a specific prompt ID from Redis
    Returns reward weight based on most recent feedback within TTL
    """
    try:
        feedback_key = f"feedback:{prompt_id}"
        
        # Get most recent feedback (highest score in sorted set)
        feedback_items = await redis_client.zrevrange(feedback_key, 0, 0, withscores=True)
        
        if not feedback_items:
            return NEUTRAL_WEIGHT, None
        
        feedback_json, timestamp = feedback_items[0]
        
        # Check if feedback is within TTL
        if timestamp < cutoff_timestamp:
            logger.debug(f"Feedback for {prompt_id} is too old: {timestamp} < {cutoff_timestamp}")
            return NEUTRAL_WEIGHT, None
        
        # Parse feedback data
        feedback_data = json.loads(feedback_json)
        score = feedback_data.get("score", 0)
        
        # Map score to weight
        weight_map = {
            1: POS_WEIGHT,
            0: NEUTRAL_WEIGHT, 
            -1: NEG_WEIGHT
        }
        
        reward = weight_map.get(score, NEUTRAL_WEIGHT)
        logger.debug(f"Prompt {prompt_id}: score={score}, reward={reward}")
        
        return reward, feedback_data
        
    except Exception as e:
        logger.warning(f"Error getting feedback for {prompt_id}: {e}")
        return NEUTRAL_WEIGHT, None

def create_training_row(prompt_id: str, prompt_text: str, cluster_id: int, reward: float, feedback_data: dict = None):
    """Create a training row with all necessary fields"""
    row = {
        "id": prompt_id,
        "prompt": prompt_text,
        "cluster_id": cluster_id,
        "reward": reward,
        "timestamp": time.time()
    }
    
    # Add feedback metadata if available
    if feedback_data:
        row["feedback"] = {
            "score": feedback_data.get("score"),
            "comment": feedback_data.get("comment"),
            "user_session": feedback_data.get("user_session"),
            "feedback_timestamp": feedback_data.get("timestamp")
        }
    
    return row

async def process_traffic_db(db_path: str, redis_client, cutoff_timestamp: float):
    """
    Process traffic database and yield training rows with rewards
    """
    logger.info(f"Processing traffic database: {db_path}")
    
    try:
        # Connect to SQLite database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Query prompts with cluster assignments
        query = """
        SELECT 
            id, 
            text, 
            COALESCE(cluster_id, -1) as cluster_id,
            timestamp
        FROM prompts 
        ORDER BY timestamp
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        logger.info(f"Found {len(rows)} prompts in traffic database")
        
        processed_count = 0
        for prompt_id, prompt_text, cluster_id, db_timestamp in rows:
            # Get feedback for this prompt
            reward, feedback_data = await get_feedback_for_prompt(redis_client, prompt_id, cutoff_timestamp)
            
            # Create training row
            training_row = create_training_row(prompt_id, prompt_text, cluster_id, reward, feedback_data)
            
            processed_count += 1
            if processed_count % 1000 == 0:
                logger.info(f"Processed {processed_count}/{len(rows)} prompts...")
            
            yield training_row
        
        conn.close()
        logger.info(f"Completed processing {processed_count} prompts")
        
    except Exception as e:
        logger.error(f"Error processing traffic database: {e}")
        raise

def push_metrics(reward_rows: int, total_rows: int, train_rows: int, holdout_rows: int):
    """Push metrics to Pushgateway"""
    try:
        import requests
        import os
        
        pushgateway_url = os.environ.get("PUSHGATEWAY_URL", "http://pushgateway:9091")
        job_name = "reward_buffer"
        
        # Calculate metrics
        reward_ratio = reward_rows / max(1, total_rows)
        
        metrics_data = f"""# TYPE reward_rows_total counter
reward_rows_total {reward_rows}

# TYPE reward_row_ratio gauge  
reward_row_ratio {reward_ratio}

# TYPE training_rows_total counter
training_rows_total {train_rows}

# TYPE holdout_rows_total counter
holdout_rows_total {holdout_rows}

# TYPE reward_buffer_processing_timestamp gauge
reward_buffer_processing_timestamp {time.time()}
"""
        
        response = requests.post(
            f"{pushgateway_url}/metrics/job/{job_name}/instance/main",
            data=metrics_data,
            headers={"Content-Type": "text/plain"},
            timeout=10
        )
        
        if response.status_code == 200:
            logger.info(f"📊 Metrics pushed successfully: {reward_rows}/{total_rows} rewards ({reward_ratio:.1%})")
        else:
            logger.warning(f"⚠️ Metrics push failed: {response.status_code}")
            
    except Exception as e:
        logger.warning(f"⚠️ Failed to push metrics: {e}")

async def main():
    """Main processing function"""
    args = parse_args()
    
    logger.info("🎯 Starting Reward Buffer processing...")
    logger.info(f"Input DB: {args.db}")
    logger.info(f"Output train: {args.out_train}")
    logger.info(f"Output holdout: {args.out_holdout}")
    
    # Validate input files
    if not Path(args.db).exists():
        raise FileNotFoundError(f"Traffic database not found: {args.db}")
    
    # Calculate cutoff timestamp for feedback TTL
    now = datetime.utcnow()
    cutoff_timestamp = (now - timedelta(days=TTL_DAYS)).timestamp()
    logger.info(f"Feedback TTL cutoff: {datetime.fromtimestamp(cutoff_timestamp).isoformat()}")
    
    # Connect to Redis
    try:
        import aioredis
        redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
        await redis_client.ping()
        logger.info("✅ Redis connected")
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {e}")
        raise
    
    # Initialize counters
    total_rows = 0
    train_rows = 0
    holdout_rows = 0
    reward_rows = 0
    score_distribution = {-1: 0, 0: 0, 1: 0}
    
    if args.dry_run:
        logger.info("🧪 DRY RUN MODE - analyzing data only")
        
        # Process data without writing files
        async for row in process_traffic_db(args.db, redis_client, cutoff_timestamp):
            total_rows += 1
            reward = row["reward"]
            
            if reward != 0.0:
                reward_rows += 1
                if reward > 0:
                    score_distribution[1] += 1
                else:
                    score_distribution[-1] += 1
            else:
                score_distribution[0] += 1
        
        # Print dry run results
        reward_ratio = reward_rows / max(1, total_rows)
        print(f"\n📊 DRY RUN RESULTS:")
        print(f"Total prompts: {total_rows}")
        print(f"With rewards: {reward_rows} ({reward_ratio:.1%})")
        print(f"Score distribution: 👍{score_distribution[1]} / 😐{score_distribution[0]} / 👎{score_distribution[-1]}")
        print(f"KPI Status: {'✅ PASS' if reward_ratio >= 0.25 else '❌ FAIL'} (target: ≥25%)")
        
    else:
        # Create output directories
        Path(args.out_train).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out_holdout).parent.mkdir(parents=True, exist_ok=True)
        
        # Process and write training data
        logger.info("📝 Writing weighted training data...")
        
        with gzip.open(args.out_train, "wt") as f_train, \
             gzip.open(args.out_holdout, "wt") as f_holdout:
            
            async for row in process_traffic_db(args.db, redis_client, cutoff_timestamp):
                total_rows += 1
                reward = row["reward"]
                
                # Track reward statistics
                if reward != 0.0:
                    reward_rows += 1
                    if reward > 0:
                        score_distribution[1] += 1
                    else:
                        score_distribution[-1] += 1
                else:
                    score_distribution[0] += 1
                
                # Assign to train or holdout (deterministic based on prompt hash)
                prompt_hash = hashlib.md5(row["id"].encode()).hexdigest()
                is_holdout = int(prompt_hash, 16) % 100 < (HOLDOUT_RATIO * 100)
                
                if is_holdout:
                    f_holdout.write(json.dumps(row) + "\n")
                    holdout_rows += 1
                else:
                    f_train.write(json.dumps(row) + "\n")
                    train_rows += 1
        
        # Final statistics
        reward_ratio = reward_rows / max(1, total_rows)
        
        logger.info("✅ Reward Buffer processing complete!")
        logger.info(f"📊 Statistics:")
        logger.info(f"   Total prompts: {total_rows}")
        logger.info(f"   Training rows: {train_rows}")
        logger.info(f"   Holdout rows: {holdout_rows}")
        logger.info(f"   Reward coverage: {reward_rows}/{total_rows} ({reward_ratio:.1%})")
        logger.info(f"   Score distribution: 👍{score_distribution[1]} / 😐{score_distribution[0]} / 👎{score_distribution[-1]}")
        logger.info(f"   KPI Status: {'✅ PASS' if reward_ratio >= 0.25 else '❌ FAIL'} (target: ≥25%)")
        
        # Push metrics
        push_metrics(reward_rows, total_rows, train_rows, holdout_rows)
    
    # Cleanup
    await redis_client.close()
    logger.info("🎯 Reward Buffer processing finished")

if __name__ == "__main__":
    asyncio.run(main()) 