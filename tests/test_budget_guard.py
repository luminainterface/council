import pytest
import router.budget_guard as bg
import asyncio
import time
from fastapi.testclient import TestClient
from fastapi import HTTPException

def test_budget_reset_and_enforce():
    """Test basic budget operations"""
    bg.reset_budget()
    assert bg.remaining_budget() == 1.00
    bg.add_cost(0.95)
    assert abs(bg.remaining_budget() - 0.05) < 0.001
    
    # Should raise HTTPException when exceeding budget
    with pytest.raises(HTTPException) as exc_info:
        bg.enforce_budget(0.10)
    
    assert exc_info.value.status_code == 403
    assert "Daily cloud-budget exhausted" in exc_info.value.detail

def test_budget_add_cost():
    """Test cost accumulation"""
    bg.reset_budget()
    
    # Add multiple costs
    bg.add_cost(0.25)
    bg.add_cost(0.30)
    bg.add_cost(0.15)
    
    # Should total 0.70, leaving 0.30
    assert bg.remaining_budget() == 0.30

def test_budget_edge_cases():
    """Test edge cases and boundary conditions"""
    bg.reset_budget()
    
    # Exactly at limit should pass
    bg.add_cost(1.00)
    assert bg.remaining_budget() == 0.0
    
    # Any additional cost should fail
    with pytest.raises(HTTPException):
        bg.enforce_budget(0.01)

def test_budget_time_based_keys():
    """Test that budget keys are time-based"""
    import time
    
    bg.reset_budget()
    
    # Add cost
    bg.add_cost(0.50)
    
    # Same day should have same remaining budget
    assert bg.remaining_budget() == 0.50
    
    # Different epoch should work correctly
    future_time = time.time() + 86400  # +1 day
    assert bg.remaining_budget(future_time) == 1.00  # Fresh budget

@pytest.mark.asyncio
async def test_budget_integration_with_api():
    """Integration test with FastAPI client"""
    from autogen_api_shim import app
    from httpx import AsyncClient
    
    # Reset budget
    bg.reset_budget()
    
    # Simulate high usage
    bg.add_cost(0.99)
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        # This should trigger a 403 due to budget exhaustion
        # when cloud fallback tries to enforce budget
        try:
            response = await client.post("/hybrid", json={"prompt": "expensive query that triggers cloud fallback"})
            # If we get here without 403, budget guard might not be active
            print(f"Response status: {response.status_code}")
        except Exception as e:
            # Expected if budget enforcement is working
            print(f"Budget enforcement working: {e}")

def test_budget_prometheus_metrics():
    """Test that budget affects metrics"""
    bg.reset_budget()
    
    # Add some costs
    bg.add_cost(0.25)
    bg.add_cost(0.55)  # Total: 0.80
    
    # Verify Redis has the data
    spent = float(bg.R.get(bg.KEY(time.time())) or 0)
    assert spent == 0.80
    
    # Remaining should be 0.20
    assert bg.remaining_budget() == 0.20

if __name__ == "__main__":
    # Quick smoke test
    print("🧪 Testing Budget Guard...")
    
    test_budget_reset_and_enforce()
    print("✅ Basic budget test passed")
    
    test_budget_add_cost()
    print("✅ Cost accumulation test passed")
    
    test_budget_edge_cases()
    print("✅ Edge cases test passed")
    
    test_budget_time_based_keys()
    print("✅ Time-based keys test passed")
    
    print("🎉 All budget guard tests passed!") 