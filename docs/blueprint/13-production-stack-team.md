# 13 — Production Architecture · Tech Stack · Development Foundation · Team Model · Parallel Workstreams

> PART 37 → PART 40, gồm Development Foundation (brief §60).

---

## PART 37 — PRODUCTION ARCHITECTURE

### 37.1. Kiến trúc đích (sau pilot, ~1,000–10,000 học sinh)

> **v0.2:** đây là kiến trúc **tham chiếu** cho khi sản phẩm vượt phạm vi đồ án. Trong đồ án, hệ thống chạy bằng Docker Compose (ADR-011 v0.2). Cấu trúc module giữ nguyên, nên chuyển lên kiến trúc này không cần viết lại.

```mermaid
flowchart TB
    subgraph Client
        WEB["Web App (React SPA / PWA)"]
    end
    subgraph Edge
        CDN["CDN + WAF"]
        LB["Global HTTPS LB"]
    end
    subgraph Compute["Cloud Run (asia-southeast1)"]
        API["api (modular monolith)<br/>autoscale"]
        VGW["voice-gateway<br/>(WebSocket/WebRTC, tách riêng)"]
        WRK["workers<br/>(ingestion, projector, scheduler, notification)"]
    end
    subgraph Data
        PG[("Cloud SQL Postgres HA<br/>+ read replica")]
        REDIS[("Memorystore Redis<br/>pub/sub SSE fan-out, rate limit")]
        GCS[("Cloud Storage<br/>docs, audio (lifecycle)")]
        WH[("Warehouse (BigQuery)<br/>qua CDC, ẩn danh hóa")]
    end
    subgraph AI["AI Providers (qua ai_gateway)"]
        P1["Claude (API trực tiếp hoặc Vertex)"]
        P2["Gemini Live / STT (Google)"]
        P3["Pronunciation (Azure)"]
    end
    subgraph Ops
        OTEL["OpenTelemetry → Monitoring"]
        SENTRY["Sentry"]
        SM["Secret Manager + KMS"]
    end
    WEB --> CDN --> LB
    LB --> API
    LB --> VGW
    API --> PG
    API --> REDIS
    API --> GCS
    WRK --> PG
    WRK --> GCS
    VGW --> API
    API --> AI
    VGW --> AI
    WRK --> AI
    PG -. CDC .-> WH
    API & VGW & WRK --> OTEL
```

### 37.2. Lộ trình tiến hóa từ MVP

| Bước | Kích hoạt khi | Thay đổi |
|---|---|---|
| MVP (đồ án, v0.2) | — | Docker Compose: api + worker + Postgres/pgvector + MinIO (ADR-011) |
| +Redis | Nhiều instance api cần fan-out SSE, rate limit phân tán | Memorystore |
| +Voice Gateway | Phase English Speaking | Service riêng, kết nối dài, scale theo concurrent streams |
| +HA + replica | Vận hành thật, ngoài phạm vi đồ án | Cloud SQL HA, PITR, replica cho reporting |
| +Warehouse | Cần phân tích cohort và nghiên cứu | CDC → BigQuery (ẩn danh hóa) |
| Region trong nước | Nếu cần khi vượt phạm vi đồ án (O5 đã đóng trong đồ án, D-T2) | Di chuyển DB và storage; giữ AI provider qua cơ chế tối thiểu hóa dữ liệu |

### 37.3. Mục tiêu vận hành production

SLO: tutor turn TTFT p95 ≤ 2s; availability 99.5% trong khung giờ học; RPO ≤ 5 phút (PITR); RTO ≤ 1 giờ. Load target: 2,000 session đồng thời (giả sử 10,000 học sinh, 20% học cùng khung giờ).

---

## PART 38 — TECH STACK

Mỗi lựa chọn có: Lý do · Trade-off · Chi phí · Khả năng đảo ngược.

> **v0.2 (D-T4):** các dòng dưới đây đã chuyển sang lựa chọn miễn phí. Kiến trúc cloud ở PART 37 là tham chiếu khi vượt phạm vi đồ án.

