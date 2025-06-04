# 🐳🎭🪴 **DOCKER DEPLOYMENT CHECKLIST**

## **🔥 PRE-DEPLOYMENT VALIDATION**

### **✅ DOCKER INFRASTRUCTURE READY**
- [ ] **Docker Compose validates:** `docker-compose config`
- [ ] **GPU access works:** `docker run --gpus all nvidia/cuda:12.2-runtime nvidia-smi`
- [ ] **Environment variables set:** Copy `docker.env.template` to `.env` and fill values
- [ ] **Volume permissions:** `sudo mkdir -p /var/lib/tamagotchi/{prometheus,grafana}`

### **✅ EMOTIONAL TAMAGOTCHI SYSTEM READY**
- [ ] **V11 Swarm operational:** 9 emotions responding in <1ms
- [ ] **Round-table protocol tested:** Emotional consensus in <10ms
- [ ] **Evolution ledger exists:** `touch evolution_checksums.txt`
- [ ] **Jobs queue directory:** `mkdir -p jobs/queue`

### **✅ SECURITY & SECRETS**
- [ ] **Grafana admin password set:** `GRAFANA_ADMIN_PASSWORD` in `.env`
- [ ] **Telegram bot configured:** `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
- [ ] **Read-only containers:** API & scheduler run as non-root
- [ ] **Docker secrets managed:** No credentials in git

---

## **🚀 DEPLOYMENT STEPS**

### **1. BUILD PHASE**
```bash
# Clone and checkout evolution-main
git clone <repo> && cd NNprojecthome
git checkout evolution-main

# Build all images
make build

# Verify build success
docker images | grep emotional-tamagotchi
```

### **2. VALIDATION PHASE**
```bash
# Test GPU access
make gpu-test

# Validate Docker Compose
docker-compose config | head -20

# Check environment
cat .env | grep -v TOKEN
```

### **3. STARTUP PHASE**
```bash
# Start the emotional evolution stack
make up

# Verify all containers running
make status

# Check health endpoints
make health
```

### **4. VERIFICATION PHASE**
```bash
# Test emotional round-table
curl -X POST http://localhost:8000/emotional-consensus \
     -H "Content-Type: application/json" \
     -d '{"task": "Test deployment consensus"}'

# Check Prometheus metrics
curl http://localhost:9091/metrics | grep emotional

# Verify Grafana access
open http://localhost:3000
```

---

## **📊 MONITORING SETUP**

### **✅ PROMETHEUS TARGETS**
- [ ] **Swarm API:** `swarm-api:9090/metrics` scraping every 5s
- [ ] **Trainer:** `trainer:8080/metrics` scraping every 30s
- [ ] **Scheduler:** `scheduler:8081/metrics` scraping every 60s

### **✅ GRAFANA DASHBOARDS**
- [ ] **Emotional Consensus:** Response times, vote distributions
- [ ] **Training Progress:** LoRA job queues, completion rates
- [ ] **System Health:** Container CPU/Memory, GPU utilization

### **✅ TELEGRAM ALERTS**
- [ ] **Training completions:** New LoRA models ready
- [ ] **System failures:** Container crashes, GPU issues
- [ ] **Evolution milestones:** Successful emotional consensus

---

## **🔍 PRODUCTION VALIDATION**

### **FIRST 30 MINUTES:**
- [ ] All 5 containers running and healthy
- [ ] Emotional round-table responds in <10ms
- [ ] Prometheus collecting metrics from all targets
- [ ] Grafana dashboards loading correctly

### **FIRST 24 HOURS:**
- [ ] Nightly scheduler triggers emotional evolution
- [ ] At least one LoRA job queued and started
- [ ] Evolution ledger has new emotional consensus entries
- [ ] No container restarts or memory issues

### **FIRST WEEK:**
- [ ] Multiple successful training cycles completed
- [ ] Performance metrics stable (latency, memory)
- [ ] Telegram notifications working correctly
- [ ] Backup system operational

---

## **🚨 FAILURE SCENARIOS & ROLLBACK**

### **CONTAINER FAILURES:**
```bash
# Check logs for errors
make logs-api | grep ERROR
make logs-trainer | grep FAILED

# Restart specific service
docker-compose restart swarm-api

# Full stack restart
make restart
```

### **GPU ACCESS ISSUES:**
```bash
# Verify GPU drivers on host
nvidia-smi

# Check container GPU access
docker-compose exec trainer nvidia-smi

# Restart with GPU debugging
docker-compose down && docker-compose up -d
```

### **EMOTIONAL CONSENSUS FAILURES:**
```bash
# Test V11 swarm directly
python v11_emotional_swarm.py

# Check emotional round-table
python emotional_roundtable_protocol.py

# Verify all 9 emotions responding
curl http://localhost:8000/swarm/status
```

### **EMERGENCY ROLLBACK:**
```bash
# Stop current deployment
make down

# Rollback to previous version
git checkout v1.0-evo^
make build && make up

# Verify system operational
make health && make evolution-status
```

---

## **📈 SUCCESS METRICS**

### **PERFORMANCE TARGETS:**
- **Emotional Consensus:** <10ms for 9-emotion vote
- **API Response:** <50ms for swarm endpoints
- **Memory Usage:** <16GB total (all containers)
- **GPU Utilization:** 70-90% during training

### **RELIABILITY TARGETS:**
- **Uptime:** 99.5% (scheduled maintenance excluded)
- **Training Success Rate:** >95% LoRA jobs complete successfully
- **Consensus Agreement:** >80% unanimous emotional votes

### **EVOLUTION TARGETS:**
- **Nightly Evolution:** Scheduled emotional council every 24h
- **Model Improvements:** Measurable performance gains in target blocks
- **Safety Compliance:** Zero red-team policy violations

---

## **🎯 POST-DEPLOYMENT TASKS**

### **IMMEDIATE (Day 1):**
- [ ] Monitor logs for first 8 hours continuously
- [ ] Verify first nightly emotional evolution cycle
- [ ] Set up log rotation and disk space monitoring
- [ ] Document any deployment-specific configurations

### **SHORT-TERM (Week 1):**
- [ ] Establish backup schedules for evolution data
- [ ] Set up automated health checks and alerting
- [ ] Performance baseline measurement and optimization
- [ ] Team training on new Docker workflow

### **LONG-TERM (Month 1):**
- [ ] Capacity planning based on actual usage
- [ ] Security audit of container configurations
- [ ] Disaster recovery testing and procedures
- [ ] Documentation of operational runbooks

---

**🔥 EMOTIONAL TAMAGOTCHI DOCKERIZED AND READY FOR PRODUCTION!** 🎭🪴🚀

*Next Command: `make build && make up`*  
*Next Check: Watch those emotional consensus times hit <10ms!* 