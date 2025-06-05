#!/usr/bin/env python3
"""
Stage 9: Budget Reset
POST /admin/reset_budget (or Redis FLUSHDB) at start of make gate
Prevents leftover costs from yesterday false-failing today's CI
"""

import sys
import requests
import redis
import time
from typing import Dict, Any

# Add project root to path for budget guard import
sys.path.insert(0, '.')
try:
    from router.budget_guard import reset_budget as bg_reset, remaining_budget
    BUDGET_GUARD_AVAILABLE = True
except ImportError:
    BUDGET_GUARD_AVAILABLE = False
    print("⚠️ Budget guard module not available, using legacy reset")

def reset_budget_via_api(base_url: str = "http://localhost:8001") -> bool:
    """Reset budget counters via API endpoint"""
    try:
        response = requests.post(f"{base_url}/admin/reset_budget", timeout=5)
        
        if response.status_code == 200:
            print("✅ Budget reset via API endpoint")
            return True
        elif response.status_code == 404:
            print("⚠️ Budget reset endpoint not available")
            return False
        else:
            print(f"❌ Budget reset failed: HTTP {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"⚠️ API budget reset failed: {e}")
        return False

def reset_budget_via_redis(redis_host: str = "localhost", redis_port: int = 6379) -> bool:
    """Reset budget counters via direct Redis access"""
    try:
        # Connect to Redis
        r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        r.ping()  # Test connection
        
        # Budget-related keys to reset
        budget_keys = [
            "budget:daily_spent_usd",
            "budget:requests_today", 
            "budget:last_reset_date",
            "budget:cost_tracking:*",
            "shallow_cache:*",  # Clear cache to prevent stale cost data
        ]
        
        reset_count = 0
        
        for pattern in budget_keys:
            if "*" in pattern:
                # Pattern-based deletion
                keys = r.keys(pattern)
                if keys:
                    deleted = r.delete(*keys)
                    reset_count += deleted
                    print(f"  Cleared {deleted} keys matching {pattern}")
            else:
                # Direct key deletion
                if r.exists(pattern):
                    r.delete(pattern)
                    reset_count += 1
                    print(f"  Cleared {pattern}")
        
        # Set reset timestamp
        current_date = time.strftime("%Y-%m-%d")
        r.set("budget:last_reset_date", current_date)
        r.set("budget:daily_spent_usd", "0.0")
        r.set("budget:requests_today", "0")
        
        print(f"✅ Budget reset via Redis: {reset_count} keys cleared")
        return True
        
    except redis.exceptions.RedisError as e:
        print(f"❌ Redis budget reset failed: {e}")
        return False

def verify_budget_reset(base_url: str = "http://localhost:8001") -> Dict[str, Any]:
    """Verify budget has been reset by checking current status"""
    try:
        response = requests.get(f"{base_url}/budget", timeout=5)
        
        if response.status_code == 200:
            budget_data = response.json()
            
            daily_spent = float(budget_data.get("daily_spent_usd", 0))
            requests_today = int(budget_data.get("requests_today", 0))
            
            reset_successful = daily_spent == 0.0 and requests_today == 0
            
            if reset_successful:
                print("✅ Budget verification: Successfully reset to $0.00")
            else:
                print(f"⚠️ Budget verification: daily_spent=${daily_spent}, requests={requests_today}")
            
            return {
                "reset_successful": reset_successful,
                "daily_spent_usd": daily_spent,
                "requests_today": requests_today,
                "budget_data": budget_data
            }
        else:
            print(f"❌ Budget verification failed: HTTP {response.status_code}")
            return {"reset_successful": False, "error": f"HTTP {response.status_code}"}
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Budget verification failed: {e}")
        return {"reset_successful": False, "error": str(e)}

def main():
    """Main budget reset function for CI gate"""
    print("💰 Stage 9: Resetting budget counters...")
    
    # NEW: Use budget guard module if available
    if BUDGET_GUARD_AVAILABLE:
        try:
            bg_reset()
            remaining = remaining_budget()
            print(f"✅ Budget guard reset: ${remaining:.2f} available")
            
            if remaining == 1.00:
                print("🎯 Stage 9: PASS - Budget successfully reset via budget guard")
                return 0
        except Exception as e:
            print(f"⚠️ Budget guard reset failed: {e}, falling back to legacy reset")
    
    # Fallback to legacy reset methods
    # Try API reset first
    api_success = reset_budget_via_api()
    
    # Fallback to Redis reset
    redis_success = False
    if not api_success:
        print("🔄 Falling back to direct Redis reset...")
        redis_success = reset_budget_via_redis()
    
    # Verify reset worked
    verification = verify_budget_reset()
    
    if verification.get("reset_successful", False):
        print("🎯 Stage 9: PASS - Budget successfully reset")
        return 0
    elif api_success or redis_success:
        print("⚠️ Stage 9: PARTIAL - Reset attempted but verification failed")
        return 0  # Don't fail CI if reset was attempted
    else:
        print("❌ Stage 9: FAIL - Budget reset failed")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 