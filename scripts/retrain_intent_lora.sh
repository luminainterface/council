#!/bin/bash
# scripts/retrain_intent_lora.sh - Intent Classifier Retraining
# Grab-and-go script for Week 2 completion

set -euo pipefail

echo "🧠 Intent Classifier Retraining - Week 2 Final Push"
echo "=================================================="

DATA_DIR=data/intent_v2
LOGS=logs/intent_train_$(date +%Y%m%d_%H%M)

# Create directories
mkdir -p $DATA_DIR
mkdir -p $LOGS

echo "📊 Extracting intent examples from chat logs..."
python scripts/extract_intent_examples.py \
  --logs_path logs/chat/*.jsonl \
  --output $DATA_DIR/raw.jsonl \
  --new_intents package_install service_restart file_write

echo "🔀 Splitting train/validation sets..."
python scripts/split_train_val.py --in $DATA_DIR/raw.jsonl --out $DATA_DIR

echo "🚀 Starting LoRA fine-tuning..."
accelerate launch scripts/finetune_lora.py \
  --model tinyllama_1b_chat_exllama2 \
  --train_file $DATA_DIR/train.jsonl \
  --validation_file $DATA_DIR/val.jsonl \
  --output_dir models/intent-10 \
  --epochs 1 \
  --lr 1e-4 \
  --bf16 \
  --target_modules q_proj,v_proj \
  --logging_dir $LOGS

echo "✅ Training complete! Updating model config..."
echo 'intent_model: models/intent-10' >> config/models.yaml

echo "🎉 Intent classifier retrained successfully!"
echo "   Model: models/intent-10"  
echo "   New intents: package_install, service_restart, file_write"
echo "   Training logs: $LOGS" 