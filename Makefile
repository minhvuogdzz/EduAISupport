PY := services/api/.venv/bin/python
WEB := apps/web
API_PORT ?= 8000
WEB_PORT ?= 5173

.PHONY: setup test lint fmt api api-memory demo demo-memory teach db-ping db-indexes ai-ping web web-live web-install web-check

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

api-memory: ## Run the API on an in-memory database: nothing is written to Atlas, sessions are lost on restart
	cd services/api && .venv/bin/python scripts/dev_memory_api.py

teach: ## Talk with the AI tutor in the terminal: the teaching loop on the decimals chapter, offline
	cd services/api && .venv/bin/python scripts/teach_cli.py

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

web-live: web-install ## Run the web app against the real API (start "make api" in another terminal first)
	cd $(WEB) && VITE_API=http pnpm dev

demo: web-install ## The whole demo, saved: API on the database of services/api/.env (cavat_dev) + web app. Ctrl+C stops both
	@echo "Buổi học và hội thoại được lưu vào database trong services/api/.env (cavat_dev). Chạy thử không lưu: make demo-memory."
	@cd services/api && .venv/bin/python -m cavat.db --ensure-indexes
	@echo "Mở http://localhost:$(WEB_PORT) khi thấy dòng 'Local:'. Bấm Ctrl+C để dừng cả hai server."
	@trap 'kill 0' EXIT; \
	(cd services/api && exec .venv/bin/uvicorn cavat.main:app --port $(API_PORT)) & \
	cd $(WEB) && CAVAT_API_PORT=$(API_PORT) VITE_API=http pnpm dev --port $(WEB_PORT) --strictPort

demo-memory: web-install ## The demo on an in-memory database: nothing is saved, everything is lost on Ctrl+C
	@echo "Database trong bộ nhớ: không lưu gì, Ctrl+C là mất hết. Mở http://localhost:$(WEB_PORT) khi thấy dòng 'Local:'."
	@trap 'kill 0' EXIT; \
	(cd services/api && CAVAT_API_PORT=$(API_PORT) exec .venv/bin/python scripts/dev_memory_api.py) & \
	cd $(WEB) && CAVAT_API_PORT=$(API_PORT) VITE_API=http pnpm dev --port $(WEB_PORT) --strictPort

web-check: web-install ## Lint, type-check, test and build the web app (same as CI)
	cd $(WEB) && pnpm lint && pnpm test && pnpm build
