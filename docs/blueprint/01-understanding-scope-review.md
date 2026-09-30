# 01 — Project Understanding · Scope Lock · Requirement Analysis · Critical Review · Pre-coding Decisions

> PART 1 → PART 5. Quy ước nhãn: **[FACT]** đã xác minh · **[REC]** khuyến nghị kỹ thuật · **[ASSUME]** giả định hiện tại · **[OPEN]** chưa đủ dữ liệu.

---

## PART 1 — PROJECT UNDERSTANDING

### 1.1. Sản phẩm là gì

CAVAT là **AI-managed Learning Session Platform**, không phải chatbot. Đơn vị giá trị là một **buổi học có cấu trúc**:

- giáo viên thiết kế,
- scheduler kích hoạt,
- Tutor Contract ràng buộc,
- Tutor Orchestrator điều phối,
- Socratic AI Tutor trực tiếp dạy.

Mọi tương tác trong buổi học đều sinh ra **Learning Evidence**. Evidence được đánh giá bằng các thuật toán tất định (deterministic), có phiên bản và có thể replay, rồi cập nhật Student Model. Kết quả trả về giáo viên và phụ huynh dưới dạng dữ liệu giải thích được.

### 1.2. Ba role và vị trí của AI

| Role | Mối quan tâm chính | Hành động chính | Quan hệ với AI Tutor |
|---|---|---|---|
| Teacher | Học sinh hiểu gì, sai gì, lớp yếu ở đâu | Thiết kế lesson, upload tài liệu, xếp lịch, duyệt nội dung, override | AI thực thi thiết kế của giáo viên, không thay giáo viên ra quyết định sư phạm cấp lesson |
| Student (trung tâm) | Học, được giúp mà không bị "cho đáp án" | Vào buổi học đúng giờ, trả lời, hỏi, xin gợi ý | AI là người dạy trực tiếp, luôn ở Socratic Mode |
| Parent/Guardian | Con có học không, hiểu không, cần giúp gì | Xem tiến độ, đồng ý xử lý dữ liệu | AI (qua report) diễn giải dữ liệu cho phụ huynh |

AI là **lớp trung gian được kiểm soát**. Nó không sở hữu lịch học, không sở hữu điểm, và không tự ghi completion.

### 1.3. Định nghĩa thành công của phiên bản đầu

Một learning loop khép kín, chứng minh được bằng dữ liệu:

```text
Teacher Design → Schedule → Tutor Contract → Tutor Session → Socratic AI Tutor
→ Student Evidence → Assessment → Student Model → Report (Teacher + Parent)
```

Loop phải chạy trên **một lesson Toán lớp 5 thật**, với tài liệu giáo viên thật. AI phải đạt các ngưỡng đo được: không lộ đáp án, đúng hint level, chẩn đoán đúng misconception. Kết quả assessment phải replay được.

---

## PART 2 — SCOPE LOCK

### 2.1. Trong phạm vi (đã chốt)

| Môn | Lớp | Kỹ năng lõi | Kênh tương tác |
|---|---|---|---|
| Math | 5 | Chương trình Toán 5 (CT GDPT 2018) | Text + Voice-to-Text tiếng Việt (nói đáp án, nói câu hỏi) |
| English | 5 | **Reading + Speaking** (subskill: vocabulary, comprehension, fluency, inference, interaction, pronunciation, grammar feedback) | Text (Reading), Realtime Voice (Speaking) |

### 2.2. Ngoài phạm vi core MVP

- Lớp 4, 6, 7 và các môn khác.
- Listening và Writing như kỹ năng đích độc lập của English. Chúng chỉ được dùng như kênh tạo bằng chứng khi cần, ví dụ học sinh nghe tutor nói trong Speaking.
- Mobile native app, gamification phức tạp, social features.

### 2.3. Hệ quả của scope đối với hai tài liệu đánh giá

- **[FACT]** Khung đánh giá Tiếng Anh viết cho lớp 4–7 và bao gồm cả Listening/Writing. Ta chỉ trích phần lớp 5 và Reading/Speaking, vẫn giữ Support Ladder S0–S5 và rubric 0–4 cho mọi subskill.
- **[FACT]** Khung đánh giá Toán dùng ví dụ lớp 10–12 (đạo hàm, cực trị, tiệm cận) và misconception đại số (M01–M07). **Phần mô hình** (6 mức hiểu, 7 chiều, công thức, gate) dùng được cho lớp 5. **Phần nội dung** (KC, misconception, ví dụ transfer) phải viết lại cho lớp 5. Đây là một deliverable của Tuần 1 (xem PART 18).

