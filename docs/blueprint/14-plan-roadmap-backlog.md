# 14 — First 30 Days · Engineering Roadmap · Engineering Backlog

> PART 41 → PART 43.

---

## PART 41 — FIRST 30 DAYS

### 41.1. Audit lịch mặc định của brief

| Brief đề xuất | Vấn đề | Điều chỉnh |
|---|---|---|
| Ngày 1–3: chỉ spec | Để nhiều người ngồi chờ; foundation không phụ thuộc spec | Foundation (repo, CI, Docker Compose, auth skeleton) chạy **từ Ngày 1** *(v0.2: track pháp lý đã gỡ, D-T2)* |
| Ngày 4–7: domain + architecture | Đóng băng domain trước khi có kết quả POC → dễ sai ở Evidence và Contract | Chốt phần **ổn định** (identity, org, tenancy, scheduling) Ngày 7; phần **evidence/contract** chốt Ngày 12–14 sau POC 1 và POC 4 |
| Tuần 2: POCs | POC 1 là rủi ro số 1; để tuần 2 là muộn | POC 1 bắt đầu **Ngày 2** với spec tối thiểu, tăng dần theo spec |
| Tuần 3: foundation + DB + core runtime | Foundation nên đã có từ tuần 1 | Tuần 3 tập trung **runtime production** (orchestrator, policy, gateway, ledger) |
| Tuần 4: vertical slice | Hợp lý | Giữ; slice chạy với synthetic students trước, sau đó **học sinh thật** (được phép, D-T3) |
| (Không có) | Thiếu eval dataset | Eval dataset v0 viết **trước** prompt production (Ngày 3–6) |
| (Không có) | Thiếu voice | Voice English **không** nằm trong 30 ngày; chỉ spike 2 ngày để giảm bất định |

### 41.2. Kế hoạch theo ngày

