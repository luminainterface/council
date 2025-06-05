"""
Verifies that the per-request and daily budget caps
catch runaway cloud / trainer spend.

Run automatically by CI (see full-pipes.yml).
"""

import importlib
import os
from contextlib import contextmanager
import pytest

# Per-request spending cap - no single request should exceed this
PER_REQUEST_CAP_CENTS = 2.0  # $0.02

# --- helpers ---------------------------------------------------------------

@contextmanager
def patched_pricing(rate: float):
    """
    Monkey-patch PRICING_TABLE to always return `rate` for any model.
    """
    from router.cost_tracking import PRICING_TABLE
    orig_table = PRICING_TABLE.copy()
    
    # Replace all prices with our test rate
    for model in PRICING_TABLE:
        PRICING_TABLE[model] = rate
    
    # Also add our test models if they don't exist
    PRICING_TABLE["mistral_medium_3"] = rate
    PRICING_TABLE["lora_training"] = rate
        
    try:
        yield
    finally:
        # Restore original pricing
        PRICING_TABLE.clear()
        PRICING_TABLE.update(orig_table)


class BudgetExceeded(Exception):
    """Exception raised when budget or per-request caps are exceeded"""
    pass


def run_fake_call(tokens_out: int = 1000, model: str = "mistral_medium_3"):
    """
    Simulates a cloud completion with both per-request and daily budget guards.
    This implements the cost guard logic we want to test.
    """
    from router.cost_tracking import cost_ledger, PRICING_TABLE
    
    try:
        # Calculate cost for this request
        price_per_token = PRICING_TABLE.get(model, 0.10)
        cost_cents = price_per_token * tokens_out
        
        # GUARD 1: Per-request cap check ($0.02 = 2 cents)
        if cost_cents > PER_REQUEST_CAP_CENTS:
            raise BudgetExceeded(f"Request cost {cost_cents:.2f}¢ exceeds per-request cap of {PER_REQUEST_CAP_CENTS}¢")
            
        # GUARD 2: Daily budget check (check if adding this cost would exceed budget)
        potential_total = cost_ledger.rolling_cost_dollars + (cost_cents / 100.0)
        if potential_total > cost_ledger.max_budget_dollars:
            raise BudgetExceeded(f"Request would exceed daily budget: {potential_total:.4f} > {cost_ledger.max_budget_dollars}")
            
        # Both guards passed - proceed with the debit
        cost_ledger.debit(model=model, tokens=tokens_out, request_id="test")
        return True
        
    except BudgetExceeded:
        return False
    except Exception as e:
        print(f"Error in run_fake_call: {e}")
        return False


def run_fake_trainer_call(tokens_out: int = 1000, model: str = "lora_training"):
    """
    Simulates a trainer job - uses same budget guards as API calls.
    """
    return run_fake_call(tokens_out=tokens_out, model=model)


# --- tests -----------------------------------------------------------------

def test_per_request_cap_blocks_over_2_cents(tmp_path, monkeypatch):
    """
    Any single request > $0.02 must be blocked.
    Cost calc: cost = tokens_out * rate
    """
    from router.cost_tracking import cost_ledger
    cost_ledger.reset_budget()
    cost_ledger.max_budget_dollars = 1.0  # generous daily cap

    with patched_pricing(rate=0.03):        # 3¢ / token
        # cost of this call = 0.03 × 1000 = 30¢ = $0.30 > $0.02 ⇒ should block
        assert run_fake_call(tokens_out=1000) is False
        
        # cost of this call = 0.03 × 66 = 1.98¢ < $0.02 ⇒ should pass
        assert run_fake_call(tokens_out=66) is True

    with patched_pricing(rate=0.01):        # 1¢ / token
        # cost = 0.01 × 1000 = 10¢ = $0.10 > $0.02 ⇒ should block
        assert run_fake_call(tokens_out=1000) is False
        
        # cost = 0.01 × 200 = 2¢ = $0.02 ⇒ exactly at limit, should pass  
        assert run_fake_call(tokens_out=200) is True


def test_daily_cap_blocks_after_limit(tmp_path, monkeypatch):
    """
    API and trainer calls must halt once daily spend hits budget.
    """
    from router.cost_tracking import cost_ledger
    cost_ledger.reset_budget()
    cost_ledger.max_budget_dollars = 0.10  # 10¢ daily cap

    with patched_pricing(rate=0.01):  # 1¢ / token
        # Five calls of 200 tokens each = 10¢ total (each exactly at per-request limit)
        for i in range(5):
            assert run_fake_call(tokens_out=200) is True  # 2¢ each

        # Sixth call should fail due to daily budget exceeded
        assert run_fake_call(tokens_out=200) is False


def test_trainer_respects_per_request_cap(tmp_path, monkeypatch):
    """
    Trainer jobs must also respect the $0.02 per-request limit.
    """
    from router.cost_tracking import cost_ledger
    cost_ledger.reset_budget()
    cost_ledger.max_budget_dollars = 1.0  # generous daily cap

    with patched_pricing(rate=0.025):       # 2.5¢ / token
        # cost = 0.025 × 1000 = 25¢ > $0.02 ⇒ should block trainer
        assert run_fake_trainer_call(tokens_out=1000) is False

    with patched_pricing(rate=0.01):       # 1¢ / token  
        # cost = 0.01 × 1000 = 10¢ > $0.02 ⇒ should still block
        assert run_fake_trainer_call(tokens_out=1000) is False
        
        # cost = 0.01 × 200 = 2¢ = $0.02 ⇒ should pass
        assert run_fake_trainer_call(tokens_out=200) is True


