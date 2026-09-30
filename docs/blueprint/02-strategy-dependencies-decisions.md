# 02 — Greenfield Strategy · Decision Dependency Graph · Architecture Decision Register · Open Technical Decisions

> PART 6, PART 7, Architecture Decision Register (brief §59/§78) và PART 47.

---

## PART 6 — GREENFIELD DEVELOPMENT STRATEGY

### 6.1. Nguyên tắc chiến lược

1. **Learning system trước, AI sau.** Làm pedagogy spec và assessment spec trước khi viết prompt production. Prompt và policy là *hiện thực hóa* của spec.
2. **Rủi ro cao nhất được kiểm chứng rẻ nhất, sớm nhất.** POC 1 (Socratic) không cần DB, UI hay infra: chỉ cần spec + notebook + eval harness.
3. **Quyết định khó đảo ngược thì chậm và có bằng chứng. Quyết định dễ đảo ngược thì nhanh và mặc định.**
4. **Vertical slice mỏng, xuyên suốt**, thay vì nhiều lớp ngang dở dang.
5. **Mọi kết luận về học sinh phải truy được về evidence.** Việc này thiết kế từ schema đầu tiên, không để "thêm sau".
6. **POC là code vứt đi, có chủ đích.** Code POC nằm trong `poc/` và không được import vào `services/`. Thứ được giữ lại là **dataset, eval, spec và quyết định**.

### 6.2. Bốn track song song ngay từ Ngày 1

```text
Track A — Pedagogy & Assessment Spec   (UX/Product + Teacher advisor + AI Eng)
Track B — AI Risk POCs                 (AI Eng, Tech Lead review)
Track C — Foundation                   (Tech Lead + Backend: repo, CI, env, schema lõi, auth)
Track D — Legal/Consent & Pilot Ops    (Product + chủ dự án, cần tư vấn pháp lý)
```

Track D không viết code, nhưng có lead time dài nhất (hợp đồng trường, consent, đánh giá tác động chuyển dữ liệu). Bắt đầu muộn thì pilot bị trễ dù code đã xong.

### 6.3. Thứ tự làm việc thực tế

```text
1. Chọn lesson + viết pedagogy spec (K1, K2)             ← không có nó thì không làm gì được
2. Viết eval dataset v0 từ spec (Socratic scenarios)      ← trước cả prompt
3. POC 1: prompt + policy stub + synthetic students      ← kiểm chứng ASSUME-0
4. Assessment Spec G5 + POC 4 (projection deterministic)  ← chốt evidence schema
5. Domain model + ADR khó đảo ngược (tenancy, events, contract, gateway)
6. Foundation code (song song từ bước 1 cho phần không phụ thuộc: repo, CI, auth skeleton)
7. POC 2/3 ingestion + grounding (song song bước 3–4)
8. Runtime production: orchestrator + policy + hint engine + gateway + ledger
9. Vertical slice end-to-end + report
10. Pilot readiness (consent, red team, observability, runbook)
```

---

## PART 7 — DECISION DEPENDENCY GRAPH

### 7.1. Đồ thị phụ thuộc tổng thể

```mermaid
flowchart TD
    P0["Scope Lock<br/>Math G5 + English G5"] --> P1["Lesson choice +<br/>Pedagogy Spec"]
    P1 --> P2["KC graph +<br/>Misconception catalog +<br/>Item bank"]
    P1 --> A1["Assessment Spec G5<br/>(bands, weights, gates)"]
    P2 --> E0["Socratic Eval Dataset v0"]
    P2 --> POC1["POC 1<br/>Socratic Tutor"]
    E0 --> POC1
    A1 --> POC4["POC 4<br/>Assessment projection"]
    POC1 --> EVS["Evidence schema v1"]
    POC4 --> EVS
    EVS --> DM["Domain Model"]
    T0["Tenancy + Child identity ADR"] --> DM
    DM --> DB["Database schema v1"]
    DM --> TC["Tutor Contract schema v1"]
    POC1 --> MS["Model selection<br/>(tutor reasoning)"]
    MS --> GW["AI Gateway interface"]
    TC --> ORC["Tutor Orchestrator"]
    GW --> ORC
    DB --> ORC
    ORC --> VS["Vertical Slice E2E"]
    TM["Teacher material samples"] --> POC2["POC 2 Ingestion"]
    POC2 --> PKG["Lesson Package schema"]
    PKG --> TC
    PKG --> POC3["POC 3 Grounding"]
    POC3 --> RAG["RAG design"]
    RAG --> ORC
    L0["Legal / consent / data transfer"] --> CLOUD["Cloud + region ADR"]
    CLOUD --> PILOT["Pilot with real students"]
    VS --> PILOT
```

