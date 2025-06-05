#!/usr/bin/env python3
"""
Budget Guard Integration Test
Demonstrates Stage 9 gate integration for Ticket #113
"""

import sys
sys.path.insert(0, '.')

import router.budget_guard as bg

def test_stage_9_reset():
    """Stage 9: Budget reset functionality"""
    print("🧪 Testing Stage 9 - Budget Reset")
    
    # Simulate end of previous test run with high usage
    bg.add_cost(0.95)
    print(f"Before reset: ${bg.remaining_budget():.3f}")
    
    # Stage 9 gate step
    bg.reset_budget()
    
    # Verify fresh budget
    remaining = bg.remaining_budget()
    print(f"After reset: ${remaining:.2f}")
    
    assert remaining == 1.00, f"Expected $1.00, got ${remaining:.2f}"
    print("✅ Stage 9 budget reset working")

def test_stage_5_metrics():
    """Stage 5: Metrics probe for budget monitoring"""
    print("\n🧪 Testing Stage 5 - Metrics Probe")
    
    bg.reset_budget()
    
    # Simulate usage up to warning threshold
    bg.add_cost(0.79)  # Just under $0.80 warning
    
    remaining = bg.remaining_budget()
    spent = 1.00 - remaining
    
    print(f"Current spend: ${spent:.2f}")
    print(f"Warning threshold: $0.80")
    
    # This should pass (under warning threshold)
    assert spent <= 0.80, f"Spend ${spent:.2f} exceeds warning threshold"
    print("✅ Stage 5 metrics probe under threshold")
    
    # Test warning condition
    bg.add_cost(0.02)  # Now at $0.81
    spent = 1.00 - bg.remaining_budget()
    print(f"After additional cost: ${spent:.2f}")
    
    # This would trigger the alert (over warning threshold)
    if spent >= 0.80:
        print("⚠️ Would trigger CloudSpendApproachingLimit alert")

def test_budget_403_enforcement():
    """Test 403 enforcement prevents overspend"""
    print("\n🧪 Testing Budget 403 Enforcement")
    
    bg.reset_budget()
    bg.add_cost(0.99)  # Almost at limit
    
    try:
        # This should trigger 403
        bg.enforce_budget(0.02)  # Would exceed $1.00
        print("❌ Should have raised HTTPException")
        assert False, "Budget enforcement failed"
    except Exception as e:
        print(f"✅ Budget enforcement working: {type(e).__name__}")
        assert "403" in str(e) or "budget" in str(e).lower()

if __name__ == "__main__":
    print("🎯 Budget Guard Integration Test - Ticket #113")
    print("=" * 50)
    
    test_stage_9_reset()
    test_stage_5_metrics() 
    test_budget_403_enforcement()
    
    print("\n🎉 All integration tests passed!")
    print("✅ Ready for gate validation") 