import pytest
from fastapi import HTTPException
import router.budget_guard as bg

def test_budget_reset_and_enforce():
    """Test basic budget operations with floating point tolerance"""
    bg.reset_budget()
    assert bg.remaining_budget() == 1.00
    
    bg.add_cost(0.95)
    remaining = bg.remaining_budget()
    assert abs(remaining - 0.05) < 0.001  # Allow for floating point precision
    
    # Should raise HTTPException when exceeding budget
    with pytest.raises(HTTPException) as exc_info:
        bg.enforce_budget(0.10)
    
    assert exc_info.value.status_code == 403
    assert "Daily cloud-budget exhausted" in exc_info.value.detail

def test_budget_enforce_exactly_at_limit():
    """Test enforcement at exact budget limit"""
    bg.reset_budget()
    
    # Should pass when exactly at limit
    bg.enforce_budget(1.00)
    
    # Add the cost
    bg.add_cost(1.00)
    
    # Any additional cost should fail
    with pytest.raises(HTTPException):
        bg.enforce_budget(0.01)

def test_budget_multiple_adds():
    """Test multiple cost additions"""
    bg.reset_budget()
    
    costs = [0.25, 0.30, 0.15]
    for cost in costs:
        bg.add_cost(cost)
    
    # Total should be 0.70, remaining 0.30
    remaining = bg.remaining_budget()
    assert abs(remaining - 0.30) < 0.001

if __name__ == "__main__":
    # Quick test run
    test_budget_reset_and_enforce()
    test_budget_enforce_exactly_at_limit() 
    test_budget_multiple_adds()
    print("✅ All budget guard tests passed!") 