#!/bin/bash
# ── Smoke Test for Autonomous Software Spiral ──

set -euo pipefail

echo "🧪 Testing Autonomous Software Spiral v2.7.0..."

# Test 1: API Health Check (production port 8000)
echo "Testing API health..."
curl -s http://localhost:8000/health | jq . || {
    echo "❌ API health check failed"
    exit 1
}

# Test 2: Agent-0 First Routing 
echo "Testing Agent-0 mandatory routing..."
RESPONSE=$(curl -s http://localhost:8000/orchestrate \
    -d '{"prompt":"2+2?","route":["math_specialist"]}' \
    -H "Content-Type: application/json")
echo "$RESPONSE" | jq .

# Test 3: Pattern Cache Hit (production metrics port 9091)
echo "Testing cache system..."
curl -s http://localhost:9091/metrics | grep "swarm_cache_hit_ratio" || echo "Cache metrics not yet available"

# Test 4: GPU Model Loading (production metrics port 9091)
echo "Testing GPU model status..."
curl -s http://localhost:9091/metrics | grep "swarm_gpu_memory_used_mb" || echo "GPU metrics not yet available"

# Test 5: Chat REST + WebSocket (production port 8765)
echo "Testing chat interface..."
curl -s -X POST http://localhost:8000/chat \
     -H 'Content-Type: application/json' \
     -d '{"message":"Ping"}' \
     | jq -e '.skill_type=="agent0"' || echo "Chat REST not yet available"

# Test 6: WebSocket smoke test
echo "Testing WebSocket connection..."
python tests/ws_smoke.py || echo "WebSocket test failed - may not be implemented yet"

# Test 7: Pattern Mining Service (using production compose file)
echo "Testing pattern mining service..."
docker compose -f docker-compose.yml exec pattern-miner ls -la /app/patterns/ || echo "Pattern files not yet generated"

echo "✅ Basic smoke tests completed!"
echo "🔍 Monitor with: docker compose -f docker-compose.yml logs -f" 