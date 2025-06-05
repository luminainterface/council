# Runbook: Trainer Failures (LoRA Training Issues)

**Alert:** `TrainerFailed` / `LoRATrainingMissed`  
**Severity:** Warning (1 failure), Critical (2+ consecutive failures)  
**Response Time:** 30 minutes (warning), 15 minutes (critical)

## 🚨 Alert Symptoms

### **Training Symptoms**
- LoRA training jobs failing with errors
- Scheduler logs showing training timeouts
- Missing nightly training completion (expected at 2:00 AM UTC)
- Prometheus metric `training_failures_total` incrementing

### **System Symptoms**
- GPU memory errors or CUDA out-of-memory
- Disk space issues in model storage
- Redis queue backing up with failed jobs
- Model hot-reload endpoints returning stale models

## 🔍 Immediate Diagnosis

### **Step 1: Check Trainer Status**
```bash
# Check trainer container status
make -f Makefile.spiral status | grep trainer

# Check recent trainer logs
make -f Makefile.spiral logs-trainer | tail -50

# Check if evolution services are running
docker compose -f docker-compose.evolution.yml ps
```

### **Step 2: Check GPU Resources**
```bash
# Check GPU memory usage
nvidia-smi

# Check CUDA availability in container
docker compose -f docker-compose.evolution.yml exec trainer \
  python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"

# Check GPU memory from inside container
docker compose -f docker-compose.evolution.yml exec trainer nvidia-smi
```

### **Step 3: Check Storage and Queue**
```bash
# Check available disk space
df -h | grep -E "(models|docker)"

# Check Redis training queue
docker compose -f docker-compose.production.yml exec redis \
  redis-cli LLEN training_queue

# Check failed job details
docker compose -f docker-compose.production.yml exec redis \
  redis-cli LRANGE training_queue:failed 0 -1
```

## ⚡ Immediate Actions

### **Option A: Restart Trainer Service**
```bash
# Restart trainer container
docker compose -f docker-compose.evolution.yml restart trainer

# Check if restart resolved the issue
make -f Makefile.spiral evolution-health

# Verify training can start
make -f Makefile.spiral evolution-once
```

### **Option B: Clear GPU Memory Issues**
```bash
# Stop all GPU processes
docker compose -f docker-compose.evolution.yml stop trainer
docker compose -f docker-compose.production.yml stop api api-canary

# Clear GPU memory
nvidia-smi --gpu-reset

# Restart services
docker compose -f docker-compose.production.yml up -d api api-canary
docker compose -f docker-compose.evolution.yml up -d trainer
```

### **Option C: Clear Storage Issues**
```bash
# Clean old model checkpoints (if disk space issue)
docker volume ls | grep models
docker compose -f docker-compose.evolution.yml exec trainer \
  find /app/models -name "*.pt" -mtime +7 -delete

# Or clean entire model cache if severely corrupted
make -f Makefile.spiral clean-models
```

## 🔧 Root Cause Analysis

### **Common Failure Modes**

1. **GPU Out-of-Memory**
   ```bash
   # Check logs for CUDA errors
   make -f Makefile.spiral logs-trainer | grep -i "cuda\|memory\|oom"
   
   # Symptoms: "CUDA out of memory", "RuntimeError: CUDA error"
   # Solution: Reduce batch size or model rank in trainer config
   ```

2. **Training Timeout**
   ```bash
   # Check for timeout messages
   make -f Makefile.spiral logs-trainer | grep -i "timeout\|exceed"
   
   # Symptoms: Jobs killed after 30-minute limit
   # Solution: Optimize training parameters or increase time limit
   ```

3. **Data Pipeline Issues**
   ```bash
   # Check for data loading errors
   make -f Makefile.spiral logs-trainer | grep -i "data\|dataset\|load"
   
   # Symptoms: "FileNotFoundError", "DataLoader", "corrupt"
   # Solution: Verify training data availability and format
   ```

4. **Model Loading/Saving Errors**
   ```bash
   # Check model I/O operations
   make -f Makefile.spiral logs-trainer | grep -i "model\|save\|load"
   
   # Symptoms: Permission errors, corrupted checkpoints
   # Solution: Fix volume permissions or clear corrupted models
   ```

### **Investigation Commands**

