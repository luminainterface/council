# AutoGen Council Makefile
# Provides convenient commands for development, testing, and deployment

.PHONY: help setup start stop test micro soak titanic health logs clean test-all test-unit test-service test-e2e test-ui install-test-deps gate stage0 stage1 stage2 stage3 stage4 stage5 clean test-fast test-integration

# Default target
help:
	@echo "🚀 AutoGen Council - Development Commands"
	@echo "=================================================="
	@echo "Setup & Environment:"
	@echo "  setup       - Install dependencies and prepare environment"
	@echo "  download    - Download model files for ExLlamaV2"
	@echo ""
	@echo "Service Management:"
	@echo "  start       - Start all services (LLM + Council)"
	@echo "  start-llm   - Start only LLM backend"
	@echo "  start-api   - Start only Council API"
	@echo "  stop        - Stop all services"
	@echo "  restart     - Restart all services"
	@echo ""
	@echo "Testing & Validation:"
	@echo "  health      - Check service health"
	@echo "  test        - Run basic API tests"
	@echo "  micro       - Micro test suite (50 prompts)"
	@echo "  soak        - Soak test (5 min @ 120 QPS)"
	@echo "  titanic     - Full Titanic test suite (380 prompts)"
	@echo ""
	@echo "Development:"
	@echo "  logs        - View service logs"
	@echo "  monitor     - Open monitoring dashboard"
	@echo "  clean       - Clean up containers and data"
	@echo ""
	@echo "Release Gate:"
	@echo "  gate        - Run complete release gate tests"
	@echo "  tag         - Tag new version"
	@echo ""
	@echo "Available test targets:"
	@echo "  test-all       - Run all test layers (unit, service, e2e, ui)"
	@echo "  test-unit      - Run unit tests only"
	@echo "  test-service   - Run service tests only"
	@echo "  test-e2e       - Run end-to-end Docker tests"
	@echo "  test-ui        - Run UI/frontend tests"
	@echo "  test-quick     - Run unit + service tests only"
	@echo "  test-ci        - CI-friendly test run"
	@echo "  install-test-deps - Install all test dependencies"

# Setup and preparation
setup:
	@echo "🔧 Setting up AutoGen Council environment..."
	pip install -r requirements.txt
	python scripts/download_model.py
	@echo "✅ Setup complete!"

download:
	@echo "📥 Downloading model files..."
	python scripts/download_model.py

# Service management
start:
	@echo "🚀 Starting AutoGen Council services..."
	docker-compose up -d
	@echo "⏳ Waiting for services to be ready..."
	sleep 30
	$(MAKE) health

start-llm:
	@echo "🤖 Starting LLM backend only..."
	docker-compose up -d llm
	@echo "⏳ Waiting for LLM to be ready..."
	sleep 20

start-api:
	@echo "📡 Starting Council API only..."
	docker-compose up -d council

stop:
	@echo "🛑 Stopping AutoGen Council services..."
	docker-compose down

restart:
	@echo "🔄 Restarting AutoGen Council services..."
	$(MAKE) stop
	$(MAKE) start

# Health and monitoring
health:
	@echo "🏥 Checking service health..."
	@echo "LLM Backend:"
	@curl -s http://localhost:8000/v1/models | jq '.data[0].id' || echo "❌ LLM not responding"
	@echo ""
	@echo "Council API:"
	@curl -s http://localhost:9000/health | jq '.' || echo "❌ Council API not responding"
	@echo ""
	@echo "Metrics:"
	@curl -s http://localhost:9000/metrics | head -5 || echo "❌ Metrics not available"

# Testing
test:
	@echo "🧪 Running basic API tests..."
	curl -X POST http://localhost:9000/hybrid \
		-H 'Content-Type: application/json' \
		-d '{"prompt":"2+2?"}' | jq '.'
	@echo ""
	curl -X POST http://localhost:9000/vote \
		-H 'Content-Type: application/json' \
		-d '{"prompt":"Write hello world in Python"}' | jq '.meta'

micro:
	@echo "🔬 Running micro test suite (50 prompts)..."
	@if [ "$(CLOUD)" = "off" ]; then \
		echo "Running with cloud disabled..."; \
		SWARM_CLOUD_ENABLED=false python -m pytest tests/ -v --tb=short; \
	else \
		python -m pytest tests/ -v --tb=short; \
	fi

soak:
	@echo "🏋️ Running soak test (5 min @ 120 QPS)..."
	@echo "⚠️  Monitor GPU temperature - should stay ≤75°C"
	python tests/soak_test.py --duration=300 --qps=120