### 2.4. Nguyên tắc mở rộng

Kiến trúc tham số hóa theo `subject × grade` ngay từ schema: `curriculum`, `kc`, `lesson`, `policy` đều có `grade`. Hiện tại chỉ có dữ liệu, policy và prompt cho Grade 5. Mở rộng lớp sau này là việc **thêm dữ liệu và policy**, không phải refactor.

---

## PART 3 — REQUIREMENT ANALYSIS

### 3.1. Functional requirements (nhóm theo domain)

| ID | Domain | Requirement | Mức |
|---|---|---|---|
| FR-01 | Content | Teacher tạo lesson có structured metadata (objectives, outcomes, prerequisites, concepts, examples, common_mistakes, exercises, assessment, duration, notes, homework, preview) | MUST |
| FR-02 | Content | Upload PDF/PPTX → trích xuất có cấu trúc → teacher review/approve → publish **Lesson Package** bất biến có version | MUST (PDF), SHOULD (PPTX) |
| FR-03 | Content | Phân biệt Raw / Processed / Chunks / Approved / Archived | MUST |
| FR-04 | Scheduling | Teacher tạo lịch tuần: môn, lesson, giờ, thời lượng; scheduler sinh LearningSession | MUST |
| FR-05 | Session | Student vào đúng giờ → kiểm tra lịch và session → mở session; không tự đổi lesson | MUST |
| FR-06 | Session | Backend enforce state, activity, contract cho mọi request | MUST |
| FR-07 | Tutor | Socratic Tutor Mode xuyên suốt (prompt + policy + state machine + hint engine) | MUST |
| FR-08 | Tutor | Multi-level hint theo policy dựa trên evidence | MUST |
| FR-09 | Tutor | Timer, ưu tiên objective → mandatory assessment → completion | MUST |
| FR-10 | Assessment | Evidence pipeline: Raw Event → Evidence → Feature → Assessment → Metric → Interpretation → Recommendation | MUST |
| FR-11 | Student Model | Mastery đa chiều theo KC/skill, mastery và confidence tách riêng, replayable | MUST |
| FR-12 | Reports | Student, Teacher, Parent views theo role | MUST (Teacher, Student), SHOULD (Parent) cho slice đầu |
| FR-13 | Teacher override | Edit lesson, đổi lịch, pause tutor, override assessment, review transcript/evidence, flag AI mistake | MUST (pause, review, override), SHOULD (phần còn lại) |
| FR-14 | Routing | Strong model trong session, lightweight ngoài session; backend quyết định | MUST (cơ chế), SHOULD (off-session chat) |
| FR-15 | Voice (Math) | Voice-to-Text tiếng Việt, chuẩn hóa biểu thức toán lớp 5 | SHOULD (MVP), MUST (Pilot) |
| FR-16 | Voice (English) | Realtime voice conversation cho Speaking | MUST ở phase English Speaking |
| FR-17 | Notifications | Nhắc giờ học, báo cáo buổi học cho phụ huynh | SHOULD |

### 3.2. Non-functional requirements

| ID | NFR | Mục tiêu ban đầu (điều chỉnh sau POC) |
|---|---|---|
| NFR-01 | Tutor latency (text) | Time-to-first-token p95 ≤ 2.0s; toàn bộ lượt p95 ≤ 6s |
| NFR-02 | Voice latency (English live) | End-of-speech → bắt đầu audio tutor, p95 ≤ 1.5s |
| NFR-03 | Durability của learning state | 0 mất evidence đã ACK; resume sau refresh/disconnect ≤ 5s |
| NFR-04 | Replay | Cùng evidence + cùng policy version → cùng projection (100%) |
| NFR-05 | Privacy | Cách ly dữ liệu theo trường/lớp; audit mọi truy cập transcript |
| NFR-06 | Cost | Chi phí biến đổi/học sinh/tháng đo được và nằm trong ngân sách **[OPEN]** |
| NFR-07 | Availability (pilot) | 99.5% trong khung giờ học |
| NFR-08 | Accessibility cho trẻ 10–11 tuổi | Câu ngắn, ngôn ngữ phù hợp, UI lớn, dùng được trên tablet/Chromebook |

### 3.3. Các yêu cầu ngầm mà brief chưa nêu