### 7.2. Chuỗi phụ thuộc chính (theo brief, đã hiệu chỉnh)

```text
Pedagogy → Learning Model (KC, activity, evidence) → Domain Model → Database
        → Tutor Contract → Tutor Orchestrator → AI Integration
```

Hiệu chỉnh quan trọng: **AI Integration không nằm cuối chuỗi về mặt thời gian.** POC 1 chạy *song song* với Domain Model, vì kết quả POC 1 (model nào, cần structured output gì, evidence gì) làm thay đổi Evidence schema và Tutor Contract. Nói gọn: AI **POC** đi sớm, AI **production integration** đi muộn.

```text
Teacher Content → Ingestion → Lesson Package (approved) → [in-session: context load]
                                                        → [cross-lesson: chunk → embed → retrieve] → Tutor
```

### 7.3. Critical Path

```text
Lesson choice (D2) → Pedagogy spec (D5) → Eval dataset v0 (D6) → POC 1 decision (D12)
→ Evidence schema + Contract schema (D12–14) → Orchestrator core (D15–21)
→ Vertical slice integration (D22–28) → Slice demo & gate (D30)
```

Song song và **có thể trở thành critical path** nếu bắt đầu muộn: Legal/consent → Pilot. Chuỗi này **không** nằm trên critical path của vertical slice nội bộ, nhưng **là** critical path của pilot với học sinh thật.

### 7.4. Không được song song hóa khi dependency chưa giải quyết

- Không viết Assessment module production trước khi Assessment Spec G5 được ký duyệt.
- Không đóng băng DB schema cho evidence trước khi có kết quả POC 1 và POC 4.
- Không build UI teacher report trước khi metric và interpretation được định nghĩa.
- Không tích hợp voice provider trước khi POC 6 chốt kiến trúc (speech-to-speech hay cascade).

---

## ARCHITECTURE DECISION REGISTER

Định dạng mỗi quyết định: Decision → Why → Options → Recommended → Trade-offs → Risk → Reversibility → When to decide → Migration path.
Mỗi ADR sẽ có file riêng trong `docs/adr/` khi được chốt chính thức. Bảng dưới đây là **đề xuất ban đầu**.

### ADR-001 — Kiến trúc tổng thể: Modular Monolith
- **Why:** Team 4–5 người, domain đang học, cần tốc độ iterate. Transaction cần chéo module (session + evidence + student model).
- **Options:** (a) modular monolith; (b) microservices; (c) hybrid: monolith + tách voice gateway.
- **Recommended:** (a) cho MVP. Có đường sang (c) khi voice realtime có nhu cầu scale riêng.
- **Trade-offs:** Deploy chung. Một module lỗi có thể ảnh hưởng toàn bộ → cần module boundary nghiêm ngặt (import rules, không truy cập bảng của module khác).
- **Risk:** Boundary bị xói mòn theo thời gian → kiểm tra bằng lint (import-linter) trong CI.
- **Reversibility:** Trung bình. Tách module thành service dễ nếu boundary sạch.
- **When:** Ngày 7.
- **Migration:** Tách Voice Gateway → tách Ingestion Workers → tách Analytics (CDC).

