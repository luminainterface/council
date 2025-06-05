# Runbook: Budget Exceeded (Cost Protection)

**Alert:** `CostExceeded` / `BudgetUtilizationHigh`  
**Severity:** Warning (>80% budget), Critical (>95% budget)  
**Response Time:** 15 minutes (warning), 5 minutes (critical)

## 🚨 Alert Symptoms

### **API Symptoms**
- HTTP 429-like responses with `BudgetExceeded` error
- API latency spikes as requests are rejected
- Error messages: "Daily budget exceeded" or "Request exceeds per-call limit"

### **Training Symptoms** 
- LoRA training jobs failing to start
- Scheduler showing "Budget exceeded" in logs
- Prometheus metric `swarm_budget_exceeded_total` incrementing

### **Monitoring Indicators**
- `swarm_router_budget_dollars_total` > $0.08 (80% of $0.10 limit)
- Recent cost spike in Grafana dashboard
- Alert fired from Alertmanager: Budget utilization high

## 🔍 Immediate Diagnosis

### **Step 1: Check Current Budget Status**
```bash
# Quick status check
make -f Makefile.spiral budget-status

# Or via API (if accessible)
curl http://localhost:9000/budget | jq '.budget_status'

# Via Redis directly
docker compose -f docker-compose.production.yml exec redis \
  redis-cli HGETALL swarm:budget:daily
```

**Expected Output:**
```json
{
  "rolling_cost_dollars": 0.087,
  "max_budget_dollars": 0.10,
  "utilization_percent": 87.0,
  "remaining_dollars": 0.013
}
```

### **Step 2: Identify Cost Sources**
```bash
# Check cost breakdown by model
curl http://localhost:9000/budget | jq '.cost_breakdown'

# Check recent expensive operations
make -f Makefile.spiral logs-api | grep "Cost tracking" | tail -20

# Check trainer costs specifically  
make -f Makefile.spiral logs-trainer | grep "💰"
```

### **Step 3: Check for Runaway Processes**
```bash
# Check for stuck training jobs
docker compose -f docker-compose.evolution.yml ps trainer

# Check Redis queue depth
docker compose -f docker-compose.production.yml exec redis \
  redis-cli LLEN training_queue

# Check recent API traffic volume
curl http://localhost:9000/metrics | grep swarm_requests_total
```

## ⚡ Immediate Actions

### **Option A: Emergency Budget Reset (Use Sparingly)**
```bash
# ⚠️ ONLY if you need immediate API restoration
make -f Makefile.spiral budget-reset

# Verify reset worked
make -f Makefile.spiral budget-status
```
**⚠️ Warning:** This resets the 24-hour rolling window. Only use if API is completely down and business critical.

### **Option B: Increase Budget Limit (Temporary)**
```bash
# Temporarily raise daily limit to $0.20
export SWARM_BUDGET=0.20

# Restart API with new limit
docker compose -f docker-compose.production.yml restart api api-canary

# Monitor closely - this doubles your spend risk
```

### **Option C: Stop Non-Critical Training (Recommended)**
```bash
# Stop evolution training to preserve API budget
make -f Makefile.spiral evolution-down

# Clear training queue
docker compose -f docker-compose.production.yml exec redis \
  redis-cli DEL training_queue

# Restart API only
docker compose -f docker-compose.production.yml up -d api api-canary
```

## 🔧 Root Cause Analysis

### **Common Causes**

1. **Expensive Model Usage**
   - Check if `mistral_7b_instruct` or `mixtral_8x7b` being used heavily
   - Look for token count spikes (large prompts/responses)
   - Verify pricing table hasn't been misconfigured

2. **Training Job Issues**
   - LoRA training jobs running too frequently
   - Training on large datasets without limits
   - Failed jobs retrying indefinitely

3. **API Traffic Spikes**
   - Sudden increase in request volume
   - Large prompt submissions (>1000 tokens)
   - Automated systems hitting API aggressively