1. **Consent của phụ huynh** là điều kiện tiên quyết để xử lý dữ liệu học sinh, nhất là giọng nói. Việc này nằm trên critical path của pilot (PART 30).
2. **Deterministic math checking.** Tính đúng sai của đáp án Toán không được phụ thuộc vào LLM.
3. **Item bank có metadata** (KC, cognitive level A–E, difficulty, transfer, expected time, hint content, misconception rules). Không có item bank thì không có assessment có ý nghĩa.
4. **Tutor persona và ngôn ngữ xưng hô** phù hợp văn hóa: tutor xưng "cô/thầy", gọi học sinh là "con" hoặc "em". Đây là quyết định của nhóm pedagogy, cần nhất quán (**[OPEN]**).
5. **Thiết bị học sinh** (tablet, Chromebook, điện thoại phụ huynh, máy ở trường) quyết định microphone, trình duyệt và băng thông (**[OPEN]**).
6. **Bản quyền sách giáo khoa.** Curriculum Knowledge không thể ingest SGK khi chưa có quyền (PART 21).

---

## PART 4 — CRITICAL REVIEW

Phần này audit brief và hai tài liệu đánh giá, chỉ ra chỗ mâu thuẫn, chỗ rủi ro và chỗ cần thiết kế lại.

### 4.1. Mâu thuẫn trong khung đánh giá Toán (cần pedagogy lead chốt)

| # | Vấn đề | Bằng chứng trong tài liệu | Đề xuất |
|---|---|---|---|
| C1 | Hàm Understanding có **6** chiều (Knowledge, Reasoning, Application, Transfer, Stability, Independence), nhưng công thức M có **7** trọng số (C, R, A, T, I, S, **D**). "Knowledge" bị thay bằng "Correctness" và thêm "Diagnostic" | §2 và §20 | **[REC]** Dùng 7 chiều của công thức M làm chuẩn tính toán; hiển thị radar 6 trục theo §24, trong đó Knowledge ≈ Correctness. Ghi rõ đây là *declared interpretation* |
| C2 | Có **ba hệ thống dải điểm khác nhau**: 6 mức hiểu (0–19/20–39/40–59/60–74/75–89/90–100), màu heatmap (0–39/40–59/60–74/75–89/90–100) và Recommendation (0–30/30–50/50–65/65–80/80–90/90+) | §4–8, §25, §50 | **[REC]** Mức hiểu và màu heatmap tương thích nhau (mức 0 và 1 cùng màu đỏ). Recommendation bands **lệch** so với hai hệ còn lại → đề xuất căn theo ranh giới mức hiểu, đưa vào `mastery_policy` có version, pedagogy lead ký duyệt |
| C3 | Gate MASTERED yêu cầu Retention ≥ 70%, nhưng retention chỉ đo được sau T1–T30 ngày. Trong một buổi học không có retention, vậy M tính thế nào? | §19, §53, §55 ("Retention: chưa đủ dữ liệu") | **[REC]** Chiều thiếu dữ liệu thì **loại khỏi mẫu số** (renormalize trọng số) và **giảm confidence**. Trạng thái cao nhất đạt được trong một buổi là `PROVISIONALLY_MASTERED` |
| C4 | Bảng Independence có 6 mức hỗ trợ; brief có 8 mức hint (H0–H7); English có S0–S5 | §11, brief §6, English §9 | **[REC]** Ladder Toán H0–H7 và ladder English S0–S5 là **hai ladder riêng**, mỗi rung ánh xạ sang `independence_weight`. Các giá trị nội suy phải ghi là declared interpretation (PART 15) |
| C5 | Trọng số M (0.20/0.20/0.15/0.15/0.10/0.10/0.10) và QuestionScore (0.35/0.30/0.15/0.10/0.10) là **đề xuất**, chưa được hiệu chỉnh | §20, §35 | **[ASSUME]** Dùng nguyên văn làm `mastery_policy v1`. Hiệu chỉnh bằng dữ liệu pilot và chấm song song với giáo viên |

### 4.2. Rủi ro và hạn chế trong khung đánh giá Tiếng Anh

- **[FACT]** Tài liệu nêu rõ các ngưỡng mastery là "đề xuất vận hành của CAVAT, không được trình bày như điểm chuẩn chính thức của Bộ GD&ĐT". Mọi UI hay report không được gọi là "chuẩn Bộ".
- **[FACT]** Tài liệu cảnh báo ASR trên giọng trẻ em có độ chính xác không đồng đều và không được chấm Speaking chỉ từ transcript. Hệ quả: đánh giá Speaking là **thành phần rủi ro AI cao nhất** của dự án, và là lý do chính để làm Math trước (PART 12, Q10).
- **[FACT]** Rubric 0–4 **không phải phần trăm**. **[REC]** Không quy đổi English sang % để đặt cạnh Toán. Cả hai môn dùng chung một lớp "trạng thái hiển thị định tính" cho phụ huynh (PART 27).

