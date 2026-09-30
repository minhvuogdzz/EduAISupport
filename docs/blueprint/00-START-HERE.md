# PROJECT AUDIT — GREENFIELD CAVAT GRADE 5

> **CAVAT AI Tutor: Product + Pedagogy + AI + RAG + Data + Engineering Blueprint**
> Phiên bản blueprint: v0.1 · Ngày: 2026-09-30 · Trạng thái: **đề xuất, chờ team review**
> Scope đã chốt: **Math Grade 5 + English Grade 5 (Reading + Speaking)**

## Quy ước nhãn (brief §79)

| Nhãn | Nghĩa |
|---|---|
| **[FACT]** | Đã xác minh (tài liệu đánh giá được cung cấp, trang giá chính thức, tài liệu API) |
| **[REC]** | Khuyến nghị kỹ thuật |
| **[ASSUME]** | Giả định hiện tại, cần kiểm chứng |
| **[OPEN]** | Chưa đủ dữ liệu để quyết định (có trong PART 47) |
| **DI-n** | *Declared Interpretation*: diễn giải công thức hoặc ngưỡng do dự án tự đặt, cần pedagogy lead duyệt |

Đầu vào đã đọc:
- Khung đánh giá Toán: `MathAIsupport.v2/docs/current/pedagogy/math/Kế hoạch đánh giá mức độ hiểu bài của học sinh bằng dữ liệu trực quan.md` (60 mục) và alignment contract đi kèm.
- Khung đánh giá Tiếng Anh: `MathAIsupport.v2/docs/current/pedagogy/english/CAVAT_Khung_danh_gia_muc_do_hieu_bai_Tieng_Anh_lop_4-7.docx` (v1.0, 16/09/2026).

Hai file không nằm ở đường dẫn gốc mà brief ghi (thư mục gốc `MathAIsupport.v2/`), mà nằm trong `docs/current/pedagogy/`. Nội dung đã được đọc đầy đủ. Dự án này là **greenfield**: codebase cũ trong `MathAIsupport.v2` **không** được dùng làm nền; chỉ hai tài liệu đánh giá được dùng làm chuẩn.

---

## Câu hỏi trung tâm

> *"Nếu hôm nay chưa có một dòng code nào, chưa có DB, chưa có model AI, chưa có RAG và chưa có infrastructure, chính xác team nên bắt đầu từ đâu, làm gì trước, xác minh điều gì trước, và vì sao?"*

### Trả lời ngắn

**Bắt đầu từ một lesson Toán lớp 5 cụ thể, không phải từ database hay chatbot.**

1. **Ngày 1–2: chốt người và nội dung.** Ký hợp đồng giáo viên cố vấn lớp 5, chọn *một* lesson (mặc định: *So sánh số thập phân*). Khởi động song song track pháp lý/consent và foundation kỹ thuật (repo, CI, staging). Hai track này không phụ thuộc gì và có lead time dài.
2. **Ngày 2–6: viết spec sư phạm có thể thực thi cho lesson đó.** Gồm KC graph, misconception catalog có "bug rules", 30–40 item theo mức A–E, hint templates, session flow và Assessment Spec lớp 5 (trích từ hai khung đánh giá, ghi rõ các DI). Từ spec đó viết **eval dataset trước khi viết prompt production**.
3. **Ngày 2–12: kiểm chứng giả định lớn nhất (ASSUME-0) bằng POC 1.** Câu hỏi là: LLM, khi được một policy engine tất định điều khiển, có dạy Socratic bằng tiếng Việt cho trẻ lớp 5 đủ tốt, đủ nhanh, đủ rẻ không? POC này không cần DB, UI hay infra. Nếu giả định sai thì mọi thứ khác vô nghĩa, nên nó phải đi đầu.
4. **Ngày 7–14: chỉ khi có dữ liệu từ POC 1 và POC 4 (assessment projection) mới chốt các quyết định khó đảo ngược**: Evidence/Event schema, Tutor Contract, AI Gateway. Tenancy và identity trẻ em chốt sớm hơn (Ngày 7) vì không phụ thuộc AI.
5. **Ngày 15–30: xây runtime production và một vertical slice mỏng xuyên suốt.** Teacher publish → Schedule → Contract → Socratic session → Evidence → Assessment → Report. Đo bằng eval, chaos test và giáo viên đóng vai.

