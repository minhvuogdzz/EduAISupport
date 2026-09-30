# 12 — Technical POCs · First Vertical Slice · MVP · Pilot

> PART 33 → PART 36, gồm "Do Not Build Yet" (brief §49).

---

## PART 33 — TECHNICAL POCs

Quy tắc chung: POC nằm trong `poc/<tên>/` và là code vứt đi. Thứ được giữ lại là **dataset, eval runner, kết quả và decision memo** (`docs/poc/<tên>-decision.md`). Mỗi POC có timebox. Hết timebox mà chưa đạt thì phải có quyết định: kéo dài có lý do, đổi hướng, hoặc giảm scope.

### POC 1 — Socratic Tutor (quan trọng nhất)

| Mục | Nội dung |
|---|---|
| Objective | Kiểm chứng ASSUME-0: LLM, khi được policy engine điều khiển, dạy Socratic đúng chuẩn cho lesson Toán 5 bằng tiếng Việt |
| Input | Pedagogy spec của lesson (KC, misconception, 30–40 item, hint templates); eval dataset v0 (≥ 150 kịch bản ban đầu, mục tiêu 300) |
| Method | Notebook/CLI: prompt L1–L5 + policy engine rút gọn (luật R-* của PART 15) + MathChecker + validator. Synthetic students (6 profile) chơi hết item loop. So sánh các model free tier (`gemini-3.8-flash`, `gemini-3.5-flash`, `gemini-2.5-pro`) với 2 mức thinking; Claude làm mốc nếu có credit (v0.2). Có ablation: *có policy* vs *chỉ prompt* để chứng minh giá trị của policy. **Theo hạn mức free tier:** chạy ~100 kịch bản ưu tiên, student simulator dạng scripted (không tốn request), judge trên mẫu, rải trong nhiều ngày |
| Metrics | Answer Leak Rate, Move Fidelity, Question Ratio, Diagnosis Accuracy, Turn Length, ngôn ngữ phù hợp (đánh giá của giáo viên), TTFT/latency, số request/buổi, cache hit |
| Success criteria | Leak ≤ 1% (practice), 0% (assessment); Move Fidelity ≥ 90%; Diagnosis ≥ 80%; giáo viên chấm "chấp nhận được" ≥ 80% transcript mẫu; TTFT p95 ≤ 2s |
| Timebox | Ngày 2 → Ngày 12 |
| Decision unlocked | Model TUTOR_REASONING (O1); schema `TutorTurn`; Evidence schema cho reasoning labels; có cần LLM phân tích riêng không; số request thực/buổi (O10) |

### POC 2 — Teacher Material Ingestion

| Mục | Nội dung |
|---|---|
| Objective | Biến PDF/PPTX thật của giáo viên Việt Nam thành `LessonDraft` có cấu trúc |
| Input | ≥ 10 file thật (PDF text, PDF scan, PPTX có công thức và hình), từ chủ dự án và giáo viên khác nếu có |
| Method | PyMuPDF/python-pptx + render ảnh trang → LLM đa phương thức với structured output → so với bản cấu trúc do người làm (gold) |
| Metrics | Field-level precision/recall (objectives, items, answers, common mistakes); tỉ lệ đáp án được MathChecker xác nhận; **thời gian giáo viên cần để sửa draft** |
| Success criteria | ≥ 85% item trích đúng; ≥ 95% đáp án đúng hoặc được cảnh báo; thời gian sửa < 15 phút/lesson |
| Timebox | Ngày 5 → Ngày 14 |
| Decision unlocked | Schema `LessonDraft`/`LessonPackage`; hỗ trợ PPTX trong MVP hay chưa; có cần OCR riêng không |

### POC 3 — Teacher Material RAG / Grounding

| Mục | Nội dung |
|---|---|
| Objective | Chứng minh grounding: tutor bám tài liệu giáo viên; so sánh Context Loading và Chunk Retrieval |
| Input | Lesson package từ POC 2; bộ 60 câu hỏi (trong lesson, bài cũ, ngoài scope, bẫy "tài liệu sai") |
| Method | A: nạp nguyên package; B: retrieval top-k với filter scope. Đo trên cùng tutor prompt |
| Metrics | Faithfulness (claim có trong nguồn), dùng đúng thuật ngữ và ký hiệu của giáo viên, retrieval recall@5 (B), tỉ lệ từ chối đúng khi ngoài scope, scope leakage (phải = 0) |
| Success criteria | Faithfulness ≥ 95%; scope leakage 0; A ≥ B về chất lượng in-session (kỳ vọng) |
| Timebox | Ngày 9 → Ngày 14 |
| Decision unlocked | Thiết kế RAG (PART 21); embedding model; có cần hybrid search trong MVP không |

