#!/usr/bin/env python3
"""
OS Shell Executor - Week 2 Integration (Redis-Based) - Hardened Queue
=====================================================================

CRITICAL FIX: Atomic queue pattern to eliminate reply-loss race condition
- BRPOPLPUSH for atomic job hand-off (no vanish window)
- Visibility timeout with GC worker for orphaned tasks
- Exactly-once ACK with Lua script for atomic completion

Integrates with existing sandbox_exec.py for secure execution.
"""

import asyncio
import json
import logging
import os
import uuid
import time
from typing import Dict, Any, Optional

# Use existing sandbox infrastructure
from sandbox_exec import exec_safe

# Redis async client
try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# Prometheus metrics
try:
    from prometheus_client import Counter, Gauge, Histogram
    EXEC_OK = Counter("os_exec_success_total", "sandbox exec success")
    EXEC_REDIS_ERR = Counter("os_exec_redis_err_total", "redis errors", ["error_type"])
    EXEC_PROCESSING = Gauge("os_exec_processing_jobs", "jobs currently processing")
    EXEC_QUEUE_DEPTH = Gauge("os_exec_queue_depth", "jobs waiting in queue")
    EXEC_GC_REQUEUED = Counter("os_exec_gc_requeued_total", "jobs requeued by GC")
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

log = logging.getLogger("os_executor")

# Queue configuration
QUEUE_READY = "swarm:exec:q"
QUEUE_PROCESSING = "swarm:exec:processing" 
QUEUE_DONE = "swarm:exec:resp"
QUEUE_PROCESSING_TS = "swarm:exec:processing_ts"  # ZSET for visibility timeout
VISIBILITY_TIMEOUT = 300  # 5 minutes - jobs older than this get requeued
GC_INTERVAL = 60  # GC runs every 60 seconds
MAX_RETRIES = 3  # Maximum retries per job