### ADR-002 — Ngôn ngữ và runtime backend: Python (FastAPI) + Pydantic
- **Why:** AI Eng và backend dùng chung hệ sinh thái. Parsing tài liệu (PyMuPDF, python-pptx), số học chính xác (`fractions`, `decimal`, SymPy), eval và data science, knowledge tracing đều mạnh ở Python.
- **Options:** Python FastAPI; TypeScript (NestJS/Fastify) toàn stack; Go.
- **Recommended:** Python 3.12+ FastAPI cho backend. Frontend TypeScript. Schema dùng chung qua **JSON Schema** sinh từ Pydantic → sinh type TS.
- **Trade-offs:** Hai ngôn ngữ trong repo. Đổi lại dùng đúng công cụ cho AI và dữ liệu.
- **Risk:** Hiệu năng async và WebSocket voice → nếu cần, tách Voice Gateway sang runtime khác.
- **Reversibility:** Khó (toàn bộ code backend).
- **When:** Ngày 5, dựa trên kỹ năng thực tế của team (**[OPEN]**: nếu team mạnh TypeScript hơn hẳn thì đảo lại).
- **Migration:** Không dự kiến.

### ADR-003 — Tenancy: shared DB, `school_id` trên mọi bảng dữ liệu người học + Postgres RLS
- **Why:** Trẻ em → cách ly dữ liệu là bắt buộc. Pilot bắt đầu với 1 trường nhưng sản phẩm hướng tới nhiều trường.
- **Options:** DB per tenant; schema per tenant; shared + RLS.
- **Recommended:** Shared + `school_id` + RLS làm lớp phòng thủ thứ hai (lớp thứ nhất là authorization ở application).
- **Trade-offs:** RLS thêm độ phức tạp cho migration và test. Đổi lại vận hành rẻ.
- **Risk:** Quên `school_id` ở bảng mới → CI test: mọi bảng có `student_id` phải có `school_id` và RLS policy.
- **Reversibility:** **Khó.**
- **When:** Ngày 7.

### ADR-004 — Identity cho học sinh lớp 5: tài khoản do giáo viên cấp, không cần email
- **Recommended:** Student đăng nhập bằng *class code + username + PIN/picture password*, do giáo viên cấp và reset. Parent đăng nhập bằng email/số điện thoại + OTP, liên kết với con qua lời mời của giáo viên. Teacher đăng nhập bằng email + mật khẩu, có thể thêm Google SSO.
- **Trade-offs:** Tự quản lý credential của trẻ → phải có rate limiting và lockout. Không lưu mật khẩu dạng khôi phục được.
- **Reversibility:** Khó (luồng người dùng + dữ liệu).
- **When:** Ngày 7.

### ADR-005 — Event và Evidence: append-only ledger trong Postgres, có version, projection tất định
- **Why:** Replay, audit, knowledge tracing về sau, và yêu cầu "mọi kết luận có evidence".
- **Options:** (a) full event sourcing; (b) state tables + append-only event ledger (event-first cho learning data); (c) chỉ log.
- **Recommended:** (b). Session, Activity, Item state là bảng trạng thái (source of truth cho runtime). Mọi thay đổi đều ghi event trong cùng transaction (transactional outbox). Evidence và Mastery là **projection** tái tạo được từ ledger + policy version.
- **Reversibility:** **Khó** (schema event là hợp đồng dài hạn) → envelope có `schema_version`, cho phép upcaster.
- **When:** Ngày 10–14 (sau POC 1 và POC 4).

### ADR-006 — Tutor Contract: tài liệu JSON bất biến, compile từ Teacher Design, snapshot theo session
- **Recommended:** `ContractCompiler` compile từ LessonVersion + Schedule + Policies (versioned) → `TutorContract` có hash. Session bind với đúng một contract. Teacher sửa lesson → version mới chỉ áp dụng cho session sau. Pause/override là *event*, không sửa contract.
- **Reversibility:** Trung bình (schema có version).
- **When:** Ngày 10–14.

