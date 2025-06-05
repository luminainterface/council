import pytest, asyncio
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from router_cascade import RouterCascade

BOILER = """Here is a template for unsupported function call
{{custom_function}}
"""

@pytest.mark.asyncio
async def test_stub_detection():
    router_cascade = RouterCascade()
    r = await router_cascade.route_query(BOILER)
    assert r["confidence"] == 0.0
    assert r.get("meta", {}).get("stub_detected") is True 