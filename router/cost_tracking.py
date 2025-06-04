#!/usr/bin/env python3
"""
Router 2.0: Cost-Aware Scheduling System

Track rolling GPU seconds and dollar costs per model head, automatically
down-shift to cheaper models when burn-rate exceeds budget thresholds.
"""

import os
import time
from typing import Dict, List, Optional
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

# Prometheus metrics for cost tracking
try:
    from prometheus_client import Gauge, Summary, Counter
    COST_TOTAL = Gauge('swarm_router_budget_dollars_total', 'Rolling $ spend (24h window)')
    GEN_COST = Summary('swarm_generation_cost_cents', 'Cost per request in cents')
    BUDGET_EXCEEDED = Counter('swarm_budget_exceeded_total', 'Number of budget threshold breaches')
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

# Pricing table: milli-cents per token (realistic GPU costs)
PRICING_TABLE = {
    # Small models - cheap and fast
    "safety_guard_0.3b": 0.02,      # 0.02¢/token
    "mistral_0.5b": 0.03,           # 0.03¢/token  
    "qwen2_0.5b": 0.03,             # 0.03¢/token
    "codellama_0.7b": 0.04,         # 0.04¢/token
    "math_specialist_0.8b": 0.05,   # 0.05¢/token
    "tinyllama_1b": 0.06,           # 0.06¢/token
    
    # Medium models - moderate cost
    "phi2_2.7b": 0.12,              # 0.12¢/token
    "openchat_3.5_0.4b": 0.15,      # 0.15¢/token (despite name, it's larger)
    
    # Large models - expensive but high quality
    "mistral_7b_instruct": 0.25,    # 0.25¢/token
    "llama2_70b_chat": 1.50,        # 1.50¢/token (when available)
    "mixtral_8x7b": 1.20,           # 1.20¢/token (when available)
}

@dataclass
class CostEntry:
    """Individual cost tracking entry"""
    model: str
    tokens: int
    cost_cents: float
    timestamp: float
    request_id: Optional[str] = None

class CostLedger:
    """Manages cost tracking and budget enforcement"""
    
    def __init__(self, max_budget_dollars: float = 5.0):
        self.max_budget_dollars = max_budget_dollars
        self.cost_history: List[CostEntry] = []
        self.rolling_cost_dollars = 0.0
        self.window_hours = 24  # 24-hour rolling window
        
    def cleanup_old_entries(self):
        """Remove cost entries older than the rolling window"""
        cutoff_time = time.time() - (self.window_hours * 3600)
        
        # Remove old entries
        old_count = len(self.cost_history)
        self.cost_history = [entry for entry in self.cost_history if entry.timestamp >= cutoff_time]
        
        if len(self.cost_history) != old_count:
            # Recalculate rolling cost
            self.rolling_cost_dollars = sum(entry.cost_cents for entry in self.cost_history) / 100.0
            
            if PROMETHEUS_AVAILABLE:
                COST_TOTAL.set(self.rolling_cost_dollars)
    
    def debit(self, model: str, tokens: int, request_id: Optional[str] = None) -> float:
        """
        Record cost for a generation and return cost in cents
        
        Args:
            model: Model name that generated the tokens
            tokens: Number of tokens generated
            request_id: Optional request ID for tracking
            
        Returns:
            Cost in cents for this generation
        """
        # Get pricing (fallback to medium cost if model not found)
        price_per_token = PRICING_TABLE.get(model, 0.10)  # 0.10¢ default
        
        # Calculate cost
        cost_cents = price_per_token * tokens
        
        # Create cost entry
        entry = CostEntry(
            model=model,
            tokens=tokens,
            cost_cents=cost_cents,
            timestamp=time.time(),
            request_id=request_id
        )
        
        # Add to history
        self.cost_history.append(entry)
        self.rolling_cost_dollars += cost_cents / 100.0
        
        # Cleanup old entries periodically
        if len(self.cost_history) % 100 == 0:  # Every 100 requests
            self.cleanup_old_entries()
        
        # Update Prometheus metrics
        if PROMETHEUS_AVAILABLE:
            COST_TOTAL.set(self.rolling_cost_dollars)
            GEN_COST.observe(cost_cents)
        
        print(f"💰 Cost tracking: {model} ${cost_cents/100:.4f} ({tokens} tokens)")
        
        return cost_cents
    
    def is_budget_exceeded(self) -> bool:
        """Check if current spending exceeds budget"""
        return self.rolling_cost_dollars > self.max_budget_dollars
    
    def get_budget_status(self) -> Dict[str, float]:
        """Get current budget status"""
        return {
            "rolling_cost_dollars": self.rolling_cost_dollars,
            "max_budget_dollars": self.max_budget_dollars,
            "utilization_percent": (self.rolling_cost_dollars / self.max_budget_dollars) * 100,
            "remaining_dollars": self.max_budget_dollars - self.rolling_cost_dollars,
            "window_hours": self.window_hours
        }
    
    def get_cost_by_model(self) -> Dict[str, float]:
        """Get cost breakdown by model (last 24h)"""
        self.cleanup_old_entries()
        
        model_costs = defaultdict(float)
        for entry in self.cost_history:
            model_costs[entry.model] += entry.cost_cents / 100.0
            
        return dict(model_costs)
    
    def downgrade_route(self, original_route: List[str]) -> List[str]:
        """
        Downgrade route to cheaper models when budget is exceeded
        
        Args:
            original_route: Original model selection
            
        Returns:
            Cost-optimized route with cheaper models
        """
        if not self.is_budget_exceeded():
            return original_route
        
        # Budget exceeded - switch to cheapest available models
        if PROMETHEUS_AVAILABLE:
            BUDGET_EXCEEDED.inc()
            
        print("⚠️ Budget exceeded! Switching to low-cost models...")
        
        # Create cost-ordered model list (cheapest first)
        available_models = list(PRICING_TABLE.keys())
        cheap_models = sorted(available_models, key=lambda m: PRICING_TABLE[m])
        
        # Map original intent to cheap alternatives
        cheap_route = []
        for model in original_route:
            if "math" in model.lower():
                # Keep math specialist as it's already cheap
                cheap_route.append("math_specialist_0.8b")
            elif "code" in model.lower():
                # Use cheapest code model
                cheap_route.append("codellama_0.7b")
            elif "safety" in model.lower():
                # Safety guard is already cheapest
                cheap_route.append("safety_guard_0.3b") 
            else:
                # Default to cheapest general model
                cheap_route.append("mistral_0.5b")
                
        return cheap_route
    
    def reset_budget(self):
        """Reset budget tracking (useful for testing)"""
        self.cost_history.clear()
        self.rolling_cost_dollars = 0.0
        if PROMETHEUS_AVAILABLE:
            COST_TOTAL.set(0.0)

# Global cost ledger instance
cost_ledger = CostLedger(
    max_budget_dollars=float(os.getenv("SWARM_BUDGET", "5.0"))
)

def debit(model: str, tokens: int, request_id: Optional[str] = None) -> float:
    """Global cost tracking function"""
    return cost_ledger.debit(model, tokens, request_id)

def is_budget_exceeded() -> bool:
    """Check if budget is exceeded"""
    return cost_ledger.is_budget_exceeded()

def downgrade_route(route: List[str]) -> List[str]:
    """Downgrade route for cost optimization"""
    return cost_ledger.downgrade_route(route)

def get_budget_status() -> Dict[str, float]:
    """Get current budget status"""
    return cost_ledger.get_budget_status()

def get_cost_breakdown() -> Dict[str, float]:
    """Get cost breakdown by model"""
    return cost_ledger.get_cost_by_model() 