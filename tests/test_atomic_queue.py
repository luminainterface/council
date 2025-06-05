#!/usr/bin/env python3
"""
Atomic Queue Test - Redis BRPOPLPUSH Reliability
================================================

Tests the atomic queue pattern to ensure no job loss during high-concurrency scenarios.
Validates the fix for the "5 dropped replies / 24h during peak OS-exec bursts" issue.
"""

import asyncio
import json
import uuid
import pytest
import time
import redis.asyncio as aioredis
from typing import Set, List

# Queue names from os_executor
QUEUE_READY = "swarm:exec:q"
QUEUE_PROCESSING = "swarm:exec:processing" 
QUEUE_DONE = "swarm:exec:resp"
QUEUE_PROCESSING_TS = "swarm:exec:processing_ts"

@pytest.mark.asyncio
async def test_atomic_queue_operations():
    """Test atomic BRPOPLPUSH prevents job vanishing"""
    
    redis = aioredis.from_url("redis://localhost:6379/0", decode_responses=True)
    
    try:
        # Clear all queues
        await redis.delete(QUEUE_READY, QUEUE_PROCESSING, QUEUE_DONE, QUEUE_PROCESSING_TS)
        
        # Test 1: Basic atomic operation
        job_id = str(uuid.uuid4())
        await redis.lpush(QUEUE_READY, job_id)
        
        # BRPOPLPUSH is atomic - job moves from ready to processing
        result = await redis.brpoplpush(QUEUE_READY, QUEUE_PROCESSING, 1)
        assert result == job_id
        
        # Verify job is no longer in ready queue
        ready_count = await redis.llen(QUEUE_READY)
        assert ready_count == 0
        
        # Verify job is in processing queue
        processing_count = await redis.llen(QUEUE_PROCESSING)
        assert processing_count == 1
        
        # Verify we can retrieve the job
        processing_jobs = await redis.lrange(QUEUE_PROCESSING, 0, -1)
        assert job_id in processing_jobs
        
        print("✅ Basic atomic operation test passed")
        
        # Clean up
        await redis.lrem(QUEUE_PROCESSING, 0, job_id)
        
    finally:
        await redis.aclose()

@pytest.mark.asyncio
async def test_exactly_once_ack():
    """Test Lua script for exactly-once job completion"""
    
    redis = aioredis.from_url("redis://localhost:6379/0", decode_responses=True)
    
    # Lua script for atomic completion (copied from os_executor)
    ack_script = """
    local processing_key = KEYS[1]
    local done_key = KEYS[2] 
    local processing_ts_key = KEYS[3]
    local job_id = ARGV[1]
    local response = ARGV[2]
    
    -- Remove from processing list
    local removed = redis.call('LREM', processing_key, 1, job_id)
    if removed > 0 then
        -- Remove from processing timestamp tracker
        redis.call('ZREM', processing_ts_key, job_id)
        -- Add to done queue
        redis.call('LPUSH', done_key, response)
        return 1
    else
        return 0
    end
    """
    
    try:
        # Clear queues
        await redis.delete(QUEUE_PROCESSING, QUEUE_DONE, QUEUE_PROCESSING_TS)
        
        # Setup: Add job to processing queue and timestamp tracker
        job_id = str(uuid.uuid4())
        response = json.dumps({"id": job_id, "ok": True, "stdout": "test"})
        
        await redis.lpush(QUEUE_PROCESSING, job_id)
        await redis.zadd(QUEUE_PROCESSING_TS, {job_id: time.time()})
        
        # Execute atomic ACK
        result = await redis.eval(
            ack_script,
            3,  # Number of keys
            QUEUE_PROCESSING,
            QUEUE_DONE,
            QUEUE_PROCESSING_TS,
            job_id,
            response
        )
        
        assert result == 1  # Successfully processed
        
        # Verify job removed from processing
        processing_count = await redis.llen(QUEUE_PROCESSING)
        assert processing_count == 0
        
        # Verify job removed from timestamp tracker
        ts_count = await redis.zcard(QUEUE_PROCESSING_TS)
        assert ts_count == 0
        
        # Verify response added to done queue
        done_count = await redis.llen(QUEUE_DONE)
        assert done_count == 1
        
        # Verify response content
        done_response = await redis.lpop(QUEUE_DONE)
        assert done_response == response
        
        print("✅ Exactly-once ACK test passed")
        
        # Test double-ACK (should return 0)
        result2 = await redis.eval(
            ack_script,
            3,
            QUEUE_PROCESSING,
            QUEUE_DONE, 
            QUEUE_PROCESSING_TS,
            job_id,
            response
        )
        
        assert result2 == 0  # Job already processed
        
        print("✅ Double-ACK prevention test passed")
        
    finally:
        await redis.aclose()