4. **Configuration Errors**
   - Per-request cap set too high
   - Daily budget set too low for workload
   - Cost tracking not properly initialized

### **Investigation Commands**

```bash
# Check API request patterns
curl http://localhost:9000/metrics | grep -E "(requests_total|request_duration)"

# Review last 24h of cost tracking
make -f Makefile.spiral logs | grep "Cost tracking" | head -50

# Check model usage distribution
curl http://localhost:9000/budget | jq '.cost_breakdown' | sort -rn

# Verify pricing configuration
docker compose -f docker-compose.production.yml exec api \
  python -c "from router.cost_tracking import PRICING_TABLE; print(PRICING_TABLE)"
```

## 🛠️ Long-term Fixes

### **Optimize Cost Efficiency**

1. **Model Selection Tuning**
   ```bash
   # Force cheaper models when budget is high
   # Edit router/cost_tracking.py to adjust downgrade thresholds
   
   # Example: downgrade at 70% instead of 100%
   if cost_ledger.rolling_cost_dollars > (cost_ledger.max_budget_dollars * 0.7):
       return downgrade_route(original_route)
   ```

2. **Training Schedule Optimization**
   ```bash
   # Reduce training frequency in scheduler/scheduler.py
   # Change from nightly to every 2-3 days during high usage periods
   
   # Or implement smart scheduling based on budget utilization
   ```

3. **Request Size Limits**
   ```bash
   # Add token limits in API validation
   # Reject requests with >500 tokens input to prevent large costs
   ```

### **Monitoring Improvements**

1. **Enhanced Alerting**
   ```bash
   # Add predictive alerts at 60% budget utilization
   # Set up trending alerts for unusual cost velocity
   ```

2. **Dashboard Updates**
   ```bash
   # Add cost velocity charts to Grafana
   # Add model usage efficiency metrics
   ```

## 📊 Post-Incident Actions

### **Immediate (Within 1 hour)**
- [ ] Document what caused the budget spike
- [ ] Verify API functionality restored
- [ ] Check if any training jobs need to be restarted
- [ ] Notify team of any service impact

### **Short-term (Within 24 hours)**
- [ ] Analyze cost patterns to prevent recurrence
- [ ] Adjust monitoring thresholds if needed
- [ ] Update budget limits if current limits are too restrictive
- [ ] Review training schedules for optimization

### **Long-term (Within 1 week)**
- [ ] Implement any necessary cost optimization changes
- [ ] Update runbooks with lessons learned
- [ ] Consider automated cost controls (dynamic budget adjustment)
- [ ] Plan for capacity increases if growth is legitimate

## 🎯 Prevention Strategies

### **Proactive Monitoring**
- Set up budget trending alerts at 50%, 70%, 90% utilization
- Monitor daily cost velocity ($/hour) for anomaly detection
- Track per-model cost efficiency metrics

### **Automated Controls**
- Implement graduated service degradation as budget approaches limit
- Add circuit breakers for expensive operations
- Set up automatic training suspension at 80% budget utilization

### **Capacity Planning**
- Review budget needs monthly based on usage trends
- Plan for traffic growth and model evolution needs
- Consider tiered budgets for different service levels

## 📞 Escalation Contacts

| Role | Contact | When to Escalate |
|------|---------|-----------------|
| On-call Engineer | [Contact Info] | Immediate (critical alerts) |
| ML Team Lead | [Contact Info] | Training-related budget issues |
| Product Owner | [Contact Info] | Budget limit adjustment decisions |
| Infrastructure Team | [Contact Info] | Platform/monitoring issues |

## 📈 Related Dashboards

- **[Grafana Budget Dashboard](http://localhost:3000/d/budget)** - Real-time cost tracking
- **[Prometheus Targets](http://localhost:9090/targets)** - Metric collection status  
- **[Alertmanager](http://localhost:9093)** - Active alerts and silences

---
**Last Updated:** December 2024  
**Version:** v2.7.0  
**Owner:** Platform Team 