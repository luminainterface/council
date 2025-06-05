@echo off
REM Autonomous Software Spiral - Nightly Maintenance
REM Runs pattern mining, distillation, and cost reporting

echo %date% %time% - Starting nightly spiral maintenance

cd /d T:\LAB

REM 1. Run pattern mining on yesterday's completions
echo [SPIRAL] Running pattern mining...
python pattern_miner.py data/completions logs/successful_completions.json --verbose

REM 2. Generate daily cost report
echo [SPIRAL] Generating cost report...
python -c "from cost_tracker import get_cost_tracker; tracker = get_cost_tracker(); summary = tracker.generate_daily_summary(); tracker.save_daily_report(summary); print(f'Daily cost: ${summary.total_cost_usd:.4f}, Saved: ${summary.total_saved_usd:.4f}')"

REM 3. Run nightly distillation (if training data available)
echo [SPIRAL] Running nightly distillation...
python nightly_distiller.py --verbose

REM 4. Clean old cache entries and patterns
echo [SPIRAL] Cleaning old data...
python -c "from cache.shallow_cache import clear_cache; print('Cache maintenance complete')"

REM 5. Update provider retirement candidates
echo [SPIRAL] Checking provider retirement...
python -c "from cost_tracker import get_cost_tracker; tracker = get_cost_tracker(); candidates = tracker.get_retirement_candidates(); print(f'Retirement candidates: {candidates}')"

echo %date% %time% - Nightly spiral maintenance complete
echo. 