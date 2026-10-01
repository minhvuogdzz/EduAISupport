PY := services/api/.venv/bin/python
WEB := apps/web

.PHONY: setup test lint fmt api db-ping db-indexes ai-ping web web-install web-check

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

db-indexes: ## Create MongoDB indexes declared by the repositories (idempotent)
	cd services/api && .venv/bin/python -m cavat.db --ensure-indexes

ai-ping: ## Call Groq (Qwen) and Gemini (vision) once with the keys in services/api/.env (local only)
	cd services/api && .venv/bin/python scripts/ai_ping.py

web-install: ## Install the web app dependencies from the lockfile (Node >= 22.13, pnpm 10)
	cd $(WEB) && pnpm install --frozen-lockfile

web: web-install ## Run the web app with the mock API at http://localhost:5173
	cd $(WEB) && pnpm dev

web-check: web-install ## Lint, type-check, test and build the web app (same as CI)
	cd $(WEB) && pnpm lint && pnpm test && pnpm build