### 4.3. Audit brief: những chỗ cần thiết kế lại

| # | Brief nói | Vấn đề | Thiết kế lại |
|---|---|---|---|
| R1 | Session state machine gộp lifecycle (SCHEDULED, READY, PAUSED) với pha sư phạm (REVIEW, TEACH, PRACTICE) | Hai loại state có tần suất đổi và luật khác nhau. Gộp lại thì số tổ hợp bùng nổ (PAUSED trong REVIEW? INTERRUPTED trong ASSESS?) | **[REC]** State machine **3 tầng, trực giao**: (1) Session Lifecycle, (2) Activity Plan, (3) Item Tutoring Loop (PART 16, 24) |
| R2 | Hint ladder tuyến tính H0→H7 theo số lần sai | Hint phải nhắm vào **chỗ sai**. Lỗi tính toán không cần "nhắc khái niệm"; misconception cần câu hỏi gây xung đột nhận thức | **[REC]** Hint là **2 trục**: *target* (đề bài / khái niệm / chiến lược / bước / tính toán) × *strength* (H0–H7) (PART 15) |
| R3 | Rút ra từ §5: "Chỉ đưa lời giải đầy đủ khi policy cho phép" | Học sinh 10 tuổi bị kẹt lâu sẽ nản. Với người mới học, worked example có hiệu quả sư phạm | **[REC]** H7 không phải "thất bại". Sau H6/H7 bắt buộc có **teach-back** ("con giải thích lại cho cô") và một **bài song sinh (isomorphic)** ở H0 để lấy lại bằng chứng độc lập |
| R4 | Session 45 phút | Với trẻ lớp 5, 45 phút liên tục với AI dễ gây mất tập trung | **[ASSUME]** Mặc định 25–30 phút, có micro-break. Teacher vẫn chỉnh được. Kiểm chứng trong pilot |
| R5 | Nghe như RAG tìm kiếm trên toàn bộ tài liệu giáo viên | Một lesson package của lớp 5 chỉ vài nghìn token, **vừa trọn trong context** | **[REC]** In-session grounding dùng **nạp nguyên Approved Lesson Package vào prompt, có cache**. Vector retrieval dùng cho curriculum rộng, ôn bài cũ và câu hỏi ngoài giờ (PART 21, Q4) |
| R6 | Math voice ví dụ "x bình phương", "âm năm" | **[ASSUME]** Theo CT 2018, số nguyên âm học ở lớp 6 và lũy thừa biến không có trong Toán 5 | Speech normalizer vẫn parse được nhưng gắn cờ `out_of_grade_scope`. Tutor chuyển hướng nhẹ nhàng |
| R7 | Tiếng Việt dùng **dấu phẩy thập phân** ("0,5" đọc "không phẩy năm") | **[FACT]** Parser, checker và UI phải dùng locale vi-VN. Nếu không, "0,5" dễ bị hiểu thành danh sách hai số | Chuẩn hóa nội bộ bằng số hữu tỉ chính xác (Fraction/Decimal), hiển thị theo vi-VN |
| R8 | Có lightweight chat ngoài giờ học | Chat tự do với trẻ 10 tuổi là **bề mặt rủi ro an toàn trẻ em** (nội dung, thu thập dữ liệu cá nhân, phụ thuộc) | **[REC]** Xây **cơ chế routing** trong MVP. Off-session chat để sau feature flag, cần consent của phụ huynh, giới hạn chủ đề và số lượt/ngày |
| R9 | Có tier "Free" của provider | **[FACT]** Trang giá Gemini API ghi free tier có "Content used to improve our products: Yes" | **[REC]** Tuyệt đối không đưa dữ liệu học sinh thật lên free tier. Free tier chỉ dùng cho POC với dữ liệu tổng hợp |
| R10 | Event list tối thiểu | Thiếu các event cần cho replay và audit: `ACTIVITY_COMPLETED`, `STEP_SUBMITTED`, `EXPLANATION_SUBMITTED`, `ANSWER_CHANGED`, `TUTOR_MESSAGE_SENT`, `POLICY_DECISION`, `STATE_TRANSITIONED`, `CONTRACT_BOUND`, `MODEL_FALLBACK`, `TIME_WARNING`, `TEACHER_OVERRIDE`, `EVIDENCE_RECORDED`, `ASSESSMENT_COMPUTED`, `SESSION_INTERRUPTED`, `SESSION_MISSED`, `SESSION_FAILED` | Bổ sung (PART 10) |
| R11 | Realtime voice (speech-to-speech) cho English | Model realtime là thứ "nói", nên orchestrator mất quyền kiểm soát từng lượt, trái với nguyên tắc "LLM không tự quản lý" | **[REC]** POC so sánh *speech-to-speech có orchestrator điều khiển qua instruction và tool call* với *pipeline cascade STT→LLM→TTS* (PART 20) |
| R12 | "Team phải làm gì trước" chỉ nói về kỹ thuật | Thiếu hai track có lead time dài: **pháp lý/consent** và **tuyển trường, giáo viên pilot** | Hai track này bắt đầu từ Ngày 1 (PART 41) |
| R13 | Team 5 người | Không có **chuyên gia sư phạm/giáo viên lớp 5** có trách nhiệm chính thức, dù pedagogy là nền của toàn bộ dự án | **[REC]** Có ít nhất 1 giáo viên cố vấn (bán thời gian, có hợp đồng) ký duyệt pedagogy spec |

