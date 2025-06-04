# -*- coding: utf-8 -*-
"""
End-to-end tests for SwarmAI orchestrate endpoint
Tests the full FastAPI server with real model loading
"""

import httpx
import pytest
import os
import subprocess
import time
import socket
import signal
from typing import Generator

def is_port_open(host: str, port: int) -> bool:
    """Check if a port is open"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        result = sock.connect_ex((host, port))
        return result == 0

@pytest.fixture(scope="session")
def api_server() -> Generator[None, None, None]:
    """Start FastAPI server for testing"""
    # Set environment for testing
    env = os.environ.copy()
    env["SWARM_GPU_PROFILE"] = "rtx_4070"
    
    # Check if server is already running
    if is_port_open("127.0.0.1", 8000):
        print("📡 Server already running on port 8000")
        yield
        return
    
    # Start server
    print("🚀 Starting FastAPI server for E2E tests...")
    proc = subprocess.Popen(
        ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait for server to start (max 15 seconds)
    for i in range(30):  # 30 * 0.5 = 15 seconds
        if is_port_open("127.0.0.1", 8000):
            print(f"✅ Server started after {i * 0.5:.1f}s")
            break
        time.sleep(0.5)
    else:
        proc.terminate()
        stdout, stderr = proc.communicate()
        pytest.fail(f"Server failed to start: {stderr.decode()}")
    
    yield
    
    # Cleanup
    print("🛑 Shutting down test server...")
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()

def test_server_health(api_server):
    """Test that the server health endpoint works"""
    with httpx.Client() as client:
        response = client.get("http://127.0.0.1:8000/health", timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert data["loaded_models"] > 0
        assert len(data["available_heads"]) > 0

def test_models_endpoint(api_server):
    """Test the models listing endpoint"""
    with httpx.Client() as client:
        response = client.get("http://127.0.0.1:8000/models", timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        assert "loaded_models" in data
        assert "count" in data
        assert data["count"] > 0

def test_orchestrate_math_specialist(api_server):
    """Test orchestration with math specialist"""
    with httpx.Client() as client:
        response = client.post(
            "http://127.0.0.1:8000/orchestrate",
            json={
                "prompt": "What is 2 + 2?", 
                "route": ["math_specialist_0.8b"]
            },
            timeout=15
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "text" in data
        assert "model_used" in data
        assert "latency_ms" in data
        
        # Check that math result is in response
        assert "4" in data["text"]
        assert data["model_used"] == "math_specialist_0.8b"
        assert data["latency_ms"] > 0

def test_orchestrate_code_specialist(api_server):
    """Test orchestration with code specialist"""
    with httpx.Client() as client:
        response = client.post(
            "http://127.0.0.1:8000/orchestrate",
            json={
                "prompt": "Write a Python function to add two numbers",
                "route": ["codellama_0.7b"]
            },
            timeout=15
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "text" in data
        assert data["model_used"] == "codellama_0.7b"
        assert data["latency_ms"] > 0

def test_orchestrate_multi_model_fallback(api_server):
    """Test orchestration with multiple model options"""
    with httpx.Client() as client:
        response = client.post(
            "http://127.0.0.1:8000/orchestrate",
            json={
                "prompt": "Explain machine learning",
                "route": ["mistral_7b_instruct", "openchat_3.5_0.4b"]
            },
            timeout=15
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "text" in data
        assert data["model_used"] in ["mistral_7b_instruct", "openchat_3.5_0.4b"]
        assert data["latency_ms"] > 0

def test_orchestrate_invalid_model(api_server):
    """Test orchestration with invalid model should fail gracefully"""
    with httpx.Client() as client:
        response = client.post(
            "http://127.0.0.1:8000/orchestrate",
            json={
                "prompt": "Test prompt",
                "route": ["nonexistent_model"]
            },
            timeout=15
        )
        
        assert response.status_code == 500
        assert "No requested heads are loaded" in response.text

def test_orchestrate_performance_baseline(api_server):
    """Test that orchestrate endpoint meets performance baseline"""
    with httpx.Client() as client:
        start_time = time.time()
        
        response = client.post(
            "http://127.0.0.1:8000/orchestrate",
            json={
                "prompt": "Quick test", 
                "route": ["tinyllama_1b"]  # Smallest model for speed
            },
            timeout=15
        )
        
        end_time = time.time()
        total_latency = (end_time - start_time) * 1000  # ms
        
        assert response.status_code == 200
        data = response.json()
        
        # Should respond within reasonable time (< 500ms for small model)
        assert total_latency < 500
        assert data["latency_ms"] < 200

def test_metrics_endpoint(api_server):
    """Test Prometheus metrics endpoint"""
    with httpx.Client() as client:
        response = client.get("http://127.0.0.1:8000/metrics", timeout=10)
        assert response.status_code == 200
        
        # Should contain Prometheus format metrics
        metrics_text = response.text
        assert "swarm_router_request_latency" in metrics_text
        assert "swarm_router_requests_total" in metrics_text 