#!/usr/bin/env python3
"""Clear cached stub responses to enable fresh stub detection"""

import sys
sys.path.append('.')

try:
    from cache.shallow_cache import clear_cache_entry
    
    stub_queries = [
        'template this needs custom_function',
        'todo: implement unsupported number theory', 
        'this has template markers custom_function todo'
    ]
    
    print("🧹 Clearing cached stub responses:")
    for query in stub_queries:
        try:
            cleared = clear_cache_entry(query)
            if cleared:
                print(f'✅ Cleared: "{query}"')
            else:
                print(f'❌ Not found: "{query}"')
        except Exception as e:
            print(f'Clear error for "{query}": {e}')
    
    print("\n🎯 Cache cleared! Stub detection should now work.")
    
except ImportError as e:
    print(f"Shallow cache module not available: {e}")
    print("Trying direct Redis clear...")
    
    try:
        import redis
        import hashlib
        
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        
        stub_queries = [
            'template this needs custom_function',
            'todo: implement unsupported number theory',
            'this has template markers custom_function todo'
        ]
        
        print("🧹 Direct Redis cache clear:")
        for query in stub_queries:
            # Create the same cache key format
            query_hash = hashlib.md5(query.encode()).hexdigest()[:16]
            cache_key = f"shallow_cache:{query_hash}"
            
            deleted = r.delete(cache_key)
            if deleted:
                print(f'✅ Deleted Redis key: {cache_key} for "{query}"')
            else:
                print(f'❌ Key not found: {cache_key} for "{query}"')
                
    except Exception as e:
        print(f"Redis clear failed: {e}")

except Exception as e:
    print(f"Cache clear failed: {e}") 