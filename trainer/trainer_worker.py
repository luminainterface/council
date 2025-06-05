#!/usr/bin/env python3
"""
Trainer Worker for Spiral v2.7.0
Watches for training jobs and executes them with proper monitoring
"""

import os
import json
import time
import redis
import subprocess
import logging
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TrainerWorker:
    def __init__(self):
        self.redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "redis"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=0, 
            decode_responses=True
        )
        
        self.running = True
        self.current_job = None
        
        # Configuration
        self.job_queue = "training_queue"
        self.jobs_dir = Path("/app/tasks")
        self.jobs_dir.mkdir(exist_ok=True)
        
        # Register signal handlers
        signal.signal(signal.SIGTERM, self.shutdown)
        signal.signal(signal.SIGINT, self.shutdown)
        
        logger.info("Trainer Worker initialized")
        
    def shutdown(self, signum, frame):
        """Graceful shutdown handler"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
        
    def check_health(self) -> bool:
        """Health check for the worker"""
        try:
            # Check Redis connection
            self.redis_client.ping()
            
            # Check if we can access the file system
            (self.jobs_dir / "health_check").touch()
            (self.jobs_dir / "health_check").unlink()
            
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
            
    def process_lora_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a LoRA training job"""
        logger.info(f"Processing LoRA job: {job_data}")
        
        try:
            # Extract job parameters
            model_name = job_data.get("model", "microsoft/phi-1_5")
            data_path = job_data.get("data_path", "/app/data/completions")
            output_dir = job_data.get("output_dir")
            config_path = job_data.get("config_path")
            
            # Generate output directory if not specified
            if not output_dir:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_dir = f"/models/lora_{timestamp}"
                
            # Build command
            cmd = [
                "python3", "/app/trainer/lora_train.py",
                "--model", model_name,
                "--data", data_path,
                "--output", output_dir
            ]
            
            if config_path:
                cmd.extend(["--config", config_path])
                
            # Execute training
            logger.info(f"Starting LoRA training: {' '.join(cmd)}")
            start_time = time.time()
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True,
                timeout=int(os.getenv("MAX_TRAINING_TIME_MINUTES", "120")) * 60
            )
            
            training_time = time.time() - start_time
            
            # Check result
            if result.returncode == 0:
                logger.info(f"LoRA training completed successfully in {training_time:.1f}s")
                
                # Load training report if available
                report_path = Path(output_dir) / "training_report.json"
                if report_path.exists():
                    with open(report_path, 'r') as f:
                        training_report = json.load(f)
                else:
                    training_report = {"status": "success", "output_dir": output_dir}
                
                return {
                    "status": "success",
                    "job_type": "lora",
                    "training_time": training_time,
                    "output_dir": output_dir,
                    "training_report": training_report,
                    "stdout": result.stdout[-1000:],  # Last 1000 chars
                    "timestamp": datetime.now().isoformat()
                }
            else:
                logger.error(f"LoRA training failed with exit code {result.returncode}")
                return {
                    "status": "failed",
                    "job_type": "lora",
                    "error_code": result.returncode,
                    "stdout": result.stdout[-1000:],
                    "stderr": result.stderr[-1000:],
                    "training_time": training_time,
                    "timestamp": datetime.now().isoformat()
                }
                
        except subprocess.TimeoutExpired:
            logger.error("LoRA training timed out")
            return {
                "status": "timeout",
                "job_type": "lora",
                "error": "Training exceeded time limit",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"LoRA training error: {e}")
            return {
                "status": "error",
                "job_type": "lora", 
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            
    def process_distillation_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a distillation job"""
        logger.info(f"Processing distillation job: {job_data}")
        
        try:
            # Run nightly distillation
            cmd = ["python3", "/app/nightly_distiller.py", "--verbose"]
            
            if job_data.get("config_path"):
                cmd.extend(["--config", job_data["config_path"]])
                
            logger.info(f"Starting distillation: {' '.join(cmd)}")
            start_time = time.time()
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)  # 1 hour max
            
            distillation_time = time.time() - start_time
            
            if result.returncode == 0:
                logger.info(f"Distillation completed successfully in {distillation_time:.1f}s")
                return {
                    "status": "success",
                    "job_type": "distillation",
                    "distillation_time": distillation_time,
                    "stdout": result.stdout[-1000:],
                    "timestamp": datetime.now().isoformat()
                }
            else:
                logger.error(f"Distillation failed with exit code {result.returncode}")
                return {
                    "status": "failed",
                    "job_type": "distillation",
                    "error_code": result.returncode,
                    "stdout": result.stdout[-1000:],
                    "stderr": result.stderr[-1000:],
                    "distillation_time": distillation_time,
                    "timestamp": datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Distillation error: {e}")
            return {
                "status": "error",
                "job_type": "distillation",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            
    def process_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a training job based on its type"""
        job_type = job_data.get("type", "lora")
        
        if job_type == "lora":
            return self.process_lora_job(job_data)
        elif job_type == "distillation":
            return self.process_distillation_job(job_data)
        else:
            logger.error(f"Unknown job type: {job_type}")
            return {
                "status": "error",
                "error": f"Unknown job type: {job_type}",
                "timestamp": datetime.now().isoformat()
            }
            
    def watch_job_files(self):
        """Watch for job files in the tasks directory"""
        job_files = list(self.jobs_dir.glob("*.json"))
        
        for job_file in job_files:
            try:
                with open(job_file, 'r') as f:
                    job_data = json.load(f)
                    
                logger.info(f"Found job file: {job_file}")
                
                # Process the job
                result = self.process_job(job_data)
                
                # Save result
                result_file = job_file.with_suffix('.result.json')
                with open(result_file, 'w') as f:
                    json.dump(result, f, indent=2)
                    
                # Remove the job file
                job_file.unlink()
                
                logger.info(f"Job completed: {result['status']}")
                
            except Exception as e:
                logger.error(f"Error processing job file {job_file}: {e}")
                
    def check_scheduled_jobs(self):
        """Check if it's time for scheduled jobs (like nightly distillation)"""
        current_hour = datetime.now().hour
        
        # Run distillation at 2 AM
        if current_hour == 2:
            last_run_key = "last_nightly_distillation"
            last_run = self.redis_client.get(last_run_key)
            today = datetime.now().strftime("%Y-%m-%d")
            
            if last_run != today:
                logger.info("Running scheduled nightly distillation...")
                
                job_data = {
                    "type": "distillation",
                    "scheduled": True,
                    "timestamp": datetime.now().isoformat()
                }
                
                result = self.process_job(job_data)
                
                if result["status"] == "success":
                    self.redis_client.set(last_run_key, today)
                    
                logger.info(f"Scheduled distillation result: {result['status']}")
                
    def run(self):
        """Main worker loop"""
        logger.info("Trainer Worker starting main loop...")
        
        while self.running:
            try:
                # Check health
                if not self.check_health():
                    logger.warning("Health check failed, continuing...")
                
                # Check for Redis queue jobs
                job_data = self.redis_client.blpop(self.job_queue, timeout=30)
                
                if job_data:
                    job_json = json.loads(job_data[1])
                    self.current_job = job_json
                    
                    logger.info(f"Processing queue job: {job_json}")
                    result = self.process_job(job_json)
                    
                    # Store result in Redis
                    result_key = f"training_result:{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    self.redis_client.setex(result_key, 86400, json.dumps(result))  # 24 hour TTL
                    
                    self.current_job = None
                    
                # Check for file-based jobs
                self.watch_job_files()
                
                # Check for scheduled jobs
                self.check_scheduled_jobs()
                
            except redis.ConnectionError:
                logger.error("Redis connection lost, retrying in 10 seconds...")
                time.sleep(10)
            except Exception as e:
                logger.error(f"Worker error: {e}")
                time.sleep(5)
                
        logger.info("Trainer Worker shutting down...")

def main():
    """Main entry point"""
    worker = TrainerWorker()
    
    try:
        worker.run()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Worker crashed: {e}")
        return 1
        
    return 0

if __name__ == "__main__":
    exit(main()) 