**Vì sao thứ tự này:** rủi ro lớn nhất của dự án không nằm ở CRUD hay hạ tầng, mà ở (a) **chất lượng sư phạm của AI** và (b) **tính đúng và tính giải thích được của assessment**. Cả hai đều kiểm chứng được rẻ và sớm bằng spec + notebook + eval. Ngược lại, database schema cho evidence thiết kế trước khi biết AI sinh ra được gì là quyết định khó đảo ngược dựa trên phỏng đoán.

---

## Mục lục blueprint

| File | Nội dung | PART |
|---|---|---|
| [01-understanding-scope-review.md](01-understanding-scope-review.md) | Project Understanding, Scope Lock, Requirement Analysis, **Critical Review**, What Must Be Decided Before Coding | 1–5 |
| [02-strategy-dependencies-decisions.md](02-strategy-dependencies-decisions.md) | Greenfield Strategy, Decision Dependency Graph + Critical Path, **Architecture Decision Register**, Open Technical Decisions | 6, 7, 47 |
| [03-domain-system-data.md](03-domain-system-data.md) | Domain Model, System Architecture, Data Architecture, Event catalog, AI Memory | 8–10 |
| [04-ai-model-voice.md](04-ai-model-voice.md) | AI Architecture, **Model Strategy + giá đã xác minh**, Realtime Voice | 11, 12, 20 |
| [05-socratic-tutor-core.md](05-socratic-tutor-core.md) | **Socratic Tutor Architecture, System Prompt, Hint Engine, Orchestrator, Tutor Contract** | 13–17 |
| [06-math-english-tutors.md](06-math-english-tutors.md) | Math Grade 5 Tutor, English Grade 5 Tutor | 18, 19 |
| [07-rag-content-pipeline.md](07-rag-content-pipeline.md) | RAG Architecture, Teacher Content Pipeline | 21, 22 |
| [08-scheduler-session-control.md](08-scheduler-session-control.md) | Scheduler, Session Control, Student Control vs Pedagogy | 23, 24 |
| [09-student-model-assessment-analytics.md](09-student-model-assessment-analytics.md) | **Assessment (trích xuất hai khung)**, Student Model, Learning Analytics | 25–27 |
| [10-database-api.md](10-database-api.md) | Database/ERD, API Design | 28, 29 |
| [11-security-observability-cost.md](11-security-observability-cost.md) | Security/Privacy, Observability, Failure Handling, **Cost Model** | 30–32 |
| [12-pocs-slice-mvp-pilot.md](12-pocs-slice-mvp-pilot.md) | **7 POCs**, First Vertical Slice, MVP, Do Not Build Yet, Pilot | 33–36 |
| [13-production-stack-team.md](13-production-stack-team.md) | Production Architecture, **Tech Stack**, Development Foundation, Team Model, Parallel Workstreams | 37–40 |
| [14-plan-roadmap-backlog.md](14-plan-roadmap-backlog.md) | **First 30 Days**, Engineering Roadmap, Engineering Backlog | 41–43 |
| [15-testing-eval-risk-blueprint.md](15-testing-eval-risk-blueprint.md) | Test Strategy, AI Evaluation, Risk Register, **Final Implementation Blueprint** | 44–46, 48 |

---

## CRITICAL QUESTIONS — trả lời trực tiếp (brief §77)

**Q1. Từ số 0 nên bắt đầu ở đâu?**
Từ **một lesson Toán 5 cụ thể và spec sư phạm có thể thực thi của nó**, cộng với POC Socratic trên spec đó. Song song là foundation kỹ thuật và pháp lý. Không bắt đầu từ DB, UI hay chatbot. Chi tiết ở câu trả lời trung tâm phía trên và PART 6, 41.

