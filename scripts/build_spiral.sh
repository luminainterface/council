#!/bin/bash
# ── Build Script for Autonomous Software Spiral v2.7.0 ──

set -euo pipefail

# Configuration
REGISTRY="${REGISTRY:-registry.example.com}"
VERSION="${VERSION:-v2.7.0-spiral}"
DOCKER_BUILDKIT=1

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

echo_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

echo_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    echo_info "Checking prerequisites..."
    
    if ! command -v docker &> /dev/null; then
        echo_error "Docker is not installed or not in PATH"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        echo_error "Docker daemon is not running"
        exit 1
    fi
    
    if ! docker buildx version &> /dev/null; then
        echo_warning "Docker buildx not available, using standard build"
    fi
    
    echo_success "Prerequisites check passed"
}

# Build API image with multi-stage optimization
build_api_image() {
    echo_info "Building API image with CUDA support..."
    
    docker build \
        --file Dockerfile.api \
        --tag "${REGISTRY}/swarm/api:${VERSION}" \
        --tag "${REGISTRY}/swarm/api:latest" \
        --build-arg BUILDKIT_INLINE_CACHE=1 \
        --progress=plain \
        . || {
        echo_error "Failed to build API image"
        exit 1
    }
    
    echo_success "API image built successfully"
}

# Build pattern miner image
build_pattern_miner_image() {
    echo_info "Building pattern miner image..."
    
    docker build \
        --file Dockerfile.pattern-miner \
        --tag "${REGISTRY}/swarm/pattern-miner:${VERSION}" \
        --tag "${REGISTRY}/swarm/pattern-miner:latest" \
        --build-arg BUILDKIT_INLINE_CACHE=1 \
        . || {
        echo_error "Failed to build pattern miner image"
        exit 1
    }
    
    echo_success "Pattern miner image built successfully"
}

# Build trainer image
build_trainer_image() {
    echo_info "Building trainer image..."
    
    docker build \
        --file Dockerfile.trainer \
        --tag "${REGISTRY}/swarm/trainer:${VERSION}" \
        --tag "${REGISTRY}/swarm/trainer:latest" \
        --build-arg BUILDKIT_INLINE_CACHE=1 \
        . || {
        echo_error "Failed to build trainer image"
        exit 1
    }
    
    echo_success "Trainer image built successfully"
}

