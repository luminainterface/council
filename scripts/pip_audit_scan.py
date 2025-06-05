#!/usr/bin/env python3
"""
Stage 11: Supply Chain Security Scan (pip-audit)
Scans dependencies for known vulnerabilities and fails on medium+ severity issues.
"""

import subprocess
import json
import sys
import os
from pathlib import Path

def install_pip_audit():
    """Ensure pip-audit is installed"""
    print("🔍 Installing pip-audit...")
    subprocess.run([
        sys.executable, "-m", "pip", "install", 
        "--quiet", "--disable-pip-version-check", 
        "pip-audit>=2.6,<3"
    ], check=True)

def run_pip_audit():
    """Run pip-audit and return results"""
    print("🔍 Scanning dependencies for vulnerabilities...")
    
    try:
        # Try to run pip-audit on requirements.txt
        result = subprocess.run([
            "pip-audit", "-r", "requirements.txt", "-f", "json", "-o", "pip_audit.json"
        ], capture_output=True, text=True, check=False)
        
        if result.returncode != 0:
            print(f"⚠️ pip-audit encountered issues: {result.stderr}")
            # Try alternative approach - scan installed packages
            print("🔄 Falling back to scanning installed packages...")
            result = subprocess.run([
                "pip-audit", "-f", "json", "-o", "pip_audit.json"
            ], capture_output=True, text=True, check=False)
        
        return result.returncode == 0
        
    except FileNotFoundError:
        print("❌ pip-audit not found - installation may have failed")
        return False

def check_vulnerabilities():
    """Check pip_audit.json for medium+ severity vulnerabilities"""
    if not Path("pip_audit.json").exists():
        print("❌ pip_audit.json not found")
        return False
    
    try:
        with open("pip_audit.json", "r") as f:
            data = json.load(f)
        
        # Handle different pip-audit output formats
        vulnerabilities = []
        if isinstance(data, list):
            vulnerabilities = data
        elif isinstance(data, dict) and "vulnerabilities" in data:
            vulnerabilities = data["vulnerabilities"]
        
        # Filter for medium+ severity
        bad_vulns = []
        for vuln in vulnerabilities:
            severity = vuln.get("vuln_severity", "").lower()
            if severity in {"medium", "high", "critical"}:
                bad_vulns.append(vuln)
        
        if bad_vulns:
            print("❌ Supply-chain vulnerabilities detected:")
            for vuln in bad_vulns:
                dep = vuln.get("dependency", "unknown")
                vuln_id = vuln.get("vuln_id", "unknown")
                severity = vuln.get("vuln_severity", "unknown")
                print(f"   • {dep} – {vuln_id} ({severity})")
            return False
        else:
            print("✅ pip-audit clean (no medium+ vulnerabilities)")
            return True
            
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse pip_audit.json: {e}")
        return False
    except Exception as e:
        print(f"❌ Error checking vulnerabilities: {e}")
        return False

def main():
    """Main function for Stage 11"""
    print("🔒 Stage 11: Supply Chain Security Scan")
    
    try:
        # Install pip-audit
        install_pip_audit()
        
        # Run the scan
        scan_success = run_pip_audit()
        if not scan_success:
            print("⚠️ pip-audit scan completed with warnings")
        
        # Check results
        if check_vulnerabilities():
            print("✅ Stage 11: PASS - No medium+ vulnerabilities found")
            return 0
        else:
            print("❌ Stage 11: FAIL - Security vulnerabilities detected")
            return 1
            
    except Exception as e:
        print(f"❌ Stage 11: ERROR - {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 