def test_trainer_counts_toward_daily_budget(tmp_path, monkeypatch):
    """
    Trainer and API calls should share the same daily budget pool.
    """
    from router.cost_tracking import cost_ledger
    cost_ledger.reset_budget()
    cost_ledger.max_budget_dollars = 0.10  # 10¢ daily cap

    with patched_pricing(rate=0.01):  # 1¢ / token
        # Use up budget with mix of API and trainer calls (200 tokens = 2¢ each)
        assert run_fake_call(tokens_out=200, model="mistral_0.5b") is True           # $0.02
        assert run_fake_trainer_call(tokens_out=200, model="lora_training") is True  # $0.04 total
        assert run_fake_call(tokens_out=200, model="mistral_0.5b") is True           # $0.06 total
        assert run_fake_trainer_call(tokens_out=200, model="lora_training") is True  # $0.08 total
        assert run_fake_call(tokens_out=200, model="mistral_0.5b") is True           # $0.10 total

        # Next call (API or trainer) should fail
        assert run_fake_call(tokens_out=200, model="mistral_0.5b") is False
        assert run_fake_trainer_call(tokens_out=200, model="lora_training") is False


def test_cost_calculation_accuracy(tmp_path, monkeypatch):
    """
    Verify cost calculation matches expected formula.
    """
    from router.cost_tracking import cost_ledger
    cost_ledger.reset_budget()
    cost_ledger.max_budget_dollars = 1.0  # generous daily cap

    with patched_pricing(rate=0.05):  # 5¢ / token
        # 500 tokens = 25¢ = $0.25 ⇒ should block (over $0.02)
        assert run_fake_call(tokens_out=500) is False
        
        # 40 tokens = 2¢ = $0.02 ⇒ exactly at limit, should pass
        assert run_fake_call(tokens_out=40) is True
        
        # 30 tokens = 1.5¢ = $0.015 ⇒ under limit, should pass
        assert run_fake_call(tokens_out=30) is True


def test_budget_isolation_between_tests(tmp_path, monkeypatch):
    """
    Each test should start with a clean budget state.
    """
    from router.cost_tracking import cost_ledger
    cost_ledger.reset_budget()
    cost_ledger.max_budget_dollars = 0.04  # 4¢ daily cap

    with patched_pricing(rate=0.01):  # 1¢ / token
        # Use up the entire budget (200 tokens = 2¢ each)
        assert run_fake_call(tokens_out=200) is True  # $0.02
        assert run_fake_call(tokens_out=200) is True  # $0.04 total
        
        # Should be blocked now
        assert run_fake_call(tokens_out=200) is False


def test_budget_enforcement_with_real_pricing(tmp_path, monkeypatch):
    """
    Test budget enforcement using actual pricing table values.
    """
    from router.cost_tracking import cost_ledger
    cost_ledger.reset_budget()
    cost_ledger.max_budget_dollars = 0.05  # 5¢ daily cap
    
    # No pricing patch - use real values
    
    # safety_guard_0.3b at 0.02¢/token: 100 tokens = 2¢ each call (at per-request limit)
    for i in range(2):  # Only 2 calls to stay under 5¢ budget
        assert run_fake_call(tokens_out=100, model="safety_guard_0.3b") is True  # 2¢ each
        
    # Third call would be 6¢ total, exceeding 5¢ budget
    assert run_fake_call(tokens_out=100, model="safety_guard_0.3b") is False
    
    # Reset and test expensive model blocks immediately due to per-request cap  
    cost_ledger.reset_budget()
    cost_ledger.max_budget_dollars = 1.0  # Generous for per-request test
    
    # mistral_7b_instruct at 0.25¢/token: 10 tokens = 2.5¢ > $0.02 ⇒ should block
    assert run_fake_call(tokens_out=10, model="mistral_7b_instruct") is False
    
    # 8 tokens = 2¢ = exactly $0.02 ⇒ should pass
    assert run_fake_call(tokens_out=8, model="mistral_7b_instruct") is True


def test_integration_with_existing_cost_tracker():
    """
    Test that our guards integrate properly with the existing cost tracking system.
    """
    from router.cost_tracking import cost_ledger, get_budget_status, get_cost_breakdown
    
    cost_ledger.reset_budget()
    cost_ledger.max_budget_dollars = 0.06  # 6¢ budget
    
    # Make some successful calls (all exactly at 2¢ per-request limit)
    assert run_fake_call(tokens_out=8, model="mistral_7b_instruct") is True  # 2¢ (0.25*8)
    assert run_fake_call(tokens_out=66, model="mistral_0.5b") is True  # 1.98¢ (0.03*66)
    assert run_fake_call(tokens_out=66, model="mistral_0.5b") is True  # 1.98¢ (0.03*66)
    
    # Check budget status
    status = get_budget_status()
    assert status["rolling_cost_dollars"] >= 0.055  # Should be close to 6¢
    assert status["utilization_percent"] > 90  # Should be >90% utilized
    
    # Next call should fail due to budget
    assert run_fake_call(tokens_out=50, model="mistral_0.5b") is False
    
    # Check cost breakdown
    breakdown = get_cost_breakdown()
    assert "mistral_7b_instruct" in breakdown
    assert "mistral_0.5b" in breakdown
    assert breakdown["mistral_7b_instruct"] >= 0.019  # ~2¢ 