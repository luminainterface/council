#!/usr/bin/env bash
set -euo pipefail

# Traffic Snapshot Pipeline
# Converts live Redis traffic into training-ready JSONL files
# Runs at 01:55 UTC daily via cron

STAMP=$(date -u +%Y-%m-%d)
WORK=/workspace/snapshots/$STAMP
mkdir -p "$WORK"

echo "🌀 [$(date -u)] Starting traffic snapshot for $STAMP"

# Step 1: Redis BGSAVE
echo "[BGSAVE] Creating Redis RDB snapshot..."
redis-cli --rdb "$WORK/raw.rdb"
echo "✅ RDB snapshot captured"

# Step 2: Parse RDB to SQLite
echo "[PARSE] Converting RDB → SQLite..."
python -m snapshot.rdb2sqlite "$WORK/raw.rdb" "$WORK/traffic.db"
echo "✅ SQLite database created"

# Step 3: Export to weighted JSONL (with reward data)
echo "[EXPORT] Generating weighted JSONL training files..."
python -m snapshot.weighted_jsonl \
    --db "$WORK/traffic.db" \
    --out-train "$WORK/train.jsonl" \
    --out-holdout "$WORK/holdout.jsonl"
echo "✅ Weighted JSONL files generated with reward buffer integration"

# Step 4: Package for trainer
echo "[PACKAGE] Compressing and staging..."
DEST=/loras/$STAMP
mkdir -p "$DEST"

gzip -9 <"$WORK/train.jsonl" >"$DEST/train.jsonl.gz"
gzip -9 <"$WORK/holdout.jsonl" >"$DEST/holdout.jsonl.gz"
cp "$WORK/traffic.db" "$DEST/"

echo "✅ Snapshot complete: $DEST"

# Cleanup old snapshots (keep last 7 days)
find /workspace/snapshots -maxdepth 1 -type d -name "20*" -mtime +7 -exec rm -rf {} \; 2>/dev/null || true
find /loras -maxdepth 1 -type d -name "20*" -mtime +14 -exec rm -rf {} \; 2>/dev/null || true

echo "🌀 [$(date -u)] Traffic snapshot pipeline complete" 