### ADR-007 — AI Gateway theo *model class*, không theo vendor
- **Recommended:** Interface `ModelClass = {TUTOR_REASONING, LIGHTWEIGHT, REALTIME_VOICE, EMBEDDING, STT, TTS, PRONUNCIATION}`. Router ánh xạ class → provider/model qua config có version. Business logic chỉ thấy `gateway.tutor_turn(request) -> TutorTurn`.
- **Trade-offs:** Mất một số tính năng riêng của vendor nếu interface quá chung → cho phép *capability flags* (ví dụ `supports_prompt_cache`, `supports_structured_output`).
- **Reversibility:** **Khó nếu không làm từ đầu**, dễ nếu làm đúng.
- **When:** Ngày 10.

### ADR-008 — Hạ tầng lưu trữ MVP: PostgreSQL (+pgvector) + Object Storage
- **Recommended:** Chỉ **2 hệ thống lưu trữ**. Postgres chứa OLTP, event ledger, job queue và vector. Object storage chứa file gốc và audio. Chưa dùng Redis, vector DB riêng hay analytics warehouse.
- **Reversibility:** Dễ để *thêm* sau (Redis, warehouse qua CDC, vector DB riêng).
- **When:** Ngày 7.

### ADR-009 — Kênh realtime cho tutor text: HTTP command + SSE stream
- **Why:** Student action là command (POST, idempotent). Tutor output là stream (SSE). SSE tự reconnect, đi qua proxy dễ, đơn giản hơn WebSocket.
- **Recommended:** SSE cho text. WebSocket/WebRTC chỉ dùng cho voice.
- **Reversibility:** Dễ.

### ADR-010 — Kiểm tra đáp án Toán: deterministic checker + bug library, LLM chỉ phân tích lập luận
- **Why:** LLM có thể tính sai. Assessment phải tất định.
- **Recommended:** `MathChecker` dùng số hữu tỉ chính xác, so sánh tương đương (0,5 = 1/2 = 50% nếu item cho phép), nhận diện misconception bằng luật "buggy rules" (ví dụ đáp án = (a+c)/(b+d) → cộng tử với tử, mẫu với mẫu). LLM phân tích lời giải thích mở và *đề xuất* nhãn. Nhãn phải qua validation layer mới thành evidence.
- **Reversibility:** Dễ.

### ADR-011 — Cloud và region
- **Options:** GCP (asia-southeast1 Singapore), AWS (ap-southeast-1), cloud trong nước (Viettel/VNPT/FPT).
- **Recommended tạm thời:** GCP asia-southeast1. Lý do: Cloud Run + Cloud SQL + GCS gọn cho team nhỏ; Vertex AI cung cấp cả Claude và Gemini trong cùng hợp đồng và DPA; Google STT hỗ trợ tiếng Việt.
- **[OPEN]:** Yêu cầu pháp lý về lưu trữ dữ liệu trẻ em trong nước và hồ sơ chuyển dữ liệu ra nước ngoài → có thể buộc DB đặt tại Việt Nam, chỉ gửi dữ liệu đã tối thiểu hóa sang AI provider.
- **Reversibility:** **Khó** khi đã có dữ liệu thật. Dễ trước pilot.
- **When:** Tạm ngày 14. Chính thức trước khi thu dữ liệu học sinh thật.

### ADR-012 — Voice English: kiến trúc quyết định bởi POC 6
- Xem PART 20. Mặc định tạm: speech-to-speech có orchestrator điều khiển (instructions + tool calls báo evidence), fallback cascade.

### ADR-013 — Monorepo
- **Recommended:** Monorepo (`apps/`, `services/`, `packages/schemas`, `evals/`, `poc/`, `docs/`, `infra/`). Schema dùng chung, một CI, team nhỏ.
- **Reversibility:** Dễ.

### ADR-014 — Frontend: React + TypeScript + Vite (SPA)
- **Why:** App đứng sau login, không cần SEO/SSR. SPA đơn giản.
- **Reversibility:** Dễ đến trung bình.

### ADR-015 — Prompt, policy, rubric là *artifact có version* trong repo, không phải chuỗi rải rác trong code
- **Recommended:** `services/api/tutor/prompts/*.md`, `policies/*.yaml`, `mastery_policy/*.yaml` có `version`. Mọi AI request log ghi version. Mọi thay đổi chạy eval regression.
- **Reversibility:** Dễ, nhưng phải làm từ đầu để có lịch sử.

