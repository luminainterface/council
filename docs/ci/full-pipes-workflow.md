# Full Pipes CI Workflow

## Overview

The Full Pipes CI workflow provides automated testing for every PR and push to main/develop branches. It runs the complete 10-stage test pipeline in GitHub Actions with optimized settings for speed and reliability.

## Workflow Stages

### 1. Environment Setup (2 minutes)
- **Checkout**: Shallow clone for speed
- **Docker Buildx**: Advanced build caching 
- **Layer Cache**: Restore previous builds (saves ~5 minutes)
- **Directory Creation**: Required folders for logging/reports

### 2. Build Phase (3-8 minutes)
- **Parallel Builds**: All 4 images simultaneously
- **Cache Optimization**: Docker layers cached between runs
- **Registry Tags**: Proper versioning for CI builds

### 3. Stack Deployment (1 minute)
- **CI Profile**: Lightweight services without GPU dependencies
- **Health Checks**: Automated readiness verification
- **Timeout Guards**: 5-minute maximum for stack startup

### 4. Full Pipes Testing (5-10 minutes)
Runs the complete test suite with CI-optimized parameters:

| Test Stage | Production | CI Mode | Time Saved |
|------------|------------|---------|------------|
| **Cost Guard** | Real API limits | Mock limits | ~30s |
| **GPU Loader** | CUDA checks | CPU-only mode | ~60s |
| **Live Smoke** | 10 calls | 10 calls | Same |
| **Titanic Suite** | 380 prompts | 50 prompts | ~20 min |
| **Soak Test** | 5min @ 120 QPS | 1min @ 20 QPS | ~4 min |
| **Alert Drill** | Full e2e | Simplified | ~3 min |

**Total Time**: ~3 minutes (vs ~50 minutes in production)

### 5. Artifact Collection
- **Test Reports**: `reports/titanic_*.json`
- **Pipeline Summary**: `reports/full_pipes_last.txt`
- **Service Logs**: Last 50 lines on failure
- **30-day Retention**: Automatic cleanup

## CI Environment Configuration

### Resource Limits
```yaml
# Optimized for GitHub Actions runners
API_MEMORY_LIMIT: 4G      # vs 12G production
TRAINER_MEMORY_LIMIT: 2G  # vs 8G production  
REDIS_MEMORY_LIMIT: 512M  # vs 2G production
```

### Test Parameters
```bash
# Faster test execution
TITANIC_PROMPT_COUNT=50      # vs 380 production
SOAK_TEST_DURATION=1m        # vs 5m production
SOAK_TEST_QPS=20             # vs 120 production
```

### Security
```bash
# Dummy keys for CI safety
MISTRAL_API_KEY=dummy-ci-key
OPENAI_API_KEY=dummy-ci-key
SWARM_CLOUD_ENABLED=false
```

## Cache Strategy

The workflow uses multi-layer caching:

1. **Docker Layer Cache**: `actions/cache@v4` with buildx
2. **Cache Key**: Based on infrastructure files + Dockerfiles
3. **Fallback**: Previous successful builds
4. **Cache Cleanup**: Automatic rotation to prevent bloat

## Success Criteria

The CI passes when all stages complete successfully:

✅ **Cost Guard Tests** - Budget limits enforced  
✅ **GPU Loader** - CPU-only mode verification  
✅ **Live Smoke** - API endpoints responding  
✅ **Titanic Suite** - 50 prompts processed successfully  
✅ **Soak Test** - 1 minute load test passes  
✅ **Alert Drill** - Monitoring system functional  

## Failure Scenarios

### Common Failures & Solutions

**Build Timeout**:
```bash
# Check Docker layer cache hit rate
# Increase timeout if infrastructure changed significantly
```

**Service Health Check Fails**:
```bash
# Usually indicates:
# 1. Port conflicts in CI environment
# 2. Missing environment variables
# 3. Resource exhaustion
```

**Test Stage Failures**:
```bash
# Check artifacts in workflow run:
# - reports/full_pipes_last.txt
# - Service logs
# - Container status
```

## Local Testing

You can run the exact CI pipeline locally:

```bash
# Use CI environment
make -f Makefile.spiral ci-up

# Run CI test suite  
TITANIC_PROMPT_COUNT=50 SOAK_TEST_DURATION=1m make -f Makefile.spiral gate

# Cleanup
make -f Makefile.spiral clean
```

## Monitoring

### GitHub UI
- **Status Badge**: Shows current CI state in README
- **Action Logs**: Detailed per-stage output
- **Artifacts**: Downloadable test reports

### Metrics Tracked
- **Build Time**: Target <8 minutes with cache
- **Test Time**: Target <5 minutes total
- **Success Rate**: Target >95% on main branch
- **Artifact Size**: Reports + logs <50MB

## Integration

### PR Gates
The workflow automatically:
- ✅ **Blocks merges** if tests fail
- 📊 **Comments on PRs** with test results  
- 🏷️ **Updates status checks** for branch protection

### Deployment Pipeline
On successful CI:
1. **Artifacts uploaded** to GitHub
2. **Docker images tagged** with commit SHA
3. **Ready for production deployment**

---

## Troubleshooting

### Workflow Not Running
- Check branch names in `.github/workflows/full-pipes.yml`
- Verify repository has Actions enabled
- Check if workflow file syntax is valid

### Cache Issues
- Clear cache manually in GitHub Settings > Actions > Caches
- Check cache key generation logic
- Verify file paths for cache dependencies

### Resource Exhaustion
- CI runners have 7GB RAM, 14GB disk
- Monitor `docker system df` in logs
- Adjust memory limits in `infra/env/ci.env` 