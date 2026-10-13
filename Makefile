PY := services/api/.venv/bin/python
WEB := apps/web
API_PORT ?= 8000
WEB_PORT ?= 5173

.PHONY: setup test lint fmt api api-memory demo demo-memory accounts library-import item-bank teaching-plan draft-teaching eval-items trial review-export teach db-ping db-indexes ai-ping web web-live web-install web-check eval-hard eval-rag eval-rag-published eval-grounded voice-setup voice

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
	cd services/api && AUTH_MODE=demo .venv/bin/python scripts/dev_memory_api.py

accounts: ## Create or update the three trial accounts (one student, one parent, one teacher) in the database of .env
	cd services/api && .venv/bin/python -m cavat.accounts

library-import: ## Import a folder of teacher documents (DIR=tailieu) into the library of the database of .env, read page by page
	cd services/api && .venv/bin/python -m cavat.library_import "$(DIR)" $(if $(AGAIN),--again,)

item-bank: ## Build the draft item bank of each chapter from the imported teacher documents (database of .env)
	cd services/api && .venv/bin/python -m cavat.item_bank

teaching-plan: ## Build the draft teaching plan (graph, periods, items) of each chapter from the teacher documents
	cd services/api && .venv/bin/python -m cavat.teaching_plan

draft-teaching: ## Draft with Qwen the hints, answers and key ideas the documents leave out, checked (free-tier quota)
	cd services/api && .venv/bin/python -m cavat.draft_teaching

eval-items: ## Mutate every checked answer of the item banks and count how many the checks catch (read-only)
	cd services/api && .venv/bin/python scripts/eval_item_bank.py

trial: ## Scripted learners study the published plans, offline and in memory (reads the database, writes none)
	cd services/api && .venv/bin/python scripts/trial_sessions.py

review-export: ## Export every review decision (who, when, why) to var/storage/reports (read-only)
	cd services/api && .venv/bin/python scripts/review_export.py

teach: ## Talk with the AI tutor in the terminal: the teaching loop on the decimals chapter, offline
	cd services/api && .venv/bin/python scripts/teach_cli.py

eval-hard: ## Ten hard students with the real Qwen and an LLM judge (uses the free-tier quota; not run by make test)
	cd services/api && .venv/bin/python scripts/eval_hard_students.py

eval-rag: ## Hybrid RAG ablation on the labelled questions (offline; LIVE=1 for Gemini embeddings, cached)
	cd services/api && .venv/bin/python scripts/eval_rag.py $(if $(LIVE),--live,)

eval-rag-published: ## Hybrid RAG on the published chapters and teacher documents (reads .env DB only; LIVE=1 for Gemini)
	cd services/api && .venv/bin/python scripts/eval_rag_published.py $(if $(LIVE),--live,)

eval-grounded: ## Qwen answers the child's questions from the RAG, a second model judges (free-tier quota)
	cd services/api && .venv/bin/python scripts/eval_grounded.py "$(ONLY)"

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

voice-setup: ## Install the tutor's voice (VieNeu-TTS, local, CPU) in its own environment services/voice/.venv
	python3.11 -m venv services/voice/.venv && services/voice/.venv/bin/pip install -q -r services/voice/requirements.txt

voice: ## Run the tutor's voice server on 127.0.0.1:8010 (make voice-setup first; the first start downloads the model)
	cd services/voice && exec .venv/bin/python server.py

demo: web-install ## The whole demo, saved: API on the database of services/api/.env (cavat_dev) + web app. Ctrl+C stops both
	@echo "Buổi học và hội thoại được lưu vào database trong services/api/.env (cavat_dev). Chạy thử không lưu: make demo-memory."
	@cd services/api && .venv/bin/python -m cavat.db --ensure-indexes
	@echo "Mở http://localhost:$(WEB_PORT) khi thấy dòng 'Local:'. Bấm Ctrl+C để dừng cả hai server."
	@trap 'kill 0' EXIT; \
	if [ -x services/voice/.venv/bin/python ]; then (cd services/voice && exec .venv/bin/python server.py) & \
	else echo "Giọng gia sư: chưa cài VieNeu (make voice-setup), trình duyệt sẽ tự đọc."; fi; \
	(cd services/api && exec .venv/bin/uvicorn cavat.main:app --port $(API_PORT)) & \
	cd $(WEB) && CAVAT_API_PORT=$(API_PORT) VITE_API=http pnpm dev --port $(WEB_PORT) --strictPort

demo-memory: web-install ## The demo on an in-memory database: nothing is saved, everything is lost on Ctrl+C
	@echo "Database trong bộ nhớ: không lưu gì, Ctrl+C là mất hết. Mở http://localhost:$(WEB_PORT) khi thấy dòng 'Local:'."
	@trap 'kill 0' EXIT; \
	(cd services/api && AUTH_MODE=demo CAVAT_API_PORT=$(API_PORT) exec .venv/bin/python scripts/dev_memory_api.py) & \
	cd $(WEB) && CAVAT_API_PORT=$(API_PORT) VITE_API=http pnpm dev --port $(WEB_PORT) --strictPort

web-check: web-install ## Lint, type-check, test and build the web app (same as CI)
	cd $(WEB) && pnpm lint && pnpm test && pnpm build
