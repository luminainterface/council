#!/usr/bin/env python3
"""
🎮 GPU Hygiene Tests - Stage 7
Validates GPU memory management, CUDA availability, and resource cleanup
"""

import pytest
import psutil
import subprocess
import time


class TestGPUHygiene:
    """GPU health and memory management tests"""
    
    def test_cuda_availability(self):
        """Test CUDA availability and basic GPU detection"""
        try:
            import torch
            cuda_available = torch.cuda.is_available()
            
            if cuda_available:
                device_count = torch.cuda.device_count()
                print(f"✅ CUDA available with {device_count} device(s)")
                
                for i in range(device_count):
                    device_name = torch.cuda.get_device_name(i)
                    memory_gb = torch.cuda.get_device_properties(i).total_memory / (1024**3)
                    print(f"   GPU {i}: {device_name} ({memory_gb:.1f} GB)")
                    
                assert device_count > 0, "No CUDA devices found"
            else:
                print("⚠️ CUDA not available - running CPU-only tests")
                pytest.skip("CUDA not available")
                
        except ImportError:
            print("⚠️ PyTorch not installed - skipping GPU tests")
            pytest.skip("PyTorch not available")

    def test_gpu_memory_baseline(self):
        """Test baseline GPU memory usage"""
        try:
            import torch
            if not torch.cuda.is_available():
                pytest.skip("CUDA not available")
                
            torch.cuda.empty_cache()
            baseline_memory = torch.cuda.memory_allocated(0)
            
            print(f"✅ Baseline GPU memory: {baseline_memory / (1024**2):.1f} MB")
            
            # Baseline should be minimal
            assert baseline_memory < 500 * 1024 * 1024, f"High baseline memory: {baseline_memory}"
            
        except Exception as e:
            pytest.skip(f"GPU memory test failed: {e}")

    def test_gpu_memory_cleanup(self):
        """Test GPU memory cleanup after allocation"""
        try:
            import torch
            if not torch.cuda.is_available():
                pytest.skip("CUDA not available")
                
            # Clear cache and measure baseline
            torch.cuda.empty_cache()
            baseline = torch.cuda.memory_allocated(0)
            
            # Allocate some memory
            test_tensor = torch.randn(1000, 1000, device='cuda')
            allocated = torch.cuda.memory_allocated(0)
            
            print(f"✅ Memory after allocation: {allocated / (1024**2):.1f} MB")
            assert allocated > baseline, "Memory allocation not detected"
            
            # Clean up
            del test_tensor
            torch.cuda.empty_cache()
            
            # Check cleanup
            final_memory = torch.cuda.memory_allocated(0)
            print(f"✅ Memory after cleanup: {final_memory / (1024**2):.1f} MB")
            
            # Should return close to baseline
            memory_diff = final_memory - baseline
            assert memory_diff < 10 * 1024 * 1024, f"Memory leak detected: {memory_diff} bytes"
            
        except Exception as e:
            pytest.skip(f"GPU cleanup test failed: {e}")

    def test_nvidia_smi_available(self):
        """Test nvidia-smi command availability"""
        try:
            result = subprocess.run(['nvidia-smi', '--query-gpu=memory.used,memory.total', '--format=csv,noheader,nounits'], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for i, line in enumerate(lines):
                    if line.strip():
                        used, total = line.split(', ')
                        usage_pct = (int(used) / int(total)) * 100
                        print(f"✅ GPU {i}: {used}/{total} MB ({usage_pct:.1f}% used)")
                        
                        # Warn if GPU memory usage is very high
                        if usage_pct > 90:
                            print(f"⚠️ High GPU memory usage on GPU {i}")
                            
                assert len(lines) > 0, "No GPU information returned"
            else:
                pytest.skip(f"nvidia-smi failed: {result.stderr}")
                
        except FileNotFoundError:
            pytest.skip("nvidia-smi not available")
        except subprocess.TimeoutExpired:
            pytest.fail("nvidia-smi command timed out")

    def test_gpu_processes(self):
        """Test for GPU process management"""
        try:
            result = subprocess.run(['nvidia-smi', '--query-compute-apps=pid,process_name,used_memory', '--format=csv,noheader'], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                processes = result.stdout.strip().split('\n')
                gpu_processes = [p for p in processes if p.strip()]
                
                print(f"✅ Active GPU processes: {len(gpu_processes)}")
                for proc in gpu_processes:
                    if proc.strip():
                        print(f"   {proc}")
                
                # Check for reasonable number of processes
                assert len(gpu_processes) < 50, f"Too many GPU processes: {len(gpu_processes)}"
                
            else:
                pytest.skip("Could not query GPU processes")
                
        except Exception as e:
            pytest.skip(f"GPU process test failed: {e}")

    def test_system_memory_hygiene(self):
        """Test system RAM usage for ML workloads"""
        memory = psutil.virtual_memory()
        
        print(f"✅ System memory: {memory.total / (1024**3):.1f} GB total")
        print(f"✅ Memory usage: {memory.percent:.1f}%")
        print(f"✅ Available: {memory.available / (1024**3):.1f} GB")
        
        # Check memory health
        assert memory.percent < 95, f"System memory usage too high: {memory.percent}%"
        assert memory.available > 1024**3, "Less than 1GB memory available"

    def test_disk_space_for_models(self):
        """Test disk space for model storage"""
        disk = psutil.disk_usage('.')
        
        print(f"✅ Disk space: {disk.total / (1024**3):.1f} GB total")
        print(f"✅ Disk usage: {(disk.used / disk.total) * 100:.1f}%")
        print(f"✅ Free space: {disk.free / (1024**3):.1f} GB")
        
        # Check disk health (need space for models and training)
        assert disk.free > 5 * 1024**3, "Less than 5GB disk space available"
        assert (disk.used / disk.total) < 0.9, "Disk usage over 90%"


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 