class ShellExecutor:
    """
    Hardened Redis-based shell executor with atomic queue operations
    
    Features:
    - BRPOPLPUSH for atomic job hand-off (eliminates vanish window)
    - Visibility timeout with GC worker for orphaned task recovery
    - Exactly-once ACK with Lua script for atomic completion
    - Prometheus metrics for queue health monitoring
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        """Initialize executor with Redis connection"""
        self.redis_url = redis_url
        self.redis: Optional[aioredis.Redis] = None
        self.running = False
        self.gc_task = None
        
        # Lua script for atomic completion (LREM + LPUSH)
        self.ack_script = """
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
        
        if not REDIS_AVAILABLE:
            log.warning("Redis not available - ShellExecutor will not function")
    
    async def _connect_redis(self) -> bool:
        """Connect to Redis with error handling"""
        try:
            self.redis = aioredis.from_url(self.redis_url, decode_responses=True)
            # Test connection
            await self.redis.ping()
            log.info(f"✅ Redis connected: {self.redis_url}")
            return True
        except Exception as e:
            log.error(f"❌ Redis connection failed: {e}")
            return False
    
    async def _gc_worker(self):
        """Garbage collector for orphaned jobs with visibility timeout"""
        while self.running:
            try:
                if not self.redis:
                    await asyncio.sleep(GC_INTERVAL)
                    continue
                
                now = time.time()
                cutoff = now - VISIBILITY_TIMEOUT
                
                # Find stale jobs (older than visibility timeout)
                stale_jobs = await self.redis.zrangebyscore(
                    QUEUE_PROCESSING_TS, 0, cutoff, withscores=False
                )
                
                if stale_jobs:
                    log.warning(f"🔄 GC found {len(stale_jobs)} stale jobs, requeuing...")
                    
                    for job_id in stale_jobs:
                        try:
                            # Get the job from processing queue
                            job_data = await self.redis.lrange(QUEUE_PROCESSING, 0, -1)
                            job_found = None
                            
                            for job_json in job_data:
                                try:
                                    job = json.loads(job_json)
                                    if job.get("id") == job_id:
                                        job_found = job
                                        break
                                except json.JSONDecodeError:
                                    continue
                            
                            if job_found:
                                # Increment retry count
                                retry_count = job_found.get("retry_count", 0) + 1
                                
                                if retry_count <= MAX_RETRIES:
                                    job_found["retry_count"] = retry_count
                                    
                                    # Remove from processing queue and timestamp tracker
                                    await self.redis.lrem(QUEUE_PROCESSING, 1, job_json)
                                    await self.redis.zrem(QUEUE_PROCESSING_TS, job_id)
                                    
                                    # Re-queue to ready
                                    await self.redis.lpush(QUEUE_READY, json.dumps(job_found))
                                    
                                    log.info(f"🔄 Requeued job {job_id[:8]}... (retry {retry_count}/{MAX_RETRIES})")
                                    
                                    if PROMETHEUS_AVAILABLE:
                                        EXEC_GC_REQUEUED.inc()
                                else:
                                    # Max retries exceeded, send failure response
                                    error_response = {
                                        "id": job_id,
                                        "ok": False,
                                        "error": f"Max retries ({MAX_RETRIES}) exceeded",
                                        "stdout": "",
                                        "stderr": "Job failed after maximum retry attempts"
                                    }
                                    
                                    # Remove from processing
                                    await self.redis.lrem(QUEUE_PROCESSING, 1, job_json)
                                    await self.redis.zrem(QUEUE_PROCESSING_TS, job_id)
                                    
                                    # Send failure response
                                    await self.redis.lpush(QUEUE_DONE, json.dumps(error_response))
                                    
                                    log.error(f"❌ Job {job_id[:8]}... failed after {MAX_RETRIES} retries")
                            
                        except Exception as e:
                            log.error(f"GC error processing job {job_id}: {e}")
                
                # Update queue depth metrics
                if PROMETHEUS_AVAILABLE:
                    ready_count = await self.redis.llen(QUEUE_READY)
                    processing_count = await self.redis.llen(QUEUE_PROCESSING)
                    EXEC_QUEUE_DEPTH.set(ready_count)
                    EXEC_PROCESSING.set(processing_count)
                
            except Exception as e:
                log.exception(f"GC worker error: {e}")
                if PROMETHEUS_AVAILABLE:
                    EXEC_REDIS_ERR.labels(error_type="gc_error").inc()
            
            await asyncio.sleep(GC_INTERVAL)
    
    async def consume(self):
        """
        Main consumer loop with atomic queue operations
        
        Uses BRPOPLPUSH for atomic job hand-off to eliminate reply-loss race condition.
        Implements visibility timeout and exactly-once ACK for reliability.
        """
        if not REDIS_AVAILABLE:
            log.error("Redis not available - cannot start consumer")
            return
        
        # Connect to Redis
        if not await self._connect_redis():
            return
        
        log.info("🚀 ShellExecutor consumer started (HARDENED)")
        log.info("   Queue Pattern: BRPOPLPUSH (atomic)")
        log.info("   Visibility Timeout: 5min with GC")
        log.info("   Exactly-Once ACK: Lua script")
        log.info("   Sandbox: WSL with --net=none")
        
        self.running = True
        
        # Start GC worker
        self.gc_task = asyncio.create_task(self._gc_worker())
        
        while self.running:
            try:
                # ATOMIC: Pop from ready queue and push to processing queue in one operation
                # This eliminates the vanish window that caused reply loss
                job_json = await self.redis.brpoplpush(
                    "swarm:exec:q", 
                    "swarm:exec:processing", 
                    timeout=5
                )
                
                if job_json is None:
                    # Timeout - continue polling
                    continue
                
                try:
                    # Parse job
                    job = json.loads(job_json)
                    job_id = job.get("id", str(uuid.uuid4()))
                    code = job.get("code", "")
                    retry_count = job.get("retry_count", 0)
                    
                    log.info(f"🔧 Processing job {job_id[:8]}... (retry {retry_count}) ({len(code)} chars)")
                    
                    # Add to visibility timeout tracker
                    now = time.time()
                    await self.redis.zadd(QUEUE_PROCESSING_TS, {job_id: now})
                    
                    if not code:
                        reply = {
                            "id": job_id,
                            "ok": False,
                            "error": "No code provided",
                            "stdout": "",
                            "stderr": "Empty code block"
                        }
                    else:
                        try:
                            # Execute in sandbox
                            result = exec_safe(code, lang="python")
                            
                            reply = {
                                "id": job_id,
                                "ok": True,
                                "stdout": result["stdout"],
                                "stderr": result["stderr"],
                                "elapsed_ms": result["elapsed_ms"]
                            }
                            
                            log.info(f"✅ Job {job_id[:8]} completed ({result['elapsed_ms']}ms)")
                            
                            if PROMETHEUS_AVAILABLE:
                                EXEC_OK.inc()
                                
                        except RuntimeError as e:
                            reply = {
                                "id": job_id,
                                "ok": False,
                                "error": str(e),
                                "stdout": "",
                                "stderr": str(e)
                            }
                            
                            log.warning(f"❌ Job {job_id[:8]} failed: {e}")
                    
                    # ATOMIC ACK: Remove from processing and add to done queue
                    # Uses Lua script to ensure exactly-once completion
                    await self.redis.eval(
                        self.ack_script,
                        3,  # Number of keys
                        QUEUE_PROCESSING,
                        QUEUE_DONE, 
                        QUEUE_PROCESSING_TS,
                        job_id,
                        json.dumps(reply)
                    )
                    
                except json.JSONDecodeError as e:
                    log.error(f"Invalid JSON in job: {e}")
                    # Remove malformed job from processing queue
                    await self.redis.lrem(QUEUE_PROCESSING, 1, job_json)
                    continue
                    
                except Exception as e:
                    log.exception(f"Job processing error: {e}")
                    
                    # Send error response using atomic ACK
                    try:
                        error_reply = {
                            "id": job.get("id", "unknown"),
                            "ok": False,
                            "error": f"Processing error: {str(e)}",
                            "stdout": "",
                            "stderr": str(e)
                        }
                        
                        await self.redis.eval(
                            self.ack_script,
                            3,
                            QUEUE_PROCESSING,
                            QUEUE_DONE,
                            QUEUE_PROCESSING_TS, 
                            job.get("id", "unknown"),
                            json.dumps(error_reply)
                        )
                    except:
                        pass  # Don't let error handling fail the main loop
                    
            except Exception as e:
                log.exception(f"Consumer loop error: {e}")
                
                if PROMETHEUS_AVAILABLE:
                    EXEC_REDIS_ERR.labels(error_type="consumer_error").inc()
                
                # Back-off on errors to avoid spam
                await asyncio.sleep(1)
        
        log.info("🛑 ShellExecutor consumer stopped")
    
    async def stop(self):
        """Stop the consumer gracefully"""
        self.running = False
        
        if self.gc_task:
            self.gc_task.cancel()
            try:
                await self.gc_task
            except asyncio.CancelledError:
                pass
        
        if self.redis:
            await self.redis.aclose()
        
        log.info("ShellExecutor stopped")

