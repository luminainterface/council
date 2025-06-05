#!/usr/bin/env python3
"""Clear cache properly using the correct key format"""

import redis
import hashlib

r = redis.Redis(host='localhost', port=6379, db=1, decode_responses=True)

queries = [
    'template this needs custom_function',
    'todo: implement unsupported number theory',
    'this has template markers custom_function todo'
]

print('🧹 Clearing cache with correct format:')
for query in queries:
    normalized = query.strip().lower()
    sha256_hash = hashlib.sha256(normalized.encode('utf-8')).hexdigest()
    cache_key = f'cache:prompt:{sha256_hash}'
    
    deleted = r.delete(cache_key)
    if deleted:
        print(f'✅ Cleared: {cache_key} for "{query}"')
    else:
        print(f'❌ Not found: {cache_key} for "{query}"')

print('\n🎯 Cache clearing complete!') 