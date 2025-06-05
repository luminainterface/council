#!/usr/bin/env python3
"""Debug script to test the scrub function"""

import sys
sys.path.append('.')
from router_cascade import scrub

# Test scrub function directly
test_cases = [
    {'text': 'template this needs custom_function', 'confidence': 0.95},
    {'text': 'todo: implement unsupported number theory', 'confidence': 0.95},
    {'text': 'this has template markers custom_function todo', 'confidence': 0.95},
    {'text': 'hello world normal response', 'confidence': 0.95}
]

print("🧪 Testing scrub function directly:")
print("=" * 50)

for i, candidate in enumerate(test_cases):
    result = scrub(candidate.copy(), candidate['text'])
    print(f'Test {i+1}: "{candidate["text"]}"')
    print(f'  Input confidence: {candidate["confidence"]}')
    print(f'  Output confidence: {result["confidence"]}')
    print(f'  Stub detected: {result.get("stub_detected", "None")}')
    print(f'  Location: {result.get("stub_location", "None")}')
    print()

print("🧪 Testing stub patterns:")
from router_cascade import STUB_PATTERNS, STUB_MARKERS

test_text = "template this needs custom_function"
print(f'Testing text: "{test_text}"')

for marker in STUB_MARKERS:
    if marker.lower() in test_text.lower():
        print(f'  ✅ Marker found: "{marker}"')

for pattern in STUB_PATTERNS:
    if pattern.search(test_text):
        print(f'  ✅ Pattern matched: {pattern.pattern}') 