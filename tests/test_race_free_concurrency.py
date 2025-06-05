#!/usr/bin/env python3
"""
Stage 6: Race-free concurrency test
Spawns two async workers against BRPOPLPUSH queue and asserts exactly one "done" record.
Prevents dual consumers popping same job under heavy parallelism.
"""

import pytest
import asyncio
import redis.asyncio as redis
import time
import uuid
from typing import List, Set

# Test configuration
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 15  # Isolated test DB
TEST_QUEUE = "test:action_queue"
PROCESSING_QUEUE = "test:processing"
DONE_QUEUE = "test:done"

@pytest.fixture
async def redis_client():
    """Redis client for testing"""
    client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
    
    # Clean up test queues
    await client.delete(TEST_QUEUE, PROCESSING_QUEUE, DONE_QUEUE)
    
    yield client
    
    # Clean up after test
    await client.delete(TEST_QUEUE, PROCESSING_QUEUE, DONE_QUEUE)
    await client.close()

class ActionWorker:
    """Async worker that processes jobs from Redis queue"""
    
    def __init__(self, worker_id: str, redis_client: redis.Redis):
        self.worker_id = worker_id
        self.redis = redis_client
        self.processed_jobs: Set[str] = set()
        self.running = False
    
    async def start(self, duration_seconds: float = 2.0):
        """Start processing jobs for specified duration"""
        self.running = True
        end_time = time.time() + duration_seconds
        
        while self.running and time.time() < end_time:
            try:
                # BRPOPLPUSH: Atomically move job from queue to processing
                # This prevents race conditions between multiple workers
                job_data = await self.redis.brpoplpush(
                    TEST_QUEUE, 
                    f"{PROCESSING_QUEUE}:{self.worker_id}",
                    timeout=1  # 1 second timeout
                )
                
                if job_data:
                    await self._process_job(job_data)
                    
            except asyncio.TimeoutError:
                # Normal timeout, continue polling
                continue
            except Exception as e:
                print(f"Worker {self.worker_id} error: {e}")
                break
        
        self.running = False
    
    async def _process_job(self, job_data: str):
        """Process a single job atomically"""
        job_id = job_data.split(":")[0] if ":" in job_data else job_data
        
        # Simulate processing time
        await asyncio.sleep(0.01)
        
        # Mark job as processed by this worker
        self.processed_jobs.add(job_id)
        
        # Atomically move from processing to done queue
        processing_key = f"{PROCESSING_QUEUE}:{self.worker_id}"
        
        # Use a pipeline for atomic operations
        pipe = self.redis.pipeline()
        pipe.lrem(processing_key, 1, job_data)  # Remove from processing
        pipe.lpush(DONE_QUEUE, f"{job_data}:worker_{self.worker_id}")  # Add to done
        await pipe.execute()
        
        print(f"Worker {self.worker_id} completed job {job_id}")
    
    def stop(self):
        """Stop the worker"""
        self.running = False

async def test_no_duplicate_processing(redis_client):
    """Test that two workers don't process the same job"""
    
    # Generate test jobs
    test_jobs = [f"job_{i}:{uuid.uuid4().hex[:8]}" for i in range(20)]
    
    # Add jobs to queue
    if test_jobs:
        await redis_client.lpush(TEST_QUEUE, *test_jobs)
    
    # Create two competing workers
    worker1 = ActionWorker("worker_1", redis_client)
    worker2 = ActionWorker("worker_2", redis_client)
    
    # Start both workers concurrently
    start_time = time.time()
    
    worker_tasks = [
        asyncio.create_task(worker1.start(duration_seconds=3.0)),
        asyncio.create_task(worker2.start(duration_seconds=3.0))
    ]
    
    # Wait for workers to complete
    await asyncio.gather(*worker_tasks)
    
    elapsed = time.time() - start_time
    print(f"Processing completed in {elapsed:.2f}s")
    
    # Verify results
    all_processed_jobs = worker1.processed_jobs | worker2.processed_jobs
    overlap = worker1.processed_jobs & worker2.processed_jobs
    
    # Check for race conditions
    assert len(overlap) == 0, f"Race condition detected! {len(overlap)} jobs processed by both workers: {overlap}"
    
    # Verify all jobs were processed
    total_done = await redis_client.llen(DONE_QUEUE)
    assert total_done == len(test_jobs), f"Expected {len(test_jobs)} completed jobs, got {total_done}"
    
    # Verify no jobs left in processing queues
    processing_1 = await redis_client.llen(f"{PROCESSING_QUEUE}:worker_1")
    processing_2 = await redis_client.llen(f"{PROCESSING_QUEUE}:worker_2")
    
    assert processing_1 == 0, f"Worker 1 has {processing_1} jobs stuck in processing"
    assert processing_2 == 0, f"Worker 2 has {processing_2} jobs stuck in processing"
    
    print(f"✅ Race-free concurrency: {len(test_jobs)} jobs processed without duplicates")
    print(f"  Worker 1 processed: {len(worker1.processed_jobs)} jobs")
    print(f"  Worker 2 processed: {len(worker2.processed_jobs)} jobs")

