#!/usr/bin/env python3
"""
Enable Nightly LoRA Distillation - Phase 2 Continuous Learning
=============================================================

Sets up automated nightly training to reduce cloud dependency over time.
Target: 50-80% fewer cloud hits within week 1.
"""

import os
import sys
import json
import schedule
import time
import threading
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

try:
    from nightly_distiller import NightlyDistiller
    DISTILLER_AVAILABLE = True
except ImportError:
    DISTILLER_AVAILABLE = False
    print("⚠️ Nightly distiller not available - creating mock scheduler")

class DistillationScheduler:
    """Manages nightly distillation scheduling"""
    
    def __init__(self):
        self.enabled = False
        self.distiller = None
        self.stats_file = "data/distill_stats.json"
        
        if DISTILLER_AVAILABLE:
            try:
                self.distiller = NightlyDistiller()
                self.enabled = self.distiller.available
            except Exception as e:
                print(f"⚠️ Distiller initialization failed: {e}")
                self.enabled = False
        
        # Ensure stats directory exists
        os.makedirs("data", exist_ok=True)
    
    def run_nightly_distill(self):
        """Execute one round of nightly distillation"""
        if not self.enabled:
            print("⚠️ Distillation not available - skipping")
            return
        
        print("🌙 Starting nightly distillation...")
        start_time = time.time()
        
        try:
            # Run distillation process
            results = self.distiller.run_nightly_cycle()
            
            elapsed = time.time() - start_time
            
            # Update statistics
            stats = self.load_stats()
            stats['last_run'] = time.time()
            stats['total_runs'] = stats.get('total_runs', 0) + 1
            stats['total_time'] = stats.get('total_time', 0) + elapsed
            stats['last_results'] = results
            
            # Track improvement metrics
            if 'cloud_reduction_pct' in results:
                stats['cloud_reduction_history'] = stats.get('cloud_reduction_history', [])
                stats['cloud_reduction_history'].append(results['cloud_reduction_pct'])
                
                # Keep only last 30 days
                stats['cloud_reduction_history'] = stats['cloud_reduction_history'][-30:]
            
            self.save_stats(stats)
            
            print(f"✅ Distillation completed in {elapsed:.1f}s")
            print(f"📊 Results: {results}")
            
        except Exception as e:
            print(f"❌ Distillation failed: {e}")
            
            # Log failure
            stats = self.load_stats()
            stats['last_error'] = str(e)
            stats['error_count'] = stats.get('error_count', 0) + 1
            self.save_stats(stats)
    
    def load_stats(self):
        """Load distillation statistics"""
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"⚠️ Failed to load stats: {e}")
        
        return {}
    
    def save_stats(self, stats):
        """Save distillation statistics"""
        try:
            with open(self.stats_file, 'w') as f:
                json.dump(stats, f, indent=2)
        except Exception as e:
            print(f"⚠️ Failed to save stats: {e}")
    
    def get_status(self):
        """Get current distillation status"""
        stats = self.load_stats()
        
        status = {
            "enabled": self.enabled,
            "available": DISTILLER_AVAILABLE,
            "total_runs": stats.get('total_runs', 0),
            "last_run": stats.get('last_run'),
            "cloud_reduction_trend": [],
            "avg_cloud_reduction": 0.0
        }
        
        # Calculate cloud reduction trend
        history = stats.get('cloud_reduction_history', [])
        if history:
            status['cloud_reduction_trend'] = history[-7:]  # Last week
            status['avg_cloud_reduction'] = sum(history) / len(history)
        
        return status

def main():
    """Main distillation enablement"""
    print("🔥 Enabling Nightly LoRA Distillation")
    print("=" * 50)
    
    scheduler = DistillationScheduler()
    status = scheduler.get_status()
    
    print(f"📊 Current Status:")
    print(f"   Available: {status['available']}")
    print(f"   Enabled: {status['enabled']}")
    print(f"   Total runs: {status['total_runs']}")
    print(f"   Avg cloud reduction: {status['avg_cloud_reduction']:.1f}%")
    
    if not status['enabled']:
        print("\n⚠️ Distillation not available. Possible reasons:")
        print("   - CUDA not available")
        print("   - Missing fine-tuning dependencies")
        print("   - Insufficient VRAM")
        print("\n💡 Run with mock mode for testing")
        return
    
    # Schedule nightly runs (2 AM)
    schedule.every().day.at("02:00").do(scheduler.run_nightly_distill)
    
    print(f"\n✅ Nightly distillation scheduled for 2:00 AM")
    print(f"🎯 Target: 50-80% cloud reduction in week 1")
    
    # Option to run immediately for testing
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        print(f"\n🧪 Running test distillation cycle...")
        scheduler.run_nightly_distill()
    
    elif len(sys.argv) > 1 and sys.argv[1] == "--daemon":
        print(f"\n🔄 Starting distillation daemon...")
        
        def run_scheduler():
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        
        # Run scheduler in background thread
        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
        
        print(f"✅ Distillation daemon started. Next run scheduled for 2:00 AM.")
        
        # Keep main thread alive
        try:
            while True:
                time.sleep(3600)  # Sleep for 1 hour
        except KeyboardInterrupt:
            print(f"\n👋 Distillation daemon stopped.")
    
    else:
        print(f"\n💡 Usage:")
        print(f"   python scripts/enable_distill.py --test     # Run once now")
        print(f"   python scripts/enable_distill.py --daemon   # Start background daemon")

if __name__ == "__main__":
    main() 