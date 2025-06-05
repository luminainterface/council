#!/usr/bin/env python3
"""
Autonomous Software Spiral - Monitoring Dashboard
==================================================

Real-time monitoring of spiral performance:
- Cost savings from patterns/cache
- Hit rates and performance
- Learning progress
- Budget utilization
"""

import json
import time
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List

def get_spiral_metrics() -> Dict[str, Any]:
    """Get comprehensive spiral metrics"""
    
    metrics = {
        "timestamp": time.time(),
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "spiral_health": "unknown",
        "components": {},
        "performance": {},
        "costs": {},
        "learning": {}
    }
    
    # Component Health Check
    print("🔍 AUTONOMOUS SOFTWARE SPIRAL - HEALTH CHECK")
    print("=" * 50)
    
    components = {
        "agent0_routing": os.path.exists("router_cascade.py"),
        "pattern_mining": os.path.exists("patterns/synthetic_specialists.py"),
        "shallow_cache": os.path.exists("cache/shallow_cache.py"),
        "cost_tracking": os.path.exists("cost_tracker.py"),
        "nightly_distiller": os.path.exists("nightly_distiller.py")
    }
    
    operational_count = sum(components.values())
    total_count = len(components)
    
    for component, status in components.items():
        status_icon = "✅" if status else "❌"
        print(f"{status_icon} {component.replace('_', ' ').title()}")
        metrics["components"][component] = status
    
    # Overall health
    health_score = operational_count / total_count
    if health_score >= 0.8:
        spiral_health = "healthy"
    elif health_score >= 0.6:
        spiral_health = "degraded"
    else:
        spiral_health = "critical"
    
    metrics["spiral_health"] = spiral_health
    print(f"\n🚀 SPIRAL HEALTH: {spiral_health.upper()} ({operational_count}/{total_count} components)")
    
    # Pattern Learning Metrics
    try:
        if os.path.exists("patterns/synthetic_specialists.py"):
            import sys
            sys.path.insert(0, "patterns")
            from synthetic_specialists import PATTERN_COUNT, GENERATED_AT
            
            metrics["learning"] = {
                "pattern_count": PATTERN_COUNT,
                "last_training": GENERATED_AT,
                "synthetic_specialists_active": True
            }
            
            print(f"\n🧠 LEARNING STATUS:")
            print(f"   📊 Patterns learned: {PATTERN_COUNT}")
            print(f"   🕒 Last training: {GENERATED_AT}")
        else:
            metrics["learning"] = {
                "pattern_count": 0,
                "synthetic_specialists_active": False
            }
            print(f"\n🧠 LEARNING STATUS: Not yet initialized")
            
    except Exception as e:
        print(f"⚠️ Learning metrics error: {e}")
    
    # Cost Tracking Metrics
    try:
        from cost_tracker import get_cost_tracker
        
        tracker = get_cost_tracker()
        summary = tracker.generate_daily_summary()
        
        metrics["costs"] = {
            "daily_spend_usd": summary.total_cost_usd,
            "daily_saved_usd": summary.total_saved_usd,
            "budget_remaining_usd": summary.budget_remaining_usd,
            "over_budget": summary.over_budget,
            "pattern_hits": summary.pattern_specialist_hits,
            "cache_hits": summary.cache_hits
        }
        
        print(f"\n💰 COST STATUS:")
        print(f"   💸 Daily spend: ${summary.total_cost_usd:.4f}")
        print(f"   💵 Daily saved: ${summary.total_saved_usd:.4f}")
        print(f"   🏦 Budget remaining: ${summary.budget_remaining_usd:.4f}")
        print(f"   🎯 Pattern hits: {summary.pattern_specialist_hits}")
        print(f"   💾 Cache hits: {summary.cache_hits}")
        
        # Calculate savings rate
        total_activity = summary.total_cost_usd + summary.total_saved_usd
        if total_activity > 0:
            savings_rate = summary.total_saved_usd / total_activity
            print(f"   📈 Savings rate: {savings_rate:.1%}")
            metrics["costs"]["savings_rate"] = savings_rate
            
    except Exception as e:
        print(f"⚠️ Cost metrics error: {e}")
    
    # Performance Metrics
    try:
        # Check cache performance
        from cache.shallow_cache import get_cache_stats
        cache_stats = get_cache_stats()
        
        metrics["performance"] = {
            "cache_type": cache_stats.get("cache_type", "unknown"),
            "cache_entries": cache_stats.get("entries", 0),
            "cache_available": cache_stats.get("available", False)
        }
        
        print(f"\n⚡ PERFORMANCE STATUS:")
        print(f"   💾 Cache: {cache_stats.get('cache_type', 'unknown')} ({cache_stats.get('entries', 0)} entries)")
        
        # GPU Status
        try:
            import torch
            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                print(f"   🖥️ GPU: {gpu_name} ({gpu_memory:.1f}GB)")
                metrics["performance"]["gpu_available"] = True
                metrics["performance"]["gpu_name"] = gpu_name
            else:
                print(f"   🖥️ GPU: Not available")
                metrics["performance"]["gpu_available"] = False
        except ImportError:
            pass
            
    except Exception as e:
        print(f"⚠️ Performance metrics error: {e}")
    
    # Provider Retirement Check
    try:
        hit_rates = tracker.get_provider_hit_rates()
        retirement_candidates = tracker.get_retirement_candidates()
        
        if retirement_candidates:
            print(f"\n🗑️ PROVIDER RETIREMENT:")
            for provider in retirement_candidates:
                rate = hit_rates.get(provider, 0)
                print(f"   📉 {provider}: {rate:.1%} hit rate (< 10% threshold)")
        else:
            print(f"\n✅ No providers scheduled for retirement")
            
        metrics["costs"]["retirement_candidates"] = retirement_candidates
        
    except:
        pass
    
    return metrics