| Lớp | Lựa chọn | Lý do | Trade-off | Chi phí | Đảo ngược |
|---|---|---|---|---|---|
| **Frontend** | React + TypeScript + Vite (SPA/PWA), TanStack Query, Tailwind; KaTeX hiển thị toán; Web Audio cho mic | Sau login, không cần SSR; hệ sinh thái lớn; PWA đủ cho tablet | Không SEO (không cần) | $0 (hosting tĩnh) | Dễ |
| **Backend** | Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2 + Alembic | AI/eval/parsing/số học chính xác; schema Pydantic → JSON Schema dùng chung | Hai ngôn ngữ trong repo | — | **Khó** |
| **Database** | PostgreSQL 16+ + pgvector, chạy bằng Docker (v0.2) | Một hệ thống cho OLTP, event, job, vector; RLS | Phải tự quản partition và vacuum cho bảng event | $0 | **Khó** (dữ liệu) |
| **Cache** | Chưa dùng ở MVP → Memorystore Redis khi scale | Tránh hệ thống thừa | — | ~$35+/tháng khi thêm | Dễ |
| **Queue** | Postgres-backed queue (Procrastinate) + transactional outbox | Cùng transaction với dữ liệu; không thêm hạ tầng | Throughput thấp hơn broker chuyên dụng (đủ cho MVP) | $0 | Dễ (sang Pub/Sub) |
| **Object Storage** | MinIO (S3-compatible, chạy bằng Docker; v0.2), bucket riêng cho docs và audio | Miễn phí, signed URL, cùng API với S3/GCS nên chuyển dễ | Tự quản dung lượng đĩa | $0 | Dễ |
| **Search** | Postgres full-text (tsvector + unaccent) | Đủ cho tìm tài liệu giáo viên | Tiếng Việt cần xử lý dấu | $0 | Dễ |
| **Vector DB** | pgvector (HNSW) | Filter theo scope ngay trong SQL; quy mô nhỏ | Kém hơn vector DB chuyên dụng ở hàng trăm triệu vector | $0 | Dễ |
| **AI — tutor** | **`gemini-3.8-flash`** (free tier, v0.2); fallback `gemini-3.5-flash`, `gemini-2.5-flash`; Claude làm mốc so sánh nếu có credit | Miễn phí; structured output; context caching miễn phí ở free tier | Hạn mức request theo project; dữ liệu free tier được dùng để cải thiện sản phẩm (đã chấp nhận, D-T3) | $0 | Dễ (qua Gateway) |
| **AI — lightweight** | `gemini-3.5-flash-lite` (free tier) | Nhanh; giữ hạn mức của model tutor cho giờ học | Không có context caching ở free tier | $0 | Dễ |
| **Embedding** | Gemini Embedding 2 (free tier); dự phòng `bge-m3` chạy local | Đa ngôn ngữ | Re-embed khi đổi | $0 | Dễ |
| **STT** | Chọn sau spike, đều miễn phí: Web Speech API (prototype), `gemini-3.5-transcribe-live` (free tier), PhoWhisper/faster-whisper chạy local | vi-VN | Web Speech ổn định nhất trên Chrome; model local cần CPU/GPU | $0 | Dễ |
| **Voice realtime** | Theo POC 6: `gemini-3.8-live` (free tier) hoặc cascade miễn phí | Latency | Kiểm soát sư phạm (PART 20); hạn mức free tier | $0 | Trung bình |
| **TTS** | `gemini-3.8-flash-tts` (free tier); dự phòng `SpeechSynthesis` của trình duyệt | Giọng tự nhiên vi-VN/en | Hạn mức | $0 | Dễ |
| **Pronunciation** | Azure Speech gói F0 (miễn phí 5 giờ/tháng; cần xác minh có pronunciation assessment) | Điểm theo từ/âm vị | Thêm vendor; hạn mức giờ | $0 | Dễ |
| **Math engine** | Python `fractions`/`decimal` + SymPy (khi cần) | Chính xác tuyệt đối | — | $0 | Dễ |
| **Doc parsing** | PyMuPDF, python-pptx, LibreOffice headless (render) + LLM vision | Hiệu quả với PDF/PPTX | License PyMuPDF là AGPL/thương mại → **cần kiểm tra** hoặc dùng pypdfium2 | $0 / license | Dễ |
| **Auth** | Tự xây trên thư viện đã kiểm chứng (argon2-cffi, itsdangerous/sessions), OIDC cho Google SSO | Tài khoản trẻ không email là đặc thù; SaaS auth thường không hợp | Tự chịu trách nhiệm bảo mật → security review | $0 | **Khó** |
| **Monitoring** | OpenTelemetry + Prometheus/Grafana/Loki chạy local, Sentry gói miễn phí, Langfuse self-host (tùy chọn) | Chuẩn mở, miễn phí | Tự vận hành | $0 | Dễ |
| **Deployment** | Docker Compose + Cloudflare Tunnel (HTTPS miễn phí) cho kiểm thử; VM miễn phí khi cần chạy 24/7 (ADR-011 v0.2); GitHub Actions cho CI | Miễn phí; một cấu hình chạy mọi nơi | Phụ thuộc máy chạy | $0 | Dễ |
| **E2E test** | Playwright | Test UI + SSE | — | $0 | Dễ |
| **Load test** | k6 | Script JS, hỗ trợ SSE/WS | — | $0 | Dễ |