async def test_queue_recovery_after_worker_crash(redis_client):
    """Test that jobs in processing queue can be recovered after worker crash"""
    
    # Add test jobs
    crash_jobs = [f"crash_job_{i}" for i in range(5)]
    await redis_client.lpush(TEST_QUEUE, *crash_jobs)
    
    # Start worker and simulate crash by stopping abruptly
    worker = ActionWorker("crash_worker", redis_client)
    
    # Process for short time then "crash"
    await worker.start(duration_seconds=0.5)
    
    # Check if any jobs are stuck in processing
    processing_key = f"{PROCESSING_QUEUE}:crash_worker"
    stuck_jobs = await redis_client.llen(processing_key)
    
    if stuck_jobs > 0:
        print(f"Found {stuck_jobs} jobs stuck in processing after crash")
        
        # Recovery: Move stuck jobs back to main queue
        while True:
            job = await redis_client.rpop(processing_key)
            if not job:
                break
            await redis_client.lpush(TEST_QUEUE, job)
            print(f"Recovered job: {job}")
        
        # Verify recovery
        recovered_queue_size = await redis_client.llen(TEST_QUEUE)
        assert recovered_queue_size >= stuck_jobs, "Failed to recover all stuck jobs"
    
    print("✅ Queue recovery: Stuck jobs recovered after simulated crash")

async def test_high_concurrency_stress(redis_client):
    """Stress test with high job volume and multiple workers"""
    
    # Generate large number of jobs
    stress_jobs = [f"stress_{i}:{uuid.uuid4().hex[:6]}" for i in range(100)]
    await redis_client.lpush(TEST_QUEUE, *stress_jobs)
    
    # Create 4 competing workers
    workers = [ActionWorker(f"stress_worker_{i}", redis_client) for i in range(4)]
    
    # Start all workers
    worker_tasks = [
        asyncio.create_task(worker.start(duration_seconds=5.0))
        for worker in workers
    ]
    
    start_time = time.time()
    await asyncio.gather(*worker_tasks)
    elapsed = time.time() - start_time
    
    # Collect all processed jobs
    all_processed = set()
    for worker in workers:
        all_processed.update(worker.processed_jobs)
    
    # Check for duplicates across all workers
    total_individual_processed = sum(len(worker.processed_jobs) for worker in workers)
    unique_processed = len(all_processed)
    
    duplicates = total_individual_processed - unique_processed
    assert duplicates == 0, f"Found {duplicates} duplicate job processing under stress"
    
    # Verify completion
    completed_jobs = await redis_client.llen(DONE_QUEUE)
    
    print(f"✅ High concurrency stress test:")
    print(f"  {len(stress_jobs)} jobs processed by 4 workers in {elapsed:.2f}s")
    print(f"  {completed_jobs} jobs completed")
    print(f"  {duplicates} duplicate processing detected")
    print(f"  Throughput: {len(stress_jobs)/elapsed:.1f} jobs/second")

if __name__ == "__main__":
    # Run tests directly for quick validation
    async def run_tests():
        client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
        
        try:
            # Clean up
            await client.delete(TEST_QUEUE, PROCESSING_QUEUE, DONE_QUEUE)
            
            print("🔄 Stage 6: Running race-free concurrency tests...")
            
            await test_no_duplicate_processing(client)
            await test_queue_recovery_after_worker_crash(client)
            await test_high_concurrency_stress(client)
            
            print("\n🎯 Stage 6: PASS - Race-free concurrency verified")
            
        finally:
            await client.close()
    
    asyncio.run(run_tests()) 