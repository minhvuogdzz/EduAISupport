# 06 — Math Grade 5 Tutor · English Grade 5 Tutor

> PART 18, PART 19.

---

## PART 18 — MATH GRADE 5 TUTOR

### 18.1. Phạm vi nội dung (anchor theo CT GDPT 2018)

**[ASSUME — cần chủ dự án (giáo viên kiểm soát) xác nhận theo CT 2018 và bộ SGK dùng trong kiểm thử]** Các mạch nội dung Toán 5:

| Mạch | Chủ đề (ví dụ) | Độ giàu misconception | Hợp với voice |
|---|---|---|---|
| Số và phép tính | Phân số (ôn tập, phân số thập phân), **số thập phân** (đọc, viết, so sánh, làm tròn, 4 phép tính), tỉ số, **tỉ số phần trăm** | Rất cao | Cao |
| Hình học và đo lường | Tam giác, hình thang, hình tròn (chu vi, diện tích), hình hộp chữ nhật, hình lập phương (diện tích xung quanh, toàn phần, thể tích), đơn vị diện tích và thể tích, thời gian, vận tốc | Cao (đơn vị, công thức) | Trung bình |
| Thống kê và xác suất | Biểu đồ hình quạt tròn, khả năng xảy ra | Trung bình | Thấp |

### 18.2. Lesson cho vertical slice đầu tiên

**[REC] Mặc định:** *So sánh số thập phân* (và sắp xếp thứ tự). **Phương án thay thế:** *Cộng, trừ số thập phân* hoặc *Tỉ số phần trăm*. Chốt với giáo viên theo lịch dạy thực tế (K1).

Lý do:
- Misconception **được nghiên cứu kỹ và nhận diện được bằng luật tất định** (bug rules), nên chẩn đoán đo được chính xác.
- Đáp án ngắn, so sánh được bằng code, nên eval tự động nhanh.
- Có đủ các mức A–E và bài error-detection tự nhiên.
- Voice hợp ("không phẩy hai lăm lớn hơn không phẩy ba").

**Knowledge Components (bản nháp):**

```text
KC-DEC-READ   Đọc, viết số thập phân
KC-DEC-PLACE  Giá trị theo hàng (phần mười, phần trăm, phần nghìn)       ← prerequisite
KC-DEC-EQ     Số thập phân bằng nhau (0,5 = 0,50)
KC-DEC-CMP    So sánh hai số thập phân                                  ← mục tiêu chính
KC-DEC-ORDER  Sắp xếp dãy số thập phân
KC-DEC-APPLY  Vận dụng so sánh trong bài toán thực tế (giá tiền, chiều cao, thời gian chạy)
```

**Misconception catalog (bản nháp, có bug rule):**

| Mã | Misconception | Bug rule / dấu hiệu | Phản ví dụ gây xung đột nhận thức |
|---|---|---|---|
| DEC-M01 | "Dài hơn thì lớn hơn" (so phần thập phân như số tự nhiên) | Chọn số có phần thập phân nhiều chữ số hơn: 0,25 > 0,3 | 0,25 m và 0,3 m: đoạn nào dài hơn trên thước? |
| DEC-M02 | "Ngắn hơn thì lớn hơn" (nghĩ phần trăm nhỏ hơn phần mười nên số nhiều chữ số luôn nhỏ hơn) | 0,4 > 0,45 | 0,45 = 0,4 + 0,05 |
| DEC-M03 | Bỏ qua chữ số 0 giữ chỗ | 0,05 = 0,5 | 5 xu và 50 xu (quy đổi tiền) |
| DEC-M04 | So phần nguyên sai hoặc bỏ qua phần nguyên | 2,1 < 1,9 | Trục số |
| DEC-M05 | Coi thêm 0 ở cuối làm số lớn hơn | 0,50 > 0,5 | Bảng giá trị theo hàng |
| CALC-SLIP | Nhầm lẫn khi đọc hoặc chép số | Chẩn đoán qua lời giải thích | — |

### 18.3. Item bank theo mức nhận thức (theo khung Toán §14–§18, chuyển sang lớp 5)