---

## DEVELOPMENT FOUNDATION (brief §60)

### Repository (monorepo)

```text
EduAISupport/
├── CLAUDE.md                     # quy ước cho mọi phiên AI (local/cloud)
├── README.md
├── docs/
│   ├── blueprint/                # tài liệu này
│   ├── adr/                      # ADR-001… (mỗi quyết định một file)
│   ├── pedagogy/                 # lesson specs, KC, misconception, assessment spec G5
│   └── poc/                      # decision memo của POC
├── packages/
│   └── schemas/                  # JSON Schema: tutor-contract, events, tutor-turn, lesson-package (nguồn sự thật)
├── services/
│   └── api/                      # FastAPI modular monolith
│       ├── app/modules/{identity,org,curriculum,content,scheduling,session,tutor,assessment,learner,reporting,notification,voice,ai_gateway,audit}/
│       ├── app/tutor/prompts/    # constitution.v1.md, math_g5.v1.md …
│       ├── app/policies/         # tutor/hint/mastery/model/safety *.yaml (versioned)
│       ├── migrations/
│       └── tests/
├── apps/
│   └── web/                      # React SPA (student, teacher, parent)
├── evals/
│   ├── datasets/                 # socratic, hint, grounding, assessment, redteam (jsonl, có version)
│   ├── synthetic_students/
│   ├── runners/
│   └── reports/
├── poc/                          # code vứt đi; không được import từ services/ hoặc apps/
└── infra/                        # terraform, docker, compose
```

### Environments

| Env | Mục đích | Dữ liệu | AI |
|---|---|---|---|
| local | Dev | Seed tổng hợp | Provider thật với key dev, hoặc **stub ghi/phát lại** (record/replay) để test không tốn tiền |
| ci | Test tự động | Ephemeral (testcontainers) | Stub; eval AI chạy ở job riêng |
| staging | Tích hợp, demo, kiểm thử với học sinh (có thể là chính máy local qua Cloudflare Tunnel) | Tổng hợp + dữ liệu kiểm thử | Gemini free tier |
| production | Kiểm thử với học sinh thật (v0.2: có thể trùng staging) | Thật (D-T3) | Gemini free tier (ADR-016) |

### Secrets

`.env` ở local (đã nằm trong `.gitignore`) kèm `.env.example`; GitHub Actions secrets cho CI; Secret Manager khi lên cloud. Không có secret trong repo. Key AI tách theo môi trường và được luân chuyển định kỳ.

### Local development

`docker compose up` (Postgres + pgvector, MinIO) → `make migrate seed` → `make dev` (api + web + worker). Seed gồm: 1 trường, 1 lớp, 1 giáo viên, 5 học sinh (synthetic profiles), 1 phụ huynh, 1 lesson đã publish, lịch "đang diễn ra ngay bây giờ" để test session tức thì.

### Database migration và seed

Alembic, migration nhỏ, có review. Mỗi migration phải chạy được up/down trong CI. Seed tất định (fixed UUIDs) để test E2E ổn định.

### Testing và CI/CD

- PR: lint (ruff, eslint), type check (mypy/pyright, tsc), unit, integration (testcontainers), schema validation, import-linter (boundary module), authorization matrix, Playwright smoke.
- Khi thay đổi `prompts/`, `policies/`, `evals/`: chạy **eval regression subset** (≈ 50 kịch bản, có giới hạn chi phí). Nightly chạy full eval.
- Merge vào `main` → deploy staging tự động. Production deploy thủ công, có tag, có migration kiểm tra trước.

### Staging và Production

*(v0.2)* Trong đồ án: một môi trường kiểm thử chạy bằng Docker Compose; backup Postgres bằng `pg_dump` định kỳ, diễn tập restore trước mỗi đợt kiểm thử. Kiến trúc hai project cloud tách biệt (IAM tách, PITR, on-call) là tham chiếu khi vượt phạm vi đồ án.

---

## PART 39 — DEVELOPMENT TEAM MODEL

### 39.0. Mô hình cho đồ án (v0.2)

| Vai trò | Người đảm nhận |
|---|---|
| Giáo viên kiểm soát, pedagogy lead, product owner | **Chủ dự án**: duyệt pedagogy spec, DI, item bank, gold labels, đánh giá transcript |
| Kỹ sư (backend, frontend, AI) | Chủ dự án và thành viên nhóm (nếu có) |
| Pair programmer | Claude Code: phiên local cho việc cần trao đổi nhiều; phiên cloud cho nhiệm vụ độc lập đã có spec rõ (mỗi nhiệm vụ một nhánh và một PR) |