### Phân loại khả năng đảo ngược

| Khó đảo ngược (quyết chậm, có bằng chứng) | Dễ đảo ngược (quyết nhanh, mặc định) |
|---|---|
| Tenancy (ADR-003), Identity trẻ em (ADR-004), Event/Evidence schema (ADR-005), Tutor Contract (ADR-006), AI Gateway abstraction (ADR-007), Cloud/region và data residency (ADR-011), Ngôn ngữ backend (ADR-002), Domain model và data ownership | UI library, chart library, SSE/WS cho text (ADR-009), embedding model, TTS provider, email/SMS provider, LLM tracing tool, cấu trúc thư mục FE |

---

## PART 47 — OPEN TECHNICAL DECISIONS

Định dạng: Unknown → Why it matters → How to validate → Temporary default → Decision deadline.

| # | Unknown | Why it matters | How to validate | Temporary default | Deadline |
|---|---|---|---|---|---|
| O1 | Model nào làm Tutor Reasoning in-session | Chất lượng Socratic, độ trễ, chi phí (yếu tố chi phí lớn nhất) | POC 1: cùng eval dataset, so ≥3 ứng viên (Claude Opus 5.5, Claude Sonnet 5.5, 1 ứng viên ngoài Anthropic) | `claude-opus-5-5`, effort `low`/`medium` | Ngày 12 |
| O2 | Voice English: speech-to-speech hay cascade | Kiểm soát sư phạm và độ trễ | POC 6: đo latency, tỉ lệ tuân thủ instruction, khả năng log evidence, chi phí/phút | Speech-to-speech + orchestrator điều khiển | Trước phase English Speaking |
| O3 | Provider STT tiếng Việt cho Toán | Evidence từ voice phải chính xác | Corpus 200–300 phát ngôn toán lớp 5 (thu từ giáo viên/người lớn trước, trẻ em sau khi có consent), đo WER + tỉ lệ parse đúng biểu thức | Google STT (Chirp) hoặc gpt-4o-transcribe | Phase MVP (tuần 6–8) |
| O4 | Pronunciation assessment cho trẻ em | Tránh chấm sai và bias | Chấm song song với giáo viên, đo agreement | Azure Pronunciation Assessment (giá cần xác minh) | Phase English Speaking |
| O5 | Có được lưu dữ liệu ngoài Việt Nam không, cần hồ sơ gì | Có thể buộc đổi cloud/region | Tư vấn pháp lý chuyên về dữ liệu cá nhân | Tối thiểu hóa: gửi AI provider chỉ tên gọi (không họ), không PII khác | Trước pilot |
| O6 | Thời lượng session mặc định | Hiệu quả học, chi phí | Pilot: đo drop-off theo phút, hỏi ý kiến giáo viên | 30 phút | Cuối pilot |
| O7 | Recommendation bands (C2) | Tutor action phụ thuộc band | Pedagogy lead quyết + dữ liệu pilot | Căn theo ranh giới 6 mức hiểu | Ngày 7 |
| O8 | Tutor xưng hô và persona | Trải nghiệm và văn hóa | Test với 3–5 giáo viên, vài học sinh (có consent) | "Cô" – "con" | Ngày 5 |
| O9 | Thiết bị học sinh | Mic, trình duyệt, UI | Khảo sát trường pilot | Chrome trên tablet/laptop | Ngày 10 |
| O10 | Giá sản phẩm/ngân sách per-student | Quyết định model routing | Business | Mục tiêu chi phí biến đổi < 30% giá bán | Trước pilot |
| O11 | Bộ SGK và quyền dùng nội dung | Curriculum Knowledge layer | Hỏi NXB/trường, dùng tài liệu giáo viên tự soạn trước | Chỉ Teacher Knowledge (tài liệu giáo viên tự soạn) | Trước MVP |
| O12 | Thuật toán knowledge tracing | Chất lượng mastery về dài hạn | So sánh Beta-Bernoulli theo chiều vs BKT trên dữ liệu pilot | Beta-Bernoulli theo chiều + công thức M | Sau pilot |
