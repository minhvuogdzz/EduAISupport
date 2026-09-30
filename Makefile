PY := services/api/.venv/bin/python

.PHONY: setup test lint fmt api db-ping

setup: ## Create the venv (Python 3.11+) and install dependencies
	@test -d services/api/.venv || python3.11 -m venv services/api/.venv
	$(PY) -m pip install -q --upgrade pip
	$(PY) -m pip install -q -e "services/api[dev]"

test:
	$(PY) -m pytest -q

lint:
	$(PY) -m ruff check services/api evals
	$(PY) -m ruff format --check services/api evals

fmt:
	$(PY) -m ruff format services/api evals
	$(PY) -m ruff check --fix services/api evals

api:
	cd services/api && .venv/bin/uvicorn cavat.main:app --reload --port 8000

db-ping:
	cd services/api && .venv/bin/python -m cavat.db
