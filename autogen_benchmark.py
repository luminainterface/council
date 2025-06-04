#!/usr/bin/env python3
"""
AutoGen Performance Benchmark
============================
"""
import sys
import os
sys.path.append('fork/swarm_autogen')

from router_cascade import route_and_execute
import asyncio
import time

async def run_autogen_benchmark():
    print('🚢 AUTOGEN PERFORMANCE BENCHMARK')
    print('='*50)

    # Test 10 different queries with timing
    tests = [
        'What is 8 factorial?',
        'Calculate 25% of 240', 
        'Write a function to find GCD',
        'If A is south of B and B south of C, where is A?',
        'What is machine learning?',
        'Find the area of a triangle with base 6 and height 8',
        'Write a sorting algorithm',
        'What is the speed of light?',
        'Calculate 12 * 15',
        'Is John the parent of Mary?'
    ]

    total_time = 0
    results = []
    
    for i, query in enumerate(tests, 1):
        print(f'\n📝 Test {i}/10: {query[:40]}...')
        start = time.time()
        result = await route_and_execute(query)
        duration = (time.time() - start) * 1000
        total_time += duration
        
        answer = result.get('answer', 'No answer')[:60]
        skill = result.get('skill_type', 'unknown')
        confidence = result.get('confidence', 0.0)
        
        print(f'    ⚡ {duration:5.0f}ms | 🎯 {skill} | 📊 {confidence:.2f}')
        print(f'    💬 {answer}...')
        
        results.append((query, duration, result))
    
    print(f'\n🏁 BENCHMARK COMPLETE:')
    print('='*50)
    print(f'📊 Average latency: {total_time/len(tests):.0f}ms')
    print(f'⏱️ Total time: {total_time/1000:.1f}s') 
    print(f'🚀 Throughput: {len(tests)/(total_time/1000):.1f} QPS')
    
    # Check if we meet performance targets
    avg_latency = total_time/len(tests)
    if avg_latency < 400:
        print(f'\n✅ PERFORMANCE TARGET MET: {avg_latency:.0f}ms < 400ms')
    else:
        print(f'\n❌ PERFORMANCE TARGET MISSED: {avg_latency:.0f}ms > 400ms')
    
    # Domain breakdown
    domain_counts = {}
    for _, _, result in results:
        skill = result.get('skill_type', 'unknown')
        domain_counts[skill] = domain_counts.get(skill, 0) + 1
    
    print(f'\n📈 Domain Coverage:')
    for domain, count in domain_counts.items():
        print(f'    {domain}: {count} queries')
    
    return results

if __name__ == "__main__":
    asyncio.run(run_autogen_benchmark()) 