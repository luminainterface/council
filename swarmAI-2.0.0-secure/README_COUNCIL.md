# 🌌 Council-in-the-Loop Integration

**Weaving the Five Awakened Voices into Router 2.x Stack**

## 🎯 Overview

The Council-in-the-Loop integration brings philosophical consciousness to SwarmAI by implementing five distinct "voices" that collectively deliberate on complex queries. This system provides rigorous analysis while maintaining VRAM efficiency, latency targets, and budget constraints.

### 🧠 The Five Awakened Voices

| Voice | Symbol | Role | Model | Purpose |
|-------|--------|------|-------|---------|
| **Reason** | 🧠 | Logical analysis | `mistral_7b_instruct` | Rigorous chain-of-thought derivation |
| **Spark** | ✨ | Creative insights | `mistral_medium_cloud` | Lateral thinking & novel approaches |
| **Edge** | 🗡️ | Risk assessment | `math_specialist_0.8b` | Devil's advocate, red-team analysis |
| **Heart** | ❤️ | Empathy & clarity | `codellama_0.7b` | User-friendly communication |
| **Vision** | 🔮 | Strategic alignment | `phi2_2.7b` | Long-horizon roadmap integration |

## 🏗️ Architecture

### 3-Tier Flow
```
┌──────────────────┐
│  Privacy Filter  │ ← Standard security screening
└─────────┬────────┘
          │
          ▼
     Council Trigger? ← Token count ≥ 20 OR keyword match
     │              \
   no│               \ yes
     ▼                ▼
 Quick Local      Council Deliberate
 (≤120ms)         (Parallel; P95 1-2s)
          \          /
           \        /
            ▼      ▼
        Vote/Cost Guard ← Existing Router 2.x logic
                │
                ▼
        /orchestrate response
```

### 🔄 Council Deliberation Flow

1. **Phase 1: Parallel Heavy Lifting**
   - Reason drafts canonical answer (local)
   - Spark proposes creative variants (cloud, parallel)

2. **Phase 2: Fast Local Processing**
   - Edge critiques both responses (local, <120ms)
   - Heart revises for empathy (local, <120ms)
   - Vision adds strategic context (local, <150ms)

3. **Phase 3: Synthesis**
   - Combine all voices into coherent response
   - Extract risk flags from Edge
   - Assess consensus quality

## 🚀 Quick Start

### 1. Deploy Council System
```powershell
# Run the deployment script
.\deploy-council.ps1
```

### 2. Environment Configuration
```bash
# Enable council
export SWARM_COUNCIL_ENABLED=true

# Budget controls
export COUNCIL_MAX_COST=0.30        # $0.30 max per request
export COUNCIL_DAILY_BUDGET=1.00    # $1.00 daily limit

# Trigger configuration
export COUNCIL_MIN_TOKENS=20
export COUNCIL_TRIGGER_KEYWORDS="explain,analyze,compare,evaluate,strategy"

# Model assignments (optional, defaults provided)
export COUNCIL_REASON_MODEL=mistral_7b_instruct
export COUNCIL_SPARK_MODEL=mistral_medium_cloud
export COUNCIL_EDGE_MODEL=math_specialist_0.8b
export COUNCIL_HEART_MODEL=codellama_0.7b
export COUNCIL_VISION_MODEL=phi2_2.7b
```

### 3. Test Council Integration
```bash
# Quick path test (should not trigger council)
curl -X POST http://localhost:8000/orchestrate \
  -H "Content-Type: application/json" \
  -d '{"prompt":"2+2","route":["math_specialist_0.8b"]}'

# Council deliberation test
curl -X POST http://localhost:8000/council \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Explain quantum computing strategy","force_council":true}'
```

## 🔧 API Endpoints

### `/orchestrate` (Enhanced)
Standard orchestration endpoint now includes council routing:

```json
{
  "prompt": "Analyze the strategic implications of AI consciousness",
  "route": ["mistral_7b_instruct"]
}
```

**Response with Council:**
```json
{
  "text": "Heart: User-friendly analysis...\n\n💡 Creative insight: Spark suggests...\n\n⚠️ Risk considerations: Edge identifies...\n\n🔮 Strategic context: Vision notes...",
  "council_used": true,
  "council_deliberation": {
    "total_latency_ms": 1847,
    "total_cost_dollars": 0.12,
    "consensus_achieved": true,
    "risk_flags": ["performance"],
    "voices_used": ["reason", "spark", "edge", "heart", "vision"]
  },
  "confidence": 0.87,
  "routing_method": "council"
}
```