| Ngày | Product/Pedagogy | AI Engineer | Tech Lead | Backend | Frontend | Gate/Deliverable |
|---|---|---|---|---|---|---|
| **1** | Kickoff; scope lock (chủ dự án là giáo viên kiểm soát); ghi hạn mức free tier từ AI Studio | Đọc 2 khung đánh giá; dựng eval harness skeleton; tạo API key Gemini free tier | Repo, CI, conventions, `CLAUDE.md` | Dev env (compose: Postgres + pgvector, MinIO) | Setup app, design tokens | Scope lock; `docs/poc/free-tier-quota.md` |
| **2** | Chủ dự án chọn lesson (K1); thu 10 file tài liệu thật | POC 1 bắt đầu: constitution v0 + 5 item | ADR-001/002/013 | Auth skeleton | UX: luồng student session (giấy/Figma) | K1 chốt |
| **3** | KC graph + misconception catalog nháp | Eval dataset v0 (kịch bản 9 loại × item) | ADR-003/004 nháp | Org/class/enrollment model | UX: teacher review lesson | — |
| **4** | Item bank A–E + error detection (30–40 item) | POC 1 vòng 1 (`gemini-3.8-flash`) | Môi trường kiểm thử (Docker Compose) | Scheduling model nháp | Prototype clickable student | — |
| **5** | Hint templates H1/H2/H4 cho mọi item; session flow | POC 2 bắt đầu (ingestion 10 file) | ADR-008/009 | CI + migration pipeline | Test prototype với 2–3 học sinh | **K2: pedagogy spec v1 được chủ dự án ký** |
| **6–7** | Assessment Spec G5 (DI-1…DI-14) để chủ dự án duyệt | POC 1 vòng 2 (policy engine rút gọn + validator); synthetic students 6 profile | ADR-003/004 chốt; security baseline | Identity/org/scheduling API v0 | App shell + login học sinh | **K3, K4 chốt; Checkpoint tuần 1** |
| **8–10** | Persona, xưng hô (O8) | POC 1: so sánh model free tier × 2 mức thinking (rải theo hạn mức); POC 4 bắt đầu | POC 7 (state/recovery) | Content tables + upload | Session UI skeleton (SSE, math input) | — |
| **11–12** | Thiết bị của học sinh kiểm thử (O9) | POC 1 decision memo; POC 3 (grounding) | ADR-005/006/007 (events, contract, gateway) | Contract compiler v0 | Teacher: lesson review UI | **O1 chốt (model); Evidence + Contract schema v1** |
| **13–14** | Sắp xếp nhóm học sinh kiểm thử; kế hoạch kiểm thử | POC 4 + POC 3 decision; POC 5 (routing) | POC 7 decision; dựng Cloudflare Tunnel | Scheduler worker | Schedule UI | **Checkpoint tuần 2: go/no-go runtime** |
| **15–17** | Kịch bản kiểm thử (UAT) | Policy/hint engine production + unit tests theo rule | Orchestrator core: 3 tầng state machine, SessionAuthorizer | Event ledger, outbox, session API | Session UI nối API thật | — |
| **18–19** | Tiêu chí báo cáo giáo viên | Validator production; MathChecker + bug rules | AI Gateway + Gemini adapter + fallback chain (+ local adapter) | Ingestion pipeline production (PDF) | Teacher: publish flow | — |
| **20–21** | Review transcript mẫu | Eval runner nối runtime thật (không phải notebook) | Observability (OTel, ai_request_log, dashboards) | Assessment projector + golden tests | Student report | **Checkpoint tuần 3: E2E nội bộ chạy được** |
| **22–24** | Chủ dự án (vai giáo viên) + 2–3 học sinh thật (vòng 1) | Eval regression trong CI; sửa prompt/policy | Chaos test; authz matrix | Reporting API (teacher) | Teacher report (KC matrix, misconception, timeline) | — |
| **25–26** | Vòng 2 với 3–5 học sinh thật | Red team v1 | Security review nội bộ | Bug fixing | Polish + a11y | — |
| **27–28** | Tổng hợp phản hồi | STT spike (2 ngày), voice spike (2 ngày, nếu kịp) | Load test theo số học sinh kiểm thử (dùng AI stub để không tiêu hạn mức) | Backup/restore test | Bug fixing | — |
| **29–30** | Demo cho stakeholder; kế hoạch MVP | Báo cáo eval + request/hạn mức thực | Báo cáo kiến trúc + rủi ro | — | — | **Gate: vertical slice đạt PART 34.2** |

### 41.3. Checkpoint và điều kiện dừng/đổi hướng

- **Ngày 7:** chưa có pedagogy spec ký duyệt → dừng mọi việc liên quan item và eval, tập trung gỡ (v0.2: người duyệt là chủ dự án, nên cần dành lịch duyệt cố định trong Tuần 1).
- **Ngày 12:** POC 1 không đạt ngưỡng với mọi model → không xây runtime production. Thay vào đó phân tích thất bại: prompt, policy, validator hay giới hạn model? Có 3–5 ngày để sửa, sau đó xem lại ASSUME-0 (ví dụ tăng tỉ trọng template, giảm tự do LLM).
- **Ngày 21:** E2E chưa chạy → cắt scope slice (bỏ TEACH có điều kiện, bỏ ingestion tự động, dùng lesson nhập tay).

---

## PART 42 — ENGINEERING ROADMAP

