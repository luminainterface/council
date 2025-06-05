#!/usr/bin/env python3
"""
Spiral QLoRA Training Orchestrator
Trains a LoRA adapter from traffic snapshot data with budget protection
"""

import os
import sys
import json
import gzip
import time
import hashlib
from pathlib import Path
from typing import Dict, Any, Iterator, List, Optional
import logging

# Training dependencies
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import LoraConfig, get_peft_model, TaskType
import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CostGuard:
    """Budget protection for training runs"""
    
    def __init__(self, budget_usd: float = 0.10):
        self.budget_usd = budget_usd
        self.spent_usd = 0.0
        
        # GPU cost estimates (per hour)
        self.gpu_costs = {
            "A100": 3.06,   # AWS p4d.xlarge
            "V100": 2.48,   # AWS p3.2xlarge
            "T4": 0.526,    # AWS g4dn.xlarge
            "RTX4090": 0.60,  # Estimated local equivalent
        }
        
        self.start_time = time.time()
        self.gpu_type = self._detect_gpu()
        self.hourly_rate = self.gpu_costs.get(self.gpu_type, 1.0)
        
        logger.info(f"💰 Budget guard: ${budget_usd:.3f} limit, ${self.hourly_rate:.3f}/hr ({self.gpu_type})")
    
    def _detect_gpu(self) -> str:
        """Detect GPU type for cost estimation"""
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            if "A100" in gpu_name:
                return "A100"
            elif "V100" in gpu_name:
                return "V100"
            elif "T4" in gpu_name:
                return "T4"
            elif "4090" in gpu_name or "RTX" in gpu_name:
                return "RTX4090"
        return "Unknown"
    
    def check(self, step: int, total_steps: int) -> bool:
        """Check if budget limit would be exceeded"""
        elapsed_hours = (time.time() - self.start_time) / 3600
        self.spent_usd = elapsed_hours * self.hourly_rate
        
        # Estimate remaining cost
        progress = step / max(total_steps, 1)
        if progress > 0:
            estimated_total_hours = elapsed_hours / progress
            estimated_total_cost = estimated_total_hours * self.hourly_rate
            
            if estimated_total_cost > self.budget_usd:
                logger.error(f"💸 Budget exceeded: ${estimated_total_cost:.3f} > ${self.budget_usd:.3f}")
                return False
        
        if step % 10 == 0:  # Log every 10 steps
            logger.info(f"💰 Step {step}/{total_steps}, spent: ${self.spent_usd:.4f}")
        
        return True

class TrainingConfig:
    """Training configuration from environment variables"""
    
    def __init__(self):
        self.data_dir = Path(os.environ.get("DATA_DIR", "/loras/2024-01-01"))
        self.base_model = os.environ.get("BASE_MODEL", "/models/tinyllama")
        self.budget_usd = float(os.environ.get("SWARM_BUDGET_USD", "0.10"))
        self.pushgateway_url = os.environ.get("PUSHGATEWAY_URL", "http://pushgateway:9091")
        self.dry_run = os.environ.get("DRY_RUN", "false").lower() == "true"
        
        # LoRA hyperparameters
        self.lora_rank = int(os.environ.get("LORA_RANK", "64"))
        self.lora_alpha = int(os.environ.get("LORA_ALPHA", "32"))
        self.learning_rate = float(os.environ.get("LEARNING_RATE", "2e-4"))
        self.batch_size = int(os.environ.get("BATCH_SIZE", "16"))
        self.max_steps = int(os.environ.get("MAX_STEPS", "500"))
        
        # Files
        self.train_file = self.data_dir / "train.jsonl.gz"
        self.holdout_file = self.data_dir / "holdout.jsonl.gz"
        self.adapter_file = self.data_dir / "adapter.bin"
        self.ready_flag = self.data_dir / "READY"
        
        logger.info(f"🔧 Config: {self.data_dir}, budget=${self.budget_usd}, rank={self.lora_rank}")

def load_dataset(file_path: Path) -> List[Dict]:
    """Load JSONL dataset"""
    if not file_path.exists():
        return []
    
    data = []
    with gzip.open(file_path, 'rt') as f:
        for line in f:
            try:
                data.append(json.loads(line.strip()))
            except:
                continue
    return data

def prepare_model_and_tokenizer(base_model_path: str):
    """Load 4-bit quantized model with LoRA configuration"""
    logger.info(f"🤖 Loading model: {base_model_path}")
    
    # 4-bit quantization config
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )
    
    # Load model and tokenizer
    tokenizer = AutoTokenizer.from_pretrained(base_model_path, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        base_model_path,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    
    # Add padding token if missing
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    # LoRA configuration
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=64,  # rank
        lora_alpha=32,
        lora_dropout=0.1,
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
    )
    
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()
    
    return model, tokenizer

def tokenize_data(examples: List[Dict], tokenizer, max_length: int = 512):
    """Tokenize training examples"""
    prompts = [ex["prompt"] for ex in examples]
    
    # Tokenize with padding and truncation
    encoded = tokenizer(
        prompts,
        truncation=True,
        padding=True,
        max_length=max_length,
        return_tensors="pt"
    )
    
    # Labels are the same as input_ids (causal LM)
    encoded["labels"] = encoded["input_ids"].clone()
    
    return encoded

