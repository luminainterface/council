#!/usr/bin/env python3
"""
🔒 Supply Chain Security Scan - Stage 11  
Validates dependencies, licenses, and security vulnerabilities
"""

import json
import subprocess
import sys
from pathlib import Path
import pkg_resources
import hashlib


class SupplyChainScanner:
    def __init__(self):
        self.results = {
            "dependencies": {},
            "licenses": {},
            "vulnerabilities": [],
            "checksums": {},
            "overall_score": 0
        }
        
    def scan_pip_dependencies(self):
        """Scan Python dependencies for known vulnerabilities"""
        print("🔍 Scanning Python dependencies...")
        
        try:
            # Get installed packages
            installed_packages = [d for d in pkg_resources.working_set]
            
            for package in installed_packages:
                name = package.project_name
                version = package.version
                
                self.results["dependencies"][name] = {
                    "version": version,
                    "location": package.location,
                    "requires": [str(req) for req in package.requires()]
                }
            
            print(f"✅ Found {len(installed_packages)} Python packages")
            
            # Check for known problematic packages
            problematic = ["tensorflow==1.15.0", "pillow<8.1.1", "pyyaml<5.4"]
            for pkg_name, pkg_info in self.results["dependencies"].items():
                pkg_version = pkg_info["version"]
                full_name = f"{pkg_name}=={pkg_version}"
                
                if any(prob in full_name for prob in problematic):
                    self.results["vulnerabilities"].append({
                        "package": pkg_name,
                        "version": pkg_version,
                        "severity": "HIGH",
                        "issue": "Known vulnerability in this version"
                    })
            
        except Exception as e:
            print(f"⚠️ Python dependency scan failed: {e}")

    def scan_npm_dependencies(self):
        """Scan Node.js dependencies if package.json exists"""
        package_json = Path("package.json")
        
        if not package_json.exists():
            print("ℹ️ No package.json found, skipping npm scan")
            return
            
        print("🔍 Scanning npm dependencies...")
        
        try:
            # Try npm audit if available
            result = subprocess.run(['npm', 'audit', '--json'], 
                                  capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                audit_data = json.loads(result.stdout)
                vulnerabilities = audit_data.get("vulnerabilities", {})
                
                for pkg_name, vuln_info in vulnerabilities.items():
                    severity = vuln_info.get("severity", "unknown")
                    if severity in ["high", "critical"]:
                        self.results["vulnerabilities"].append({
                            "package": pkg_name,
                            "severity": severity.upper(),
                            "issue": "npm audit vulnerability",
                            "ecosystem": "npm"
                        })
                
                print(f"✅ npm audit completed - found {len(vulnerabilities)} vulnerabilities")
            else:
                print("⚠️ npm audit failed or not available")
                
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError) as e:
            print(f"⚠️ npm dependency scan failed: {e}")

    def check_file_integrity(self):
        """Check integrity of critical files"""
        print("🔍 Checking file integrity...")
        
        critical_files = [
            "requirements.txt",
            "autogen_api_shim.py", 
            "docker-compose.yml",
            "Makefile"
        ]
        
        for file_path in critical_files:
            path = Path(file_path)
            if path.exists():
                # Calculate SHA256 hash
                content = path.read_bytes()
                sha256_hash = hashlib.sha256(content).hexdigest()
                
                self.results["checksums"][file_path] = {
                    "sha256": sha256_hash,
                    "size_bytes": len(content),
                    "exists": True
                }
                
                # Basic sanity checks
                if file_path == "requirements.txt":
                    lines = content.decode('utf-8').split('\n')
                    if any('eval(' in line or 'exec(' in line for line in lines):
                        self.results["vulnerabilities"].append({
                            "file": file_path,
                            "severity": "HIGH", 
                            "issue": "Suspicious code execution in requirements"
                        })
            else:
                self.results["checksums"][file_path] = {"exists": False}
        
        print(f"✅ Checked {len(critical_files)} critical files")

    def check_docker_security(self):
        """Check Docker configuration for security issues"""
        print("🔍 Checking Docker security...")
        
        docker_files = ["Dockerfile", "docker-compose.yml", "docker-compose.override.yml"]
        
        for docker_file in docker_files:
            path = Path(docker_file)
            if path.exists():
                content = path.read_text()
                
                # Check for security anti-patterns
                issues = []
                
                if "FROM ubuntu:latest" in content or "FROM python:latest" in content:
                    issues.append("Using 'latest' tag - not reproducible")
                
                if "RUN apt-get install" in content and "apt-get update" not in content:
                    issues.append("apt-get install without update")
                
                if "--privileged" in content:
                    issues.append("Privileged container detected")
                
                if "ADD http" in content:
                    issues.append("Downloading files with ADD - use COPY instead")
                
                for issue in issues:
                    self.results["vulnerabilities"].append({
                        "file": docker_file,
                        "severity": "MEDIUM",
                        "issue": issue
                    })
        
        print(f"✅ Checked Docker configurations")

    def check_secrets_exposure(self):
        """Check for accidentally committed secrets"""
        print("🔍 Checking for exposed secrets...")
        
        secret_patterns = [
            "api_key", "password", "secret", "token", "PRIVATE_KEY",
            "aws_access_key", "GITHUB_TOKEN", "OPENAI_API_KEY"
        ]
        
        code_files = list(Path(".").glob("**/*.py")) + list(Path(".").glob("**/*.yml"))
        
        for file_path in code_files:
            if ".git" in str(file_path) or "__pycache__" in str(file_path):
                continue
                
            try:
                content = file_path.read_text()
                for pattern in secret_patterns:
                    if pattern in content and "=" in content:
                        # Look for actual assignments, not just variable names
                        lines = content.split('\n')
                        for i, line in enumerate(lines):
                            if pattern in line and "=" in line and not line.strip().startswith("#"):
                                # Check if it looks like a real secret (not a variable name)
                                if '"' in line or "'" in line:
                                    value = line.split("=", 1)[1].strip().strip("\"'")
                                    if len(value) > 10 and not value.startswith("$"):
                                        self.results["vulnerabilities"].append({
                                            "file": str(file_path),
                                            "line": i + 1,
                                            "severity": "CRITICAL",
                                            "issue": f"Potential secret exposure: {pattern}"
                                        })
            except Exception:
                continue  # Skip files that can't be read
        
        print(f"✅ Scanned code files for secrets")

    def calculate_security_score(self):
        """Calculate overall security score"""
        score = 100
        
        # Deduct points for vulnerabilities
        for vuln in self.results["vulnerabilities"]:
            severity = vuln.get("severity", "unknown")
            if severity == "CRITICAL":
                score -= 25
            elif severity == "HIGH":
                score -= 15
            elif severity == "MEDIUM":
                score -= 5
            else:
                score -= 2
        
        # Bonus for having security files
        security_files = ["requirements.txt", "Dockerfile", ".gitignore"]
        existing_files = sum(1 for f in security_files if Path(f).exists())
        score += (existing_files / len(security_files)) * 10
        
        self.results["overall_score"] = max(0, min(100, score))

    def run_full_scan(self):
        """Run complete supply chain security scan"""
        print("🔒 SUPPLY CHAIN SECURITY SCAN")
        print("=" * 40)
        
        self.scan_pip_dependencies()
        self.scan_npm_dependencies()
        self.check_file_integrity()
        self.check_docker_security()
        self.check_secrets_exposure()
        self.calculate_security_score()
        
        # Generate report
        print(f"\n📊 SECURITY REPORT")
        print(f"Dependencies scanned: {len(self.results['dependencies'])}")
        print(f"Vulnerabilities found: {len(self.results['vulnerabilities'])}")
        print(f"Overall security score: {self.results['overall_score']}/100")
        
        # Show vulnerabilities
        if self.results["vulnerabilities"]:
            print(f"\n❌ VULNERABILITIES FOUND:")
            for vuln in self.results["vulnerabilities"]:
                print(f"   {vuln['severity']}: {vuln.get('package', vuln.get('file', 'unknown'))}")
                print(f"      Issue: {vuln['issue']}")
        else:
            print(f"\n✅ No vulnerabilities found!")
        
        # Pass/fail criteria
        criteria = {
            "no_critical_vulns": not any(v["severity"] == "CRITICAL" for v in self.results["vulnerabilities"]),
            "few_high_vulns": sum(1 for v in self.results["vulnerabilities"] if v["severity"] == "HIGH") <= 2,
            "good_score": self.results["overall_score"] >= 70
        }
        
        print(f"\n🎯 PASS/FAIL CRITERIA:")
        for criterion, passed in criteria.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{criterion}: {status}")
        
        overall_pass = all(criteria.values())
        print(f"\n🔒 OVERALL: {'✅ PASS' if overall_pass else '❌ FAIL'}")
        
        # Save detailed results
        with open("supply_chain_scan_results.json", "w") as f:
            json.dump(self.results, f, indent=2)
        
        return overall_pass


def main():
    """Run supply chain security scan"""
    scanner = SupplyChainScanner()
    
    try:
        success = scanner.run_full_scan()
        
        if success:
            print("\n🎉 Supply chain security scan passed!")
        else:
            print("\n⚠️ Supply chain security issues detected")
            
        return success
        
    except Exception as e:
        print(f"\n❌ Security scan failed: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 