| Phase | Objective | Why Now | Dependencies | Tasks (tóm tắt) | AI Tasks | Data Tasks | Frontend | Backend | Testing | Exit Criteria |
|---|---|---|---|---|---|---|---|---|---|---|
| **P0 Discovery & Spec** (D1–7) | Chốt scope, lesson, pedagogy + assessment spec, ADR ổn định | Mọi thứ phụ thuộc vào đây | Chủ dự án (giáo viên kiểm soát) | Spec, ADR, repo, CI | Eval harness skeleton, dataset v0 | KC, misconception, item bank | UX prototype | Auth/org skeleton | CI xanh | K1–K4 chốt |
| **P1 Risk POCs** (D2–16) | Kiểm chứng AI và state trước khi build | Rủi ro cao nhất, rẻ nhất để test | P0 (một phần) | POC 1–5, 7 | Prompt, policy, validator, model compare | Evidence/assessment schema | — | POC 7 | Eval, chaos | Decision memos; O1 chốt; schema v1 |
| **P2 Foundation + Runtime** (D10–21) | Runtime production cho 1 lesson | Sau khi schema ổn định | P1 | Orchestrator, gateway, ledger, projector, content pipeline, scheduler | Policy/hint prod, MathChecker | Migrations, partition | Session UI, teacher UI | Session API, content, scheduling | Unit, integration, authz | E2E nội bộ |
| **P3 Vertical Slice** (D18–30) | Loop hoàn chỉnh, đo được | Chứng minh giá trị | P2 | Reports, observability, hardening | Eval CI, red team v1 | Read models | Reports UI | Reporting API | E2E, chaos, load 100 | PART 34.2 đạt |
| **P4 MVP Math** (tuần 5–10) | Một chương Toán 5, sẵn sàng kiểm thử | Slice đã chứng minh loop | P3 | Nhiều lesson, review schedule, parent, override, voice-to-text, degraded mode | STT normalizer, hint tuning, AI flag → dataset | Retention, forgetting risk | Parent view, radar, timeline | Notification, review scheduler | Security review, load test (AI stub) | MVP exit (PART 35) |
| **P5 Kiểm thử Math** (tuần 11–16) | Kiểm chứng với học sinh thật; số liệu cho chương thực nghiệm | MVP xong | P4 | Vận hành, đo lường, hiệu chỉnh | Calibrate judge vs giáo viên; policy v2 | κ, pre/post | Sửa theo phản hồi | Hardening | Monitoring thật | Tiêu chí PART 36 |
| **P6 English Reading** (tuần 9–14, song song P4–P5) | Reading lớp 5 trên cùng runtime | Runtime ổn định; không cần voice | P3 | Skill taxonomy, rubric 0–4, reading flow | Prompt English module, rubric scorer, support S0–S5 | Skill state | Reading UI | Assessment English | Eval English | Slice English Reading đạt |
| **P7 English Speaking + Voice** (tuần 13–22) | Speaking realtime | Rủi ro voice cao, cần nền ổn định | P6 + POC 6 đầy đủ | Voice gateway, pronunciation, speaking flow | Realtime control, speaking scoring, calibration | Audio lifecycle | Voice UI, mic preflight | Voice gateway | Latency, ASR fairness | Sẵn sàng kiểm thử English Speaking |
| **P8 Production scale** (ngoài phạm vi đồ án, tham chiếu) | 1,000+ học sinh | Có bằng chứng giá trị | P5 | HA, Redis, warehouse, multi-school onboarding | Cost optimization | CDC | Admin trường | Tenancy ops | Load 2,000 | SLO đạt |

---

## PART 43 — ENGINEERING BACKLOG

Ký hiệu owner: TL (Tech Lead), BE, FE, AI, PM (UX/Product), TA (Teacher Advisor — v0.2: chủ dự án). Priority: P0 (slice), P1 (MVP), P2 (pilot/sau).

### Epic E1 — Product & Pedagogy

