#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')

from router.budget_guard import *

print("🧪 Testing Budget Guard...")
reset_budget()
print(f"Initial budget: ${remaining_budget():.2f}")

add_cost(0.75)
print(f"After adding $0.75: ${remaining_budget():.2f}")

try:
    enforce_budget(0.30)
    print("❌ Should have failed - budget exceeded!")
except Exception as e:
    print(f"✅ Budget enforcement working: {type(e).__name__}")

print("🎉 Budget guard test complete!") 