# -*- coding: utf-8 -*-
"""
Prometheus metrics exporter for SwarmAI monitoring
Exports metrics required by the Grafana dashboard
"""

import time
import psutil
import subprocess
from prometheus_client import start_http_server, Gauge, Counter, Histogram
from pathlib import Path

# Metrics for Grafana dashboard
vram_used_bytes = Gauge('swarm_vram_used_bytes', 'VRAM usage in bytes', ['gpu'])
host_ram_used_bytes = Gauge('swarm_host_ram_used_bytes', 'Host RAM usage in bytes')
gpu_temp_celsius = Gauge('swarm_gpu_temp_celsius', 'GPU temperature in Celsius', ['gpu'])
cuda_fragmentation_events = Counter('swarm_cuda_fragmentation_events_total', 'CUDA memory fragmentation events')
model_loaded = Gauge('swarm_model_loaded', 'Model loading status', ['model', 'profile'])

# Router metrics
router_requests = Counter('swarm_router_requests_total', 'Total router requests')
router_request_latency = Histogram('swarm_router_request_latency', 'Router request latency in seconds')

# Streaming metrics for first-token latency monitoring
stream_first_token_latency = Histogram(
    'swarm_stream_first_token_latency_seconds', 
    'First token latency for streaming requests',
    buckets=(0.025, 0.050, 0.080, 0.100, 0.200, 0.500, 1.0, float('inf'))  # 25ms, 50ms, 80ms, 100ms, 200ms buckets
)

# Registry singleton metrics (Ticket #121)
registry_singleton_violation_total = Counter('registry_singleton_violation_total', 'Registry singleton violations prevented')
registry_duplicate_push_total = Counter('registry_duplicate_push_total', 'Legacy duplicate push metric (deprecated)')  # Legacy metric maintained for compatibility

def get_gpu_metrics():
    """Get GPU metrics using nvidia-smi"""
    try:
        result = subprocess.run([
            'nvidia-smi', 
            '--query-gpu=memory.used,temperature.gpu', 
            '--format=csv,noheader,nounits'
        ], capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0:
            line = result.stdout.strip()
            if line:
                memory_mb, temp = line.split(', ')
                return int(memory_mb) * 1024 * 1024, int(temp)  # Convert MB to bytes
    except Exception as e:
        print(f"GPU metrics error: {e}")
    return 0, 0

def update_system_metrics():
    """Update system-level metrics"""
    # Host RAM
    ram = psutil.virtual_memory()
    host_ram_used_bytes.set(ram.used)
    
    # GPU metrics
    vram_bytes, temp = get_gpu_metrics()
    if vram_bytes > 0:
        vram_used_bytes.labels(gpu='0').set(vram_bytes)
        gpu_temp_celsius.labels(gpu='0').set(temp)

def update_model_status():
    """Update model loading status from our deterministic loader"""
    try:
        # Check which models are loaded based on config
        import yaml
        config = yaml.safe_load(Path('config/models.yaml').read_text())
        
        # Simulate model loading status - in real implementation,
        # this would check actual model states
        profile = "rtx_4070"  # Could be environment variable
        strategy = config.get('loading_strategy', {}).get(profile, {})
        
        # Reset all models
        for category in ['gpu_heads_small', 'gpu_heads_medium', 'gpu_heads_large']:
            for model in config.get(category, []):
                model_loaded.labels(model=model['name'], profile=profile).set(0)
        
        # Mark loaded models (based on VRAM budget)
        # This is a simplified version - real implementation would track actual loads
        total_vram = 0
        limit = strategy.get('vram_limit_mb', 10500)
        
        for category in strategy.get('priority_order', []):
            for model in config.get(category, []):
                if total_vram + model['vram_mb'] <= limit:
                    model_loaded.labels(model=model['name'], profile=profile).set(1)
                    total_vram += model['vram_mb']
                else:
                    break
                    
    except Exception as e:
        print(f"Model status error: {e}")

def simulate_router_metrics():
    """Simulate router metrics - replace with real router integration"""
    import random
    
    # Simulate some requests
    if random.random() < 0.1:  # 10% chance
        router_requests.inc()
        
        # Simulate latency (higher when approaching fragmentation threshold)
        base_latency = 0.05  # 50ms base
        fragmentation_penalty = 0.02 if random.random() < 0.1 else 0  # Occasional spike
        latency = base_latency + fragmentation_penalty
        
        router_request_latency.observe(latency)
        
        # Occasionally trigger fragmentation event
        if fragmentation_penalty > 0:
            cuda_fragmentation_events.inc()

def main():
    """Main metrics collection loop"""
    # Start Prometheus metrics server
    start_http_server(8000)
    print("🔥 Prometheus metrics server started on port 8000")
    print("📊 Metrics available at: http://localhost:8000/metrics")
    print("🎯 Grafana dashboard ready for: swarm_* metrics")
    
    while True:
        try:
            update_system_metrics()
            update_model_status() 
            simulate_router_metrics()
            time.sleep(10)  # Update every 10 seconds
            
        except KeyboardInterrupt:
            print("\n🛑 Metrics exporter stopped")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main() 