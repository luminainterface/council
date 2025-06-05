#!/usr/bin/env python3
"""
Direct WSL Test - bypass firejail issues
"""

import subprocess
import tempfile
from pathlib import Path
import time

def test_wsl_direct():
    """Test WSL execution without firejail"""
    
    code = '''
import os, pathlib, json

# Create workspace directory
pathlib.Path("workspace/tmp").mkdir(parents=True, exist_ok=True)

# Write hello file
with open("workspace/tmp/hello.txt", "w") as f:
    f.write("hi")

# Read it back
with open("workspace/tmp/hello.txt", "r") as f:
    content = f.read()

print(content)
'''

    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "snippet.py"
        src.write_text(code)
        
        # Convert Windows path to WSL path
        abs_path = src.resolve()
        drive_letter = abs_path.drive[0].lower()  # T: -> t
        path_without_drive = str(abs_path)[3:]    # Remove "T:\"
        wsl_path = f"/mnt/{drive_letter}/{path_without_drive.replace(chr(92), '/')}"
        
        print(f"WSL path: {wsl_path}")
        
        # Direct WSL command without firejail
        cmd = [
            "wsl", "--",
            "bash", "-c", f"timeout 10s python3 '{wsl_path}'"
        ]
        
        print(f"Command: {' '.join(cmd)}")
        
        start = time.perf_counter()
        proc = subprocess.run(cmd, capture_output=True, text=True)
        elapsed = int((time.perf_counter() - start) * 1000)
        
        print(f"Return code: {proc.returncode}")
        print(f"Stdout: '{proc.stdout}'")
        print(f"Stderr: '{proc.stderr}'")
        print(f"Elapsed: {elapsed}ms")
        
        if proc.returncode == 0 and proc.stdout.strip() == "hi":
            print("✅ WSL direct execution successful!")
            return True
        else:
            print("❌ WSL direct execution failed")
            return False

if __name__ == "__main__":
    test_wsl_direct() 