#!/usr/bin/env python3
"""
Stage 8: Load Test Runner
Execute Locust load test and validate results against acceptance criteria.
"""

import subprocess
import sys
import csv
import json
import time
import os
from pathlib import Path

def run_locust_test(users=30, spawn_rate=5, duration="5m", output_prefix="locust_out"):
    """Run Locust load test with specified parameters"""
    
    print(f"🏋️ Starting Locust load test:")
    print(f"  Users: {users}")
    print(f"  Spawn rate: {spawn_rate} users/sec")
    print(f"  Duration: {duration}")
    print(f"  Output: {output_prefix}_*.csv")
    
    cmd = [
        "locust",
        "-f", "tests/locust_actions.py",
        "-u", str(users),
        "-r", str(spawn_rate),
        "--run-time", duration,
        "--headless",
        "--csv", output_prefix,
        "--html", f"{output_prefix}_report.html"
    ]
    
    try:
        print("🚀 Executing load test...")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=400)
        
        print(f"Locust exit code: {result.returncode}")
        
        if result.stdout:
            print("STDOUT:")
            print(result.stdout)
        
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print("❌ Load test timed out after 400 seconds")
        return False
    except FileNotFoundError:
        print("❌ Locust not found. Install with: pip install locust")
        return False
    except Exception as e:
        print(f"❌ Load test failed: {e}")
        return False

def parse_locust_results(output_prefix="locust_out"):
    """Parse Locust CSV results and validate acceptance criteria"""
    
    stats_file = f"{output_prefix}_stats.csv"
    failures_file = f"{output_prefix}_failures.csv"
    history_file = f"{output_prefix}_stats_history.csv"
    
    results = {
        "success": False,
        "p95_latency": 0.0,
        "failure_count": 0,
        "total_requests": 0,
        "error_rate": 0.0
    }
    
    # Parse stats history for p95 latency
    if Path(history_file).exists():
        try:
            with open(history_file, 'r') as f:
                reader = csv.reader(f)
                rows = list(reader)
                
                if len(rows) > 1:  # Skip header
                    # Get the last row (final stats)
                    last_row = rows[-1]
                    if len(last_row) > 9:  # Ensure we have enough columns
                        # Column 9 is typically the 95th percentile
                        results["p95_latency"] = float(last_row[9]) / 1000.0  # Convert ms to seconds
                        print(f"📊 P95 latency: {results['p95_latency']:.3f}s")
                    
        except (ValueError, IndexError, FileNotFoundError) as e:
            print(f"⚠️ Could not parse stats history: {e}")
    
    # Parse failures
    if Path(failures_file).exists():
        try:
            with open(failures_file, 'r') as f:
                reader = csv.reader(f)
                rows = list(reader)
                results["failure_count"] = max(0, len(rows) - 1)  # Subtract header
                print(f"📊 Failures: {results['failure_count']}")
                
        except FileNotFoundError:
            print("⚠️ No failures file found")
    
    # Parse main stats
    if Path(stats_file).exists():
        try:
            with open(stats_file, 'r') as f:
                reader = csv.reader(f)
                rows = list(reader)
                
                total_requests = 0
                total_failures = 0
                
                for row in rows[1:]:  # Skip header
                    if len(row) > 4 and row[0] != "Aggregated":  # Skip summary row
                        try:
                            requests = int(row[3])  # Request count
                            failures = int(row[4])   # Failure count
                            total_requests += requests
                            total_failures += failures
                        except (ValueError, IndexError):
                            continue
                
                results["total_requests"] = total_requests
                if total_requests > 0:
                    results["error_rate"] = (total_failures / total_requests) * 100
                
                print(f"📊 Total requests: {total_requests}")
                print(f"📊 Error rate: {results['error_rate']:.2f}%")
                
        except FileNotFoundError:
            print("⚠️ No stats file found")
    
    return results

def validate_acceptance_criteria(results):
    """Validate results against acceptance criteria"""
    
    print("\n🎯 Validating acceptance criteria:")
    
    # Criteria
    max_p95_latency = 0.8  # 800ms
    max_failure_count = 20
    min_success_rate = 99.5  # 99.5%
    
    passed = True
    
    # Check P95 latency
    if results["p95_latency"] > 0:
        if results["p95_latency"] <= max_p95_latency:
            print(f"  ✅ P95 latency: {results['p95_latency']:.3f}s ≤ {max_p95_latency}s")
        else:
            print(f"  ❌ P95 latency: {results['p95_latency']:.3f}s > {max_p95_latency}s")
            passed = False
    else:
        print("  ⚠️ P95 latency: No data available")
    
    # Check failure count
    if results["failure_count"] <= max_failure_count:
        print(f"  ✅ Failures: {results['failure_count']} ≤ {max_failure_count}")
    else:
        print(f"  ❌ Failures: {results['failure_count']} > {max_failure_count}")
        passed = False
    
    # Check success rate
    success_rate = 100.0 - results["error_rate"]
    if success_rate >= min_success_rate:
        print(f"  ✅ Success rate: {success_rate:.1f}% ≥ {min_success_rate}%")
    else:
        print(f"  ❌ Success rate: {success_rate:.1f}% < {min_success_rate}%")
        passed = False
    
    return passed

def main():
    """Main load test execution and validation"""
    print("🏋️ Stage 8: Load Canary Test")
    print("=" * 40)
    
    # Check if server is running
    try:
        import requests
        response = requests.get("http://localhost:8001/health", timeout=5)
        if response.status_code != 200:
            print("❌ Server not responding at http://localhost:8001")
            print("   Start with: python autogen_api_shim.py")
            return 1
        print("✅ Server health check passed")
    except Exception as e:
        print(f"❌ Server health check failed: {e}")
        print("   Start with: python autogen_api_shim.py")
        return 1
    
    # Clean up old test results
    for file in ["locust_out_stats.csv", "locust_out_failures.csv", "locust_out_stats_history.csv"]:
        if Path(file).exists():
            os.remove(file)
    
    # Run load test
    test_success = run_locust_test()
    
    if not test_success:
        print("❌ Load test execution failed")
        return 1
    
    # Parse and validate results
    results = parse_locust_results()
    criteria_passed = validate_acceptance_criteria(results)
    
    if criteria_passed:
        print("\n🎯 Stage 8: PASS - Load test acceptance criteria met")
        return 0
    else:
        print("\n❌ Stage 8: FAIL - Load test acceptance criteria not met")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 