#!/usr/bin/env python3
"""Test scrub function on actual API response patterns"""

import sys
sys.path.append('.')
from router_cascade import scrub

# Test with the exact responses from the API
candidates = [
    {'text': 'I can help research DRAFT_FROM_AGENT0: I can help with template this needs custom_function', 'confidence': 0.90},
    {'text': 'I can help research DRAFT_FROM_AGENT0: I understand todo: implement unsupported number theory', 'confidence': 0.90}
]

queries = [
    'template this needs custom_function',
    'todo: implement unsupported number theory'
]

print('🧪 Testing scrub function on API-like responses:')
for i, (candidate, query) in enumerate(zip(candidates, queries)):
    result = scrub(candidate.copy(), query)
    print(f'Test {i+1}: {query}')
    print(f'  Input text: {candidate["text"][:50]}...')
    print(f'  Input conf: {candidate["confidence"]}')
    print(f'  Output conf: {result["confidence"]}')
    print(f'  Stub detected: {result.get("stub_detected", False)}')
    print() 