| Story | Tasks | Owner | Dep | Pri | Acceptance Criteria |
|---|---|---|---|---|---|
| E1-S1 Chọn lesson slice | Chủ dự án chốt; đối chiếu lịch dạy; chốt SGK tham chiếu | PM, TA | — | P0 | Quyết định ghi trong `docs/pedagogy/decisions.md` |
| E1-S2 KC graph + misconception catalog | Viết KC; prerequisite; misconception + bug rule + phản ví dụ | TA, AI | S1 | P0 | ≥ 5 KC, ≥ 5 misconception có bug rule; TA ký |
| E1-S3 Item bank lesson 1 | 30–40 item có metadata A–E, error detection, isomorphic groups | TA, AI | S2 | P0 | Mọi item có answer_spec, KC, difficulty; checker xác nhận đáp án |
| E1-S4 Hint templates | H1/H2/H4 cho mọi item; H3/H5 cho item khó | TA | S3 | P0 | 100% item có ≥ 3 template đã duyệt |
| E1-S5 Assessment Spec G5 | DI-1…DI-14 + bảng ví dụ số | AI, TA, TL | S2 | P0 | TA + TL ký; boundary examples có kết quả mong đợi |
| E1-S6 Persona + ngôn ngữ | Xưng hô, danh sách từ vựng lớp 5, mẫu câu an toàn | PM, TA | — | P0 | Tài liệu duyệt; validator dùng danh sách từ |
| E1-S7 Thông báo kiểm thử cho phụ huynh và học sinh | Soạn ngắn, ngôn ngữ trẻ hiểu (pháp lý đã xử lý, D-T2) | PM | — | P2 | Chủ dự án duyệt |

### Epic E2 — Foundation / DevOps

| Story | Tasks | Owner | Dep | Pri | AC |
|---|---|---|---|---|---|
| E2-S1 Monorepo + CI | Cấu trúc thư mục; lint/type/test; import-linter; pre-commit | TL | — | P0 | PR chạy đủ check < 10 phút |
| E2-S2 Local dev | compose, Makefile, seed tất định | TL, BE | S1 | P0 | Dev mới chạy được trong < 30 phút |
| E2-S3 Môi trường kiểm thử | Docker Compose + Cloudflare Tunnel (v0.2); script backup `pg_dump` | TL | ADR-011 | P0 | Học sinh truy cập qua HTTPS, micro hoạt động |
| E2-S4 Observability | OTel, logs có correlation, Sentry, dashboards | TL | S3 | P0 | Trace đầy đủ một tutor turn |
| E2-S5 Backup/restore | `pg_dump` định kỳ + diễn tập restore | TL | S3 | P1 | Restore thành công vào env tạm |

### Epic E3 — Identity & Org

| Story | Tasks | Owner | Dep | Pri | AC |
|---|---|---|---|---|---|
| E3-S1 Tenancy + RLS | school_id, RLS policy, middleware set context | BE, TL | ADR-003 | P0 | Test cross-tenant fail cho mọi bảng |
| E3-S2 Student login (class code + PIN) | Credential, lockout, rate limit | BE | S1 | P0 | 5 lần sai → khóa; teacher reset được |
| E3-S3 Teacher login | Email/password + (P1) Google SSO | BE | S1 | P0 | — |
| E3-S4 Class, enrollment, teaching assignment | CRUD + API | BE | S1 | P0 | — |
| E3-S5 Guardian link | Invitation, đăng nhập phụ huynh, ghi nhận consent đơn giản | BE, FE | — | P1 | Phụ huynh xem được báo cáo của con |

### Epic E4 — Content & Ingestion

| Story | Tasks | Owner | Dep | Pri | AC |
|---|---|---|---|---|---|
| E4-S1 Lesson + version model | Trạng thái, metadata schema | BE | ADR | P0 | Published version bất biến (trigger) |
| E4-S2 Upload + validation | Signed URL, hash, type/size, malware scan | BE | S1 | P0 | File sai bị reject có lý do |
| E4-S3 Parsing + structure extraction | PDF → artifacts → LessonDraft (LLM) | AI, BE | POC 2 | P0 | Đạt ngưỡng POC 2 trên bộ file test |
| E4-S4 Content validation | MathChecker kiểm tra đáp án, sai lớp, injection scan, coverage | AI | S3 | P0 | Báo cáo validation hiển thị cho giáo viên |
| E4-S5 Review/approve/publish UI | Side-by-side, sửa item/hint, approve | FE | S3 | P0 | Giáo viên publish lesson trong < 20 phút |
| E4-S6 Package build + chunk/embed/index | LessonPackage invariants; pgvector | BE, AI | S5 | P0 | Invariant test pass; smoke retrieval |
| E4-S7 PPTX support | Render + extract | AI | POC 2 | P1 | — |

