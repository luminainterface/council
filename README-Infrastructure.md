# Spiral v2.7.0 Infrastructure Guide

This guide covers the production-ready infrastructure with Traefik load balancing, canary deployments, and comprehensive monitoring.

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose v2.0+
- NVIDIA Docker runtime for GPU support
- 16 GB RAM, 50 GB disk space
- NVIDIA GPU with driver ≥535, CUDA 12.1

### One-Command Deployment

```bash
# Clone and prepare
git clone https://github.com/<you>/swarm-ai.git
cd swarm-ai

# Initialize environment (downloads models, creates volumes)
make -f Makefile.spiral init

# Update API keys in .env.spiral
# MISTRAL_API_KEY=sk-your-key
# OPENAI_API_KEY=sk-your-key

# Build and start full stack
make -f Makefile.spiral docker-build-all
make -f Makefile.spiral up
```

After startup (~45 seconds), you'll have:
- **API**: http://localhost:9000 (via Traefik)
- **Traefik Dashboard**: http://localhost:8080
- **Grafana**: http://localhost:3000 (admin/swarm_admin_2024)
- **Prometheus**: http://localhost:9090

## 🏗️ Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐
│   Traefik LB    │────│   API (Main)     │ 95%
│   Port 8080     │    │   + GPU Support  │
│                 │────│   API (Canary)   │ 5%
└─────────────────┘    └──────────────────┘
         │
         ├── Pattern Miner (Background)
         ├── Trainer (GPU, Nightly LoRA)
         ├── Scheduler (Cron Jobs)
         └── Monitoring Stack
             ├── Prometheus
             ├── Grafana
             └── Alertmanager
```

## 🔄 Canary Deployments

The infrastructure supports seamless canary deployments:

```bash
# Deploy new version as canary (5% traffic)
CANARY_VERSION=v2.7.1 make -f Makefile.spiral up-canary

# Adjust traffic split
make -f Makefile.spiral set-canary-weight PERCENT=20

# Promote to main (100% traffic)
make -f Makefile.spiral promote-canary

# Emergency rollback
make -f Makefile.spiral rollback
```

Traffic is split at the Traefik level with health check gating - unhealthy services automatically get zero traffic.

## 🧪 Testing Pipeline

### Smoke Tests (2 minutes)
```bash
make -f Makefile.spiral smoke-loader    # GPU/VRAM check
make -f Makefile.spiral smoke-live      # 10 API calls
make -f Makefile.spiral test-cost-guard # Budget guardrails
```

### Full Release Gate (~50 minutes)
```bash
make -f Makefile.spiral gate
```

This runs the complete testing pipeline:
1. **Cost Guard Tests** - Verify budget limits work
2. **GPU Loader** - CUDA availability and memory checks  
3. **Live Smoke** - API endpoint validation
4. **Titanic Suite** - 380 prompts, comprehensive accuracy testing
5. **Soak Test** - 5 min @ 120 QPS load testing
6. **Alert Drill** - End-to-end alerting verification

Success criteria:
- ✅ Effective success ≥ 97%
- ✅ Composite accuracy ≥ 85% 
- ✅ Cost ≤ $0.07 (with cache + pattern heads)
- ✅ P95 latency ≤ 200ms

## 📊 Monitoring & Alerts

### Dashboards
- **Grafana**: Real-time metrics, GPU utilization, request latencies
- **Traefik**: Load balancer metrics, traffic distribution
- **Prometheus**: Raw metrics and alerting rules

### Key Metrics
- `swarm_gpu_memory_used_bytes` - VRAM usage
- `swarm_cache_hit_ratio` - Redis cache performance  
- `swarm_fragmentation_events_total` - Memory fragmentation
- `swarm_lora_version` - Current model version

### Alert Examples
```bash
# Test VRAM alerts
make -f Makefile.spiral test-alerts-e2e

# Manual alert check
curl http://localhost:9093/api/v1/alerts
```

## 💰 Cost Management

Built-in budget tracking and guardrails:

```bash
# Check current spending
make -f Makefile.spiral budget-status

# Reset daily budget
make -f Makefile.spiral budget-reset

# Run with strict cost limits
make -f Makefile.spiral test-cost-guard STRICT_COST=on
```

Budget limits are enforced at the API level - requests are blocked when daily limits are exceeded.

## 🔧 Development Workflow

### Local Development
```bash
# Use lighter development stack
make -f Makefile.spiral dev-up

# Quick validation  
make -f Makefile.spiral quick-test
```

### Debugging
```bash
# Service logs
make -f Makefile.spiral logs-api
make -f Makefile.spiral logs-trainer

# Container status
make -f Makefile.spiral status

# Health check all services
make -f Makefile.spiral health
```

## 🚨 Production Deployment

For production deployment:

1. **Update environment**:
   ```bash
   cp .env.spiral .env.production
   # Set production API keys, disable debug flags
   ```

2. **Use production compose**:
   ```bash
   ENV_FILE=.env.production make -f Makefile.spiral up
   ```

3. **Configure TLS** (remove `api.insecure=true` from Traefik)

4. **Set up external monitoring** (PagerDuty, Slack integration)

## 📋 Troubleshooting

### Common Issues

**GPU not accessible**:
```bash
# Check NVIDIA runtime
docker run --rm --gpus all nvidia/cuda:12.1-runtime-ubuntu22.04 nvidia-smi
```

**Services not healthy**:
```bash
# Check specific service logs
make -f Makefile.spiral logs-api

# Verify environment variables
docker compose -f docker-compose.production.yml config
```

**High latency**:
```bash
# Check VRAM usage (should be ≤10 GB)
make -f Makefile.spiral health

# Monitor fragmentation
curl -s http://localhost:9090/api/v1/query?query=swarm_fragmentation_events_total
```

## 🔄 Maintenance

### Regular Tasks
```bash
# Weekly cleanup
make -f Makefile.spiral clean

# Model cache refresh (if needed)
make -f Makefile.spiral clean-models
make -f Makefile.spiral init
```

### Backup Important Data
- Redis data: `docker volume inspect redis_data`
- Model files: `./models/`
- Configuration: `.env.spiral`, monitoring config

---

For CI/CD integration, see the GitHub Actions workflow in the next section. 