### 4.4. Giả định lớn nhất của dự án (phải kiểm chứng sớm)

> **[ASSUME-0]** Một LLM hiện đại, khi được một policy engine tất định điều khiển, có thể dạy Socratic cho trẻ lớp 5 bằng tiếng Việt với chất lượng giáo viên chấp nhận được, trong độ trễ và chi phí chấp nhận được.

Nếu giả định này sai, mọi thứ còn lại đều vô nghĩa. Vì vậy **POC 1 bắt đầu từ Ngày 2**, trước cả database.

---

## PART 5 — WHAT MUST BE DECIDED BEFORE CODING

Phân loại theo "phải biết trước khi viết code production", "phải prototype", "quyết sau được".

### 5.1. Phải biết/chốt trước khi viết code production

| # | Cần biết | Vì sao | Hình thức chốt | Deadline |
|---|---|---|---|---|
| K1 | Lesson đầu tiên của vertical slice (Toán 5) + bộ SGK tham chiếu | Mọi item, KC, misconception, eval đều phụ thuộc | Quyết định với giáo viên cố vấn | Ngày 2 |
| K2 | Pedagogy spec cho lesson đó: objectives, KC graph, misconception catalog, item bank A–E, hint content, session flow | Là input của POC 1, Tutor Contract, Assessment | Tài liệu `docs/pedagogy/math-g5/<lesson>/` được ký duyệt | Ngày 5 |
| K3 | Assessment Spec Grade 5 v1: chiều, trọng số, dải, gate, xử lý thiếu dữ liệu, mapping ladder → independence | Assessment phải deterministic, có version | ADR + `mastery_policy v1` | Ngày 7 |
| K4 | Tenancy model (School → Class → Enrollment) và identity model cho trẻ em (không email) | Khó đảo ngược | ADR | Ngày 7 |
| K5 | Event và Evidence schema v1 (append-only, versioned) | Khó đảo ngược, là nền của replay | ADR + JSON Schema | Ngày 10 |
| K6 | Tutor Contract schema v1 | Là API giữa Teacher Design và Runtime | ADR + JSON Schema | Ngày 10 |
| K7 | AI Gateway abstraction (interface theo *model class*, không theo vendor) | Khó đảo ngược nếu business logic gọi SDK trực tiếp | ADR + interface | Ngày 10 |
| K8 | Cloud, region lưu trữ và chiến lược chuyển dữ liệu xuyên biên giới | Pháp lý, khó đảo ngược | ADR + ý kiến pháp lý | Ngày 14 (tạm), trước pilot (chính thức) |

### 5.2. Phải prototype (không quyết bằng suy luận)

- Chất lượng Socratic và độ tuân thủ policy của model ứng viên (POC 1).
- Trích xuất cấu trúc từ PDF/PPTX thật của giáo viên Việt Nam (POC 2).
- Grounding khi dùng lesson package so với chunk retrieval (POC 3).
- Tính tất định của mastery projection trên evidence tổng hợp (POC 4).
- Độ chính xác STT tiếng Việt cho phát ngôn toán lớp 5 (spike trong POC 6/7).
- Độ trễ và khả năng kiểm soát của realtime voice với tiếng Anh trẻ em (POC 6).

### 5.3. Quyết sau được (dễ đảo ngược)

UI component library, chart library, thư viện state management phía FE, nhà cung cấp email/SMS, công cụ tracing LLM cụ thể, embedding model (chi phí re-embed ở quy mô này không đáng kể), provider TTS.
