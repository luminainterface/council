# sandbox_exec.py – Multi-provider secure code execution for AutoGen Council
# ==========================================================================
# Supports: Firejail (Linux), Docker (all platforms), WSL (Windows), none
# Auto-detects available providers and falls back gracefully

import os, subprocess, tempfile, time, textwrap, json
from pathlib import Path
from prometheus_client import Counter, Summary
import yaml

# ─── Prometheus metrics ─────────────────────────────────────────────
EXEC_LAT = Summary("swarm_exec_latency_seconds", "Sandbox exec latency")
EXEC_FAILS = Counter("swarm_exec_fail_total", "Sandbox exec failures", ["reason"])

# ─── Configuration loading ──────────────────────────────────────────
def load_settings():
    """Load sandbox settings from config/settings.yaml with fallbacks"""
    settings_path = Path("config/settings.yaml")
    default_settings = {
        "sandbox": {
            "provider": "auto",  # auto-detect
            "enabled": True,
            "timeout_seconds": 5,
            "memory_limit_mb": 256,
            "cpu_limit": 1.0,
            "docker": {
                "image": "agent-sandbox:latest",
                "network": "none",
                "remove_after": True,
                "working_dir": "/tmp/execution"
            },
            "firejail": {
                "profile": "sandbox/profile.conf",
                "private_tmp": True,
                "no_network": True
            },
            "wsl": {
                "distro": "Ubuntu-22.04",
                "user": "sandbox"
            }
        }
    }
    
    if settings_path.exists():
        try:
            with open(settings_path, 'r') as f:
                loaded = yaml.safe_load(f)
                return loaded.get("sandbox", default_settings["sandbox"])
        except Exception as e:
            print(f"Warning: Failed to load settings.yaml: {e}")
    
    return default_settings["sandbox"]

# ─── Provider detection ─────────────────────────────────────────────
def detect_available_providers():
    """Auto-detect available sandbox providers on this system"""
    providers = []
    
    # Check for Firejail (Linux)
    if Path("/usr/bin/firejail").exists() or Path("/bin/firejail").exists():
        try:
            result = subprocess.run(["firejail", "--version"], 
                                  capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                providers.append("firejail")
        except:
            pass
    
    # Check for Docker
    try:
        result = subprocess.run(["docker", "--version"], 
                              capture_output=True, text=True, timeout=2)
        if result.returncode == 0:
            providers.append("docker")
    except:
        pass
    
    # Check for WSL (Windows)
    if os.name == 'nt':  # Windows
        try:
            result = subprocess.run(["wsl", "--list", "--quiet"], 
                                  capture_output=True, text=True, timeout=2)
            if result.returncode == 0 and result.stdout.strip():
                providers.append("wsl")
        except:
            pass
    
    return providers

# ─── Provider implementations ───────────────────────────────────────
def exec_firejail(code: str, lang: str, settings: dict) -> dict:
    """Execute code using Firejail sandbox"""
    firejail_bin = "/usr/bin/firejail"
    if not Path(firejail_bin).exists():
        firejail_bin = "/bin/firejail"
    
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / f"snippet.{lang}"
        src.write_text(textwrap.dedent(code))
        
        timeout = settings.get("timeout_seconds", 5)
        cmd = [
            firejail_bin, "--quiet", "--private", "--net=none",
            "--rlimit-cpu=5", "--rlimit-fsize=20480000",  # 20 MB output cap
            "bash", "-c", f"timeout {timeout}s python {src}"
        ]
        
        start = time.perf_counter()
        proc = subprocess.run(cmd, capture_output=True, text=True)
        elapsed = int((time.perf_counter() - start) * 1000)
        
        if proc.returncode == 124:  # timeout
            raise RuntimeError("Sandbox execution timed out")
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip()[:400] or "non-zero exit")
        
        return {"stdout": proc.stdout.strip(), "stderr": proc.stderr.strip(), "elapsed_ms": elapsed}

def exec_docker(code: str, lang: str, settings: dict) -> dict:
    """Execute code using Docker container"""
    docker_settings = settings.get("docker", {})
    image = docker_settings.get("image", "agent-sandbox:latest")
    
    # Check if image exists
    check_cmd = ["docker", "image", "inspect", image]
    check_result = subprocess.run(check_cmd, capture_output=True, text=True)
    if check_result.returncode != 0:
        raise RuntimeError(f"Docker image {image} not found. Run: docker build -f Dockerfile.sandbox -t {image} .")
    
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / f"snippet.{lang}"
        src.write_text(textwrap.dedent(code))
        
        timeout = settings.get("timeout_seconds", 5)
        memory_limit = f"{settings.get('memory_limit_mb', 256)}m"
        cpu_limit = str(settings.get('cpu_limit', 1.0))
        
        cmd = [
            "docker", "run", "--rm",
            f"--memory={memory_limit}",
            f"--cpus={cpu_limit}",
            "--network=none",  # No network access
            "--read-only",     # Read-only filesystem
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=100m",  # Writable /tmp
            "-v", f"{src}:/tmp/execution/code.py:ro",  # Mount code file
            image,
            "timeout", f"{timeout}s", "python", "/tmp/execution/code.py"
        ]
        
        start = time.perf_counter()
        proc = subprocess.run(cmd, capture_output=True, text=True)
        elapsed = int((time.perf_counter() - start) * 1000)
        
        if proc.returncode == 124:  # timeout
            raise RuntimeError("Sandbox execution timed out")
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip()[:400] or "non-zero exit")
        
        return {"stdout": proc.stdout.strip(), "stderr": proc.stderr.strip(), "elapsed_ms": elapsed}