**Q2. Có nên design domain trước DB không?**
**Có.** Domain (bounded contexts, aggregate, ownership, lifecycle) quyết định schema, không phải ngược lại. Nhưng domain được chốt **theo hai đợt**: phần ổn định (identity, org, tenancy, scheduling) ở Ngày 7; phần evidence/contract ở Ngày 12–14, sau khi POC 1 và POC 4 cho biết AI thực sự sinh ra và cần gì (PART 7, 8).

**Q3. Có nên POC AI trước khi chốt model provider không?**
**Có, bắt buộc.** Chọn model là quyết định về chất lượng sư phạm, độ trễ và chi phí, và chỉ đo được bằng eval trên chính lesson và kịch bản của dự án. Mặc định tạm thời là `claude-opus-5-5` (effort thấp/vừa), nhưng POC 1 so sánh ≥ 3 ứng viên. Nhờ AI Gateway (ADR-007), việc đổi provider sau này rẻ (PART 12, 33).

**Q4. Có nên xây RAG trước Tutor hay đồng thời?**
**Tutor trước. RAG tối thiểu đi đồng thời. RAG đầy đủ đi sau.** Lesson package của lớp 5 vừa trọn trong context, nên grounding in-session dùng **nạp nguyên package đã duyệt (có cache)**, không cần vector search. Ingestion (POC 2) chạy song song vì nó tạo ra package. Retrieval theo scope (bài cũ, ngoài giờ) được xây sau và không nằm trên critical path (PART 21).

**Q5. Teacher material có nên trở thành scoped RAG knowledge không?**
**Có, nhưng chỉ sau khi được duyệt.** Luồng là Raw → Processed → Draft → **Approved** → Package/Chunks, và mỗi chunk mang scope (trường, lớp, lesson, version, visibility). Retrieval lọc theo scope của contract ngay trong SQL, với RLS làm lớp phòng thủ thứ hai. Học sinh A không bao giờ truy xuất được toàn bộ tài liệu giáo viên, answer key hay bài chưa tới lịch (PART 21.4, 22).

**Q6. Teacher material có nên được ưu tiên hơn generic model knowledge không?**
**Có về nội dung và cách trình bày, nhưng không mù quáng về tính đúng.** Thứ tự ưu tiên: Published Teacher Lesson → Approved Curriculum → Allowed Knowledge → General Model Knowledge (chỉ để diễn đạt). Tài liệu giáo viên bị kiểm tra khi ingestion (MathChecker xác minh đáp án, phát hiện sai lớp, prompt injection). Nếu có sai sót thì **chặn publish và báo giáo viên**, không để tutor dạy điều sai (PART 21.3).

**Q7. Socratic Tutor có nên được xây ngay từ prototype đầu tiên không?**
**Có.** Socratic là bản chất sản phẩm, không phải tính năng. Prototype đầu tiên (POC 1) **chính là** Socratic Tutor với policy + hint engine + validator. Một chatbot giải bài "thêm Socratic sau" sẽ có kiến trúc sai: LLM tự quyết mọi thứ. POC 1 còn có ablation "chỉ prompt" và "prompt + policy" để chứng minh giá trị của policy (PART 13, 33).

**Q8. System prompt, hint engine và state machine nên phối hợp thế nào?**
Mỗi thành phần trả lời một câu hỏi khác nhau:
- **State machine** (3 tầng: lifecycle, activity, item loop) trả lời *đang ở đâu, được đi đâu*.
- **Policy + Hint engine** trả lời *nước đi sư phạm tiếp theo là gì* (move, target × level, kèm reason codes).
- **System prompt** (5 lớp; lớp L5 là Turn Directive từ policy) trả lời *nói thế nào*.
- **Validator** trả lời *output có tuân thủ không* (lộ đáp án, đúng move, một câu hỏi, ngôn ngữ, grounding).

LLM **diễn đạt** nước đi đã được chọn, và **đề xuất** nhãn phân tích. Nó không tự chuyển state, không tự chọn hint level, không ghi mastery (PART 13–16).