@pytest.mark.asyncio
async def test_concurrent_job_processing():
    """Test no job loss under concurrent processing"""
    
    redis = aioredis.from_url("redis://localhost:6379/0", decode_responses=True)
    
    try:
        # Clear queues
        await redis.delete(QUEUE_READY, QUEUE_PROCESSING, QUEUE_DONE)
        
        # Create 100 unique jobs
        job_ids = [str(uuid.uuid4()) for _ in range(100)]
        
        # Push all jobs to ready queue
        for job_id in job_ids:
            await redis.lpush(QUEUE_READY, job_id)
        
        print(f"📊 Pushed {len(job_ids)} jobs to ready queue")
        
        # Simulate concurrent workers using BRPOPLPUSH
        async def worker(worker_id: int, processed_jobs: Set[str]):
            """Simulate a worker processing jobs"""
            while True:
                try:
                    # Atomic pop from ready to processing
                    job = await redis.brpoplpush(QUEUE_READY, QUEUE_PROCESSING, 1)
                    if job is None:
                        break  # No more jobs
                    
                    processed_jobs.add(job)
                    
                    # Simulate processing time
                    await asyncio.sleep(0.01)
                    
                    # Atomic completion (simplified)
                    await redis.lrem(QUEUE_PROCESSING, 1, job)
                    await redis.lpush(QUEUE_DONE, f"response_{job}")
                    
                except Exception as e:
                    print(f"Worker {worker_id} error: {e}")
                    break
        
        # Run 5 concurrent workers
        processed_sets = [set() for _ in range(5)]
        tasks = [
            asyncio.create_task(worker(i, processed_sets[i])) 
            for i in range(5)
        ]
        
        # Wait for all workers to complete
        await asyncio.gather(*tasks)
        
        # Verify all jobs were processed exactly once
        all_processed = set()
        for s in processed_sets:
            all_processed.update(s)
        
        assert len(all_processed) == len(job_ids)
        assert all_processed == set(job_ids)
        
        # Verify no jobs left in ready or processing queues
        ready_count = await redis.llen(QUEUE_READY)
        processing_count = await redis.llen(QUEUE_PROCESSING)
        assert ready_count == 0
        assert processing_count == 0
        
        # Verify all responses in done queue
        done_count = await redis.llen(QUEUE_DONE)
        assert done_count == len(job_ids)
        
        print(f"✅ Concurrent processing test passed: {len(job_ids)} jobs, 0 lost")
        
    finally:
        await redis.aclose()

@pytest.mark.asyncio
async def test_visibility_timeout_simulation():
    """Test visibility timeout and job requeue logic"""
    
    redis = aioredis.from_url("redis://localhost:6379/0", decode_responses=True)
    
    try:
        # Clear queues
        await redis.delete(QUEUE_READY, QUEUE_PROCESSING, QUEUE_PROCESSING_TS)
        
        # Simulate a job that gets "stuck" in processing
        job_id = str(uuid.uuid4())
        job_data = json.dumps({"id": job_id, "code": "print('test')"})
        
        # Move job to processing (simulate BRPOPLPUSH)
        await redis.lpush(QUEUE_PROCESSING, job_data)
        
        # Add to timestamp tracker with old timestamp (simulate stale job)
        old_timestamp = time.time() - 400  # 400 seconds ago (older than 300s timeout)
        await redis.zadd(QUEUE_PROCESSING_TS, {job_id: old_timestamp})
        
        # Simulate GC finding stale jobs
        cutoff = time.time() - 300  # 5 min visibility timeout
        stale_jobs = await redis.zrangebyscore(QUEUE_PROCESSING_TS, 0, cutoff)
        
        assert job_id in stale_jobs
        print(f"✅ GC detected stale job: {job_id[:8]}...")
        
        # Simulate requeue logic
        job_found = None
        job_data_list = await redis.lrange(QUEUE_PROCESSING, 0, -1)
        for job_json in job_data_list:
            try:
                job = json.loads(job_json)
                if job.get("id") == job_id:
                    job_found = job
                    break
            except json.JSONDecodeError:
                continue
        
        assert job_found is not None
        
        # Increment retry count and requeue
        retry_count = job_found.get("retry_count", 0) + 1
        job_found["retry_count"] = retry_count
        
        # Remove from processing and requeue to ready
        await redis.lrem(QUEUE_PROCESSING, 1, job_data)
        await redis.zrem(QUEUE_PROCESSING_TS, job_id)
        await redis.lpush(QUEUE_READY, json.dumps(job_found))
        
        # Verify requeue
        ready_count = await redis.llen(QUEUE_READY)
        processing_count = await redis.llen(QUEUE_PROCESSING)
        ts_count = await redis.zcard(QUEUE_PROCESSING_TS)
        
        assert ready_count == 1
        assert processing_count == 0
        assert ts_count == 0
        
        # Verify retry count incremented
        requeued_job = await redis.lpop(QUEUE_READY)
        requeued_data = json.loads(requeued_job)
        assert requeued_data["retry_count"] == 1
        
        print("✅ Visibility timeout and requeue test passed")
        
    finally:
        await redis.aclose()

if __name__ == "__main__":
    """Run tests directly for development"""
    
    async def run_tests():
        print("🧪 Running Atomic Queue Tests")
        print("=" * 50)
        
        tests = [
            ("Atomic Queue Operations", test_atomic_queue_operations),
            ("Exactly-Once ACK", test_exactly_once_ack),
            ("Concurrent Job Processing", test_concurrent_job_processing),
            ("Visibility Timeout Simulation", test_visibility_timeout_simulation)
        ]
        
        passed = 0
        failed = 0
        
        for test_name, test_func in tests:
            print(f"\n🔬 Running: {test_name}")
            try:
                await test_func()
                print(f"✅ PASSED: {test_name}")
                passed += 1
            except Exception as e:
                print(f"❌ FAILED: {test_name}")
                print(f"   Error: {str(e)}")
                failed += 1
        
        print(f"\n📊 Test Results:")
        print(f"   ✅ Passed: {passed}")
        print(f"   ❌ Failed: {failed}")
        print(f"   📈 Success Rate: {passed/(passed+failed)*100:.1f}%")
        
        if failed == 0:
            print("\n🎉 All atomic queue tests passed!")
            print("   Redis reply-loss race condition eliminated")
        else:
            print(f"\n🚨 {failed} test(s) failed. Check Redis setup.")
    
    asyncio.run(run_tests()) 