#!/usr/bin/env python3
"""
Smoke Gauntlet - Quick 30-prompt test
=====================================

Mini version of Titanic Gauntlet to quickly test improvements
"""

import sys
import os
import json
import time
import requests
from typing import Dict, List

def generate_smoke_prompts() -> List[Dict]:
    """Generate 30 representative test prompts"""
    return [
        # Math (10 prompts)
        {"domain": "math", "prompt": "What is 2 + 2?"},
        {"domain": "math", "prompt": "Calculate 8 factorial"},
        {"domain": "math", "prompt": "What is the square root of 64?"},
        {"domain": "math", "prompt": "Find the GCD of 12 and 18"},
        {"domain": "math", "prompt": "What is 5 * 7?"},
        {"domain": "math", "prompt": "Solve x^2 - 5x + 6 = 0"},
        {"domain": "math", "prompt": "What is the area of a triangle with base 6 and height 8?"},
        {"domain": "math", "prompt": "Calculate 2^10"},
        {"domain": "math", "prompt": "What is log base 10 of 1000?"},
        {"domain": "math", "prompt": "Find the derivative of x^3 + 2x^2 - 5x + 1"},
        
        # Reasoning (8 prompts)
        {"domain": "reasoning", "prompt": "If A is south of B and B south of C, where is A?"},
        {"domain": "reasoning", "prompt": "Why might a company choose to outsource manufacturing?"},
        {"domain": "reasoning", "prompt": "What are the pros and cons of renewable energy?"},
        {"domain": "reasoning", "prompt": "How do cognitive biases affect decision making?"},
        {"domain": "reasoning", "prompt": "Analyze the causes and effects of urbanization"},
        {"domain": "reasoning", "prompt": "Explain why biodiversity is important for ecosystems"},
        {"domain": "reasoning", "prompt": "What are the ethical implications of AI in healthcare?"},
        {"domain": "reasoning", "prompt": "Analyze the impact of social media on modern communication"},
        
        # Coding (7 prompts)
        {"domain": "coding", "prompt": "Write a function to add two numbers"},
        {"domain": "coding", "prompt": "Implement a bubble sort algorithm"},
        {"domain": "coding", "prompt": "Create a factorial function"},
        {"domain": "coding", "prompt": "Write a function to calculate GCD"},
        {"domain": "coding", "prompt": "Explain the difference between a list and a tuple in Python"},
        {"domain": "coding", "prompt": "Write a function to check if a number is prime"},
        {"domain": "coding", "prompt": "What are the benefits of using version control systems?"},
        
        # Science (5 prompts)
        {"domain": "science", "prompt": "Explain the structure and function of DNA"},
        {"domain": "science", "prompt": "What is quantum entanglement and why is it important?"},
        {"domain": "science", "prompt": "What causes evolution and natural selection?"},
        {"domain": "science", "prompt": "Describe the process of photosynthesis"},
        {"domain": "science", "prompt": "What is the speed of light in a vacuum?"},
    ]

def test_prompt(prompt_data: Dict) -> Dict:
    """Test a single prompt and return results"""
    start_time = time.time()
    
    try:
        response = requests.post(
            "http://localhost:8000/hybrid",
            json={"prompt": prompt_data["prompt"]},
            timeout=10
        )
        
        latency_ms = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            result = response.json()
            
            # Check for mock responses
            is_mock = any(pattern in result["text"].lower() for pattern in [
                "not sure", "unknown", "unsupported", "mock", "fallback"
            ])
            
            # Improved content quality check
            # Short math answers can be good if they're numeric and not mocks
            is_numeric = result["text"].replace(".", "").replace("-", "").replace(" ", "").isdigit()
            is_reasonable_length = len(result["text"]) > 0
            has_actual_content = len(result["text"].strip()) > 3 or is_numeric
            
            content_quality = "good" if has_actual_content and not is_mock else "poor"
            
            return {
                "status": "success",
                "domain": prompt_data["domain"],
                "prompt": prompt_data["prompt"],
                "response": result["text"][:100] + "..." if len(result["text"]) > 100 else result["text"],
                "latency_ms": latency_ms,
                "model": result.get("model", "unknown"),
                "skill_type": result.get("skill_type", "unknown"),
                "confidence": result.get("confidence", 0.0),
                "is_mock": is_mock,
                "content_quality": content_quality
            }
        else:
            return {
                "status": "error",
                "domain": prompt_data["domain"],
                "prompt": prompt_data["prompt"],
                "error": f"HTTP {response.status_code}",
                "latency_ms": latency_ms,
                "is_mock": False,
                "content_quality": "error"
            }
            
    except Exception as e:
        return {
            "status": "error", 
            "domain": prompt_data["domain"],
            "prompt": prompt_data["prompt"],
            "error": str(e),
            "latency_ms": (time.time() - start_time) * 1000,
            "is_mock": False,
            "content_quality": "error"
        }