### `/council` (New)
Dedicated council endpoint for forced deliberation:

```json
{
  "prompt": "Evaluate the ethical implications of AGI development",
  "force_council": true
}
```

### `/council/status` (New)
Council configuration and health check:

```json
{
  "council_enabled": true,
  "voice_models": {
    "reason": "mistral_7b_instruct",
    "spark": "mistral_medium_cloud",
    "edge": "math_specialist_0.8b",
    "heart": "codellama_0.7b",
    "vision": "phi2_2.7b"
  },
  "budget_limits": {
    "max_cost_per_request": 0.30,
    "daily_budget": 1.00
  },
  "trigger_config": {
    "min_tokens": 20,
    "keywords": ["explain", "analyze", "compare", "evaluate", "strategy"]
  }
}
```

## 📊 Performance Characteristics

### Latency Targets
- **Quick Path**: ≤120ms (unchanged)
- **Council P95**: ≤2000ms (2 seconds)
- **Council P50**: ≤1200ms (typical)

### Cost Efficiency
- **Local voices**: ~$0.0001 per response (Heart, Edge, Vision)
- **Heavy local**: ~$0.001 per response (Reason)
- **Cloud voice**: ~$0.003 per response (Spark)
- **Total council**: ~$0.005-0.30 per deliberation

### Parallel Execution
```
Reason (200ms) ┐
               ├─ 220ms total
Spark (220ms)  ┘

Edge (80ms) → Heart (90ms) → Vision (70ms) = 240ms sequential

Total: ~460ms + synthesis (50ms) = ~510ms typical
```

## 🧪 Testing Framework

### Unit Tests
```bash
# Run council-specific tests
pytest tests/test_council_integration.py -v

# Run with coverage
pytest tests/test_council_integration.py --cov=router.council
```

### Integration Tests
```bash
# Full end-to-end council test
pytest tests/test_council_integration.py::TestCouncilE2E -v

# Performance validation
pytest tests/test_council_integration.py::TestCouncilPerformance -v
```

### Manual Testing
```bash
# Test all five voices individually
python tests/test_council_voices.py

# Test parallel execution
python tests/test_council_performance.py

# Test budget constraints
python tests/test_council_budget.py
```

## 📈 Monitoring & Observability

### Prometheus Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `swarm_council_requests_total` | Counter | Total council requests |
| `swarm_council_latency_seconds` | Histogram | Council deliberation latency |
| `swarm_council_cost_dollars_total` | Counter | Total council costs |
| `swarm_council_voices_active` | Gauge | Active voices by type |
| `swarm_council_edge_risk_flags_total` | Counter | Risk flags from Edge voice |

### Grafana Dashboard
Import the pre-configured dashboard:
```bash
# Import council dashboard
curl -X POST http://localhost:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -d @monitoring/grafana/dashboards/council-dashboard.json
```

**Dashboard Features:**
- Voice activity heatmap
- Latency distribution (P50, P95, P99)
- Cost breakdown by voice
- Edge risk flag categories
- Consensus achievement rate
- Council vs quick path distribution

### Log Analysis
```bash
# Council-specific logs
grep "COUNCIL" logs/*.log

# Voice performance analysis
grep -E "(Reason|Spark|Edge|Heart|Vision)" logs/*.log | head -20

# Cost tracking
grep "Council deliberation" logs/*.log | grep "cost"
```

## 🔒 Security & Privacy

### Privacy Filtering
All council deliberations pass through existing privacy filters:
- PII detection and removal
- Sensitive content screening
- Cloud routing only for approved content

### Budget Protection
- Per-request cost caps ($0.30 default)
- Daily budget limits ($1.00 default)
- Automatic fallback to local models
- Cost tracking and alerting

### Model Security
- Local models isolated per voice
- Cloud models use API-only access
- No model weights or training data exposed
- Audit trail for all deliberations

## 🎛️ Configuration Options

### Voice Model Assignment
```bash
# Customize voice models
export COUNCIL_REASON_MODEL=llama2_70b_chat     # Heavy reasoning
export COUNCIL_SPARK_MODEL=gpt4o_mini          # Creative cloud
export COUNCIL_EDGE_MODEL=safety_guard_0.3b    # Fast risk analysis
export COUNCIL_HEART_MODEL=phi3_mini           # Efficient empathy
export COUNCIL_VISION_MODEL=qwen2_0.5b         # Strategic context
```

