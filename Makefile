PY := services/api/.venv/bin/python
WEB := apps/web
# REL-1 (ADR-035): ONE port, the API serves the web app. PORT picks it (API_PORT is the old name, kept so
# `make demo API_PORT=...` still works); BIND_HOST 0.0.0.0 would open it to the local network (no HTTPS there).
API_PORT ?= 8000
PORT ?= $(API_PORT)
BIND_HOST ?= 127.0.0.1
VOICE_PORT ?= 8010

.PHONY: setup test lint fmt api api-memory run run-memory web-build doctor tunnel backup db-pack storage-pack smoke demo demo-memory accounts library-import item-bank teaching-plan draft-teaching eval-items trial review-export teach db-ping db-indexes ai-ping web web-live web-install web-check eval-hard eval-rag eval-rag-published eval-grounded voice-setup voice misconception-coverage eval-baselines paper paper-data paper-compact paper-rev eval-chooser model-usage compare-models

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

draft-teaching: ## Draft with Qwen the hints, answers, key ideas and "vì sao" the documents leave out, checked (free-tier quota; ONLY=VERIFY: only those)
	cd services/api && .venv/bin/python -m cavat.draft_teaching "$(ONLY)"

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

paper: ## Build the paper docs/paper/cavat-paper.pdf (Tectonic: brew install tectonic)
	cd docs/paper && tectonic -X compile cavat-paper.tex

paper-compact: ## Build the 8-page version docs/paper/cavat-paper-compact.pdf (Tectonic)
	cd docs/paper && tectonic -X compile cavat-paper-compact.tex

paper-rev: ## Build the 6-page REV-ECIT 2026 version docs/paper/rev-ecit-2026/main.pdf (Tectonic)
	cd docs/paper/rev-ecit-2026 && tectonic -X compile main.tex

paper-data: ## Regenerate docs/paper/data/*.json (database read-only, no writes) and the tables and figures in docs/paper/gen
	cd services/api && .venv/bin/python scripts/paper_corpus.py && .venv/bin/python scripts/paper_rag.py \
		&& .venv/bin/python scripts/paper_student.py && .venv/bin/python scripts/paper_assessment.py \
		&& .venv/bin/python scripts/paper_baselines.py && .venv/bin/python scripts/paper_figures.py

eval-baselines: ## CAVAT against a market chatbot (Gemini) and a prompted LLM (Qwen): hard students and grading (free-tier quota)
	cd services/api && .venv/bin/python scripts/eval_vs_baselines.py

eval-chooser: ## How Qwen picks among the moves the policy allows, on many turns (AUTO-3; reads the database, writes none; uses the Groq quota)
	cd services/api/scripts && ../.venv/bin/python eval_chooser.py

model-usage: ## What the model calls of the real sessions cost: model, tokens, 429 and its limit (reads the database, writes none; DAYS=7, SESSION=id)
	cd services/api && .venv/bin/python scripts/model_usage.py $(if $(DAYS),--days $(DAYS)) $(if $(SESSION),--session $(SESSION))

compare-models: ## BRAIN-1: the same real hard turns put to several models, side by side in evals/reports (reads the database, writes none; MODELS="qwen/qwen3.8-27b openai/gpt-oss-120b ...")
	cd services/api && .venv/bin/python scripts/compare_tutor_models.py --models $(MODELS) $(if $(CASES),--cases $(CASES))

misconception-coverage: ## Which misconceptions of the published chapters the tutor recognises (reads the database, writes none)
	cd services/api && .venv/bin/python scripts/misconception_coverage.py

voice-setup: ## Install the tutor's voice (VieNeu-TTS, local, CPU) in its own environment services/voice/.venv
	python3.11 -m venv services/voice/.venv && services/voice/.venv/bin/pip install -q -r services/voice/requirements.txt

voice: ## Run the tutor's voice server on 127.0.0.1:8010 (make voice-setup first; the first start downloads the model)
	cd services/voice && exec .venv/bin/python server.py

# The tutor's voice server (VieNeu, local), started by make run when `make voice-setup` was done (VOICE=off: not).
VOICE ?= on
VOICE_START := if [ "$(VOICE)" = off ]; then :; elif [ -x services/voice/.venv/bin/python ]; then \
		(cd services/voice && VOICE_PORT=$(VOICE_PORT) exec .venv/bin/python server.py) & \
		else echo "Giọng gia sư: chưa cài VieNeu (make voice-setup), trình duyệt sẽ tự đọc."; fi