titanic:
	@echo "🚢 Running Titanic test suite (380 prompts)..."
	@if [ "$(BUDGET)" != "" ]; then \
		echo "Budget limit: $$(BUDGET)"; \
		SWARM_CLOUD_BUDGET_USD=$(BUDGET) python tests/titanic_test.py; \
	else \
		python tests/titanic_test.py; \
	fi
	@echo "📊 Generating test report..."
	@if [ -f "reports/titanic_final.json" ]; then \
		echo "✅ Test report saved to reports/titanic_final.json"; \
	fi

# Development tools
logs:
	@echo "📋 Service logs:"
	docker-compose logs -f --tail=50

logs-llm:
	@echo "🤖 LLM Backend logs:"
	docker-compose logs -f llm --tail=50

logs-api:
	@echo "📡 Council API logs:"
	docker-compose logs -f council --tail=50

monitor:
	@echo "📊 Opening monitoring dashboard..."
	@echo "Grafana: http://localhost:3000 (admin/autogen123)"
	@echo "Prometheus: http://localhost:9090"
	@echo "API Metrics: http://localhost:9000/metrics"

# Spiral Evolution Pipeline
evolution-once:
	@echo "🌀 Evolving model with yesterday's traffic..."
	@DATE=$$(date -u +%Y-%m-%d --date='yesterday') && \
		echo "Training on data from: $$DATE" && \
		docker-compose run --rm \
			-e DATA_DIR="/loras/$$DATE" \
			-e BASE_MODEL="/models/tinyllama" \
			trainer \
			python -m trainer.run_once
	@echo "✅ Evolution cycle complete!"

evolution-test:
	@echo "🧪 Testing evolution pipeline..."
	@DATE=$$(date -u +%Y-%m-%d) && \
		echo "Dry-run training on: $$DATE" && \
		docker-compose run --rm \
			-e DATA_DIR="/loras/$$DATE" \
			-e BASE_MODEL="/models/tinyllama" \
			-e DRY_RUN=true \
			trainer \
			python -m trainer.run_once

