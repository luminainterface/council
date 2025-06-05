#!/usr/bin/env python3
"""Check if cache is interfering with stub detection"""

import sys
sys.path.append('.')

try:
    from cache.shallow_cache import get_cached_response
    
    queries = [
        'template this needs custom_function',
        'todo: implement unsupported number theory',
        'this has template markers custom_function todo'
    ]
    
    print("🔍 Checking shallow cache for stub queries:")
    for query in queries:
        try:
            cached = get_cached_response(query)
            if cached:
                print(f'CACHED: "{query}" -> conf={cached.confidence:.2f}')
                print(f'  Model: {cached.model_used}')
                print(f'  Response: {cached.text[:50]}...')
            else:
                print(f'NO CACHE: "{query}"')
        except Exception as e:
            print(f'Cache error for "{query}": {e}')
    
except ImportError as e:
    print(f"Shallow cache not available: {e}")
except Exception as e:
    print(f"Cache check failed: {e}") 