**Q9. Có thể route strong model trong session và lightweight model ngoài session không?**
**Có.** Routing là quyết định server-side dựa trên SessionContext (session ACTIVE hợp lệ + `contract.modelPolicy`). Client không có tham số model. Ngoài giờ, LIGHTWEIGHT (`claude-haiku-4-5`) chạy với guard và rate limit, và **không có code path** nào ghi evidence, completion hay schedule. Cơ chế routing được xây trong MVP; chat ngoài giờ bị giữ sau feature flag, chờ consent và safety review (PART 12.4, POC 5).

**Q10. Math Grade 5 hay English Grade 5 nên là vertical slice đầu tiên?**
**Math Grade 5.**

| Tiêu chí | Math G5 | English G5 |
|---|---|---|
| Technical complexity | Thấp–vừa (text, render toán; voice tùy chọn) | Cao (realtime audio, barge-in, pronunciation) |
| AI risk | Vừa (lộ đáp án, sai số học → khắc phục bằng checker tất định) | Cao (ASR trẻ em L2 thiếu ổn định, chấm speaking chủ quan, bias) |
| Voice dependency | Không bắt buộc | Bắt buộc cho Speaking |
| Pedagogical complexity | Vừa, misconception có catalog và bug rule | Cao (đáp án mở, nhiều chiều) |
| RAG dependency | Tương đương | Tương đương |
| Assessment complexity | Vừa, correctness tất định + nhãn reasoning | Cao, rubric 0–4 × nhiều chiều, cần giáo viên chấm song song |
| Validation speed | **Nhanh**: eval tự động bằng checker và synthetic students | Chậm, cần người chấm, cần giọng trẻ (cần consent) |

English **Reading** (text) là slice thứ hai, chạy trên cùng runtime từ khoảng tuần 9. English **Speaking/Voice** đi cuối, sau khi POC 6 chốt kiến trúc voice.

**Q11. Có nên xây Student Model ngay từ MVP không?**
**Có, nhưng ở dạng tối giản và tất định từ vertical slice.** Brief yêu cầu evidence → assessment → report, và không có Student Model thì không có report ý nghĩa. v1 là Beta theo từng chiều của khung Toán + công thức M + confidence (các DI). BKT hay knowledge tracing nâng cao để sau pilot. Quan trọng hơn thuật toán là **evidence ledger đúng và replay được**, để sau này đổi thuật toán mà không mất dữ liệu (PART 25).

**Q12. Assessment nên nằm trong Tutor Runtime hay service/module riêng?**
**Module riêng** (trong monolith), được runtime gọi theo hai đường: `check()` đồng bộ (đúng/sai, bug rule) và `record_evidence()` → projector bất đồng bộ (mastery). Lý do: assessment phải tất định, có version và replay được, và teacher override hay re-projection không được đụng tới runtime (PART 26.4).

**Q13. Realtime voice nên tích hợp ở phase nào?**
- **Math voice-to-text:** trong MVP (tuần 5–10), sau spike STT ở tuần 4.
- **English realtime speaking:** phase P7 (từ khoảng tuần 13), sau English Reading và POC 6 đầy đủ, khi runtime text đã ổn định và có consent cho giọng trẻ.
- Trong 30 ngày đầu chỉ có spike 2 ngày để giảm bất định về latency và khả năng điều khiển (PART 20, 42).

**Q14. Analytics nào phải có ngay từ ngày đầu?**
Không phải dashboard đẹp, mà là **dữ liệu đúng**: 100% event theo schema (có sequence, correlation, version); attendance và completion; outcome từng item kèm support level, số hint, thời gian; misconception frequency; chỉ số Socratic (leak, reject, fidelity); latency và cost mỗi session; mastery + confidence theo KC cho giáo viên. Radar, timeline, knowledge graph và retention đi vào MVP hoặc pilot khi có đủ dữ liệu dọc (PART 27.3).

**Q15. MVP nên có bao nhiêu database/storage system?**
**Hai:** PostgreSQL (OLTP + event ledger + job queue + pgvector) và Object Storage (file gốc, audio). Không dùng Redis, vector DB riêng, MongoDB hay warehouse trong MVP. Mỗi thứ đều có đường thêm vào sau khi có nhu cầu đo được (ADR-008, PART 10).

