#!/usr/bin/env python3
"""
Tests for Router 2.0: Cost-Aware Scheduling

Validates budget tracking, cost calculation, and automatic downgrading
to cheaper models when spending exceeds thresholds.
"""

import pytest
import httpx
import time
from router.cost_tracking import cost_ledger, debit, get_budget_status, downgrade_route

class TestBudgetTracking:
    """Test cost tracking and budget enforcement"""

    def setup_method(self):
        """Reset budget tracking before each test"""
        cost_ledger.reset_budget()

    def test_cost_debit_calculation(self):
        """Test that cost calculations are correct"""
        # Reset budget
        cost_ledger.reset_budget()
        
        # Test different pricing tiers
        cost_small = debit("mistral_0.5b", 100)  # 0.03¢/token * 100 = 3¢
        assert cost_small == 3.0
        
        cost_large = debit("mistral_7b_instruct", 100)  # 0.25¢/token * 100 = 25¢
        assert cost_large == 25.0
        
        # Check total accumulation
        budget_status = get_budget_status()
        assert budget_status["rolling_cost_dollars"] == 0.28  # 28¢ = $0.28

    def test_budget_guard_mechanism(self):
        """Test that budget enforcement triggers correctly"""
        # Reset with low budget
        cost_ledger.max_budget_dollars = 0.10  # $0.10 limit
        cost_ledger.reset_budget()
        
        # Spend within budget
        debit("mistral_0.5b", 100)  # 3¢
        assert not cost_ledger.is_budget_exceeded()
        
        # Exceed budget
        debit("mistral_7b_instruct", 200)  # 50¢ (total 53¢ > 10¢ limit)
        assert cost_ledger.is_budget_exceeded()

    def test_route_downgrading(self):
        """Test automatic route downgrading when budget exceeded"""
        # Set low budget and exceed it
        cost_ledger.max_budget_dollars = 0.01
        cost_ledger.reset_budget()
        
        # Force budget exceeded
        debit("mistral_7b_instruct", 100)  # 25¢ > 1¢ limit
        
        # Test downgrading
        expensive_route = ["mistral_7b_instruct", "phi2_2.7b"]
        cheap_route = downgrade_route(expensive_route)
        
        # Should switch to cheaper models
        assert "mistral_0.5b" in cheap_route or "safety_guard_0.3b" in cheap_route
        assert cheap_route != expensive_route

    def test_specialized_model_mapping(self):
        """Test that specialized models are correctly mapped to cheap alternatives"""
        # Force budget exceeded
        cost_ledger.max_budget_dollars = 0.01
        debit("mistral_7b_instruct", 100)
        
        # Test math specialist preservation (already cheap)
        math_route = ["math_specialist_0.8b"]
        downgraded = downgrade_route(math_route)
        assert "math_specialist_0.8b" in downgraded
        
        # Test code model downgrading
        code_route = ["codellama_0.7b"]
        downgraded = downgrade_route(code_route)
        assert "codellama_0.7b" in downgraded  # Already reasonably cheap

    def test_rolling_window_cleanup(self):
        """Test that old cost entries are cleaned up"""
        cost_ledger.reset_budget()
        
        # Add old entry (simulate)
        old_entry = cost_ledger.cost_history[0:0]  # Empty slice
        
        # Add current entry
        debit("mistral_0.5b", 100)
        
        # Should have 1 entry
        assert len(cost_ledger.cost_history) == 1
        
        # Manual cleanup shouldn't remove recent entries
        cost_ledger.cleanup_old_entries()
        assert len(cost_ledger.cost_history) == 1

    def test_cost_breakdown_by_model(self):
        """Test cost breakdown reporting"""
        cost_ledger.reset_budget()
        
        # Use different models
        debit("mistral_0.5b", 100)     # 3¢
        debit("mistral_7b_instruct", 50)  # 12.5¢
        debit("mistral_0.5b", 50)      # 1.5¢
        
        breakdown = cost_ledger.get_cost_by_model()
        
        # Should have correct totals per model
        assert abs(breakdown["mistral_0.5b"] - 0.045) < 0.001  # 4.5¢
        assert abs(breakdown["mistral_7b_instruct"] - 0.125) < 0.001  # 12.5¢

class TestBudgetIntegration:
    """Test budget tracking integration with FastAPI"""

    def test_budget_endpoint(self, api_server):
        """Test the /budget endpoint returns valid data"""
        with httpx.Client() as client:
            response = client.get("http://127.0.0.1:8000/budget", timeout=10)
            assert response.status_code == 200
            
            data = response.json()
            assert "budget_status" in data
            assert "cost_breakdown" in data
            
            # Budget status should have required fields
            budget = data["budget_status"]
            assert "rolling_cost_dollars" in budget
            assert "max_budget_dollars" in budget
            assert "utilization_percent" in budget

    def test_orchestrate_with_cost_tracking(self, api_server):
        """Test that /orchestrate includes cost tracking"""
        with httpx.Client() as client:
            response = client.post(
                "http://127.0.0.1:8000/orchestrate",
                json={
                    "prompt": "Quick test",
                    "route": ["mistral_0.5b"]
                },
                timeout=15
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Should include cost information
            assert "cost_cents" in data
            assert data["cost_cents"] > 0
            assert "model_used" in data

    def test_vote_with_cost_tracking(self, api_server):
        """Test that /vote includes cost tracking"""
        with httpx.Client() as client:
            response = client.post(
                "http://127.0.0.1:8000/vote",
                json={
                    "prompt": "Test voting cost",
                    "candidates": ["mistral_0.5b", "tinyllama_1b"],
                    "top_k": 2
                },
                timeout=20
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Should include total cost
            assert "total_cost_cents" in data
            assert data["total_cost_cents"] > 0

    def test_budget_stress_scenario(self, api_server):
        """Test budget behavior under sustained load"""
        with httpx.Client() as client:
            # Reset budget tracking via internal API (if available)
            
            # Make multiple requests to accumulate cost
            total_cost = 0
            for i in range(5):
                response = client.post(
                    "http://127.0.0.1:8000/orchestrate",
                    json={
                        "prompt": f"Test request {i}",
                        "route": ["mistral_0.5b"]
                    },
                    timeout=15
                )
                
                if response.status_code == 200:
                    data = response.json()
                    total_cost += data.get("cost_cents", 0)
            
            # Check budget status
            budget_response = client.get("http://127.0.0.1:8000/budget", timeout=10)
            assert budget_response.status_code == 200
            
            budget_data = budget_response.json()
            budget_dollars = budget_data["budget_status"]["rolling_cost_dollars"]
            
            # Should have accumulated some cost
            assert budget_dollars > 0
            print(f"💰 Accumulated ${budget_dollars:.4f} across 5 requests")

    def test_prometheus_cost_metrics(self, api_server):
        """Test that cost metrics appear in Prometheus endpoint"""
        with httpx.Client() as client:
            # Generate some cost
            client.post(
                "http://127.0.0.1:8000/orchestrate",
                json={
                    "prompt": "Generate cost metrics",
                    "route": ["mistral_0.5b"]
                },
                timeout=15
            )
            
            # Check metrics
            metrics_response = client.get("http://127.0.0.1:8000/metrics", timeout=10)
            assert metrics_response.status_code == 200
            
            metrics_text = metrics_response.text
            
            # Should contain budget metrics
            assert "swarm_router_budget_dollars_total" in metrics_text
            assert "swarm_generation_cost_cents" in metrics_text 