### Epic E5 — Scheduling

| Story | Tasks | Owner | Dep | Pri | AC |
|---|---|---|---|---|---|
| E5-S1 Schedule rule + occurrences | Materialize 14 ngày, idempotent | BE | E3 | P0 | Chạy lại không tạo trùng |
| E5-S2 Session generation + windows | SCHEDULED → READY → MISSED | BE | S1 | P0 | Test theo thời gian giả lập |
| E5-S3 Schedule UI | Lịch tuần, ngoại lệ | FE | S1 | P0 | — |
| E5-S4 Review schedule (retention) | T1/T3/T7 → WARMUP_REVIEW | BE, AI | E8 | P1 | — |

### Epic E6 — Session & Orchestrator

| Story | Tasks | Owner | Dep | Pri | AC |
|---|---|---|---|---|---|
| E6-S1 Contract compiler | Compile + JSON Schema validate + invariants + hash | TL | ADR-006 | P0 | Golden tests; contract sai → session BLOCKED |
| E6-S2 State machine 3 tầng | Lifecycle, activity plan, item loop; transition table test | TL | S1 | P0 | 100% transition có test; transition sai bị reject |
| E6-S3 SessionAuthorizer | SessionContext + 8 kiểm tra | TL | S2 | P0 | Authz matrix test pass |
| E6-S4 Event ledger + outbox | Envelope, sequence_no, partition | BE | ADR-005 | P0 | Không có event mồ côi; replay được |
| E6-S5 Session API + SSE | join/responses/hints/pause/exit/state/stream | BE | S3, S4 | P0 | Idempotency + version conflict hoạt động |
| E6-S6 Timer + reserve | Time warnings, forced transition | TL | S2 | P0 | Test: hết giờ vẫn có exit assessment |
| E6-S7 Recovery | Turn "requested" quá hạn → retry/template | TL | S5 | P0 | Chaos test POC 7 pass trên runtime thật |
| E6-S8 Teacher live controls | Pause, end, extend, message | BE, FE | S5 | P1 | Audit ghi đủ |

### Epic E7 — Tutor AI

| Story | Tasks | Owner | Dep | Pri | AC |
|---|---|---|---|---|---|
| E7-S1 Prompt layers v1 | Constitution, Math G5 module, L3 builder, L4 snapshot, L5 directive | AI | POC 1 | P0 | Versioned; cache hit ≥ 80% đo được |
| E7-S2 Policy + hint engine | Rules R-* với rule_id; unit test từng rule | AI | E1-S5 | P0 | 100% rule có test; decision log đầy đủ |
| E7-S3 Output validator | Leak (dạng tương đương), 1 câu hỏi, độ dài, từ vựng, grounding, safety | AI | S1 | P0 | Leak eval 0% ở assessment |
| E7-S4 MathChecker + bug rules | Fraction/Decimal, locale vi-VN, tương đương | AI | E1-S2 | P0 | 100% đáp án item bank được xác nhận |
| E7-S5 AI Gateway + adapters | Interface model class; Gemini adapter (mặc định), local adapter, Anthropic adapter (tùy chọn); fallback khi 429; quota/cost log | TL, AI | ADR-007, ADR-016 | P0 | Test fallback chain; không có vendor SDK ngoài adapter (lint) |
| E7-S6 Degraded mode | Template-only tutor | AI | S2 | P1 | Session hoàn tất được khi tắt LLM |
| E7-S7 Off-session routing | LIGHTWEIGHT + guard + flag | AI | S5 | P2 | 0 bypass trong eval POC 5 |