```bash
# Detailed trainer diagnostics
docker compose -f docker-compose.evolution.yml exec trainer \
  python -c "
import torch
import os
print(f'CUDA: {torch.cuda.is_available()}')
print(f'GPU Count: {torch.cuda.device_count()}')
print(f'GPU Memory: {torch.cuda.get_device_properties(0).total_memory // 1024**3}GB')
print(f'Disk Space: {os.statvfs(\"/app/models\").f_bavail * os.statvfs(\"/app/models\").f_frsize // 1024**3}GB')
"

# Check training job configuration
make -f Makefile.spiral logs-trainer | grep "LoRA.*config" | tail -5

# Verify Redis connectivity
docker compose -f docker-compose.evolution.yml exec trainer \
  python -c "import redis; r=redis.Redis(host='redis'); print(r.ping())"
```

## 🛠️ Specific Fixes

### **Fix 1: GPU Memory Optimization**
```bash
# Edit trainer configuration to use less GPU memory
# In trainer/lora_train.py, reduce these parameters:

# MAX_RANK = 8  # Reduce from 16
# BATCH_SIZE = 1  # Reduce from 2
# GRADIENT_ACCUMULATION = 2  # Increase to maintain effective batch size
```

### **Fix 2: Training Data Refresh**
```bash
# Clear cached training data and regenerate
docker compose -f docker-compose.evolution.yml exec trainer \
  rm -rf /app/training_data/cache/*

# Restart pattern mining to regenerate data
docker compose -f docker-compose.evolution.yml restart scheduler
```

### **Fix 3: Fix Permissions Issues**
```bash
# Fix model volume permissions
sudo chown -R 1000:1000 $(docker volume inspect models_vol --format '{{.Mountpoint}}')

# Or recreate the volume
docker volume rm models_vol
docker compose -f docker-compose.evolution.yml up -d
```

### **Fix 4: Manual Training Recovery**
```bash
# Run a manual training job to test the pipeline
docker compose -f docker-compose.evolution.yml exec trainer \
  python trainer/lora_train.py --manual --rank 8 --max-samples 100

# If successful, restart the scheduler
docker compose -f docker-compose.evolution.yml restart scheduler
```

## 📊 Health Checks & Validation

### **Training Pipeline Validation**
```bash
# Test complete training flow
make -f Makefile.spiral evolution-once

# Verify model was saved
docker compose -f docker-compose.evolution.yml exec trainer \
  ls -la /app/models/ | grep $(date +%Y-%m-%d)

# Test model hot-reload
curl -X POST http://localhost:9000/admin/reload

# Verify new model is loaded
curl http://localhost:9000/health | jq '.model_info'
```

### **Monitoring Validation**
```bash
# Check training metrics
curl http://localhost:9000/metrics | grep training

# Verify scheduler is active
docker compose -f docker-compose.evolution.yml logs scheduler | tail -10

# Check next scheduled job
docker compose -f docker-compose.evolution.yml exec scheduler \
  python -c "from scheduler.scheduler import scheduler; scheduler.print_jobs()"
```

## 🎯 Prevention & Monitoring

### **Proactive Monitoring**
- Set up alerts for consecutive training failures (>2 in 24h)
- Monitor GPU memory usage trends during training
- Track training completion rate and job duration

### **Automated Recovery**
- Implement training job retry with exponential backoff
- Add automatic GPU memory cleanup on failure
- Set up storage cleanup for old model checkpoints

### **Capacity Planning**
- Monitor training data size growth
- Plan for model storage capacity (current: ~50MB per model)
- Track GPU utilization patterns for optimal scheduling

## 📞 Escalation Matrix

| Issue Type | Escalate To | Timeline |
|------------|-------------|----------|
| GPU/Hardware Issues | Infrastructure Team | Immediate |
| Training Algorithm Problems | ML Team | 2+ failures |
| Storage/Persistence Issues | Platform Team | Disk >90% full |
| Scheduler Configuration | Platform Team | Jobs not queuing |

## 🔗 Related Resources

- **[GPU Monitoring Dashboard](http://localhost:3000/d/gpu)** - Real-time GPU metrics
- **[Training Jobs Queue](http://localhost:9000/admin/jobs)** - Job status and history
- **[Budget Runbook](./budget.md)** - If training fails due to cost limits
- **[Alert Reference](./alerts.md)** - Complete alert troubleshooting

---
**Last Updated:** December 2024  
**Version:** v2.7.0  
**Tested With:** NVIDIA RTX 4090, CUDA 12.1 