### POC 4 — Assessment Projection

| Mục | Nội dung |
|---|---|
| Objective | Assessment Spec G5 chạy tất định trên evidence và cho kết luận hợp lý theo đánh giá của giáo viên |
| Input | Evidence tổng hợp từ transcript POC 1 + 14 tình huống tối thiểu của alignment contract §9 (đúng lập luận đúng, đúng đáp án sai lập luận, partial, arithmetic slip, misconception, đoán, nhiều lần thử, hint leo thang, application thành công, near/far transfer thất bại, error detection, mâu thuẫn, thiếu dữ liệu, retention trễ) |
| Method | Projector thuần (Python) + golden tests + đưa kết quả cho 2 giáo viên xem mà không cho biết hệ thống kết luận gì |
| Metrics | Replay determinism (100%); đồng thuận với giáo viên về state label (κ); boundary tests pass |
| Success criteria | Determinism 100%; mọi boundary test pass; giáo viên đồng ý ≥ 80% nhãn trạng thái |
| Timebox | Ngày 7 → Ngày 14 |
| Decision unlocked | `mastery_policy v1`; Evidence schema v1; DI-1…DI-14 được duyệt hoặc sửa |

### POC 5 — Model Routing

| Mục | Nội dung |
|---|---|
| Objective | Routing in-session/off-session là server-side, không vượt qua được, và không tiêu hạn mức của model tutor ngoài giờ |
| Input | Gateway stub + SessionContext giả lập |
| Method | Test: request có/không có session ACTIVE, cố chèn tham số model, jailbreak "cho con dùng model mạnh", đo chi phí off-session |
| Metrics | 0 bypass; model class của mọi lời gọi off-session |
| Success criteria | 0 bypass trong 50 kịch bản tấn công; 100% lời gọi off-session dùng LIGHTWEIGHT |
| Timebox | 2 ngày (Ngày 12–13) |
| Decision unlocked | Interface AI Gateway (ADR-007) |

### POC 6 — English Voice (Grade 5 Speaking)

| Mục | Nội dung |
|---|---|
| Objective | Chọn kiến trúc voice (A speech-to-speech hay B cascade) cho Speaking lớp 5 |
| Input | 3 kịch bản speaking; giọng học sinh lớp 5 thật (D-T3) và giọng người lớn để so sánh |
| Method | Prototype A (`gemini-3.8-live`, free tier) và B (Web Speech API hoặc `gemini-3.5-transcribe-live` + `gemini-3.8-flash` + `gemini-3.8-flash-tts`), đều miễn phí |
| Metrics | Xem PART 20.3; thêm độ ổn định trên Chrome, Safari iPad; mức dùng hạn mức/phút |
| Success criteria | Như bảng PART 20.3 |
| Timebox | Spike 2 ngày trong tháng 1 (chỉ đo latency và khả năng điều khiển); POC đầy đủ ở phase English Speaking |
| Decision unlocked | ADR-012; provider voice; có tách Voice Gateway không |

### POC 7 — Session State (persistence/recovery)

| Mục | Nội dung |
|---|---|
| Objective | Learning state không mất khi refresh, disconnect, crash hoặc gửi trùng |
| Input | Orchestrator skeleton + Postgres |
| Method | Chaos test: kill process giữa lượt LLM, ngắt mạng, gửi trùng command, 2 tab cùng lúc |
| Metrics | Evidence mất (phải = 0), thời gian resume, xử lý trùng |
| Success criteria | 0 mất evidence đã ACK; resume ≤ 5s; command trùng không tạo event trùng |
| Timebox | Ngày 12 → Ngày 16 |
| Decision unlocked | ADR-005 (event + state), ADR-009 (SSE) |

**Spike thêm — STT Toán tiếng Việt** (2–3 ngày, tuần 3–4): 200 phát ngôn toán lớp 5 do học sinh thật và người lớn đọc (phân số, số thập phân với "phẩy", phần trăm, đơn vị) → đo WER và tỉ lệ normalizer parse đúng trên các lựa chọn miễn phí (Web Speech API, `gemini-3.5-transcribe-live`, PhoWhisper/faster-whisper local).

