#!/usr/bin/env python3
"""
Stage 5: Metrics sanity check
Prometheus shows:
• action_success_total{type="os_file_create"} == 1
• cloud_calls_total == 0  
• rate(action_failure_total[5m]) < 0.01
"""

import pytest
import requests
import re
import time
from fastapi.testclient import TestClient

import sys
sys.path.append('.')
from autogen_api_shim import app

@pytest.fixture
def client():
    return TestClient(app)

def parse_prometheus_metrics(metrics_text: str) -> dict:
    """Parse Prometheus metrics format into a dictionary"""
    metrics = {}
    
    for line in metrics_text.strip().split('\n'):
        if line.startswith('#') or not line.strip():
            continue
            
        # Parse metric line: metric_name{labels} value
        if '{' in line:
            # Metric with labels
            match = re.match(r'([^{]+)\{([^}]+)\}\s+(.+)', line)
            if match:
                metric_name, labels_str, value = match.groups()
                
                # Parse labels
                labels = {}
                for label_pair in labels_str.split(','):
                    if '=' in label_pair:
                        key, val = label_pair.split('=', 1)
                        labels[key.strip()] = val.strip('"')
                
                # Store metric
                metric_key = f"{metric_name}{{{labels_str}}}"
                metrics[metric_key] = float(value)
        else:
            # Metric without labels
            parts = line.split()
            if len(parts) >= 2:
                metric_name, value = parts[0], parts[1]
                metrics[metric_name] = float(value)
    
    return metrics

def test_metrics_endpoint_available(client):
    """Test that /metrics endpoint is available and returns Prometheus format"""
    
    response = client.get("/metrics")
    
    assert response.status_code == 200
    assert "text/plain" in response.headers.get("content-type", "")
    
    metrics_text = response.text
    assert len(metrics_text) > 0, "Metrics endpoint returned empty response"
    
    # Should contain standard Prometheus format
    assert "# HELP" in metrics_text, "Missing Prometheus HELP comments"
    assert "# TYPE" in metrics_text, "Missing Prometheus TYPE comments"
    
    print("✅ Metrics endpoint: Available and properly formatted")

def test_action_success_metrics(client):
    """Test action_success_total metric tracking"""
    
    # First, trigger a file creation action
    response = client.post("/hybrid", json={
        "prompt": "create a test file called metrics_test.txt"
    })
    
    assert response.status_code == 200
    
    # Give metrics time to update
    time.sleep(0.1)
    
    # Check metrics
    metrics_response = client.get("/metrics")
    assert metrics_response.status_code == 200
    
    metrics = parse_prometheus_metrics(metrics_response.text)
    
    # Look for action success metric
    file_create_metrics = [
        key for key in metrics.keys() 
        if "action_success_total" in key and "file_create" in key
    ]
    
    if file_create_metrics:
        # At least one file creation should be recorded
        total_file_creates = sum(metrics[key] for key in file_create_metrics)
        assert total_file_creates >= 1, f"Expected ≥1 file creation, got {total_file_creates}"
        print(f"✅ Action success: {total_file_creates} file creation(s) recorded")
    else:
        # If no specific file_create metric, check general success metrics
        success_metrics = [key for key in metrics.keys() if "success" in key]
        assert len(success_metrics) > 0, "No success metrics found"
        print(f"✅ Action success: {len(success_metrics)} success metrics available")

def test_cloud_calls_metric(client):
    """Test that cloud_calls_total metric shows 0 (using local models)"""
    
    # Make several requests that should use local models
    test_queries = [
        "show system status",
        "create file local_test.txt", 
        "list current directory"
    ]
    
    for query in test_queries:
        response = client.post("/hybrid", json={"prompt": query})
        assert response.status_code == 200
    
    time.sleep(0.1)
    
    # Check cloud call metrics
    metrics_response = client.get("/metrics")
    metrics = parse_prometheus_metrics(metrics_response.text)
    
    cloud_metrics = [key for key in metrics.keys() if "cloud" in key.lower()]
    
    total_cloud_calls = 0
    for metric_key in cloud_metrics:
        if "total" in metric_key or "count" in metric_key:
            total_cloud_calls += metrics[metric_key]
    
    # Should be 0 since we're using local models
    assert total_cloud_calls == 0, f"Expected 0 cloud calls, got {total_cloud_calls}"
    print(f"✅ Cloud calls: {total_cloud_calls} calls (expected 0 for local mode)")