### Epic E8 — Assessment & Student Model

| Story | Tasks | Owner | Dep | Pri | AC |
|---|---|---|---|---|---|
| E8-S1 Evidence extraction | Event → Evidence (validated), label gate | BE, AI | ADR-005 | P0 | Evidence rejected có lý do |
| E8-S2 Projector | Beta per dimension, M, confidence, state, gates | BE | E1-S5 | P0 | Golden + boundary tests; determinism 100% |
| E8-S3 Teacher override | API + projection semantics + audit | BE | S2 | P1 | — |
| E8-S4 Retention & forgetting risk | Delayed probes, risk | BE | E5-S4 | P1 | — |
| E8-S5 English rubric scorer | 0–4 + support S0–S5 | AI | P6 | P2 | κ với giáo viên ≥ 0.6 |

### Epic E9 — Reports & Analytics

| Story | Tasks | Owner | Dep | Pri | AC |
|---|---|---|---|---|---|
| E9-S1 Teacher report slice | KC matrix, misconception, session timeline, transcript (audit) | FE, BE | E8 | P0 | Mọi số có drill-down evidence |
| E9-S2 Student report | Ngôn ngữ đơn giản | FE | E8 | P0 | Được giáo viên duyệt ngôn ngữ |
| E9-S3 Parent report | Trạng thái định tính, xu hướng | FE, BE | E3-S5 | P1 | — |
| E9-S4 Radar, timeline, class heatmap | — | FE | E8 | P1 | — |

### Epic E10 — Voice

| Story | Tasks | Owner | Dep | Pri | AC |
|---|---|---|---|---|---|
| E10-S1 STT spike Toán | Corpus 200 phát ngôn (học sinh thật + người lớn); các lựa chọn miễn phí | AI | — | P1 | Decision memo |
| E10-S2 Math speech normalizer | Rules + LLM fallback + echo confirm | AI, FE | S1 | P1 | ≥ 95% parse đúng trên corpus |
| E10-S3 English voice POC 6 | A vs B | AI, TL | P6 | P2 | ADR-012 |
| E10-S4 Voice gateway + pronunciation | — | TL, AI | S3 | P2 | Latency SLO |

### Epic E11 — QA / Evaluation / Security

| Story | Tasks | Owner | Dep | Pri | AC |
|---|---|---|---|---|---|
| E11-S1 Eval harness + datasets | Socratic, hint, grounding, assessment, red team (jsonl có version) | AI | E1 | P0 | Chạy bằng 1 lệnh; báo cáo HTML |
| E11-S2 Synthetic students | 6 profile, tất định (seed) + LLM-driven | AI | S1 | P0 | Tái lập được |
| E11-S3 Eval regression CI | Subset trên PR prompt/policy; full eval rải theo ngày trong hạn mức free tier | AI, TL | S1 | P0 | Chặn merge khi tụt ngưỡng |
| E11-S4 E2E + chaos + load | Playwright, chaos, k6 | TL, FE | E6 | P0 | Theo PART 34.2 |
| E11-S5 Red team | Injection, extraction, bypass, manipulation | AI, TL | E7 | P0 (v1), P1 (v2) | Không có lỗ hổng mức cao |
| E11-S6 Security review | Auth, RLS, secrets, dependency scan | TL | E3 | P1 | Checklist pass |

**Ví dụ subtask chi tiết (E6-S2 State machine 3 tầng):**
1. Định nghĩa bảng transition dạng dữ liệu (không if/else rải rác).
2. Hàm `transition(state, command, context) -> (new_state, events) | Rejection`, là hàm thuần.
3. Property-based test (Hypothesis): chuỗi command ngẫu nhiên không bao giờ dẫn tới state không hợp lệ.
4. Test mọi đường tới trạng thái kết thúc.
5. Sinh sơ đồ Mermaid từ bảng transition (tài liệu tự cập nhật).
