#!/usr/bin/env python3
"""
Simple test for hardened queue debugging
"""

import redis
import json
import uuid
import time

def test_hardened_queue():
    """Test hardened queue status"""
    
    r = redis.Redis()
    
    # Check queue status
    ready = r.llen("swarm:exec:q")
    processing = r.llen("swarm:exec:processing")
    done = r.llen("swarm:exec:resp")
    processing_ts = r.zcard("swarm:exec:processing_ts")
    
    print(f"Queue Status:")
    print(f"  Ready: {ready}")
    print(f"  Processing: {processing}")
    print(f"  Done: {done}")
    print(f"  Processing TS: {processing_ts}")
    
    # Send a simple test job
    job_id = str(uuid.uuid4())
    job = {
        "id": job_id,
        "code": "print('Hardened queue test!')"
    }
    
    print(f"\nSending test job {job_id[:8]}...")
    r.rpush("swarm:exec:q", json.dumps(job))
    
    # Wait and check status
    for i in range(10):
        time.sleep(1)
        
        ready = r.llen("swarm:exec:q")
        processing = r.llen("swarm:exec:processing")
        done = r.llen("swarm:exec:resp")
        
        print(f"  {i+1}s: Ready={ready}, Processing={processing}, Done={done}")
        
        if done > 0:
            # Get response
            response_raw = r.lpop("swarm:exec:resp")
            if response_raw:
                response = json.loads(response_raw)
                if response["id"] == job_id:
                    print(f"✅ Got response: {response}")
                    return True
                else:
                    # Put it back if different job
                    r.lpush("swarm:exec:resp", response_raw)
    
    print("❌ No response received")
    return False

if __name__ == "__main__":
    test_hardened_queue() 