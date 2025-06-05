#!/usr/bin/env python3
"""
🧪 Feedback System Integration Test - #201 Feedback-Ingest
Quick smoke test to verify feedback endpoints and Redis storage
"""

import requests
import json
import time
import redis
from datetime import datetime

def test_feedback_submission():
    """Test the feedback submission endpoint"""
    print("🎯 Testing feedback submission...")
    
    # Test data
    feedback_data = {
        "id": f"test_response_{int(time.time())}",
        "score": 1,
        "comment": "Great response! Very helpful."
    }
    
    try:
        # Submit feedback
        response = requests.post(
            "http://localhost:8001/api/feedback",
            json=feedback_data,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"   Status: {response.status_code}")
        if response.status_code == 202:
            result = response.json()
            print(f"   ✅ Feedback accepted: {result}")
            return True
        else:
            print(f"   ❌ Feedback failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ Request failed: {e}")
        return False

def test_feedback_stats():
    """Test the feedback stats endpoint"""
    print("📊 Testing feedback stats...")
    
    try:
        response = requests.get("http://localhost:8001/api/feedback/stats")
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            stats = response.json()
            print(f"   ✅ Stats retrieved:")
            print(f"      Total feedback: {stats.get('total_feedback', 0)}")
            print(f"      Positive: {stats.get('positive_count', 0)}")
            print(f"      Negative: {stats.get('negative_count', 0)}")
            print(f"      Neutral: {stats.get('neutral_count', 0)}")
            return True
        else:
            print(f"   ❌ Stats failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ Request failed: {e}")
        return False

def test_redis_storage():
    """Test direct Redis storage verification"""
    print("🗄️ Testing Redis storage...")
    
    try:
        # Connect to Redis
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        r.ping()
        
        # Check for feedback keys
        feedback_keys = r.keys("feedback:*")
        print(f"   ✅ Redis connected, found {len(feedback_keys)} feedback items")
        
        # Show sample feedback
        if feedback_keys:
            sample_key = feedback_keys[0]
            feedback_data = r.zrevrange(sample_key, 0, 0)
            if feedback_data:
                fb = json.loads(feedback_data[0])
                print(f"   📝 Sample feedback: ID={fb.get('id')}, Score={fb.get('score')}")
        
        return True
        
    except Exception as e:
        print(f"   ⚠️ Redis test failed: {e}")
        return False

def test_prometheus_metrics():
    """Test Prometheus metrics collection"""
    print("📊 Testing Prometheus metrics...")
    
    try:
        # Check pushgateway for feedback metrics
        response = requests.get("http://localhost:9091/metrics")
        if response.status_code == 200:
            metrics_text = response.text
            
            # Look for feedback metrics
            feedback_metrics = [
                "feedback_ingest_total",
                "feedback_score_total"
            ]
            
            found_metrics = []
            for metric in feedback_metrics:
                if metric in metrics_text:
                    found_metrics.append(metric)
            
            print(f"   ✅ Found metrics: {found_metrics}")
            return len(found_metrics) > 0
        else:
            print(f"   ⚠️ Pushgateway not available: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"   ⚠️ Metrics test failed: {e}")
        return False

def run_comprehensive_test():
    """Run all feedback system tests"""
    print("🎯 FEEDBACK SYSTEM INTEGRATION TEST")
    print("=" * 50)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()
    
    results = {}
    
    # Test feedback submission
    results['feedback_submission'] = test_feedback_submission()
    
    # Wait a moment for async processing
    time.sleep(1)
    
    # Test stats endpoint
    results['feedback_stats'] = test_feedback_stats()
    
    # Test Redis storage
    results['redis_storage'] = test_redis_storage()
    
    # Test metrics
    results['prometheus_metrics'] = test_prometheus_metrics()
    
    # Summary
    print("\n📋 TEST RESULTS:")
    total_tests = len(results)
    passed_tests = sum(results.values())
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {test_name}: {status}")
    
    print(f"\n🎯 OVERALL: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 Feedback system fully operational!")
        print("Ready for RL-LoRA data collection!")
    else:
        print("⚠️ Some components need attention")
    
    return passed_tests == total_tests

if __name__ == "__main__":
    success = run_comprehensive_test()
    exit(0 if success else 1) 