---

## PART 34 — FIRST VERTICAL SLICE

### 34.1. Phạm vi nhỏ nhất vẫn chứng minh được toàn bộ loop

```text
Teacher (1 người, 1 lớp demo)
 → tạo 1 lesson Toán 5 "So sánh số thập phân"
 → upload 1 PDF → ingestion → review/sửa → approve → publish (LessonPackage)
 → tạo lịch: 1 buổi, 30 phút
 → Scheduler sinh session → T-10' compile Tutor Contract
 → Student đăng nhập (class code + PIN) → "Đã đến giờ học Toán" → vào session
 → Socratic Tutor (text): CONCEPT_CHECK → [TEACH] → GUIDED_PRACTICE (hint engine) → EXIT_ASSESSMENT → SUMMARY
 → Evidence → Assessment projection → Student Model
 → Student report (đơn giản) + Teacher report (mastery/confidence theo KC, misconception, timeline session, transcript + audit)
```

**Không có trong slice:** voice, English, parent view (chỉ có tài khoản parent cho demo), off-session chat, PPTX, homework, retention review, dashboard lớp nâng cao.

### 34.2. Success criteria của slice

| Tiêu chí | Ngưỡng |
|---|---|
| E2E happy path chạy bằng Playwright trong CI | Pass |
| 5 synthetic student profile chạy hết session | 100% hoàn tất, không FAILED |
| Socratic eval (dataset v1) trên runtime thật (không phải notebook) | Đạt ngưỡng POC 1 |
| Replay: xóa projection → chạy lại → giống hệt | 100% |
| Chaos: refresh, disconnect, trùng command | 0 mất evidence |
| Authorization matrix test | 100% pass |
| Chủ dự án (vai giáo viên) và 3–5 học sinh thật dùng thử (D-T3) | ≥ 4/5 điểm "hữu ích"; ghi nhận danh sách vấn đề |
| Request và mức dùng hạn mức mỗi session | Có trong dashboard; đủ cho số buổi kiểm thử dự kiến mỗi ngày |

### 34.3. Benchmark ghi lại khi kết thúc slice (baseline cho mọi thay đổi sau)

TTFT p50/p95, turn latency, request/session, cache hit ratio, reject rate, leak rate, move fidelity, diagnosis accuracy, thời gian giáo viên soạn một lesson (từ upload đến publish).

---

## PART 35 — MVP

### 35.1. MVP phải chứng minh

```text
Teacher Design → Schedule → Tutor Contract → Tutor Session → Socratic AI Tutor
→ Student Evidence → Assessment → Report
```

...cho **một chương Toán 5 hoàn chỉnh** (5–8 lesson), với **một lớp thật trong pilot**, qua **nhiều tuần**. Một chatbot đơn thuần không được tính là MVP.

### 35.2. MVP = vertical slice + những thứ sau

| Thêm | Lý do |
|---|---|
| Nhiều lesson, lịch tuần, "lesson tiếp theo trong kế hoạch" | Học liên tục |
| ReviewSchedule + WARMUP_REVIEW (retention T1/T3/T7) | Chiều S và gate MASTERED |
| Parent account, parent report (consent chỉ là ghi nhận đơn giản) | Role thứ 3 |
| Teacher override, AI flag, pause tutor live | Kiểm soát của giáo viên |
| Math voice-to-text (sau spike STT) | Yêu cầu brief §18 |
| Radar, mastery timeline, class heatmap | Analytics giáo viên |
| PPTX ingestion (nếu POC 2 đạt) | Tài liệu giáo viên thực tế |
| Degraded mode, runbook sự cố, backup/restore đã diễn tập | Vận hành với trẻ thật |
| Red team pass, security review, audit log | An toàn |

### 35.3. DO NOT BUILD YET (brief §49)

