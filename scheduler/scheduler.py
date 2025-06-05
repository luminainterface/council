#!/usr/bin/env python3
"""
Scheduler for Spiral v2.7.0
Handles nightly distillation, pattern mining, and other scheduled tasks
"""

import os
import json
import time
import redis
import logging
import signal
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("/app/logs/scheduler.log")
    ]
)
logger = logging.getLogger(__name__)

class SpiralScheduler:
    def __init__(self):
        self.redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "redis"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=0,
            decode_responses=True
        )
        
        self.scheduler = BlockingScheduler()
        self.tasks_dir = Path("/app/tasks")
        self.tasks_dir.mkdir(exist_ok=True)
        
        # Configuration
        self.nightly_enabled = os.getenv("SCHEDULE_NIGHTLY_DISTILLATION", "true").lower() == "true"
        self.pattern_mining_enabled = os.getenv("SCHEDULE_PATTERN_MINING", "true").lower() == "true"
        self.fallback_prompts_enabled = os.getenv("FALLBACK_PROMPTS_ENABLED", "true").lower() == "true"
        
        logger.info("Scheduler initialized")
        
    def queue_training_job(self, job_data: Dict[str, Any]):
        """Queue a training job via Redis"""
        try:
            job_json = json.dumps(job_data)
            self.redis_client.lpush("training_queue", job_json)
            logger.info(f"Queued training job: {job_data['type']}")
        except Exception as e:
            logger.error(f"Failed to queue job: {e}")
            
    def create_job_file(self, job_data: Dict[str, Any], filename: str):
        """Create a job file for file-based processing"""
        try:
            job_file = self.tasks_dir / filename
            with open(job_file, "w") as f:
                json.dump(job_data, f, indent=2)
            logger.info(f"Created job file: {filename}")
        except Exception as e:
            logger.error(f"Failed to create job file: {e}")
            
    def schedule_nightly_distillation(self):
        """Schedule nightly distillation job"""
        if not self.nightly_enabled:
            return
            
        logger.info("Scheduling nightly distillation...")
        
        job_data = {
            "type": "distillation",
            "scheduled": True,
            "timestamp": datetime.now().isoformat(),
            "config": {
                "min_samples": 50,
                "max_time_minutes": 120
            }
        }
        
        # Try Redis first, fallback to file
        try:
            self.queue_training_job(job_data)
        except:
            self.create_job_file(job_data, f"nightly_distillation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            
    def schedule_pattern_mining(self):
        """Schedule pattern mining job"""
        if not self.pattern_mining_enabled:
            return
            
        logger.info("Scheduling pattern mining...")
        
        # This would trigger pattern mining via API call or message
        # For now, just log the event
        try:
            self.redis_client.set("pattern_mining_trigger", datetime.now().isoformat())
            logger.info("Pattern mining trigger set")
        except Exception as e:
            logger.error(f"Failed to trigger pattern mining: {e}")
            
    def generate_fallback_prompts(self):
        """Generate fallback training prompts if data is insufficient"""
        if not self.fallback_prompts_enabled:
            return
            
        logger.info("Generating fallback prompts...")
        
        # Check if we have enough training data
        try:
            # This is a simplified check - in production would analyze actual data
            data_count = self.redis_client.get("completion_data_count") or "0"
            if int(data_count) < 20:
                logger.info("Insufficient training data, generating fallback prompts")
                
                fallback_prompts = [
                    {"prompt": "What is 2+2?", "response": "2+2 equals 4."},
                    {"prompt": "Explain Python functions", "response": "Python functions are reusable blocks of code defined with the def keyword."},
                    {"prompt": "How do you create a list in Python?", "response": "You can create a list in Python using square brackets: my_list = [1, 2, 3]"}
                ]
                
                # Save fallback prompts
                fallback_file = Path("/app/data/completions/fallback_prompts.json")
                fallback_file.parent.mkdir(parents=True, exist_ok=True)
                
                with open(fallback_file, "w") as f:
                    json.dump(fallback_prompts, f, indent=2)
                    
                logger.info(f"Generated {len(fallback_prompts)} fallback prompts")
        except Exception as e:
            logger.error(f"Failed to generate fallback prompts: {e}")
            
    def cleanup_old_jobs(self):
        """Clean up old job files and results"""
        try:
            # Remove job files older than 7 days
            cutoff_time = datetime.now() - timedelta(days=7)
            
            for job_file in self.tasks_dir.glob("*.json"):
                if job_file.stat().st_mtime < cutoff_time.timestamp():
                    job_file.unlink()
                    logger.info(f"Cleaned up old job file: {job_file.name}")
        except Exception as e:
            logger.error(f"Failed to cleanup old jobs: {e}")
            
    def setup_schedules(self):
        """Setup all scheduled jobs"""
        # Nightly distillation at 2:00 AM
        if self.nightly_enabled:
            self.scheduler.add_job(
                self.schedule_nightly_distillation,
                CronTrigger(hour=2, minute=0),
                id="nightly_distillation"
            )
            logger.info("Scheduled nightly distillation for 2:00 AM")
            
        # Pattern mining every 6 hours
        if self.pattern_mining_enabled:
            self.scheduler.add_job(
                self.schedule_pattern_mining,
                IntervalTrigger(hours=6),
                id="pattern_mining"
            )
            logger.info("Scheduled pattern mining every 6 hours")
            
        # Fallback prompt generation every 12 hours
        if self.fallback_prompts_enabled:
            self.scheduler.add_job(
                self.generate_fallback_prompts,
                IntervalTrigger(hours=12),
                id="fallback_prompts"
            )
            logger.info("Scheduled fallback prompt generation every 12 hours")
            
        # Cleanup old jobs daily at 1:00 AM
        self.scheduler.add_job(
            self.cleanup_old_jobs,
            CronTrigger(hour=1, minute=0),
            id="cleanup"
        )
        logger.info("Scheduled daily cleanup at 1:00 AM")
        
    def run(self):
        """Start the scheduler"""
        logger.info("Starting Spiral Scheduler v2.7.0")
        
        # Setup all scheduled jobs
        self.setup_schedules()
        
        # Start the scheduler
        try:
            self.scheduler.start()
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
        finally:
            self.scheduler.shutdown()
            logger.info("Scheduler shutdown complete")
            
def main():
    scheduler = SpiralScheduler()
    scheduler.run()
    
if __name__ == "__main__":
    main() 