Nếu nhóm chỉ có 1–2 người, áp dụng kế hoạch rút gọn ở 39.2. Vì người duyệt sư phạm chính là chủ dự án, không có độ trễ chờ phê duyệt từ bên ngoài.

### 39.1. Team 5 người (theo brief)

| Vai trò | Ownership chính | Phụ thuộc vào | Cung cấp cho |
|---|---|---|---|
| **Tech Lead** | Kiến trúc, ADR, Orchestrator core (state machine, SessionAuthorizer, event ledger), AI Gateway interface, security, infra/CI/DevOps | Pedagogy spec, kết quả POC | Tất cả |
| **Backend Engineer** | identity/org, content (ingestion pipeline production), scheduling, session API, assessment projector, DB/migration, reporting API | ADR, schemas | FE, AI Eng |
| **Frontend Engineer** | Student session UI (SSE, math input, micro choices), Teacher (lesson review/approve, schedule, live monitor, reports), Parent view, a11y | API contracts (OpenAPI), UX | Người dùng |
| **AI Engineer** | Prompts, policy/hint engine rules, validator, MathChecker/bug rules, eval harness, synthetic students, POC 1–4, 6, RAG, provider adapters | Pedagogy spec | TL, BE |
| **UX/Product (part-time)** | Pedagogy spec (cùng giáo viên kiểm soát), UX prototype, acceptance criteria, sắp xếp kiểm thử | Giáo viên kiểm soát | Tất cả |
| **Giáo viên kiểm soát lớp 5** (v0.2: chủ dự án đảm nhận) | Ký duyệt pedagogy spec, misconception, item bank, gold labels, đánh giá transcript | — | AI Eng, Product |

### 39.2. Chỉ có 2 developer: giảm scope

| Dev A (Full-stack + Infra) | Dev B (AI + Backend) |
|---|---|
| Repo, CI, auth, org, scheduling, session API, toàn bộ FE | Pedagogy spec cùng giáo viên, POC 1/4, policy/hint engine, gateway, assessment projector, ingestion |

Cắt giảm bắt buộc:
1. Chỉ Math, chỉ text (không voice ở MVP).
2. Không có ingestion tự động PPTX. PDF được trích xuất bán tự động; giáo viên nhập item qua form có AI hỗ trợ.
3. Không có parent dashboard. Phụ huynh nhận **báo cáo tuần qua email** (PDF hoặc HTML) sinh từ projection.
4. Không có off-session chat.
5. Báo cáo giáo viên dạng bảng + heatmap đơn giản (không radar, không timeline).
6. Một trường (vẫn giữ `school_id` và RLS).
7. Dùng auth managed đơn giản cho giáo viên (Google SSO) để giảm việc tự xây.
8. Thời gian vertical slice kéo dài lên **6–7 tuần** thay vì 4.

---

## PART 40 — PARALLEL WORKSTREAMS

```text
Ngày:        1 ─────── 7 ─────── 14 ─────── 21 ─────── 30
Product/Ped  [Spec lesson+KC+items][Assessment spec][UX test][Test prep ──────────]
AI Eng       [Eval ds v0][POC1 ─────────][POC4][Hint/Policy prod][Eval CI][Slice eval]
             [      POC2 ────────][POC3]                         [STT spike]
Tech Lead    [Repo/CI/Infra][ADRs][POC7][Orchestrator core ────────][Hardening]
Backend      [Auth/Org skel][Schema core][Content pipeline][Session API][Projector][Reports API]
Frontend     [UX proto w/ Product][App shell+auth][Session UI ─────][Teacher UI][Reports]
Test Ops     [Sắp xếp học sinh kiểm thử][Lịch kiểm thử ─────][Kiểm thử nội bộ ────]
```

**Được song song ngay từ đầu (không phụ thuộc chưa giải quyết):**
- Pedagogy spec ∥ Repo/CI/Docker Compose ∥ UX prototype ∥ sắp xếp học sinh kiểm thử.
- POC 1 (cần spec của 1 lesson, không cần infra) ∥ POC 2 (cần file giáo viên) ∥ Auth/org skeleton.
- Frontend app shell ∥ Backend core schema (identity/org/scheduling ít phụ thuộc AI).

**Không được song song (phải chờ):**
- Evidence/assessment tables ← POC 1 + POC 4.
- Orchestrator production ← Tutor Contract schema + Gateway interface + POC 7.
- Teacher reports UI ← định nghĩa metric (Assessment spec).
- Voice integration ← POC 6.
- Kiểm thử diện rộng với học sinh thật ← MVP exit (v0.2: không còn phụ thuộc pháp lý).
