#!/usr/bin/env python3
"""
Redis-Based OS Executor Integration Test
========================================

Tests the complete Redis queue flow:
Redis → ShellExecutor → sandbox_exec → Redis

Validates end-to-end OS command execution pipeline.
"""

import asyncio
import json
import uuid
import pytest
import time
from typing import Optional

# Redis client
try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

@pytest.mark.asyncio
async def test_create_echo_cat():
    """Golden-path test: create file, echo content, cat it back"""
    
    if not REDIS_AVAILABLE:
        pytest.skip("Redis not available")
    
    # Generate unique job ID
    rid = str(uuid.uuid4())
    
    # Connect to Redis
    redis = aioredis.from_url("redis://localhost:6379/0", decode_responses=True)
    
    try:
        # Test connection
        await redis.ping()
    except Exception as e:
        pytest.skip(f"Redis not available: {e}")
    
    # Python code to execute in sandbox
    code = '''
import os, pathlib, json

# Create workspace directory
pathlib.Path("workspace/tmp").mkdir(parents=True, exist_ok=True)

# Write hello file
with open("workspace/tmp/hello.txt", "w") as f:
    f.write("hi")

# Read it back
with open("workspace/tmp/hello.txt", "r") as f:
    content = f.read()

print(content)
'''
    
    # Push job to queue
    job = {"id": rid, "code": code}
    await redis.rpush("swarm:exec:q", json.dumps(job))
    
    print(f"🔧 Sent job {rid[:8]}... to Redis queue")
    
    # Wait for response (up to 20 seconds with polling)
    for attempt in range(10):
        result = await redis.blpop("swarm:exec:resp", timeout=2)
        
        if result is None:
            continue  # Timeout, try again
        
        _queue, raw = result
        response = json.loads(raw)
        
        if response["id"] == rid:
            print(f"✅ Got response for job {rid[:8]}...")
            print(f"   OK: {response['ok']}")
            print(f"   Stdout: {response.get('stdout', '')[:50]}...")
            print(f"   Elapsed: {response.get('elapsed_ms', 0)}ms")
            
            # Validate successful execution
            assert response["ok"], f"Job failed: {response.get('error', 'Unknown error')}"
            assert response["stdout"].strip() == "hi", f"Expected 'hi', got '{response['stdout']}'"
            
            # Performance check
            elapsed_ms = response.get("elapsed_ms", 0)
            assert elapsed_ms < 5000, f"Execution took too long: {elapsed_ms}ms"
            
            await redis.close()
            return
        else:
            # Different job ID, put it back (though this shouldn't happen in tests)
            await redis.rpush("swarm:exec:resp", raw)
    
    await redis.close()
    pytest.fail(f"Executor did not return response for job {rid} in time")

@pytest.mark.asyncio
async def test_error_handling():
    """Test that sandbox errors are properly reported"""
    
    if not REDIS_AVAILABLE:
        pytest.skip("Redis not available")
    
    rid = str(uuid.uuid4())
    redis = aioredis.from_url("redis://localhost:6379/0", decode_responses=True)
    
    try:
        await redis.ping()
    except Exception as e:
        pytest.skip(f"Redis not available: {e}")
    
    # Code that will cause an error
    error_code = '''
# This will cause a runtime error
import nonexistent_module
print("This should not print")
'''
    
    # Push error job
    job = {"id": rid, "code": error_code}
    await redis.rpush("swarm:exec:q", json.dumps(job))
    
    print(f"🚨 Sent error job {rid[:8]}... to Redis queue")
    
    # Wait for error response
    for attempt in range(10):
        result = await redis.blpop("swarm:exec:resp", timeout=2)
        
        if result is None:
            continue
        
        _queue, raw = result
        response = json.loads(raw)
        
        if response["id"] == rid:
            print(f"❌ Got error response for job {rid[:8]}...")
            print(f"   OK: {response['ok']}")
            print(f"   Error: {response.get('error', '')[:100]}...")
            
            # Validate error handling
            assert not response["ok"], "Job should have failed"
            assert "error" in response, "Error message should be present"
            
            error_msg = response["error"].lower()
            assert any(keyword in error_msg for keyword in ["import", "module", "not found"]), \
                f"Error should mention import issue: {error_msg}"
            
            await redis.close()
            return
    
    await redis.close()
    pytest.fail(f"Executor did not return error response for job {rid} in time")

if __name__ == "__main__":
    """Run tests directly for development"""
    
    async def run_tests():
        print("🧪 Running Redis-based OS Executor Integration Tests")
        print("=" * 60)
        
        tests = [
            ("Golden Path: Create, Echo, Cat", test_create_echo_cat),
            ("Error Handling", test_error_handling)
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
            print("\n🎉 All tests passed! Redis-based OS executor is working!")
        else:
            print(f"\n🚨 {failed} test(s) failed. Check Redis/ShellExecutor setup.")
    
    asyncio.run(run_tests()) 