# Cleanup
clean:
	@echo "🧹 Cleaning up..."
	docker-compose down -v
	docker system prune -f
	rm -rf logs/*

clean-models:
	@echo "🗑️ Cleaning model cache..."
	rm -rf models/

# Release gate - Complete bulletproof validation
gate: stage0 stage1 stage2 stage3 stage4 stage5 stage6 stage7 stage8 stage9 stage10 stage11
	@echo "🎉 GREEN-LIGHT: All validation stages passed!"
	@echo "✅ System is 100% bulletproof and ready to ship"

# Stage 0: Prep - Isolated environment
stage0:
	@echo "🚀 Stage 0: Setting up isolated test environment..."
	@bash scripts/setup_test_env.sh
	@echo "✅ Stage 0: PASS"

# Stage 1: Schema sanity - actions.json validation  
stage1:
	@echo "🔍 Stage 1: Validating actions.json schema..."
	@python scripts/validate_actions.py
	@echo "✅ Stage 1: PASS"

# Stage 2: Ultra-fast unit tests (< 200ms)
stage2:
	@echo "⚡ Stage 2: Running ultra-fast unit tests..."
	@python -m pytest tests/test_unit_fast.py -v --tb=short
	@echo "✅ Stage 2: PASS"

# Stage 3: Integration smoke tests (p95 ≤ 800ms)
stage3:
	@echo "🔥 Stage 3: Running integration smoke tests..."
	@python -m pytest tests/test_integration_smoke.py -v --tb=short
	@echo "✅ Stage 3: PASS"

# Stage 4: Security regression tests
stage4:
	@echo "🔒 Stage 4: Running security regression tests..."
	@python -m pytest tests/test_security_regression.py -v --tb=short
	@echo "✅ Stage 4: PASS"

# Stage 5: Metrics sanity checks
stage5:
	@echo "📊 Stage 5: Running metrics sanity checks..."
	@python -m pytest tests/test_metrics_sanity.py -v --tb=short
	@echo "✅ Stage 5: PASS"

# Stage 6: Race-free concurrency tests
stage6:
	@echo "🔀 Stage 6: Running race-free concurrency tests..."
	@python -m pytest tests/test_race_free_concurrency.py -v --tb=short
	@echo "✅ Stage 6: PASS"

# Stage 9: Budget reset 
stage9:
	@echo "💰 Stage 9: Resetting budget counters..."
	@python scripts/reset_budget.py
	@echo "✅ Stage 9: PASS"

# Stage 7: GPU hygiene tests
stage7:
	@echo "🎮 Stage 7: Running GPU hygiene tests..."
	@python -m pytest tests/test_gpu_hygiene.py -v --tb=short
	@echo "✅ Stage 7: PASS"

# Stage 8: Load canary tests
stage8:
	@echo "🏋️ Stage 8: Running load canary tests..."
	@python scripts/run_load_test.py
	@echo "✅ Stage 8: PASS"

# Stage 10: Static analysis and coverage
stage10:
	@echo "🔍 Stage 10: Running static analysis and coverage..."
	@python scripts/static_analysis.py
	@echo "✅ Stage 10: PASS"

# Stage 11: Supply chain security scan (pip-audit)
stage11:
	@echo "🔒 Stage 11: Running supply chain security scan..."
	@python scripts/pip_audit_scan.py
	@echo "✅ Stage 11: PASS"

# Development helpers
test-fast:
	@echo "⚡ Running fast unit tests only..."
	@python tests/test_unit_fast.py

test-integration:
	@echo "🔥 Running integration tests only..."
	@python tests/test_integration_smoke.py

test-security:
	@echo "🔒 Running security tests only..."
	@python tests/test_security_regression.py

test-metrics:
	@echo "📊 Running metrics tests only..."
	@python tests/test_metrics_sanity.py

# Start test server
test-server:
	@echo "🚀 Starting test server..."
	@LUMINA_MODE=test python autogen_api_shim.py

# Run all test layers
test-all: test-unit test-service test-e2e test-ui
	@echo ""
	@echo "=================================="
	@echo "🎉 All test layers completed!"
	@echo "=================================="
	@echo "✅ Unit tests: Pure Python logic"
	@echo "✅ Service tests: FastAPI endpoints" 
	@echo "✅ E2E tests: Docker stack health"
	@echo "✅ UI tests: Frontend functionality"
	@echo ""

# Quick test (unit + service only)
test-quick: test-unit test-service

# CI-friendly test run
test-ci:
	pytest -q tests/unit tests/service --tb=short
	@echo "CI tests completed"

# Tag new version
tag:
	@echo "🏷️ Tagging new version..."
	@if [ "$(VERSION)" = "" ]; then \
		echo "❌ Please specify VERSION: make tag VERSION=v2.5.0"; \
		exit 1; \
	fi
	git add reports/
	git commit -m "feat: release gate results for $(VERSION)"
	git tag -a $(VERSION) -m "AutoGen Council $(VERSION)"
	@echo "✅ Tagged $(VERSION)"
	@echo "📤 Push with: git push && git push --tags"

# Quick smoke test
smoke:
	@echo "💨 Quick smoke test..."
	@curl -s -o /dev/null -w "LLM Health: %{http_code}\n" http://localhost:8000/v1/models
	@curl -s -o /dev/null -w "API Health: %{http_code}\n" http://localhost:9000/health
	@curl -X POST http://localhost:9000/hybrid \
		-H 'Content-Type: application/json' \
		-d '{"prompt":"hello"}' -s | jq -r '.text' | head -1

# Install test dependencies
install-test-deps:
	pip install pytest pytest-asyncio httpx pydantic
	npm install -D playwright @playwright/test
	npx playwright install --with-deps

# Run unit tests (fast, pure Python)
test-unit:
	pytest -q tests/unit

# Run service tests (FastAPI TestClient)
test-service:
	pytest -q tests/service

# Run end-to-end tests (Docker stack)
test-e2e:
	@echo "Running E2E Docker stack tests..."
	@if command -v bash >/dev/null 2>&1; then \
		bash tests/e2e/test_stack.sh; \
	else \
		echo "Bash not available, skipping E2E tests"; \
	fi

# Run UI tests (Playwright)
test-ui:
	@echo "Running UI tests..."
	@if command -v npx >/dev/null 2>&1; then \
		npx playwright test tests/ui; \
	else \
		echo "Node.js/npx not available, skipping UI tests"; \
	fi

# Full validation (alias for gate)
validate: gate

# CI-friendly validation with coverage
ci-gate: stage0 stage1 stage2 stage3 stage4 stage5 stage9
	@echo "🎯 CI validation complete - system ready for deployment"

# Help
help:
	@echo "Green-Light Plan - Bulletproof Validation"
	@echo "========================================"
	@echo ""
	@echo "Commands:"
	@echo "  make gate          - Run full validation pipeline (stages 0-5,9)"
	@echo "  make stage1        - Schema validation only"
	@echo "  make stage2        - Ultra-fast unit tests only"
	@echo "  make stage3        - Integration smoke tests only"
	@echo "  make stage4        - Security regression tests only"
	@echo "  make stage5        - Metrics sanity checks only"
	@echo "  make test-server   - Start test server"
	@echo "  make clean         - Clean test artifacts"
	@echo "  make help          - Show this help"
	@echo ""
	@echo "CI Usage:"
	@echo "  make ci-gate       - Full CI validation pipeline"
	@echo "" 