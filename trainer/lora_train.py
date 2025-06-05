#!/usr/bin/env python3
"""
LoRA Training Module for Spiral v2.7.0
Handles QLoRA fine-tuning with budget and time constraints
"""

import os
import json
import time
import torch
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from transformers import (
    AutoTokenizer, AutoModelForCausalLM, 
    TrainingArguments, Trainer, DataCollatorForLanguageModeling
)
from peft import LoraConfig, get_peft_model, TaskType
from datasets import Dataset
import redis

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LoRATrainer:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.redis_client = redis.Redis(
            host=config.get('redis_host', 'redis'),
            port=config.get('redis_port', 6379),
            db=0, 
            decode_responses=True
        )
        
        # Training parameters
        self.lora_rank = config.get('lora_rank', 16)
        self.lora_alpha = config.get('lora_alpha', 32)
        self.max_training_time = config.get('max_training_time_minutes', 120) * 60
        self.budget_usd = config.get('training_budget_usd', 0.05)
        
        logger.info(f"LoRA Trainer initialized - Rank: {self.lora_rank}, Alpha: {self.lora_alpha}")
        
    def check_gpu(self) -> bool:
        """Check GPU availability and memory"""
        if not torch.cuda.is_available():
            logger.warning("CUDA not available - training will be CPU-only")
            return False
            
        gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        logger.info(f"GPU: {torch.cuda.get_device_name(0)}, Memory: {gpu_memory:.1f}GB")
        
        if gpu_memory < 6:
            logger.warning(f"GPU memory ({gpu_memory:.1f}GB) may be insufficient for training")
            
        return True
        
    def load_training_data(self, data_path: str) -> Dataset:
        """Load and prepare training data"""
        logger.info(f"Loading training data from {data_path}")
        
        data_files = []
        if os.path.isfile(data_path):
            data_files = [data_path]
        elif os.path.isdir(data_path):
            data_files = list(Path(data_path).glob("*.json"))
            
        if not data_files:
            raise ValueError(f"No training data found in {data_path}")
            
        # Load all JSON data
        all_data = []
        for file_path in data_files:
            with open(file_path, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    all_data.extend(data)
                else:
                    all_data.append(data)
                    
        logger.info(f"Loaded {len(all_data)} training examples")
        
        # Convert to Hugging Face dataset format
        texts = []
        for item in all_data:
            if 'prompt' in item and 'response' in item:
                text = f"### Prompt: {item['prompt']}\n### Response: {item['response']}<|endoftext|>"
                texts.append(text)
        
        return Dataset.from_dict({"text": texts})
        
    def setup_lora_config(self) -> LoraConfig:
        """Configure LoRA parameters"""
        lora_config = LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=self.lora_rank,
            lora_alpha=self.lora_alpha,
            lora_dropout=0.1,
            target_modules=[
                "q_proj", "v_proj", "k_proj", "o_proj",
                "gate_proj", "up_proj", "down_proj"  # For Llama-style models
            ],
            bias="none",
            inference_mode=False,
        )
        
        logger.info(f"LoRA config: r={lora_config.r}, alpha={lora_config.lora_alpha}")
        return lora_config
        
    def train_model(self, model_name: str, training_data: Dataset, output_dir: str) -> Dict[str, Any]:
        """Train LoRA model with the given data"""
        start_time = time.time()
        logger.info(f"Starting LoRA training - Model: {model_name}")
        
        try:
            # Load tokenizer and model
            tokenizer = AutoTokenizer.from_pretrained(model_name)
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token
                
            # Load model in 4-bit for QLoRA
            model = AutoModelForCausalLM.from_pretrained(
                model_name,
                torch_dtype=torch.float16,
                device_map="auto" if torch.cuda.is_available() else None,
                load_in_4bit=True if torch.cuda.is_available() else False,
                trust_remote_code=True
            )
            
            # Setup LoRA
            lora_config = self.setup_lora_config()
            model = get_peft_model(model, lora_config)
            
            # Tokenize dataset
            def tokenize_function(examples):
                return tokenizer(
                    examples["text"], 
                    truncation=True, 
                    padding=True, 
                    max_length=512
                )
            
            tokenized_dataset = training_data.map(tokenize_function, batched=True)
            
            # Training arguments
            training_args = TrainingArguments(
                output_dir=output_dir,
                overwrite_output_dir=True,
                num_train_epochs=1,  # Single epoch for quick training
                per_device_train_batch_size=1,
                gradient_accumulation_steps=4,
                warmup_steps=10,
                max_steps=min(100, len(tokenized_dataset)),  # Limit steps
                logging_steps=10,
                save_steps=50,
                eval_steps=50,
                logging_dir=f"{output_dir}/logs",
                report_to=None,  # Disable wandb in production
                remove_unused_columns=False,
                dataloader_pin_memory=False,
            )
            
            # Data collator
            data_collator = DataCollatorForLanguageModeling(
                tokenizer=tokenizer,
                mlm=False,
                pad_to_multiple_of=8
            )
            
            # Trainer
            trainer = Trainer(
                model=model,
                args=training_args,
                train_dataset=tokenized_dataset,
                data_collator=data_collator,
            )
            
            # Train with timeout
            logger.info("Starting training...")
            trainer.train()
            
            # Save the model
            trainer.save_model()
            tokenizer.save_pretrained(output_dir)
            
            training_time = time.time() - start_time
            
            # Generate training report
            report = {
                "status": "success",
                "model_name": model_name,
                "output_dir": output_dir,
                "training_examples": len(training_data),
                "training_time_seconds": training_time,
                "lora_rank": self.lora_rank,
                "lora_alpha": self.lora_alpha,
                "timestamp": datetime.now().isoformat(),
                "gpu_used": torch.cuda.is_available()
            }
            
            logger.info(f"Training completed in {training_time:.1f}s")
            return report
            
        except Exception as e:
            logger.error(f"Training failed: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "training_time_seconds": time.time() - start_time,
                "timestamp": datetime.now().isoformat()
            }

