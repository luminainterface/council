#!/bin/bash
# ── Redis-Based OS Integration Test ──

set -euo pipefail

echo "🧪 Testing Redis-Based OS Executor Integration..."

# Check Redis availability
echo "Testing Redis connection..."
if ! redis-cli ping > /dev/null 2>&1; then
    echo "❌ Redis not available - starting with Docker Compose"
    if ! docker-compose -f docker-compose.yml up -d redis; then
        echo "❌ Failed to start Redis with Docker Compose"
        exit 1
    fi
    
    # Wait for Redis to be ready
    echo "⏳ Waiting for Redis to be ready..."
    for i in {1..30}; do
        if redis-cli ping > /dev/null 2>&1; then
            echo "✅ Redis is ready"
            break
        fi
        sleep 1
    done
    
    if ! redis-cli ping > /dev/null 2>&1; then
        echo "❌ Redis failed to start after 30 seconds"
        exit 1
    fi
fi

# Check if FastAPI with ShellExecutor is running
echo "Testing FastAPI health..."
if ! curl -s http://localhost:8000/health > /dev/null; then
    echo "❌ FastAPI not available - please start the application first"
    echo "   Run: SWARM_EXEC_ENABLED=true python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
    exit 1
fi

# Check if ShellExecutor is enabled
echo "Testing ShellExecutor status..."
HEALTH_RESPONSE=$(curl -s http://localhost:8000/health || echo '{}')
echo "Health response: $HEALTH_RESPONSE"

# Test Redis queue directly
echo "Testing Redis queue functionality..."
JOB_ID=$(python3 -c "import uuid; print(uuid.uuid4())")
TEST_CODE='import time; print("Redis test successful"); print(f"Elapsed: {int(time.time() * 1000)}")'

# Push test job to Redis
redis-cli RPUSH "swarm:exec:q" "{\"id\":\"$JOB_ID\",\"code\":\"$TEST_CODE\"}" > /dev/null

echo "🔧 Pushed test job $JOB_ID to Redis queue"

# Wait for response (up to 10 seconds)
echo "⏳ Waiting for ShellExecutor response..."
for i in {1..10}; do
    RESPONSE=$(redis-cli BLPOP "swarm:exec:resp" 1 2>/dev/null || echo "")
    if [[ -n "$RESPONSE" ]]; then
        # Parse the response (Redis returns queue name and JSON)
        JSON_RESPONSE=$(echo "$RESPONSE" | tail -n 1)
        echo "📋 Raw response: $JSON_RESPONSE"
        
        # Check if this is our job
        RESPONSE_ID=$(echo "$JSON_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('id', 'unknown'))")
        if [[ "$RESPONSE_ID" == "$JOB_ID" ]]; then
            echo "✅ Got response for our job!"
            
            # Validate response
            SUCCESS=$(echo "$JSON_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('ok', False))")
            STDOUT=$(echo "$JSON_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('stdout', ''))")
            
            if [[ "$SUCCESS" == "True" ]] && [[ "$STDOUT" == *"Redis test successful"* ]]; then
                echo "✅ Redis-based execution successful!"
                echo "   Output: $STDOUT"
                break
            else
                echo "❌ Redis execution failed"
                echo "   Response: $JSON_RESPONSE"
                exit 1
            fi
        else
            # Put back if it's not our job
            redis-cli RPUSH "swarm:exec:resp" "$JSON_RESPONSE" > /dev/null
        fi
    fi
    
    if [[ $i -eq 10 ]]; then
        echo "❌ No response received after 10 seconds"
        echo "   Check if ShellExecutor consumer is running"
        exit 1
    fi
done

# Run pytest integration tests
echo "Running pytest integration tests..."
cd tests
python3 -m pytest os_exec_smoke.py -v --tb=short

echo "✅ All Redis-based OS integration tests passed!"
echo ""
echo "🔍 Monitor Redis queues with:"
echo "   redis-cli LLEN swarm:exec:q      # Pending jobs"
echo "   redis-cli LLEN swarm:exec:resp   # Completed responses"
echo ""
echo "🔧 Send manual test job with:"
echo "   redis-cli RPUSH swarm:exec:q '{\"id\":\"test\",\"code\":\"print(\\\"Hello World\\\")\"}'" 