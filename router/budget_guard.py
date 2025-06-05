import time, redis
from fastapi import HTTPException

R = redis.Redis.from_url("redis://localhost/2")  # DB 2 reserved for budget
DAILY_LIMIT = 1.00        # USD

KEY = lambda epoch: f"cloud_spend:{time.strftime('%Y-%m-%d', time.gmtime(epoch))}"

def add_cost(amount: float, epoch: float | None = None):
    """Add `amount` (USD) to today's spend."""
    epoch = epoch or time.time()
    R.incrbyfloat(KEY(epoch), amount)

def remaining_budget(epoch: float | None = None) -> float:
    epoch = epoch or time.time()
    spent = float(R.get(KEY(epoch)) or 0)
    return DAILY_LIMIT - spent

def enforce_budget(cost: float):
    """Raise 403 if adding `cost` would breach DAILY_LIMIT."""
    if remaining_budget() - cost < 0:
        raise HTTPException(
            status_code=403,
            detail="Daily cloud-budget exhausted; try again tomorrow."
        )

def reset_budget():
    """Used by Stage 9 gate to flush counter at start of CI run."""
    R.flushdb() 