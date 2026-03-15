# SDD Template - Makefile
# Common commands for Spec-Driven Development workflow

.PHONY: help install dev test lint format clean \
        spec-lint spec-coverage spec-compliance spec-drift \
        generate-contracts generate-docs generate-scaffold \
        sdd-check

# Python executable (use venv if available)
PYTHON := $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
PYTEST := $(if $(wildcard .venv/bin/pytest),.venv/bin/pytest,pytest)

# Default target
help:
	@echo "SDD Template - Available Commands"
	@echo "================================"
	@echo ""
	@echo "Development:"
	@echo "  make install         Install dependencies"
	@echo "  make dev             Start development server"
	@echo "  make test            Run all tests"
	@echo "  make lint            Run linters"
	@echo "  make format          Format code"
	@echo ""
	@echo "SDD Workflow:"
	@echo "  make spec-lint       Lint all specs"
	@echo "  make spec-coverage   Check spec-to-test coverage"
	@echo "  make spec-compliance Check implementation compliance"
	@echo "  make spec-drift      Detect spec drift"
	@echo "  make sdd-check       Run all SDD checks"
	@echo ""
	@echo "Code Generation:"
	@echo "  make generate-contracts  Generate data contracts"
	@echo "  make generate-docs       Generate documentation"
	@echo "  make generate-scaffold   Generate code scaffold"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean           Remove generated files"

# Development commands
install:
	$(PYTHON) -m pip install -e ".[dev]"
	@if [ -f package.json ]; then npm install; fi

dev:
	PYTHONPATH=$(PWD) $(PYTHON) -m uvicorn src.main:app --reload --port 8000

test:
	PYTHONPATH=$(PWD) $(PYTEST) tests/ -v --cov=src --cov-report=term-missing

test-acceptance:
	PYTHONPATH=$(PWD) $(PYTEST) tests/acceptance/ -v

test-unit:
	PYTHONPATH=$(PWD) $(PYTEST) tests/unit/ -v

test-integration:
	PYTHONPATH=$(PWD) $(PYTEST) tests/integration/ -v

lint:
	$(PYTHON) -m ruff check . --fix
	$(PYTHON) -m mypy src/

format:
	$(PYTHON) -m black .
	$(PYTHON) -m isort .

# SDD Workflow commands
# These invoke Claude Code skills

spec-lint:
	@echo "Running spec linter..."
	@claude /spec-lint specs/

spec-coverage:
	@echo "Checking spec coverage..."
	@claude /spec-coverage-tracker specs/ tests/

spec-compliance:
	@echo "Checking implementation compliance..."
	@claude /implementation-compliance-checker specs/ src/

spec-drift:
	@echo "Detecting spec drift..."
	@claude /spec-drift-detector specs/ src/

sdd-check: spec-lint spec-coverage spec-compliance
	@echo "All SDD checks passed!"

# Code generation
generate-contracts:
	@echo "Generating data contracts..."
	@claude /data-contract-generator specs/ contracts/

generate-docs:
	@echo "Generating documentation..."
	@claude /living-doc-generator specs/ docs/

generate-scaffold:
	@echo "Enter spec file path (e.g., specs/features/FEAT-001.yaml):"
	@read spec_path; \
	claude /spec-to-scaffold-generator $$spec_path

generate-stubs:
	@echo "Generating interface stubs..."
	@claude /stub-first-builder specs/ stubs/

generate-tests:
	@echo "Enter spec file path:"
	@read spec_path; \
	claude /test-generation $$spec_path

# Git workflow
commit:
	@claude /safe-commit

pr:
	@claude /commit-push-pr

# Database
db-migrate:
	alembic upgrade head

db-rollback:
	alembic downgrade -1

db-reset:
	alembic downgrade base && alembic upgrade head

# Cleanup
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .coverage htmlcov/ .mypy_cache/

# Docker
docker-build:
	docker build -t sdd-template:latest .

docker-run:
	docker-compose up -d

docker-stop:
	docker-compose down