def main():
    """Run the smoke gauntlet"""
    print("🚀 Smoke Gauntlet - 30 Prompt Test")
    print("=" * 50)
    
    prompts = generate_smoke_prompts()
    results = []
    
    success_count = 0
    mock_count = 0
    good_content_count = 0
    total_latency = 0
    
    for i, prompt_data in enumerate(prompts, 1):
        print(f"Testing {i}/30: {prompt_data['domain']} - {prompt_data['prompt'][:50]}...")
        
        result = test_prompt(prompt_data)
        results.append(result)
        
        if result["status"] == "success":
            success_count += 1
            total_latency += result["latency_ms"]
            
            if result["is_mock"]:
                mock_count += 1
                print(f"  ⚠️ MOCK: {result['response']}")
            else:
                if result["content_quality"] == "good":
                    good_content_count += 1
                    print(f"  ✅ GOOD: {result['response']}")
                else:
                    print(f"  ⚠️ POOR: {result['response']}")
        else:
            print(f"  ❌ ERROR: {result['error']}")
    
    # Calculate metrics
    avg_latency = total_latency / max(success_count, 1)
    success_rate = success_count / len(prompts) * 100
    mock_rate = mock_count / max(success_count, 1) * 100
    content_accuracy = good_content_count / len(prompts) * 100
    
    print("\n📊 SMOKE GAUNTLET RESULTS")
    print("=" * 50)
    print(f"✅ Success Rate: {success_rate:.1f}% ({success_count}/{len(prompts)})")
    print(f"🚨 Mock Rate: {mock_rate:.1f}% ({mock_count}/{success_count})")
    print(f"📝 Content Accuracy: {content_accuracy:.1f}% ({good_content_count}/{len(prompts)})")
    print(f"⚡ Average Latency: {avg_latency:.1f}ms")
    print()
    
    # Domain breakdown
    domains = {}
    for result in results:
        domain = result["domain"]
        if domain not in domains:
            domains[domain] = {"total": 0, "success": 0, "good": 0, "mock": 0}
        
        domains[domain]["total"] += 1
        if result["status"] == "success":
            domains[domain]["success"] += 1
            if result["content_quality"] == "good":
                domains[domain]["good"] += 1
            if result["is_mock"]:
                domains[domain]["mock"] += 1
    
    print("📊 Domain Breakdown:")
    for domain, stats in domains.items():
        success_pct = stats["success"] / stats["total"] * 100
        good_pct = stats["good"] / stats["total"] * 100
        mock_pct = stats["mock"] / max(stats["success"], 1) * 100
        print(f"  {domain}: {success_pct:.0f}% success, {good_pct:.0f}% good content, {mock_pct:.0f}% mock")
    
    # Save results
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"reports/smoke_gauntlet_{timestamp}.json"
    os.makedirs("reports", exist_ok=True)
    
    with open(filename, 'w') as f:
        json.dump({
            "timestamp": timestamp,
            "total_prompts": len(prompts),
            "success_rate": success_rate,
            "mock_rate": mock_rate,
            "content_accuracy": content_accuracy,
            "avg_latency_ms": avg_latency,
            "domain_breakdown": domains,
            "detailed_results": results
        }, f, indent=2)
    
    print(f"\n📄 Results saved to: {filename}")
    
    # Exit codes for CI
    if content_accuracy >= 80:
        print("🎉 SMOKE TEST PASSED!")
        sys.exit(0)
    elif content_accuracy >= 60:
        print("⚠️ SMOKE TEST PARTIAL PASS")
        sys.exit(1)
    else:
        print("❌ SMOKE TEST FAILED")
        sys.exit(2)

if __name__ == "__main__":
    main() 