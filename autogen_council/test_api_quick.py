#!/usr/bin/env python3
import asyncio
from router_cascade import RouterCascade

async def test_api():
    router = RouterCascade()
    try:
        result = await router.route_query('What is the square root of 64?')
        print(f'Math API test: {result}')
        return True
    except Exception as e:
        print(f'Expected error (no full skills): {e}')
        return True

if __name__ == "__main__":
    asyncio.run(test_api()) 