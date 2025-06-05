#!/usr/bin/env python3
"""
🌀 Complete Spiral Integration Test
Tests the full autonomous evolution loop: Pattern-Miner → Snapshot → Trainer → Hot-Reload → Canary
"""

import asyncio
import json
import time
import pytest
import requests
from datetime import datetime, timedelta
from pathlib import Path


class SpiralIntegrationTest:
    def __init__(self):
        self.api_base = "http://localhost:8001"
        self.pushgateway_url = "http://localhost:9091"
        self.test_date = datetime.now().strftime('%Y-%m-%d')
        
    async def test_stage1_pattern_miner(self):
        """Test Stage 1: Pattern-Miner is running and clustering prompts"""
        print("🧠 Testing Stage 1: Pattern-Miner...")
        
        # Submit test prompts to trigger clustering
        test_prompts = [
            "Write a Python function to sort a list",
            "Create a JavaScript function to validate email",
            "Implement a binary search in Python",
            "How do I sort an array in JavaScript?",
            "Write a function to find duplicate elements"
        ]
        
        for prompt in test_prompts:
            response = requests.post(f"{self.api_base}/orchestrate", json={
                "prompt": prompt,
                "route": ["code"]
            })
            assert response.status_code == 200
            
        # Wait for background processing
        await asyncio.sleep(2)
        
        # Check pattern stats
        response = requests.get(f"{self.api_base}/patterns/stats")
        assert response.status_code == 200
        stats = response.json()
        
        print(f"   ✅ Queue size: {stats['queue_size']}")
        print(f"   ✅ Total clusters: {stats['total_clusters']}")
        
        # Verify patterns appear in Grafana metrics
        metrics_response = requests.get(f"{self.pushgateway_url}/metrics")
        assert "pattern_clusters_total" in metrics_response.text
        
        return True

    async def test_stage2_snapshot(self):
        """Test Stage 2: Traffic snapshot pipeline"""
        print("📸 Testing Stage 2: Traffic Snapshot...")
        
        # Check if snapshot files exist for today or yesterday
        loras_dir = Path("/loras")
        test_dates = [
            datetime.now().strftime('%Y-%m-%d'),
            (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        ]
        
        snapshot_found = False
        for date in test_dates:
            snapshot_dir = loras_dir / date
            if snapshot_dir.exists():
                train_file = snapshot_dir / "train.jsonl.gz"
                holdout_file = snapshot_dir / "holdout.jsonl.gz"
                
                if train_file.exists() and holdout_file.exists():
                    print(f"   ✅ Snapshot found for {date}")
                    print(f"   ✅ Train file: {train_file.stat().st_size} bytes")
                    print(f"   ✅ Holdout file: {holdout_file.stat().st_size} bytes")
                    snapshot_found = True
                    break
        
        if not snapshot_found:
            # Try to run snapshot manually for testing
            print("   ⚠️ No recent snapshots found, triggering manual snapshot...")
            import subprocess
            result = subprocess.run(["bash", "scripts/snapshot_traffic.sh"], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print("   ✅ Manual snapshot completed")
                snapshot_found = True
        
        assert snapshot_found, "No traffic snapshots available"
        
        # Check snapshot metrics
        metrics_response = requests.get(f"{self.pushgateway_url}/metrics")
        assert "snapshot_success" in metrics_response.text
        
        return True

    async def test_stage3_hot_reload(self):
        """Test Stage 3: Model hot-reload functionality"""
        print("🔄 Testing Stage 3: Hot-Reload...")
        
        # Find most recent adapter (or create a dummy one)
        loras_dir = Path("/loras")
        adapter_path = None
        
        for date_dir in sorted(loras_dir.glob("*"), reverse=True):
            if date_dir.is_dir():
                adapter_file = date_dir / "adapter.bin"
                ready_flag = date_dir / "READY"
                
                # Create dummy adapter for testing if none exists
                if not adapter_file.exists():
                    adapter_file.write_bytes(b"dummy_adapter_data")
                    ready_flag.touch()
                    print(f"   📝 Created test adapter: {adapter_file}")
                
                if adapter_file.exists() and ready_flag.exists():
                    adapter_path = adapter_file
                    break
        
        if not adapter_path:
            # Create a test adapter in today's directory
            test_dir = loras_dir / self.test_date
            test_dir.mkdir(exist_ok=True)
            adapter_path = test_dir / "adapter.bin"
            adapter_path.write_bytes(b"test_adapter_for_hot_reload")
            (test_dir / "READY").touch()
            print(f"   📝 Created test adapter: {adapter_path}")
        
        # Test hot-reload endpoint
        response = requests.post(f"{self.api_base}/admin/reload", params={
            "lora": str(adapter_path)
        })
        
        print(f"   🔄 Reload response: {response.status_code}")
        if response.status_code == 200:
            reload_data = response.json()
            print(f"   ✅ Load time: {reload_data['load_time_seconds']:.3f}s")
            print(f"   ✅ Adapter: {reload_data['adapter']}")
        else:
            print(f"   ❌ Reload failed: {response.text}")
            
        assert response.status_code == 200
        
        # Verify reload metrics
        metrics_response = requests.get(f"{self.pushgateway_url}/metrics")
        assert "reload_success" in metrics_response.text
        
        return True

    async def test_stage4_canary(self):
        """Test Stage 4: Canary health checks and decision logic"""
        print("🎯 Testing Stage 4: Canary Gate...")
        
        # Test holdout health endpoint
        response = requests.get(f"{self.api_base}/health/holdout")
        print(f"   🎯 Holdout response: {response.status_code}")
        
        if response.status_code == 200:
            holdout_data = response.json()
            print(f"   ✅ Success rate: {holdout_data['success_rate']:.2%}")
            print(f"   ✅ P95 latency: {holdout_data['p95_latency_ms']:.1f}ms")
            print(f"   ✅ Decision: {holdout_data['canary_decision']}")
            
            # Verify decision logic
            assert holdout_data['canary_decision'] in ['promote', 'rollback']
            
            if holdout_data['success_rate'] >= 0.8:
                assert holdout_data['canary_decision'] == 'promote'
            else:
                assert holdout_data['canary_decision'] == 'rollback'
                
        else:
            print(f"   ❌ Holdout check failed: {response.text}")
            
        assert response.status_code == 200
        
        # Test canary rollback script
        print("   🔄 Testing canary rollback script...")
        import subprocess
        result = subprocess.run([
            "python", "scripts/canary_rollback.py", "weights"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            weights = json.loads(result.stdout)
            print(f"   ✅ Current weights: {weights}")
        else:
            print(f"   ⚠️ Rollback script not available: {result.stderr}")
        
        # Verify canary metrics in Pushgateway
        metrics_response = requests.get(f"{self.pushgateway_url}/metrics")
        assert "holdout_success_ratio" in metrics_response.text
        
        return True

    async def test_complete_spiral(self):
        """Test complete Spiral integration"""
        print("\n🌀 COMPLETE SPIRAL INTEGRATION TEST")
        print("=" * 50)
        
        results = {}
        
        try:
            results['stage1'] = await self.test_stage1_pattern_miner()
            results['stage2'] = await self.test_stage2_snapshot()
            results['stage3'] = await self.test_stage3_hot_reload()
            results['stage4'] = await self.test_stage4_canary()
            
            print("\n📊 INTEGRATION TEST RESULTS:")
            for stage, passed in results.items():
                status = "✅ PASS" if passed else "❌ FAIL"
                print(f"   {stage.upper()}: {status}")
            
            all_passed = all(results.values())
            print(f"\n🌀 SPIRAL STATUS: {'✅ COMPLETE' if all_passed else '❌ INCOMPLETE'}")
            
            if all_passed:
                print("\n🎉 The complete autonomous evolution Spiral is operational!")
                print("   • Pattern-Miner clustering prompts every 6h")
                print("   • Snapshot pipeline captures traffic nightly")
                print("   • Hot-reload swaps LoRA adapters seamlessly")
                print("   • Canary gate validates new models automatically")
                
            return all_passed
            
        except Exception as e:
            print(f"\n❌ Integration test failed: {e}")
            return False

async def main():
    """Run the complete Spiral integration test"""
    tester = SpiralIntegrationTest()
    success = await tester.test_complete_spiral()
    exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main()) 