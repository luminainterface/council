# AutoGen Council - Installation Guide

## 🚀 **One-Line Install**

```bash
git clone <your-repo-url> && cd autogen-council && pip install -e .
```

## 📋 **Step-by-Step Installation**

### **1. System Requirements**
- Python 3.8+ 
- CUDA-capable GPU (4GB+ VRAM recommended)
- 8GB+ RAM
- 5GB free disk space

### **2. Clone Repository**
```bash
git clone <your-repo-url>
cd autogen-council
```

### **3. Install Dependencies**
```bash
# Option A: Using pip
pip install -r requirements.txt

# Option B: Using setup.py (recommended)
pip install -e .

# Option C: With GPU acceleration
pip install -e .[gpu]

# Option D: Full development setup
pip install -e .[gpu,logic,dev,monitoring]
```

### **4. Verify Installation**
```bash
# Test basic functionality
python -c "from fork.swarm_autogen.router_cascade import RouterCascade; print('✅ Installation successful!')"

# Start the server
python autogen_api_shim.py
# Should see: "Server starting on http://localhost:8000"

# Run quick test (in another terminal)
python autogen_titanic_gauntlet.py 1.0 10
# Should see: 90%+ success rate
```

## 🔧 **Optional Components**

### **GPU Acceleration (Recommended)**
```bash
# For NVIDIA GPUs
pip install faiss-gpu torch

# Verify CUDA
python -c "import torch; print(f'CUDA Available: {torch.cuda.is_available()}')"
```

### **Logic Programming**
```bash
# Install SWI-Prolog
# Ubuntu/Debian:
sudo apt-get install swi-prolog

# MacOS:
brew install swi-prolog

# Windows: Download from https://www.swi-prolog.org/

# Then install Python bindings:
pip install pyswip
```

### **Monitoring (Production)**
```bash
pip install prometheus-client grafana-api
```

## 🚨 **Troubleshooting**

### **Common Issues**

**1. CUDA Out of Memory**
```bash
# Use CPU-only mode
export CUDA_VISIBLE_DEVICES=""
```

**2. Missing Dependencies**
```bash
# Install missing packages
pip install torch transformers sentence-transformers
```

**3. Permission Issues**
```bash
# Use virtual environment
python -m venv autogen-env
source autogen-env/bin/activate  # Linux/Mac
# OR
autogen-env\Scripts\activate  # Windows
pip install -e .
```

**4. PySwip Issues**
```bash
# Skip logic programming for now
# System will work with other 3 specialists
```

## ✅ **Verification Tests**

### **Test Individual Components**
```bash
# Math specialist
python -c "from fork.swarm_autogen.skills.lightning_math import solve_math; import asyncio; print(asyncio.run(solve_math('2+2')))"

# Code specialist  
curl -X POST http://localhost:8000/hybrid -d '{"query": "fibonacci function"}' -H "Content-Type: application/json"

# Knowledge specialist
curl -X POST http://localhost:8000/hybrid -d '{"query": "what is DNA"}' -H "Content-Type: application/json"
```

### **Performance Benchmark**
```bash
# Quick benchmark (53 queries)
python autogen_titanic_gauntlet.py 1.0 53

# Expected results:
# ✅ Success rate: 92-98%
# ⚡ Latency: 87-131ms
# 💰 Cost: $0.047-0.052
```

## 🎯 **Ready to Use!**

Once installed, you have access to:

- **REST API**: `http://localhost:8000/hybrid`
- **Health Check**: `http://localhost:8000/health`  
- **Metrics**: `http://localhost:8000/stats`
- **Benchmarking**: `python autogen_titanic_gauntlet.py`

**Happy AI routing!** 🚀 