def exec_wsl(code: str, lang: str, settings: dict) -> dict:
    """Execute code using WSL (Windows Subsystem for Linux) with security isolation"""
    wsl_settings = settings.get("wsl", {})
    distro = wsl_settings.get("distro", "Ubuntu")
    
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / f"snippet.{lang}"
        src.write_text(textwrap.dedent(code))
        
        timeout = settings.get("timeout_seconds", 5)
        memory_limit = settings.get("memory_limit_mb", 256)
        
        # Convert Windows path to WSL path
        # T:\LAB\temp\file.py -> /mnt/t/LAB/temp/file.py
        abs_path = src.resolve()
        drive_letter = abs_path.drive[0].lower()  # T: -> t
        path_without_drive = str(abs_path)[3:]    # Remove "T:\"
        wsl_path = f"/mnt/{drive_letter}/{path_without_drive.replace(chr(92), '/')}"  # Use chr(92) for backslash
        
        # Enhanced WSL command with resource limits and security
        cmd = [
            "wsl", "-d", distro, "--",
            "firejail", "--quiet", 
            "--private-tmp",          # Isolated temp directory
            "--net=none",             # No network access
            "--memory", str(memory_limit * 1024 * 1024),  # Memory limit in bytes
            f"--rlimit-cpu={timeout}",  # CPU time limit
            "bash", "-c", f"timeout {timeout}s python3 '{wsl_path}'"
        ]
        
        # Fallback to basic WSL if firejail not available
        fallback_cmd = [
            "wsl", "-d", distro, "--",
            "bash", "-c", f"timeout {timeout}s python3 '{wsl_path}'"
        ]
        
        start = time.perf_counter()
        
        # Try firejail first, fallback to basic WSL if firejail fails
        proc = subprocess.run(cmd, capture_output=True, text=True)
        
        # If firejail command failed (likely because firejail not installed), try fallback
        if proc.returncode != 0 and ("firejail" in proc.stderr and ("not found" in proc.stderr or "command not found" in proc.stderr)):
            proc = subprocess.run(fallback_cmd, capture_output=True, text=True)
            
        elapsed = int((time.perf_counter() - start) * 1000)
        
        if proc.returncode == 124:  # timeout
            raise RuntimeError("Sandbox execution timed out")
        if proc.returncode != 0:
            error_msg = proc.stderr.strip() or proc.stdout.strip() or "non-zero exit"
            raise RuntimeError(f"WSL execution failed: {error_msg[:400]}")
        
        return {"stdout": proc.stdout.strip(), "stderr": proc.stderr.strip(), "elapsed_ms": elapsed}

# ─── Main execution function ────────────────────────────────────────
@EXEC_LAT.time()
def exec_safe(code: str, lang: str = "python") -> dict:
    """
    Execute code in a secure sandbox environment.
    Auto-detects available providers: Docker, Firejail, WSL
    """
    settings = load_settings()
    
    if not settings.get("enabled", True):
        EXEC_FAILS.labels("disabled").inc()
        raise RuntimeError("Sandbox execution is disabled in settings")
    
    provider = settings.get("provider", "auto")
    available_providers = detect_available_providers()
    
    # Auto-select provider if set to "auto"
    if provider == "auto":
        if "docker" in available_providers:
            provider = "docker"
        elif "firejail" in available_providers:
            provider = "firejail"
        elif "wsl" in available_providers:
            provider = "wsl"
        else:
            provider = "none"
    
    # Execute with selected provider
    try:
        if provider == "firejail" and "firejail" in available_providers:
            return exec_firejail(code, lang, settings)
        elif provider == "docker" and "docker" in available_providers:
            return exec_docker(code, lang, settings)
        elif provider == "wsl" and "wsl" in available_providers:
            return exec_wsl(code, lang, settings)
        else:
            EXEC_FAILS.labels("no_provider").inc()
            raise RuntimeError(f"No sandbox provider available. Detected: {available_providers}, Requested: {provider}")
    
    except subprocess.TimeoutExpired:
        EXEC_FAILS.labels("timeout").inc()
        raise RuntimeError("Sandbox execution timed out")
    except Exception as e:
        EXEC_FAILS.labels("runtime").inc()
        raise RuntimeError(f"Sandbox execution failed: {str(e)}")

# ─── Provider status function ───────────────────────────────────────
def get_sandbox_status():
    """Get current sandbox configuration and status"""
    settings = load_settings()
    available = detect_available_providers()
    provider = settings.get("provider", "auto")
    
    if provider == "auto":
        provider = available[0] if available else "none"
    
    return {
        "enabled": settings.get("enabled", True),
        "provider": provider,
        "available_providers": available,
        "timeout_seconds": settings.get("timeout_seconds", 5),
        "status": "operational" if provider in available else "unavailable"
    }

# ─── Quick manual test ──────────────────────────────────────────────
if __name__ == "__main__":
    print("🛡️ Sandbox Status:", json.dumps(get_sandbox_status(), indent=2))
    print("\n🧪 Testing sandbox execution...")
    try:
        result = exec_safe("print(f'Hello from sandbox! 2+2={2+2}')")
        print("✅ Test successful:", result)
    except Exception as e:
        print("❌ Test failed:", e) 