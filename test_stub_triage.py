#!/usr/bin/env python3
import json, requests, sys
tests = ['hi', '2+2', 'Write a python factorial', 'Unsupported edge case']
for q in tests:
    try:
        r = requests.post('http://localhost:8000/vote', json={'prompt': q, 'session_id': 'test'}, timeout=5).json()
        txt = r.get('text','')[:120]
        stub = any(p in txt.lower() for p in ['todo','template','custom_function'])
        print(f'{q[:20]:<25} → {r.get("specialist", "unknown")} | stub={stub} | {txt}')
    except Exception as e:
        print(f'{q[:20]:<25} → ERROR: {str(e)[:50]}') 