| Mức | Dạng | Ví dụ |
|---|---|---|
| A — Recall | Nhận biết hàng | "Trong số 3,47, chữ số 4 ở hàng nào?" |
| B — Procedural | So sánh trực tiếp | "Điền dấu >, <, =: 0,7 … 0,65" |
| C — Conceptual | Giải thích | "Vì sao 0,7 lớn hơn 0,65 dù 65 lớn hơn 7?" |
| D — Application | Toán có lời | "Lan chạy 60 m hết 9,8 giây, Hoa hết 9,75 giây. Ai chạy nhanh hơn?" |
| E — Transfer | Bối cảnh mới | "Bác Tư muốn mua gói kẹo nặng hơn: 0,5 kg hay 0,45 kg? Giá như nhau." |
| Error detection | Tìm lỗi | "Bạn An nói 0,25 > 0,3 vì 25 > 3. Bạn An đúng hay sai? Vì sao?" |
| Near transfer (biến thể) | Cấu trúc khác | "Tìm chữ số x để 0,x5 > 0,6" |

Mỗi item có metadata: `kc_ids`, `cognitive_level`, `difficulty ∈ [0,1]`, `transfer ∈ {none, near, far}`, `expected_time_s`, `answer_spec` (giá trị + dạng tương đương chấp nhận), `bug_rules`, `hint_templates`, `isomorphic_group`.

### 18.4. Math Session Flow: phân tích baseline của brief

Baseline: `START → GOAL → REVIEW → CONCEPT CHECK → GUIDED EXAMPLE → SOCRATIC PRACTICE → INDEPENDENT PRACTICE → ASSESSMENT → SUMMARY`

| Activity | Đánh giá | Mandatory? | Điều kiện |
|---|---|---|---|
| OPENING (Goal orientation) | Giữ, ≤ 90s. Nêu mục tiêu bằng lời trẻ hiểu + micro-choice (chọn nhân vật ví dụ) | ✅ | — |
| WARMUP_REVIEW | Giữ, là retrieval practice cho KC tiên quyết và **retention probe** của lesson trước | ⚪ | Bỏ qua nếu prerequisite mastery ≥ 0.75 & confidence ≥ 0.6; **không bỏ** nếu có ReviewSchedule đến hạn |
| CONCEPT_CHECK | **Chuyển lên trước dạy** (diagnostic, theo khung Toán §51 bước 1). 2–3 item mức A–C | ✅ | Kết quả quyết định có TEACH hay không |
| TEACH (Guided example) | Đổi thành **có điều kiện**: chỉ khi concept check cho thấy chưa nắm. Dạng worked example + câu hỏi tự giải thích | ⚪ | Vào khi concept check fail; quay lại khi loop-back |
| GUIDED_PRACTICE (Socratic) | Lõi của session | ✅ | ≥ 3 item resolved, ≥ 2 item đạt INDEPENDENT/SUPPORTED |
| INDEPENDENT_PRACTICE | Giữ, số lượng co giãn theo thời gian. Hint cap H5 | ⚪ | Bị cắt đầu tiên khi thiếu giờ |
| TRANSFER / CHALLENGE | **Bổ sung**: 1 item mức E khi học sinh làm tốt | ⚪ | Chỉ khi còn thời gian và practice tốt |
| EXIT_ASSESSMENT | Giữ. Phủ mức B, C, D + 1 error-detection. Hint cap H1 | ✅ | Được bảo vệ bằng assessment reserve |
| SUMMARY | Giữ. Học sinh tự nói lại 1 điều học được (self-explanation), tutor tóm tắt tích cực | ✅ | — |

**Khi nào quay lại concept (loop-back):**
- Cùng misconception xuất hiện ở ≥ 2 item sau khi đã đến H5 → quay về TEACH với **biểu diễn khác** (ví dụ từ bảng hàng sang trục số hoặc tiền).
- Concept check sai cả hai item → TEACH trước practice.

**Khi nào giảm độ khó:**
- 2 item liên tiếp outcome WORKED → item kế tiếp chọn difficulty thấp hơn 0.2 trong cùng KC.
- Nhưng **không hạ xuống dưới mức B** trong guided practice. Nếu vẫn kẹt, đánh dấu cho giáo viên (`needs_teacher_attention`).

