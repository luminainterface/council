# -*- coding: utf-8 -*-
"""
Shared test fixtures for SwarmAI tests
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