def main():
    """Main training entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="LoRA Training for Spiral")
    parser.add_argument("--model", default="microsoft/phi-1_5", help="Base model name")
    parser.add_argument("--data", default="/app/data/completions", help="Training data path")
    parser.add_argument("--output", help="Output directory")
    parser.add_argument("--config", help="Config file path")
    
    args = parser.parse_args()
    
    # Default output directory
    if not args.output:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = f"/models/lora_{timestamp}"
    
    # Load config
    config = {
        "lora_rank": int(os.getenv("LORA_RANK", "16")),
        "lora_alpha": int(os.getenv("LORA_ALPHA", "32")),
        "max_training_time_minutes": int(os.getenv("MAX_TRAINING_TIME_MINUTES", "120")),
        "training_budget_usd": float(os.getenv("TRAINING_BUDGET_USD", "0.05"))
    }
    
    if args.config and os.path.exists(args.config):
        with open(args.config, 'r') as f:
            file_config = json.load(f)
            config.update(file_config)
    
    # Initialize trainer
    trainer = LoRATrainer(config)
    
    # Check GPU
    trainer.check_gpu()
    
    # Load training data
    try:
        training_data = trainer.load_training_data(args.data)
    except Exception as e:
        logger.error(f"Failed to load training data: {e}")
        return 1
    
    # Ensure output directory exists
    os.makedirs(args.output, exist_ok=True)
    
    # Train model
    report = trainer.train_model(args.model, training_data, args.output)
    
    # Save report
    report_path = f"{args.output}/training_report.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
        
    logger.info(f"Training report saved to {report_path}")
    
    # Update metrics in Redis
    try:
        if report["status"] == "success":
            trainer.redis_client.incr("swarm_lora_training_runs_total")
            trainer.redis_client.set("swarm_lora_version", datetime.now().strftime("%Y%m%d_%H%M%S"))
        else:
            trainer.redis_client.incr("swarm_lora_training_failures_total")
    except Exception as e:
        logger.warning(f"Failed to update Redis metrics: {e}")
    
    return 0 if report["status"] == "success" else 1

if __name__ == "__main__":
    exit(main()) 