# Build scheduler image (enhanced from v2.6.0)
build_scheduler_image() {
    echo_info "Building enhanced scheduler image..."
    
    if [ ! -d "scheduler" ]; then
        mkdir -p scheduler
        cat > scheduler/Dockerfile << 'EOF'
FROM python:3.11-slim

RUN apt-get update && apt-get install -y cron curl && rm -rf /var/lib/apt/lists/*
RUN pip install redis pyyaml requests

WORKDIR /app
COPY scheduler_worker.py /app/
COPY crontab /etc/cron.d/spiral-scheduler
RUN chmod 0644 /etc/cron.d/spiral-scheduler && crontab /etc/cron.d/spiral-scheduler

CMD ["python", "scheduler_worker.py"]
EOF
        
        cat > scheduler/scheduler_worker.py << 'EOF'
#!/usr/bin/env python3
"""Enhanced scheduler for Autonomous Software Spiral"""
import redis
import json
import time
from datetime import datetime

redis_client = redis.Redis(host="redis", port=6379, db=0, decode_responses=True)

def schedule_nightly_distillation():
    """Schedule nightly distillation job"""
    job = {
        "type": "distillation",
        "scheduled_at": datetime.now().isoformat(),
        "priority": "high"
    }
    redis_client.rpush("training_queue", json.dumps(job))
    print(f"Scheduled nightly distillation: {job}")

def main():
    print("Enhanced scheduler starting...")
    while True:
        current_hour = datetime.now().hour
        
        if current_hour == 2:  # 2 AM distillation
            schedule_nightly_distillation()
            time.sleep(3600)  # Sleep for 1 hour
        else:
            time.sleep(300)  # Check every 5 minutes

if __name__ == "__main__":
    main()
EOF
        
        cat > scheduler/crontab << 'EOF'
# Nightly distillation at 2 AM
0 2 * * * /usr/local/bin/python /app/scheduler_worker.py >> /var/log/cron.log 2>&1
EOF
    fi
    
    docker build \
        --file scheduler/Dockerfile \
        --tag "${REGISTRY}/swarm/cron:${VERSION}" \
        --tag "${REGISTRY}/swarm/cron:latest" \
        scheduler/ || {
        echo_error "Failed to build scheduler image"
        exit 1
    }
    
    echo_success "Scheduler image built successfully"
}

# Test images locally
test_images() {
    echo_info "Testing built images..."
    
    # Test API image
    echo_info "Testing API image..."
    docker run --rm "${REGISTRY}/swarm/api:${VERSION}" python -c "
import torch
print(f'PyTorch version: {torch.__version__}')
print(f'CUDA available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'CUDA version: {torch.version.cuda}')
" || {
        echo_warning "API image test failed (this may be expected without GPU)"
    }
    
    # Test pattern miner image
    echo_info "Testing pattern miner image..."
    docker run --rm "${REGISTRY}/swarm/pattern-miner:${VERSION}" python -c "
import sentence_transformers
import hdbscan
import sklearn
print('Pattern miner dependencies OK')
" || {
        echo_error "Pattern miner image test failed"
        exit 1
    }
    
    echo_success "Image tests completed"
}

# Push images to registry
push_images() {
    if [ "${PUSH_IMAGES:-false}" != "true" ]; then
        echo_info "Skipping image push (set PUSH_IMAGES=true to enable)"
        return
    fi
    
    echo_info "Pushing images to registry..."
    
    docker push "${REGISTRY}/swarm/api:${VERSION}"
    docker push "${REGISTRY}/swarm/api:latest"
    
    docker push "${REGISTRY}/swarm/pattern-miner:${VERSION}"
    docker push "${REGISTRY}/swarm/pattern-miner:latest"
    
    docker push "${REGISTRY}/swarm/trainer:${VERSION}"
    docker push "${REGISTRY}/swarm/trainer:latest"
    
    docker push "${REGISTRY}/swarm/cron:${VERSION}"
    docker push "${REGISTRY}/swarm/cron:latest"
    
    echo_success "Images pushed to registry"
}

# Main build process
main() {
    echo_info "Starting Autonomous Software Spiral v2.7.0 build process..."
    echo_info "Registry: ${REGISTRY}"
    echo_info "Version: ${VERSION}"
    echo
    
    check_prerequisites
    
    # Build all images in parallel for efficiency
    echo_info "Building all images..."
    
    # Build API image (longest build time due to CUDA compilation)
    build_api_image &
    API_PID=$!
    
    # Build other images
    build_pattern_miner_image &
    MINER_PID=$!
    
    build_trainer_image &
    TRAINER_PID=$!
    
    build_scheduler_image &
    SCHEDULER_PID=$!
    
    # Wait for all builds to complete
    wait $API_PID
    wait $MINER_PID
    wait $TRAINER_PID
    wait $SCHEDULER_PID
    
    echo_success "All images built successfully!"
    
    # Test and push
    test_images
    push_images
    
    echo
    echo_success "Build process completed successfully!"
    echo_info "To deploy the stack:"
    echo_info "  export MISTRAL_API_KEY=your_key"
    echo_info "  export OPENAI_API_KEY=your_key"
    echo_info "  docker compose -f docker-compose.spiral.yml up -d"
    echo
    echo_info "Monitor the deployment:"
    echo_info "  docker compose -f docker-compose.spiral.yml logs -f"
    echo_info "  curl http://localhost:9000/health"
    echo_info "  open http://localhost:3000 (Grafana)"
}

# Handle script arguments
case "${1:-}" in
    "api")
        check_prerequisites
        build_api_image
        ;;
    "pattern-miner")
        check_prerequisites
        build_pattern_miner_image
        ;;
    "trainer")
        check_prerequisites
        build_trainer_image
        ;;
    "scheduler")
        check_prerequisites
        build_scheduler_image
        ;;
    "test")
        test_images
        ;;
    "push")
        PUSH_IMAGES=true
        push_images
        ;;
    *)
        main
        ;;
esac 