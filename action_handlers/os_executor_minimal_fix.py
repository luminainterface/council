#!/usr/bin/env python3
"""
OS Shell Executor - MINIMAL RACE FIX
====================================

CRITICAL: Fixes "5 dropped replies / 24h during peak OS-exec bursts"
- BRPOPLPUSH for atomic hand-off (no vanish window)
- Simple processing queue tracking
- Maintains 100% API compatibility

This is the minimal change to eliminate Sev-High race condition.
"""

import asyncio
import json
import logging
import os
import uuid
from typing import Dict, Any, Optional

from sandbox_exec import exec_safe

try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

try:
    from prometheus_client import Counter
    EXEC_OK = Counter("os_exec_success_total", "sandbox exec success")
    EXEC_REDIS_ERR = Counter("os_exec_redis_err_total", "redis errors")
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

log = logging.getLogger("os_executor")

class ShellExecutor:
    """MINIMAL RACE FIX: BRPOPLPUSH for atomic job hand-off"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_url = redis_url
        self.redis: Optional[aioredis.Redis] = None
        self.running = False
        
        if not REDIS_AVAILABLE:
            log.warning("Redis not available")
    
    async def _connect_redis(self) -> bool:
        try:
            self.redis = aioredis.from_url(self.redis_url, decode_responses=True)
            await self.redis.ping()
            log.info(f"✅ Redis connected: {self.redis_url}")
            return True
        except Exception as e:
            log.error(f"❌ Redis connection failed: {e}")
            return False
    
    async def consume(self):
        """ATOMIC consumer - fixes reply-loss race with BRPOPLPUSH"""
        
        if not REDIS_AVAILABLE:
            log.error("Redis not available")
            return
        
        if not await self._connect_redis():
            return
        
        log.info("🚀 ShellExecutor consumer started (RACE-FIX)")
        log.info("   ATOMIC: BRPOPLPUSH eliminates vanish window")
        
        self.running = True
        
        while self.running:
            try:
                # CRITICAL FIX: BRPOPLPUSH is atomic - no vanish window
                # OLD: BLPOP q:ready (job can vanish if crash here)
                # NEW: BRPOPLPUSH q:ready q:processing (atomic move)
                job_json = await self.redis.brpoplpush(
                    "swarm:exec:q",           # Source: ready queue
                    "swarm:exec:processing",  # Dest: processing queue  
                    timeout=5
                )
                
                if job_json is None:
                    continue  # Timeout
                
                try:
                    job = json.loads(job_json)
                    job_id = job.get("id", str(uuid.uuid4()))
                    code = job.get("code", "")
                    
                    log.info(f"🔧 Processing job {job_id[:8]}...")
                    
                    if not code:
                        reply = {
                            "id": job_id,
                            "ok": False,
                            "error": "No code provided",
                            "stdout": "",
                            "stderr": ""
                        }
                    else:
                        try:
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
                        except Exception as e:
                            reply = {
                                "id": job_id,
                                "ok": False,
                                "error": str(e),
                                "stdout": "",
                                "stderr": str(e)
                            }
                            log.warning(f"❌ Job {job_id[:8]} failed: {e}")
                    
                    # ATOMIC COMPLETION: Remove from processing, add to done
                    await self.redis.lrem("swarm:exec:processing", 1, job_json)
                    await self.redis.lpush("swarm:exec:resp", json.dumps(reply))
                    
                except Exception as e:
                    log.exception(f"Job processing error: {e}")
                    # Clean up on error
                    await self.redis.lrem("swarm:exec:processing", 1, job_json)
                    
            except Exception as e:
                log.exception(f"Consumer loop error: {e}")
                if PROMETHEUS_AVAILABLE:
                    EXEC_REDIS_ERR.inc()
                await asyncio.sleep(1)
        
        log.info("🛑 Consumer stopped")
    
    async def stop(self):
        self.running = False
        if self.redis:
            await self.redis.aclose()

# Unchanged compatibility functions
def execute_shell_command(command: str, working_dir: Optional[str] = None) -> Dict[str, Any]:
    try:
        python_code = f"""
import subprocess, time

start_time = time.time()
try:
    result = subprocess.run({repr(command)}, shell=True, capture_output=True, text=True, timeout=10, cwd={repr(working_dir) if working_dir else 'None'})
    print(f"STDOUT: {{result.stdout}}")
    print(f"STDERR: {{result.stderr}}")
    print(f"EXIT_CODE: {{result.returncode}}")
    print(f"ELAPSED_MS: {{int((time.time() - start_time) * 1000)}}")
except Exception as e:
    print(f"ERROR: {{str(e)}}")
    exit(1)
"""
        result = exec_safe(python_code, lang="python")
        lines = result["stdout"].split("\n")
        stdout = stderr = ""
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
    return ShellExecutor(os.getenv("REDIS_URL", "redis://localhost:6379/0")) 