def push_metric(name: str, value: float, pushgateway_url: str, labels: Dict[str, str] = None):
    """Push metric to Prometheus Pushgateway"""
    if not pushgateway_url:
        return
        
    labels = labels or {}
    label_str = ",".join([f'{k}="{v}"' for k, v in labels.items()])
    
    metric_data = f"# TYPE {name} gauge\n{name}{{{label_str}}} {value}\n"
    
    try:
        response = requests.post(
            f"{pushgateway_url}/metrics/job/trainer/instance/main",
            data=metric_data,
            headers={"Content-Type": "text/plain"},
            timeout=5
        )
        if response.status_code == 200:
            logger.debug(f"📊 Metric pushed: {name}={value}")
        else:
            logger.warning(f"⚠️ Metric push failed: {response.status_code}")
    except Exception as e:
        logger.warning(f"⚠️ Failed to push metric {name}: {e}")

def train_model(model, tokenizer, dataset: List[Dict], config: TrainingConfig):
    """Train the LoRA adapter"""
    logger.info(f"🎯 Starting training with {len(dataset)} examples")
    
    cost_guard = CostGuard(config.budget_usd)
    total_loss = 0.0
    
    # Simple training loop (no fancy trainer)
    model.train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=config.learning_rate)
    
    # Batch the dataset
    batches = []
    for i in range(0, len(dataset), config.batch_size):
        batch = dataset[i:i + config.batch_size]
        batches.append(batch)
    
    total_steps = min(len(batches), config.max_steps)
    
    for step, batch in enumerate(batches[:config.max_steps]):
        # Budget check
        if not cost_guard.check(step, total_steps):
            push_metric("trainer_cost_guard_trip", 1, config.pushgateway_url)
            logger.error("💸 Budget exhausted, stopping training")
            break
        
        # Prepare batch
        inputs = tokenize_data(batch, tokenizer)
        inputs = {k: v.to(model.device) for k, v in inputs.items()}
        
        # Forward pass
        outputs = model(**inputs)
        loss = outputs.loss
        total_loss += loss.item()
        
        # Backward pass
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        
        # Log progress
        if step % 10 == 0:
            avg_loss = total_loss / (step + 1)
            logger.info(f"Step {step}/{total_steps}, Loss: {loss.item():.4f}, Avg: {avg_loss:.4f}")
            
            # Push metrics
            push_metric("trainer_step_loss", loss.item(), config.pushgateway_url)
            push_metric("trainer_avg_loss", avg_loss, config.pushgateway_url)
    
    final_avg_loss = total_loss / max(step + 1, 1)
    logger.info(f"✅ Training complete. Final avg loss: {final_avg_loss:.4f}")
    
    return final_avg_loss

def evaluate_model(model, tokenizer, holdout_dataset: List[Dict], config: TrainingConfig) -> float:
    """Evaluate model on holdout set"""
    logger.info(f"📊 Evaluating on {len(holdout_dataset)} holdout examples")
    
    model.eval()
    total_loss = 0.0
    num_batches = 0
    
    with torch.no_grad():
        for i in range(0, len(holdout_dataset), config.batch_size):
            batch = holdout_dataset[i:i + config.batch_size]
            inputs = tokenize_data(batch, tokenizer)
            inputs = {k: v.to(model.device) for k, v in inputs.items()}
            
            outputs = model(**inputs)
            total_loss += outputs.loss.item()
            num_batches += 1
    
    val_loss = total_loss / max(num_batches, 1)
    logger.info(f"📊 Validation loss: {val_loss:.4f}")
    
    return val_loss

def main():
    """Main training orchestrator"""
    logger.info("🌀 Starting Spiral LoRA Training")
    
    # Load configuration
    config = TrainingConfig()
    
    if config.dry_run:
        logger.info("🧪 DRY RUN MODE - No actual training")
        
        # Just validate files exist
        if config.train_file.exists():
            logger.info(f"✅ Training file found: {config.train_file}")
        else:
            logger.error(f"❌ Training file missing: {config.train_file}")
            return 1
            
        if config.holdout_file.exists():
            logger.info(f"✅ Holdout file found: {config.holdout_file}")
        else:
            logger.error(f"❌ Holdout file missing: {config.holdout_file}")
            return 1
        
        # Create dummy adapter file
        config.data_dir.mkdir(parents=True, exist_ok=True)
        config.adapter_file.write_text("dummy adapter for dry run")
        config.ready_flag.touch()
        
        logger.info("🎉 Dry run complete!")
        return 0
    
    # Load datasets
    train_data = load_dataset(config.train_file)
    holdout_data = load_dataset(config.holdout_file)
    
    if not train_data:
        logger.error("❌ No training data found")
        return 1
    
    logger.info(f"📊 Loaded {len(train_data)} training, {len(holdout_data)} holdout examples")
    
    # Load model
    model, tokenizer = prepare_model_and_tokenizer(config.base_model)
    
    # Train
    start_time = time.time()
    avg_loss = train_model(model, tokenizer, train_data, config)
    train_time = time.time() - start_time
    
    # Evaluate
    val_loss = evaluate_model(model, tokenizer, holdout_data, config)
    
    # Save adapter
    logger.info(f"💾 Saving adapter to: {config.adapter_file}")
    config.data_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(config.data_dir))
    
    # Create ready flag
    config.ready_flag.write_text(json.dumps({
        "timestamp": time.time(),
        "train_loss": avg_loss,
        "val_loss": val_loss,
        "train_examples": len(train_data),
        "holdout_examples": len(holdout_data),
        "train_time_seconds": train_time,
        "adapter_file": str(config.adapter_file)
    }))
    
    # Push final metrics
    push_metric("trainer_val_loss", val_loss, config.pushgateway_url)
    push_metric("trainer_train_time", train_time, config.pushgateway_url)
    push_metric("trainer_success", 1, config.pushgateway_url)
    
    logger.info("🎉 Training complete!")
    return 0

if __name__ == "__main__":
    sys.exit(main()) 