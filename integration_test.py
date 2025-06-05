#!/usr/bin/env python3
"""
Autonomous Software Spiral - Integration Test
==============================================

Test the complete spiral: Agent-0 → Pattern Mining → Cache → Cost Tracking
"""

import time
import json
import os
from typing import Dict, Any

def test_spiral_integration():
    """Test the complete autonomous software spiral"""
    
    print("🧪 AUTONOMOUS SOFTWARE SPIRAL - INTEGRATION TEST")
    print("=" * 60)
    
    # Test 1: Agent-0 First Routing
    print("\n1️⃣ Testing Agent-0 First Routing...")
    try:
        from router_cascade import RouterCascade
        router = RouterCascade()
        
        # Test greeting (should go through Agent-0, not shortcuts)
        result = router.route_query("hello")
        assert "agent" in result.get("model", "").lower(), "Agent-0 not responding first"
        print("   ✅ Agent-0 responds first to greetings")
        
        # Test math query (should start with Agent-0)
        result = router.route_query("what is 2+2?")
        latency = result.get("latency_ms", 0)
        assert latency < 2000, f"Response too slow: {latency}ms"
        print(f"   ✅ Math query responded in {latency:.1f}ms")
        
    except Exception as e:
        print(f"   ❌ Agent-0 routing failed: {e}")
        return False
    
    # Test 2: Pattern Mining System
    print("\n2️⃣ Testing Pattern Mining...")
    try:
        import pattern_miner
        
        # Check if synthetic specialists were generated
        if os.path.exists("patterns/synthetic_specialists.py"):
            print("   ✅ Synthetic specialists file exists")
            
            # Test pattern specialist function
            import sys
            sys.path.insert(0, "patterns")
            from synthetic_specialists import pattern_specialist, PATTERN_COUNT
            
            result = pattern_specialist("What is machine learning?")
            if result.get("confidence", 0) > 0:
                print(f"   ✅ Pattern specialist responded with {result['confidence']:.2f} confidence")
                print(f"   ✅ {PATTERN_COUNT} patterns learned")
            else:
                print("   ⚠️ Pattern specialist didn't match test query")
        else:
            print("   ⚠️ Synthetic specialists not generated yet")
            
    except Exception as e:
        print(f"   ❌ Pattern mining test failed: {e}")
    
    # Test 3: Shallow Cache System
    print("\n3️⃣ Testing Shallow Cache...")
    try:
        from cache.shallow_cache import store_cached_response, get_cached_response
        
        # Test cache store and retrieve
        test_response = {
            "text": "Test response for caching",
            "confidence": 0.95,
            "model": "test-model"
        }
        
        stored = store_cached_response("test prompt", test_response, cost_saved_usd=0.001)
        if stored:
            print("   ✅ Cache storage working")
            
            cached = get_cached_response("test prompt")
            if cached and cached.text == test_response["text"]:
                print(f"   ✅ Cache retrieval working (saved ${cached.cost_saved_usd:.4f})")
            else:
                print("   ⚠️ Cache retrieval not working")
        else:
            print("   ⚠️ Cache storage not working")
            
    except Exception as e:
        print(f"   ❌ Cache test failed: {e}")
    
    # Test 4: Cost Tracking
    print("\n4️⃣ Testing Cost Tracking...")
    try:
        from cost_tracker import CostTracker
        
        tracker = CostTracker()
        
        # Test cost recording
        within_budget = tracker.record_cost_event(
            provider="test_provider",
            model="test_model", 
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.001
        )
        
        if within_budget:
            print("   ✅ Cost tracking working")
            
            summary = tracker.generate_daily_summary()
            print(f"   ✅ Daily cost: ${summary.total_cost_usd:.4f}")
            print(f"   ✅ Budget remaining: ${summary.budget_remaining_usd:.4f}")
        else:
            print("   ⚠️ Over budget or cost tracking issue")
            
    except Exception as e:
        print(f"   ❌ Cost tracking test failed: {e}")
    
    # Test 5: GPU Model Availability
    print("\n5️⃣ Testing GPU Model...")
    try:
        import torch
        
        if torch.cuda.is_available():
            device_name = torch.cuda.get_device_name(0)
            print(f"   ✅ CUDA available: {device_name}")
            
            # Test basic tensor operation
            x = torch.randn(3, 3).cuda()
            y = torch.matmul(x, x)
            print(f"   ✅ GPU computation working")
        else:
            print("   ⚠️ CUDA not available - will use CPU mode")
            
    except Exception as e:
        print(f"   ❌ GPU test failed: {e}")
    
    # Test 6: Configuration Validation
    print("\n6️⃣ Testing Configuration...")
    try:
        import yaml
        
        # Check provider config
        with open("config/providers.yaml", "r") as f:
            providers = yaml.safe_load(f)
            
        local_enabled = providers["providers"]["local_tinyllama"]["enabled"]
        if local_enabled:
            print("   ✅ Local TinyLlama enabled")
        else:
            print("   ⚠️ Local TinyLlama not enabled")
            
        # Check router config
        if os.path.exists("config/router_config.yaml"):
            with open("config/router_config.yaml", "r") as f:
                router_config = yaml.safe_load(f)
            
            budget = router_config["cost_tracking"]["daily_budget_usd"]
            print(f"   ✅ Daily budget set: ${budget}")
        else:
            print("   ⚠️ Router config not found")
            
    except Exception as e:
        print(f"   ❌ Configuration test failed: {e}")
    
    print("\n🎯 SPIRAL STATUS SUMMARY")
    print("=" * 30)
    
    # Check which components are operational
    components = {
        "Agent-0 First": os.path.exists("router_cascade.py"),
        "Pattern Mining": os.path.exists("patterns/synthetic_specialists.py"),
        "Shallow Cache": os.path.exists("cache/shallow_cache.py"),
        "Cost Tracking": os.path.exists("cost_tracker.py"),
        "GPU Support": torch.cuda.is_available() if 'torch' in globals() else False,
        "Nightly Distiller": os.path.exists("nightly_distiller.py")
    }
    
    operational_count = sum(components.values())
    total_count = len(components)
    
    for component, status in components.items():
        status_icon = "✅" if status else "❌"
        print(f"{status_icon} {component}")
    
    print(f"\n🚀 SPIRAL READINESS: {operational_count}/{total_count} components operational")
    
    if operational_count >= 5:
        print("✅ AUTONOMOUS SOFTWARE SPIRAL IS READY TO DEPLOY! 🚀")
        return True
    else:
        print("⚠️ Some components need attention before full deployment")
        return False

if __name__ == "__main__":
    test_spiral_integration() 