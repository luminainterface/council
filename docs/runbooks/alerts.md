# Alert Reference Guide

**System:** Autonomous Software Spiral v2.7.0  
**Monitoring:** Prometheus + Alertmanager + Grafana  
**Alert Manager:** http://localhost:9093

## 🚨 Critical Alerts (Immediate Response Required)

### **GPU Alerts**

| Alert Name | Threshold | Symptoms | Runbook |
|------------|-----------|----------|---------|
| **VRAMCritical** | >12GB usage | API timeouts, training failures | [GPU Memory](#gpu-memory-critical) |
| **GPUFragmentation** | >5 fragmentation events/hour | Slow model loading, CUDA errors | [GPU Fragmentation](#gpu-fragmentation) |
| **CUDAError** | CUDA runtime failures | Complete GPU unavailability | [CUDA Recovery](#cuda-error-recovery) |

### **API Performance Alerts**

| Alert Name | Threshold | Symptoms | Runbook |
|------------|-----------|----------|---------|
| **APILatencyCritical** | >5000ms p95 | User complaints, timeouts | [High Latency](#api-latency-critical) |
| **APIErrorRateHigh** | >5% errors | Failed requests, 500s | [Error Rate](#api-error-rate) |
| **APIDown** | Health check fails | Complete service unavailability | [Service Down](#api-service-down) |

### **Cost & Budget Alerts**

| Alert Name | Threshold | Symptoms | Runbook |
|------------|-----------|----------|---------|
| **BudgetExceeded** | >95% daily budget | API rejections, training stops | [Budget Runbook](./budget.md) |
| **CostSpike** | >200% cost velocity | Unexpected spend increase | [Cost Investigation](#cost-spike) |

### **Training Alerts**

| Alert Name | Threshold | Symptoms | Runbook |
|------------|-----------|----------|---------|
| **TrainingMissed** | Nightly job failed | No model updates | [Trainer Runbook](./trainer.md) |
| **TrainingTimeout** | >30min job duration | Resource contention | [Training Timeout](#training-timeout) |

## 🔧 Alert Troubleshooting Procedures

### **GPU Memory Critical**
```bash
# Immediate diagnosis
nvidia-smi
docker stats --format "table {{.Container}}\t{{.MemUsage}}"

# Emergency GPU reset
docker compose -f docker-compose.production.yml stop api api-canary trainer
nvidia-smi --gpu-reset
docker compose -f docker-compose.production.yml up -d api api-canary
```

### **GPU Fragmentation**
```bash
# Check fragmentation stats
nvidia-smi --query-gpu=memory.free,memory.used --format=csv

# Clear fragmentation
docker compose -f docker-compose.production.yml restart api api-canary
# Or implement CUDA memory pool with fixed blocks
```

### **CUDA Error Recovery**
```bash
# Check CUDA driver status
nvidia-smi -q | grep -E "(Driver|CUDA)"

# Container-level CUDA check
docker compose -f docker-compose.production.yml exec api \
  python -c "import torch; print(torch.cuda.is_available())"

# Full GPU reset if needed
sudo rmmod nvidia_uvm nvidia_drm nvidia_modeset nvidia
sudo modprobe nvidia nvidia_modeset nvidia_drm nvidia_uvm
```

### **API Latency Critical**
```bash
# Check current latency
curl -w "%{time_total}" http://localhost:9000/health

# Identify bottlenecks
make -f Makefile.spiral logs-api | grep -E "(slow|timeout|latency)"

# Emergency actions: restart containers, switch to faster models
```

### **API Error Rate**
```bash
# Check error distribution
curl http://localhost:9000/metrics | grep -E "error|exception"

# Review recent errors
make -f Makefile.spiral logs-api | grep -E "ERROR|Exception" | tail -20

# Common fixes
# 1. Check model loading issues
# 2. Verify GPU memory availability
# 3. Check budget limits
# 4. Restart unhealthy containers
```

### **API Service Down**
```bash
# Check container status
docker compose -f docker-compose.production.yml ps api api-canary

# Check health endpoint
curl http://localhost:9000/health || echo "API Down"

# Emergency restart
docker compose -f docker-compose.production.yml restart api api-canary

# Check logs for crash reason
make -f Makefile.spiral logs-api | tail -100
```

### **Cost Spike Investigation**
```bash
# Check recent cost breakdown
curl http://localhost:9000/budget | jq '.cost_breakdown'

# Identify expensive operations
make -f Makefile.spiral logs | grep "Cost tracking" | tail -20
```

### **Training Timeout**
```bash
# Check current training job
make -f Makefile.spiral logs-trainer | tail -50

# Check GPU contention
nvidia-smi dmon -s pucv -c 5

# Check if multiple training jobs running
docker compose -f docker-compose.evolution.yml ps trainer

# Solutions
# 1. Reduce training dataset size
# 2. Optimize LoRA parameters (lower rank)
# 3. Increase timeout limit if legitimate
```

## 📊 Alert Severity Matrix

### **Response Times**
- **Critical:** 5 minutes (immediate)
- **Warning:** 30 minutes (business hours)
- **Info:** Monitor only (daily review)

### **Escalation Paths**
1. **On-call Engineer** → Initial response and basic troubleshooting
2. **Platform Team Lead** → Complex infrastructure issues
3. **ML Team Lead** → Training algorithm and model issues
4. **Product Owner** → Budget and capacity decisions

## 🔔 Alert Configuration

### **Alertmanager Integration**
```yaml
# Example alert rule linking to runbooks
groups:
  - name: spiral_alerts
    rules:
      - alert: VRAMCritical
        expr: gpu_memory_used_bytes > 12e9
        annotations:
          summary: "GPU memory usage critical"
          description: "GPU memory usage is {{ $value }}GB (>12GB threshold)"
          runbook_url: "http://docs.spiral.local/runbooks/alerts.md#gpu-memory-critical"
```

### **Notification Channels**
- **Slack:** #spiral-alerts (all alerts)
- **PagerDuty:** Critical alerts only
- **Email:** Platform team for warnings
- **Grafana Dashboard:** Visual alert status

## 🎯 Alert Tuning Guidelines

### **Reducing False Positives**
- Use trending/rate alerts instead of absolute thresholds
- Implement alert dampening for flapping conditions
- Set up alert dependencies (don't alert on API if GPU is down)

### **Critical Alert Criteria**
- User-facing service impact
- Data loss risk
- Security vulnerabilities
- Budget overrun risk

### **Regular Alert Review**
- Weekly review of alert frequency and accuracy
- Monthly tuning of thresholds based on system evolution
- Quarterly runbook updates and incident retrospectives

## 📚 Related Documentation

- **[Budget Runbook](./budget.md)** - Cost troubleshooting
- **[Trainer Runbook](./trainer.md)** - Training failures
- **[Architecture Guide](../evolution/v2.7.0.md)** - System overview
- **[Grafana Dashboards](http://localhost:3000)** - Visual monitoring

## 🔍 Alert History & Analytics

### **Common Alert Patterns**
- **Morning GPU spikes:** Due to scheduled training jobs
- **Budget warnings on weekends:** Accumulation from Friday traffic
- **API latency during model reloads:** Expected during updates

### **Alert Metrics to Track**
- Mean time to detection (MTTD)
- Mean time to resolution (MTTR)
- False positive rate
- Alert escalation frequency

---
**Last Updated:** December 2024  
**Version:** v2.7.0  
**Maintained By:** Platform Team 