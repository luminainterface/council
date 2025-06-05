#!/usr/bin/env python3
"""
Swarm Metrics Exporter - Production wrapper for monitoring/exporter.py
Ensures metrics are available on port 9091 as per run-book
"""

import sys
import os

# Add monitoring directory to path
sys.path.insert(0, '/app/monitoring')

# Import and run the main exporter
from exporter import app

if __name__ == "__main__":
    import uvicorn
    print("🔍 Starting Swarm Metrics Exporter on port 9091...")
    print("📊 Metrics available at: http://localhost:9091/metrics")
    print("❤️ Health check at: http://localhost:9091/health")
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=9091,
        log_level="info"
    ) 