**Khi nào tăng độ khó:** 2 item INDEPENDENT liên tiếp → item sau tăng difficulty hoặc mức nhận thức (B → C → D).

### 18.5. Math Tutor bám giáo viên như thế nào

- Lesson package là nguồn duy nhất cho định nghĩa, ký hiệu, ví dụ (cách giáo viên gọi "hàng phần mười", cách trình bày).
- Common mistakes do giáo viên nhập được **ánh xạ vào misconception catalog** (hoặc tạo mã mới cần duyệt).
- Teacher notes (ví dụ "lớp này hay nhầm đơn vị") đi vào L3 và có thể điều chỉnh `hintPolicy` (ví dụ ưu tiên target FORMAT).

---

## PART 19 — ENGLISH GRADE 5 TUTOR (viết lại 12/11/2026)

> Bản cũ của PART 19 (chuẩn kỹ năng lớp 5 theo khung English, skill taxonomy Reading/Speaking, Support Ladder S0–S5, flow Reading 10 bước, flow Speaking, rubric 0–4, mastery rule §10.1) **đã bị xóa** theo yêu cầu của chủ dự án. Hướng hiện hành: `docs/plan/plan-english-g5-unit11-family-time.md`; khung đánh giá: `docs/adr/ADR-060-english-assessment-framework.md`.

### 19.1. Phạm vi

- Một unit lớp 5: **Unit 11 "Family time"**, SGK Tiếng Anh 5 Global Success tập hai (chủ đề "Me and my family"). Gia sư **ôn bài ở nhà** sau khi con đã học trên lớp, không phải khóa học kỹ năng, không đo trình độ CEFR/IELTS.
- Nội dung (từ, mẫu câu, item, đáp án) lấy từ ấn phẩm công khai chủ dự án cung cấp (SGK/sách giáo viên Tiếng Anh 5, giáo án, bài tập kèm đáp án), qua cùng đường ingest với Toán. Không bịa item hay đáp án.

### 19.2. Cùng khuôn với Toán

| Khía cạnh | Toán | Tiếng Anh |
|---|---|---|
| Gói nội dung | `ChapterPackage` + `LessonPackage` | Như Toán, `subject: english`; một unit là một gói chương |
| Vòng dạy | 6 bước (ADR-059) | Giữ nguyên 6 bước |
| Nút kiến thức | Khái niệm/phương pháp của chương | Cụm hoạt động kỳ nghỉ (buy souvenirs, eat seafood…), "Did you …? – Yes, I did. / No, I didn't.", "What did your family do in …? – We …", hội thoại kể kỳ nghỉ (ADR-060 mục 3) |
| Item | Mức A–E + DIAG | Mức A–E + DIAG (ADR-060 mục 3.2) |
| Đúng/sai | `MathChecker` tất định | `EnglishChecker` tất định, so với đáp án chấp nhận (có biến thể "I'm"/"I am", DI-110) |
| Thang gợi ý | H0–H7 | H0–H7, nội dung theo DI-112 |
| Đánh giá | Projector node-mastery, 7 chiều | Cùng projector, `MasteryPolicy` tiếng Anh |
| Ngôn ngữ cô | Tiếng Việt | Tiếng Việt; từ và câu đích bằng tiếng Anh ("Con nói theo cô nhé: *We ate seafood.*"); từ đích luôn nằm trong một câu |
| Giọng nói | Một cách trả lời | Một cách trả lời, không phải kỹ năng riêng; Whisper chọn `en`/`vi` theo bước, không tự nhận dạng; chưa chấm phát âm |

### 19.3. Khác Toán ở đâu

- Hiểu lầm điển hình là ngôn ngữ chứ không phải số học: trả lời "Yes, I do" cho câu hỏi "Did you…?", dùng động từ nguyên mẫu sau "We" khi kể việc đã qua, quên "did", nhầm nghĩa cụm từ (ADR-060 mục 5).
- Lời giải thích "vì sao" bằng tiếng Việt; câu trả lời đích bằng tiếng Anh.
- Dữ liệu giọng nói có độ tin cậy ASR (DI-109) và giáo viên nghe lại được audio.