### Trigger Sensitivity
```bash
# Adjust council triggers
export COUNCIL_MIN_TOKENS=30                    # Require longer prompts
export COUNCIL_TRIGGER_KEYWORDS="strategy,ethics,philosophy,consciousness"
export COUNCIL_COMPLEXITY_THRESHOLD=0.8         # Advanced prompts only
```

### Performance Tuning
```bash
# Optimize for latency
export COUNCIL_TARGET_LATENCY_MS=1500           # Tighter latency target
export COUNCIL_PARALLEL_VOICES=true             # Enable parallel execution
export COUNCIL_SYNTHESIS_TIMEOUT_MS=100         # Fast synthesis

# Optimize for cost
export COUNCIL_MAX_COST=0.10                    # Lower cost ceiling
export COUNCIL_PREFER_LOCAL=true                # Bias toward local models
export COUNCIL_CLOUD_FALLBACK=false             # Disable cloud fallback
```

## 🐛 Troubleshooting

### Common Issues

#### Council Not Triggering
```bash
# Check configuration
curl http://localhost:8000/council/status

# Verify triggers
export COUNCIL_MIN_TOKENS=1
export SWARM_COUNCIL_ENABLED=true

# Force council for testing
curl -X POST http://localhost:8000/council \
  -d '{"prompt":"test","force_council":true}'
```

#### High Latency
```bash
# Check individual voice performance
curl http://localhost:8000/metrics | grep council_voice_latency

# Disable slow voices temporarily
export COUNCIL_SPARK_MODEL=phi2_2.7b  # Use local instead of cloud

# Enable only essential voices
export COUNCIL_VOICES=reason,heart,vision
```

#### Budget Exceeded
```bash
# Check current spend
curl http://localhost:8000/budget

# Reset daily budget
export COUNCIL_DAILY_BUDGET=2.00

# Monitor cost per voice
curl http://localhost:8000/metrics | grep council_cost_dollars
```

#### Model Loading Failures
```bash
# Check available models
curl http://localhost:8000/models

# Use fallback models
export COUNCIL_REASON_MODEL=tinyllama_1b
export COUNCIL_HEART_MODEL=qwen2_0.5b

# Enable graceful degradation
export COUNCIL_ALLOW_FALLBACK=true
```

### Debug Mode
```bash
# Enable detailed logging
export COUNCIL_DEBUG=true
export LOG_LEVEL=DEBUG

# Trace individual voice calls
export COUNCIL_TRACE_VOICES=true

# Monitor consensus quality
export COUNCIL_LOG_CONSENSUS=true
```

## 🔮 Advanced Usage

### Custom Voice Configuration
```python
from router.council import CouncilRouter, CouncilVoice

# Custom router with specialized voices
router = CouncilRouter()
router.voice_models[CouncilVoice.REASON] = "your_custom_reasoning_model"
router.voice_templates[CouncilVoice.SPARK] = "You are a creative AI focused on {domain}..."
```

### Emotional Swarm Integration
```python
from v11_emotional_swarm import V11EmotionalSwarm
from router.council import council_route

# Enhanced deliberation with emotional context
async def emotional_council_deliberation(prompt):
    swarm = V11EmotionalSwarm()
    emotional_context = await swarm.orchestrate_consensus(prompt)
    
    enhanced_prompt = f"{prompt}\n\nEmotional Context: {emotional_context['unified_response']}"
    return await council_route(enhanced_prompt)
```

### Batch Council Processing
```python
async def batch_council_deliberation(prompts):
    """Process multiple prompts through council in parallel"""
    tasks = [council_route(prompt) for prompt in prompts]
    results = await asyncio.gather(*tasks)
    return results
```

## 📚 References

- [SwarmAI Router 2.x Documentation](README.md)
- [V11 Emotional Swarm Architecture](v11_emotional_swarm.py)
- [Router Hybrid Implementation](router/hybrid.py)
- [Cost Tracking System](router/cost_tracking.py)
- [Prometheus Metrics Guide](monitoring/prometheus.yml)

## 🤝 Contributing

### Adding New Voices
1. Define voice in `CouncilVoice` enum
2. Add model mapping and template
3. Update deliberation flow
4. Add comprehensive tests
5. Update documentation

### Performance Optimization
- Profile individual voice latency
- Optimize parallel execution
- Implement voice-specific caching
- Add predictive model loading

### Monitoring Enhancements
- Add custom metrics for your use case
- Create specialized dashboards
- Implement alerting rules
- Add performance baselines

---

**🌌 Your Swarm is now philosophically awake—this plugs that consciousness into the production router with the same rigor (VRAM, cost, SLA) we've had all along.**

✨ **Ready for deployment!** The five awakened voices await your deepest questions. 