def save_metrics_history(metrics: Dict[str, Any]) -> None:
    """Save metrics to history file"""
    
    os.makedirs("data/monitoring", exist_ok=True)
    
    history_file = "data/monitoring/spiral_metrics.jsonl"
    
    try:
        with open(history_file, "a", encoding="utf-8") as f:
            json.dump(metrics, f)
            f.write("\n")
        
        print(f"\n📊 Metrics saved to {history_file}")
        
    except Exception as e:
        print(f"⚠️ Failed to save metrics: {e}")

def generate_daily_report() -> str:
    """Generate a daily spiral report"""
    
    metrics = get_spiral_metrics()
    
    report = f"""
AUTONOMOUS SOFTWARE SPIRAL - DAILY REPORT
Date: {metrics['date']}
Health: {metrics['spiral_health'].upper()}

COMPONENT STATUS:
{chr(10).join(f"  {name}: {'✅' if status else '❌'}" for name, status in metrics['components'].items())}

LEARNING PROGRESS:
  Patterns Learned: {metrics['learning'].get('pattern_count', 0)}
  Synthetic Specialists: {'Active' if metrics['learning'].get('synthetic_specialists_active') else 'Inactive'}

COST PERFORMANCE:
  Daily Spend: ${metrics['costs'].get('daily_spend_usd', 0):.4f}
  Daily Saved: ${metrics['costs'].get('daily_saved_usd', 0):.4f}
  Budget Remaining: ${metrics['costs'].get('budget_remaining_usd', 0):.4f}
  Pattern Hits: {metrics['costs'].get('pattern_hits', 0)}
  Cache Hits: {metrics['costs'].get('cache_hits', 0)}
  Savings Rate: {metrics['costs'].get('savings_rate', 0):.1%}

RECOMMENDATIONS:
"""
    
    # Add recommendations based on metrics
    recommendations = []
    
    if metrics['spiral_health'] == 'critical':
        recommendations.append("🚨 Multiple components down - check system integrity")
    
    if metrics['learning'].get('pattern_count', 0) == 0:
        recommendations.append("🧠 Run pattern mining to start learning from completions")
    
    if metrics['costs'].get('daily_spend_usd', 0) > 0.08:
        recommendations.append("💰 Approaching daily budget limit - prioritize local models")
    
    if metrics['costs'].get('savings_rate', 0) < 0.3:
        recommendations.append("📈 Low savings rate - increase pattern/cache utilization")
    
    retirement_candidates = metrics['costs'].get('retirement_candidates', [])
    if retirement_candidates:
        recommendations.append(f"🗑️ Consider retiring providers: {', '.join(retirement_candidates)}")
    
    if not recommendations:
        recommendations.append("✅ System operating optimally - spiral is autonomous!")
    
    for rec in recommendations:
        report += f"  {rec}\n"
    
    return report

def main():
    """Main dashboard function"""
    
    print("🚀 Autonomous Software Spiral - Monitoring Dashboard")
    print("=" * 60)
    
    # Get current metrics
    metrics = get_spiral_metrics()
    
    # Save to history
    save_metrics_history(metrics)
    
    # Generate and save daily report
    report = generate_daily_report()
    
    report_file = f"data/monitoring/daily_report_{datetime.now().strftime('%Y-%m-%d')}.txt"
    try:
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\n📋 Daily report saved: {report_file}")
    except Exception as e:
        print(f"⚠️ Failed to save report: {e}")
    
    print("\n" + "=" * 60)
    print("📊 SPIRAL DASHBOARD COMPLETE")

if __name__ == "__main__":
    main() 