**Q16. Kiến trúc nào khó thay đổi nhất?**
Theo thứ tự: (1) **Event/Evidence schema và data ownership**, vì là hợp đồng dài hạn của mọi phân tích và replay; (2) **Tenancy và identity trẻ em**; (3) **Cloud/region và luồng dữ liệu xuyên biên giới** (pháp lý); (4) **Tutor Contract schema**; (5) **AI Gateway abstraction** (khó nếu không làm từ đầu, dễ nếu làm đúng); (6) ngôn ngữ backend. UI library, chart library, embedding model và TTS đều dễ đổi (ADR register).

**Q17. Những phần nào có thể làm song song?**
Ngay từ Ngày 1: pedagogy spec ∥ foundation (repo, CI, infra, auth skeleton) ∥ UX prototype ∥ pháp lý/consent. Sau khi có spec một lesson: POC 1 ∥ POC 2 ∥ identity/org/scheduling. Sau khi schema chốt: orchestrator ∥ content pipeline ∥ session UI ∥ projector. **Không song song**: evidence tables trước POC 1/4; orchestrator trước contract/gateway schema; report UI trước metric spec; voice trước POC 6; pilot trước pháp lý (PART 40).

**Q18. Những phần nào tuyệt đối chưa nên code?**
- Gamification phức tạp, social features.
- Mobile native, microservices, custom/fine-tuned model.
- ML recommendation engine, multi-grade.
- Nhiều provider voice, nhiều vector DB.
- Off-session chat mở rộng.
- Dashboard dự báo hoặc knowledge graph động trước khi có dữ liệu.
- Bất kỳ code production nào cho evidence/assessment trước khi Assessment Spec G5 được ký.
- Bất kỳ luồng nào đưa dữ liệu trẻ thật vào hệ thống trước khi có consent và ý kiến pháp lý.

Chi tiết ở PART 35.3.

---

## 10 phát hiện quan trọng nhất của audit

1. **Khung đánh giá Toán dùng ví dụ lớp 10–12.** Phần mô hình dùng được cho lớp 5; phần nội dung (KC, misconception, transfer) phải viết lại. Việc này có trong kế hoạch Tuần 1.
2. **Khung Toán có ba hệ dải điểm không khớp nhau** (6 mức, màu heatmap, recommendation) và **6 chiều khác 7 trọng số**. Cần pedagogy lead chốt (C1, C2).
3. **Retention không đo được trong một buổi học.** Vì vậy "MASTERED" chỉ có thể là *provisional* cho tới khi có delayed probe, nên ReviewSchedule phải có trong MVP.
4. **Hint ladder nên có hai trục (target × level)**, không phải một thang tuyến tính. Lỗi tính toán cần "tự kiểm tra", không cần "nhắc khái niệm".
5. **State machine của brief nên tách làm ba tầng trực giao.** Gộp lifecycle với pha sư phạm sẽ gây bùng nổ tổ hợp trạng thái.
6. **Grounding in-session không cần vector search**, vì lesson package vừa trọn trong context. Critical path không phụ thuộc chất lượng retrieval.
7. **Free tier của Gemini ghi rõ dữ liệu được dùng để cải thiện sản phẩm**, nên tuyệt đối không dùng với dữ liệu trẻ thật.
8. **Pháp lý về dữ liệu trẻ em và chuyển dữ liệu ra nước ngoài** là critical path của pilot, không phải của code. Phải bắt đầu Ngày 1.
9. **Chi phí ước tính khoảng $13–20/học sinh/tháng** với lịch 6 buổi/tuần (Sonnet 5.5 hoặc Opus 5.5). Output token của tutor là khoản lớn nhất. Giá bán quyết định kịch bản khả thi.
10. **Thiếu vai trò giáo viên cố vấn lớp 5** trong team 5 người. Không có người này, pedagogy spec, thứ đi đầu critical path, sẽ bị chậm.
