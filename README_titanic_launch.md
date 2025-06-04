# 🚢 Titanic Gauntlet - The Ultimate SwarmAI Benchmark

**The definitive test**: Is a purpose-built micro-swarm actually smarter per dollar than a single mega-model?

## 🎯 **Battle Plan Overview**

### **The Question**
Can SwarmAI's council of specialized 0.5-7B models outperform Mistral-Medium 3's single 13B model across diverse domains while maintaining 10x cost advantage?

### **The Test**
- **380 prompts** across 6 domains (Math, Reasoning, Coding, Science, Planning, Writing)
- **Weighted composite scoring** (Math 30%, Reasoning 25%, Code 20%, Science 15%, Planning/Writing 5% each)
- **Statistical rigor**: 95% confidence intervals, Wilson CIs, effect size analysis
- **Operational guards**: $20 budget cap, adaptive throttling, VRAM monitoring

### **The Stakes**
**Pass Requirements:**
- ≥15pp accuracy advantage over Mistral-Medium 3
- ≥10x cost advantage
- Sub-second P95 latency
- 95% confidence intervals non-overlapping
- Zero VRAM spill (9.9GB envelope preserved)

## 🚢 **Running the Titanic Gauntlet**

### **Prerequisites**
```bash
# Environment variables
export OPENAI_API_KEY=your_openai_key
export MISTRAL_API_KEY=your_mistral_key

# Dependencies
pip install prometheus_client GPUtil psutil

# Swarm server running
python start_swarm_server.py &
```

### **Quick Test (Stub Dataset)**
```bash
python run_titanic_gauntlet.py
```

### **Full Production Run**
```bash
# Create sealed 380-prompt dataset first
# python create_titanic_dataset.py

# Run full gauntlet
python run_titanic_gauntlet.py
```

## 📊 **Monitoring & Observability**

### **Real-Time Metrics**
- **Prometheus endpoint**: `http://localhost:8001/metrics`
- **Progress tracking**: `titanic_progress_percent{shard="X"}`
- **Cost accumulation**: `titanic_cost_usd{provider="swarm_council"}`
- **Latency distribution**: `titanic_latency_ms{provider="mistral_medium_3"}`

### **Checkpointing**
- **Auto-save**: Every 10 chunks (380 items)
- **Resume capability**: `--resume checkpoints/titanic_checkpoint_N.json`
- **Budget protection**: Adaptive throttling at $15 cloud spend

## 🎯 **Operational Safeguards**

### **Budget Management**
```yaml
budget_management:
  total_cap_usd: 20.0                    # Hard stop at $20
  adaptive_throttling:
    cloud_threshold: 15.0                # Pause at $15 cloud spend
    throttle_delay_minutes: 5            # Wait 5min before continuing
```

### **Statistical Guards**
```yaml
guards:
  swarm_beats_mistral_by: ">=15pp"       # 15 percentage point advantage
  statistical_confidence: ">=95%"        # 95% confidence required
  cost_advantage: ">=10x"                # 10x cost savings minimum
  swarm_p95_latency_ms: "<=1000"         # Sub-second P95 latency
```

### **Chunked Execution**
- **10 shards** of 38 items each
- **Fault tolerance**: Individual chunk failures don't kill entire run
- **Progress visibility**: Real-time shard completion tracking

## 📈 **Expected Outcomes**

### **Optimistic Scenario**
```
SwarmAI Council: 72% composite accuracy, $0.015/request, 850ms P95
Mistral-Medium: 57% composite accuracy, $0.180/request, 1200ms P95

Result: ✅ PASSED
- 15pp accuracy advantage 
- 12x cost advantage
- Sub-second latency achieved
- Statistical significance confirmed
```

### **Realistic Scenario**
```
SwarmAI Council: 68% composite accuracy, $0.020/request, 950ms P95  
Mistral-Medium: 60% composite accuracy, $0.200/request, 1100ms P95

Result: ⚠️ MIXED
- 8pp accuracy advantage (< 15pp required)
- 10x cost advantage (✅ meets threshold)
- Sub-second latency achieved
- CIs may overlap (inconclusive)
```

### **Failure Modes**
- **Accuracy gap < 15pp**: Swarm needs optimization
- **CI overlap**: Insufficient statistical power, need more data
- **Latency > 1s**: Council deliberation too slow
- **Budget exceeded**: Cloud costs too high
- **VRAM spill**: Memory optimization needed

## 📊 **Report Structure**

### **Statistical Analysis**
```json
{
  "statistical_analysis": {
    "swarm_council": {
      "composite_accuracy": 0.68,
      "confidence_interval": [0.64, 0.72],
      "domain_breakdown": {
        "math": 0.75,
        "reasoning": 0.70,
        "coding": 0.65
      }
    }
  }
}
```

### **Operational Metrics**
```json
{
  "operational": {
    "total_duration_seconds": 2400,
    "chunks_processed": 10,
    "vram_peak_mb": 9850,
    "total_cost_usd": 18.50,
    "cloud_cost_usd": 14.20
  }
}
```

## 🏆 **Success Criteria**

### **Technical Validation**
- [ ] 95% confidence intervals non-overlapping
- [ ] Effect size ≥ 15 percentage points
- [ ] Cost advantage ≥ 10x verified
- [ ] P95 latency ≤ 1000ms measured
- [ ] VRAM envelope preserved (<10GB)

### **Business Validation**
- [ ] Total spend ≤ $20 (budget discipline)
- [ ] Adaptive throttling prevents overruns
- [ ] Prometheus metrics capture operational reality
- [ ] Statistical rigor prevents false claims

### **README-Ready Claims**
If **PASSED**:
> "SwarmAI passes Titanic Gauntlet with 15pp accuracy advantage, 10x cost savings, and sub-second latency. Statistical significance confirmed across 380 prompts spanning 6 domains."

If **FAILED**:
> "SwarmAI shows promise but requires optimization before production claims. Comprehensive statistical analysis guides development priorities."

## 🚀 **Next Steps**

1. **Create Dataset**: Curate 380 high-quality prompts across 6 domains
2. **Baseline Run**: Execute stub dataset to verify infrastructure
3. **Production Run**: Launch full Titanic Gauntlet with monitoring
4. **Analysis**: Statistical deep-dive on results
5. **Optimization**: Address identified weaknesses
6. **Publication**: README update with confident claims or honest limitations

**Ready to light the fuse? 🔥**

```bash
python run_titanic_gauntlet.py
``` 