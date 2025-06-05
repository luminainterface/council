#!/usr/bin/env python3
"""
Minimal Redis queue test for ShellExecutor
"""

import asyncio
import json
import uuid
import redis.asyncio as aioredis

async def test_redis_basic():
    """Test basic Redis queue functionality"""
    
    # Connect to Redis
    redis = aioredis.from_url("redis://localhost:6379/0", decode_responses=True)
    
    try:
        # Test connection
        pong = await redis.ping()
        print(f"✅ Redis connected: {pong}")
        
        # Check queue lengths
        q_len = await redis.llen("swarm:exec:q")
        resp_len = await redis.llen("swarm:exec:resp")
        print(f"📊 Queue status: {q_len} pending, {resp_len} responses")
        
        # Push a simple test job
        job_id = str(uuid.uuid4())
        test_job = {
            "id": job_id,
            "code": "print('Hello from Redis queue!')"
        }
        
        await redis.rpush("swarm:exec:q", json.dumps(test_job))
        print(f"🔧 Pushed test job {job_id[:8]}...")
        
        # Wait briefly to see if anything processes it
        print("⏳ Waiting 3 seconds for processing...")
        await asyncio.sleep(3)
        
        # Check if there's a response
        new_q_len = await redis.llen("swarm:exec:q")
        new_resp_len = await redis.llen("swarm:exec:resp")
        print(f"📊 After 3s: {new_q_len} pending, {new_resp_len} responses")
        
        if new_resp_len > resp_len:
            # Try to get the response
            response = await redis.lpop("swarm:exec:resp")
            if response:
                resp_data = json.loads(response)
                print(f"✅ Got response: {resp_data}")
                return True
        
        if new_q_len == q_len + 1:
            print("⚠️ Job still in queue - ShellExecutor consumer not running")
            # Clean up
            await redis.lpop("swarm:exec:q")  # Remove our test job
        
        return False
        
    finally:
        await redis.aclose()

if __name__ == "__main__":
    asyncio.run(test_redis_basic()) 