| Hạng mục | Quyết định | Lý do | Khi nào xem lại |
|---|---|---|---|
| Gamification phức tạp (điểm, xếp hạng, cửa hàng) | ❌ Hoãn | Dễ làm lệch động lực (học vì điểm), tạo so sánh giữa trẻ; chưa chứng minh được learning loop | Sau pilot, chỉ khi có dữ liệu engagement cần cải thiện. Chấp nhận các yếu tố nhẹ: chuỗi ngày học, lời khen quá trình |
| Social features (chat giữa học sinh, bảng xếp hạng) | ❌ Hoãn | Rủi ro an toàn trẻ em, moderation | Không nằm trong roadmap 6 tháng |
| Mobile native app | ❌ Hoãn | Web responsive + PWA đủ cho tablet; native tốn gấp đôi công | Khi dữ liệu thiết bị cho thấy cần (mic, offline) |
| Advanced recommendation engine (ML) | ❌ Hoãn | Chưa có dữ liệu; rule-based (PART 26, DI-8) minh bạch hơn | Sau pilot với ≥ vài nghìn session |
| Microservices | ❌ Hoãn | ADR-001 | Khi có bottleneck đo được |
| Custom foundation model / fine-tune | ❌ Hoãn | Chi phí và rủi ro cao; prompt + policy chưa hết dư địa | Không trước năm 2 |
| Excessive analytics (knowledge graph động, dự báo) | ⚠️ Chỉ thu thập dữ liệu, chưa làm UI | Cần dữ liệu dọc thời gian | Pilot |
| Multi-grade support | ❌ Hoãn (chỉ tham số hóa schema) | Scope lock | Sau khi loop Grade 5 được kiểm chứng |
| Nhiều provider voice cùng lúc | ❌ Hoãn | Một provider + fallback text là đủ | Khi có vấn đề chất lượng hoặc giá cụ thể |
| Nhiều vector DB | ❌ Không | pgvector đủ ở quy mô này | Khi > vài triệu chunk hoặc latency không đạt |
| Off-session chat mở rộng | ⚠️ Chỉ cơ chế routing + flag | An toàn trẻ em | Sau safety review (red team) |
| Homework mode | ⚠️ Sau MVP | Cần loop chính ổn định | Phase sau pilot hoặc cuối MVP |

---

## PART 36 — PILOT (v0.2: kiểm thử nội bộ)

### 36.1. Thiết kế pilot

| Mục | Đề xuất |
|---|---|
| Quy mô | Nhóm học sinh lớp 5 kiểm thử nội bộ do chủ dự án sắp xếp (gợi ý 10–30 em, giới hạn bởi hạn mức free tier); chủ dự án là giáo viên |
| Thời gian | 6 tuần Toán (Pilot 1). English Reading/Speaking là Pilot 2 |
| Điều kiện bắt đầu | *(v0.2: pháp lý/consent đã được chủ dự án xử lý, D-T2)* runbook; red team pass; MVP exit criteria đạt; hạn mức free tier đủ cho lịch kiểm thử |
| Giám sát | Tuần 1: giáo viên ngồi cùng lớp trong mọi session. Review transcript hằng ngày theo mẫu (10%). Kênh báo sự cố nhanh |
| Đo lường | Học tập: pre/post test độc lập do giáo viên soạn (không phải item của hệ thống). Tutor: chỉ số Socratic trên dữ liệu thật. Assessment: giáo viên chấm song song 10% item giải thích (κ). Trải nghiệm: khảo sát ngắn học sinh (hình mặt cười), giáo viên, phụ huynh. Vận hành: uptime, latency, cost |
| Tiêu chí thành công | Không có sự cố an toàn nghiêm trọng; leak ở assessment = 0; κ giáo viên–hệ thống ≥ 0.6 cho state label; ≥ 80% session COMPLETED; giáo viên muốn tiếp tục dùng; không vượt hạn mức free tier trong ngày kiểm thử |
| Tiêu chí dừng | Sự cố an toàn trẻ em; lộ dữ liệu; tỉ lệ FAILED > 5%; giáo viên đánh giá hại nhiều hơn lợi |
| Kết quả | Báo cáo kiểm thử + hiệu chỉnh `mastery_policy v2`, `hint_policy v2`; số liệu cho chương thực nghiệm của đồ án |

### 36.2. Ghi chú đạo đức

- Không dùng hệ thống để xếp loại hay đánh giá học sinh chính thức trong pilot. Assessment chỉ là **formative/diagnostic** (khung English §15).
- Học sinh và phụ huynh có quyền rút khỏi pilot bất cứ lúc nào, và dữ liệu sẽ bị xóa theo yêu cầu.