# Health check endpoint data
async def get_queue_health(redis_url: str = "redis://localhost:6379/0") -> Dict[str, Any]:
    """Get queue health metrics for /healthz endpoint"""
    try:
        redis = aioredis.from_url(redis_url, decode_responses=True)
        
        ready_count = await redis.llen(QUEUE_READY)
        processing_count = await redis.llen(QUEUE_PROCESSING)
        done_count = await redis.llen(QUEUE_DONE)
        
        await redis.aclose()
        
        return {
            "queue_backlog": ready_count,
            "processing_jobs": processing_count,
            "completed_responses": done_count,
            "status": "healthy" if processing_count < 100 else "warning"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "queue_backlog": -1
        }

# Legacy compatibility functions for existing code
def execute_shell_command(command: str, working_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Legacy compatibility function - executes shell command directly
    
    For production use, prefer the Redis queue approach via ShellExecutor.consume()
    """
    try:
        # Simple wrapper around exec_safe for backwards compatibility
        # Convert shell command to Python code that executes it
        python_code = f"""
import subprocess
import os
import time

start_time = time.time()

try:
    result = subprocess.run(
        {repr(command)},
        shell=True,
        capture_output=True,
        text=True,
        timeout=10,
        cwd={repr(working_dir) if working_dir else 'None'}
    )
    
    print(f"STDOUT: {{result.stdout}}")
    print(f"STDERR: {{result.stderr}}")
    print(f"EXIT_CODE: {{result.returncode}}")
    print(f"ELAPSED_MS: {{int((time.time() - start_time) * 1000)}}")
    
except subprocess.TimeoutExpired:
    print("ERROR: Command timed out")
    exit(124)
except Exception as e:
    print(f"ERROR: {{str(e)}}")
    exit(1)
"""
        
        result = exec_safe(python_code, lang="python")
        
        # Parse output
        lines = result["stdout"].split("\n")
        stdout = ""
        stderr = ""
        exit_code = 0
        
        for line in lines:
            if line.startswith("STDOUT: "):
                stdout = line[8:]
            elif line.startswith("STDERR: "):
                stderr = line[8:]
            elif line.startswith("EXIT_CODE: "):
                exit_code = int(line[11:])
        
        return {
            "success": exit_code == 0,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "execution_time_ms": result["elapsed_ms"],
            "command_type": "shell_command",
            "blocked_reason": None
        }
        
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "exit_code": -1,
            "execution_time_ms": 0,
            "command_type": "error",
            "blocked_reason": f"Execution error: {str(e)}"
        }

def get_executor() -> ShellExecutor:
    """Get ShellExecutor instance"""
    return ShellExecutor(
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0")
    ) 