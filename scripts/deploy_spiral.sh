#!/bin/bash
# ── Quick Deploy Script for Autonomous Software Spiral ──

set -euo pipefail

# Quick 3-command deployment as outlined in the requirements
echo "🐳 Deploying Autonomous Software Spiral v2.7.0..."

# 1. Build the API image
echo "Building API image..."
docker build -t registry.example.com/swarm/api:v2.7.0-spiral -f Dockerfile.api .

# 2. Pull/build additional images  
echo "Building pattern miner and trainer..."
docker build -t registry.example.com/swarm/pattern-miner:v2.7.0 -f Dockerfile.pattern-miner .
docker build -t registry.example.com/swarm/trainer:v2.7.0 -f Dockerfile.trainer .

# 3. Compose up
echo "Starting the stack..."
export MISTRAL_API_KEY=${MISTRAL_API_KEY:-""}
export OPENAI_API_KEY=${OPENAI_API_KEY:-""}
export ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-""}

docker compose -f docker-compose.spiral.yml up -d

echo "✅ Spiral stack deployed!"
echo "🔍 Check status: docker compose -f docker-compose.spiral.yml ps"
echo "📊 Grafana: http://localhost:3000 (admin/swarm_admin_2024)"
echo "🔥 API: http://localhost:9000/health" 