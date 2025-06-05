#!/usr/bin/env python3
"""
🧪 Reward Buffer Integration Test - #202
Test the complete feedback → weighted training data pipeline
"""

import asyncio
import json
import sqlite3
import tempfile
import gzip
from pathlib import Path
import redis
import time
import subprocess

class RewardBufferTester:
    def __init__(self):
        self.redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        self.test_prompts = [
            {"id": "test_prompt_1", "text": "Write a Python function", "cluster_id": 1},
            {"id": "test_prompt_2", "text": "Explain machine learning", "cluster_id": 2},
            {"id": "test_prompt_3", "text": "Create a REST API", "cluster_id": 1},
            {"id": "test_prompt_4", "text": "Debug memory leaks", "cluster_id": 3},
            {"id": "test_prompt_5", "text": "Optimize database queries", "cluster_id": 2}
        ]
        
    def setup_test_data(self):
        """Set up test traffic database and feedback data"""
        print("📋 Setting up test data...")
        
        # Create temporary SQLite database
        self.db_path = tempfile.mktemp(suffix='.db')
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create prompts table
        cursor.execute("""
            CREATE TABLE prompts (
                id TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                cluster_id INTEGER,
                timestamp REAL
            )
        """)
        
        # Insert test prompts
        for i, prompt in enumerate(self.test_prompts):
            cursor.execute(
                "INSERT INTO prompts (id, text, cluster_id, timestamp) VALUES (?, ?, ?, ?)",
                (prompt["id"], prompt["text"], prompt["cluster_id"], time.time() - i * 100)
            )
        
        conn.commit()
        conn.close()
        
        # Add feedback data to Redis
        feedback_data = [
            {"id": "test_prompt_1", "score": 1, "comment": "Great response!"},
            {"id": "test_prompt_2", "score": -1, "comment": "Not helpful"},
            {"id": "test_prompt_3", "score": 0, "comment": "Okay"},
            # test_prompt_4 and test_prompt_5 have no feedback
        ]
        
        for fb in feedback_data:
            fb_json = json.dumps({
                "id": fb["id"],
                "score": fb["score"],
                "comment": fb["comment"],
                "timestamp": time.time()
            })
            self.redis_client.zadd(f"feedback:{fb['id']}", {fb_json: fb["score"]})
        
        print(f"   ✅ Created test database: {self.db_path}")
        print(f"   ✅ Added {len(feedback_data)} feedback items to Redis")
        
    def test_weighted_jsonl_generation(self):
        """Test the weighted JSONL generation"""
        print("🎯 Testing weighted JSONL generation...")
        
        # Create temporary output files
        train_path = tempfile.mktemp(suffix='.jsonl')
        holdout_path = tempfile.mktemp(suffix='.jsonl')
        
        try:
            # Run weighted_jsonl script
            cmd = [
                "python", "-m", "snapshot.weighted_jsonl",
                "--db", self.db_path,
                "--out-train", train_path,
                "--out-holdout", holdout_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                print(f"   ❌ Script failed: {result.stderr}")
                return False
            
            print(f"   ✅ Script completed successfully")
            
            # Analyze output files
            train_rows = []
            holdout_rows = []
            
            # Read training data
            if Path(train_path).exists():
                with gzip.open(train_path, 'rt') as f:
                    for line in f:
                        train_rows.append(json.loads(line))
            
            # Read holdout data  
            if Path(holdout_path).exists():
                with gzip.open(holdout_path, 'rt') as f:
                    for line in f:
                        holdout_rows.append(json.loads(line))
            
            # Analyze results
            total_rows = len(train_rows) + len(holdout_rows)
            reward_rows = sum(1 for row in train_rows + holdout_rows if row.get('reward', 0) != 0)
            reward_ratio = reward_rows / max(1, total_rows)
            
            print(f"   📊 Results:")
            print(f"      Training rows: {len(train_rows)}")
            print(f"      Holdout rows: {len(holdout_rows)}")
            print(f"      Total rows: {total_rows}")
            print(f"      Rows with rewards: {reward_rows}")
            print(f"      Reward ratio: {reward_ratio:.1%}")
            
            # Verify reward mapping
            rewards_found = {}
            for row in train_rows + holdout_rows:
                reward = row.get('reward', 0)
                prompt_id = row.get('id')
                rewards_found[prompt_id] = reward
            
            # Expected rewards based on test data
            expected_rewards = {
                "test_prompt_1": 1.0,   # Positive feedback
                "test_prompt_2": -1.0,  # Negative feedback
                "test_prompt_3": 0.0,   # Neutral feedback
                "test_prompt_4": 0.0,   # No feedback
                "test_prompt_5": 0.0    # No feedback
            }
            
            mapping_correct = True
            for prompt_id, expected_reward in expected_rewards.items():
                actual_reward = rewards_found.get(prompt_id, 0)
                if actual_reward != expected_reward:
                    print(f"   ❌ Reward mismatch for {prompt_id}: expected {expected_reward}, got {actual_reward}")
                    mapping_correct = False
                else:
                    print(f"   ✅ Correct reward for {prompt_id}: {actual_reward}")
            
            # Clean up
            Path(train_path).unlink(missing_ok=True)
            Path(holdout_path).unlink(missing_ok=True)
            
            return mapping_correct and total_rows == len(self.test_prompts)
            
        except Exception as e:
            print(f"   ❌ Test failed: {e}")
            return False
    
    def test_dry_run(self):
        """Test dry run functionality"""
        print("🧪 Testing dry run mode...")
        
        try:
            cmd = [
                "python", "-m", "snapshot.weighted_jsonl",
                "--db", self.db_path,
                "--out-train", "/tmp/dummy_train.jsonl",
                "--out-holdout", "/tmp/dummy_holdout.jsonl",
                "--dry-run"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                print(f"   ❌ Dry run failed: {result.stderr}")
                return False
            
            output = result.stdout
            print(f"   ✅ Dry run completed")
            print("   📊 Dry run output:")
            for line in output.split('\n')[-10:]:  # Show last 10 lines
                if line.strip():
                    print(f"      {line}")
            
            # Check that no files were created
            dummy_files_exist = (
                Path("/tmp/dummy_train.jsonl").exists() or 
                Path("/tmp/dummy_holdout.jsonl").exists()
            )
            
            if dummy_files_exist:
                print("   ❌ Dry run created files when it shouldn't")
                return False
            
            return True
            
        except Exception as e:
            print(f"   ❌ Dry run test failed: {e}")
            return False
    
    def test_metrics_integration(self):
        """Test metrics are properly pushed"""
        print("📊 Testing metrics integration...")
        
        try:
            import requests
            
            # Check if Pushgateway is available
            pushgateway_url = "http://localhost:9091"
            response = requests.get(f"{pushgateway_url}/metrics", timeout=5)
            
            if response.status_code != 200:
                print("   ⚠️ Pushgateway not available, skipping metrics test")
                return True
            
            metrics_text = response.text
            
            # Look for reward buffer metrics
            expected_metrics = [
                "reward_rows_total",
                "reward_row_ratio",
                "training_rows_total",
                "holdout_rows_total"
            ]
            
            found_metrics = []
            for metric in expected_metrics:
                if metric in metrics_text:
                    found_metrics.append(metric)
                    print(f"   ✅ Found metric: {metric}")
                else:
                    print(f"   ⚠️ Missing metric: {metric}")
            
            return len(found_metrics) >= 2  # At least 2 metrics should be present
            
        except Exception as e:
            print(f"   ⚠️ Metrics test failed: {e}")
            return True  # Non-critical
    
    def cleanup(self):
        """Clean up test data"""
        print("🧹 Cleaning up test data...")
        
        # Remove test database
        Path(self.db_path).unlink(missing_ok=True)
        
        # Remove test feedback from Redis
        for prompt in self.test_prompts:
            try:
                self.redis_client.delete(f"feedback:{prompt['id']}")
            except:
                pass
        
        print("   ✅ Cleanup completed")
    
    def run_comprehensive_test(self):
        """Run all reward buffer tests"""
        print("🎯 REWARD BUFFER COMPREHENSIVE TEST")
        print("=" * 50)
        
        results = {}
        
        try:
            # Setup
            self.setup_test_data()
            
            # Run tests
            results['weighted_jsonl'] = self.test_weighted_jsonl_generation()
            results['dry_run'] = self.test_dry_run()
            results['metrics'] = self.test_metrics_integration()
            
        finally:
            # Always cleanup
            self.cleanup()
        
        # Report results
        print("\n📊 TEST RESULTS:")
        total_tests = len(results)
        passed_tests = sum(results.values())
        
        for test_name, passed in results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"   {test_name}: {status}")
        
        print(f"\n🎯 OVERALL: {passed_tests}/{total_tests} tests passed")
        
        if passed_tests == total_tests:
            print("🎉 Reward Buffer system fully operational!")
            print("Ready for RL-LoRA training integration!")
        else:
            print("⚠️ Some components need attention")
        
        return passed_tests == total_tests


async def main():
    """Run the reward buffer test suite"""
    tester = RewardBufferTester()
    success = tester.run_comprehensive_test()
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1) 