web-build: web-install ## Build the web app (VITE_API=http) into apps/web/dist, only when the sources are newer than the last build
	@if services/api/.venv/bin/python -m cavat.webbuild; then :; else \
		echo "Dựng web (VITE_API=http)..."; \
		(cd $(WEB) && VITE_API=http pnpm build) && services/api/.venv/bin/python -m cavat.webbuild --mark; fi

run: web-build ## The latest build at ONE port (PORT=8000): web app + API together, saved in the database of services/api/.env. Ctrl+C stops it
	@echo "Buổi học và hội thoại được lưu vào database $$(cd services/api && .venv/bin/python -c 'from cavat.config import get_settings; print(get_settings().mongodb_db)') trong services/api/.env. Chạy thử không lưu: make run-memory."
	@cd services/api && .venv/bin/python -m cavat.db --ensure-indexes
	@echo "Mở http://localhost:$(PORT) khi thấy dòng 'Uvicorn running'. Học sinh ở máy khác: make tunnel. Ctrl+C để dừng."
	@trap 'kill 0' EXIT; $(VOICE_START); \
	cd services/api && VIENEU_URL=http://127.0.0.1:$(VOICE_PORT) .venv/bin/uvicorn cavat.main:app --host $(BIND_HOST) --port $(PORT) --no-server-header

run-memory: web-build ## Like make run on an in-memory database: nothing is saved, everything is lost on Ctrl+C
	@echo "Database trong bộ nhớ: không lưu gì, Ctrl+C là mất hết. Mở http://localhost:$(PORT) khi thấy dòng 'Uvicorn running'."
	@trap 'kill 0' EXIT; $(VOICE_START); \
	cd services/api && AUTH_MODE=$${AUTH_MODE:-demo} VIENEU_URL=http://127.0.0.1:$(VOICE_PORT) CAVAT_API_HOST=$(BIND_HOST) CAVAT_API_PORT=$(PORT) .venv/bin/python scripts/dev_memory_api.py

demo: ## Old name of make run
	@echo "make demo đã đổi tên thành make run (một cổng, $(PORT)): chạy make run."
	@$(MAKE) --no-print-directory run

demo-memory: ## Old name of make run-memory
	@echo "make demo-memory đã đổi tên thành make run-memory (một cổng, $(PORT)): chạy make run-memory."
	@$(MAKE) --no-print-directory run-memory

doctor: ## Before a trial: check keys, database, models, voice, port, disk, build (read-only; LIVE=1 also calls each model once)
	cd services/api && .venv/bin/python -m cavat.doctor --port $(PORT) $(if $(LIVE),--live,)

tunnel: ## A public HTTPS address for the app at PORT (Cloudflare quick tunnel) while this runs; start make run first
	cd services/api && .venv/bin/python -m cavat.tunnel --port $(PORT)

backup: ## Export every collection of the database of services/api/.env to var/storage/backups/<time>/*.jsonl (read-only)
	cd services/api && .venv/bin/python -m cavat.backup

db-pack: ## Pack the database of services/api/.env into db-dump/cavat-db-<time>.tar.gz for the server's restore (read-only; the file holds the children's words, never on git)
	@mkdir -p db-dump
	cd services/api && .venv/bin/python -m cavat.backup --archive ../../db-dump/cavat-db-$$(date -u +%Y%m%dT%H%M%SZ).tar.gz

storage-pack: ## Pack documents, voice files and runtime caches for the server (private; no backup or trial outputs)
	@mkdir -p db-dump
	cd services/api && .venv/bin/python -m cavat.storage_transfer pack ../../db-dump/cavat-storage-$$(date -u +%Y%m%dT%H%M%SZ).tar.gz

smoke: ## Start make run-memory on a free port, curl /health and /, stop it (what CI does for the one-port build)
	services/api/.venv/bin/python services/api/scripts/smoke_one_port.py

web-check: web-install ## Lint, type-check, test and build the web app (same as CI)
	cd $(WEB) && pnpm lint && pnpm test && pnpm build