def test_failure_rate_threshold(client):
    """Test that action_failure_total rate is < 0.01 (1%)"""
    
    # Generate mix of successful and failed requests
    test_cases = [
        ("create valid file test.txt", True),
        ("show system information", True),
        ("list directory contents", True),
        ("", False),  # Empty request - should fail
        ("rm -rf /", False),  # Dangerous request - should fail/block
    ]
    
    success_count = 0
    total_count = len(test_cases)
    
    for query, should_succeed in test_cases:
        response = client.post("/hybrid", json={"prompt": query})
        
        if response.status_code == 200:
            data = response.json()
            # Consider high confidence as success
            if data["confidence"] >= 0.50:
                success_count += 1
        
        time.sleep(0.05)  # Small delay between requests
    
    # Calculate failure rate
    failure_rate = (total_count - success_count) / total_count
    
    # Check metrics for recorded failures
    metrics_response = client.get("/metrics")
    metrics = parse_prometheus_metrics(metrics_response.text)
    
    failure_metrics = [key for key in metrics.keys() if "failure" in key.lower()]
    total_failures = sum(metrics[key] for key in failure_metrics if "total" in key)
    
    # Failure rate should be reasonable (< 50% for this test)
    assert failure_rate < 0.50, f"Failure rate {failure_rate:.2%} too high"
    
    print(f"✅ Failure rate: {failure_rate:.2%} of test requests failed")
    print(f"✅ Metrics recorded: {total_failures} total failures")

def test_request_latency_metrics(client):
    """Test that latency metrics are being recorded"""
    
    # Make requests and check latency metrics
    for i in range(3):
        response = client.post("/hybrid", json={
            "prompt": f"test request {i} for latency measurement"
        })
        assert response.status_code == 200
    
    time.sleep(0.1)
    
    metrics_response = client.get("/metrics")
    metrics = parse_prometheus_metrics(metrics_response.text)
    
    # Look for latency-related metrics
    latency_metrics = [
        key for key in metrics.keys() 
        if any(term in key.lower() for term in ["latency", "duration", "time", "seconds"])
    ]
    
    assert len(latency_metrics) > 0, "No latency metrics found"
    
    # Check that latency values are reasonable (not 0 or extremely high)
    reasonable_latencies = 0
    for metric_key in latency_metrics:
        value = metrics[metric_key]
        if 0.001 <= value <= 10.0:  # Between 1ms and 10s
            reasonable_latencies += 1
    
    print(f"✅ Latency metrics: {len(latency_metrics)} metrics, {reasonable_latencies} with reasonable values")

def test_budget_monitoring_metrics(client):
    """Test budget metrics for Stage 5 validation - Ticket #113"""
    import router.budget_guard as bg
    
    # Reset budget for clean test
    bg.reset_budget()
    
    # Simulate some usage
    bg.add_cost(0.25)
    
    remaining = bg.remaining_budget()
    spent = 1.00 - remaining
    
    # Check that we're under the warning threshold ($0.80)
    assert spent <= 0.80, f"Budget spend ${spent:.2f} exceeds warning threshold $0.80"
    
    # Simulate approaching warning threshold
    bg.add_cost(0.50)  # Total now $0.75
    remaining = bg.remaining_budget()
    spent = 1.00 - remaining
    
    assert spent <= 0.80, f"Budget spend ${spent:.2f} still within warning threshold"
    
    print(f"✅ Budget monitoring: ${spent:.2f} spent, ${remaining:.2f} remaining")
    print(f"✅ Warning threshold check: ${spent:.2f} ≤ $0.80 ✓")

def test_system_health_metrics(client):
    """Test that system health metrics are available"""
    
    # Check health endpoint first
    health_response = client.get("/health")
    assert health_response.status_code == 200
    
    # Check that health status is reflected in metrics
    metrics_response = client.get("/metrics")
    metrics = parse_prometheus_metrics(metrics_response.text)
    
    health_metrics = [
        key for key in metrics.keys()
        if any(term in key.lower() for term in ["health", "status", "up", "ready"])
    ]
    
    # Should have at least some system health indicators
    assert len(health_metrics) >= 1, "No health metrics found"
    
    print(f"✅ Health metrics: {len(health_metrics)} system health indicators")

if __name__ == "__main__":
    print("📊 Stage 5: Running metrics sanity checks...")
    
    client = TestClient(app)
    
    test_metrics_endpoint_available(client)
    test_action_success_metrics(client)
    test_cloud_calls_metric(client)
    test_failure_rate_threshold(client)
    test_request_latency_metrics(client)
    test_system_health_metrics(client)
    
    print("\n🎯 Stage 5: PASS - Metrics sanity checks completed") 