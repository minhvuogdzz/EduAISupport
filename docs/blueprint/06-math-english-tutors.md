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

## PART 19 — ENGLISH GRADE 5 TUTOR

### 19.1. Chuẩn lớp 5 (khung English §11, lấy từ CT GDPT 2018)

**[FACT — theo tài liệu khung]**
- Listening: hội thoại hoặc độc thoại ngắn khoảng **45–60 từ**.
- Reading: đoạn ngắn, đơn giản khoảng **60–80 từ**; thông điệp/chỉ dẫn ngắn.
- Writing: khoảng **30–40 từ** có gợi ý.
- Trọng tâm assessment: **main idea, detail, simple inference, retell with prompts, interview response**.
- Task gợi ý: short factual/story text, familiar dialogue; Speaking: mini interview, picture story, 2–3 sentence retell. Độ sâu: main idea → cause → inference một bước.
- Mục tiêu cuối tiểu học: Bậc 1 khung năng lực ngoại ngữ 6 bậc (CEFR A1).

### 19.2. Skill taxonomy dùng trong Student Model (theo khung English §3, lọc theo scope)

```text
reading.detail   reading.main_idea   reading.sequence   reading.cause_effect
reading.vocab_in_context   reading.inference   reading.evidence   reading.retell
reading.oral_fluency (tách riêng, KHÔNG gộp vào comprehension — khung §4.1)
speaking.semantic   speaking.vocab_grammar   speaking.pronunciation   speaking.fluency
speaking.coherence   speaking.interaction   support.dependency (theo S0–S5)
language.vocabulary   language.grammar_target (ví dụ "because", "past simple")
```

### 19.3. Socratic Mode cho English: khác Math ở đâu

| Khía cạnh | Math | English |
|---|---|---|
| "Đáp án" | Một giá trị đúng, kiểm tra tất định | Thường mở (main idea, retell); đúng về **nghĩa** chứ không về câu chữ |
| Chẩn đoán | Bước sai, bug rule | Hiểu sai nghĩa, thiếu từ vựng, không tìm được dẫn chứng, lỗi ngữ pháp target |
| Gợi ý | Hint ladder H0–H7 theo target | Support ladder S0–S5: repeat → rephrase/slow → hint (vùng thông tin) → choice → model |
| Self-correction | "Con kiểm tra lại bước 2" | Recast, mời nói lại; "Which part of the text helped you know that?" |
| Ngôn ngữ tutor | Tiếng Việt | Tiếng Anh đơn giản (A1), có thể **code-switch** sang tiếng Việt ở S2/S3 khi học sinh kẹt. Đây là quyết định sư phạm cần chốt **[OPEN]** |
| Kiểm tra hiểu | "Vì sao?" | "How do you know?" + chỉ ra câu trong bài |

**Reading không được bị Speaking làm nhiễu:** câu trả lời đúng về nghĩa nhưng phát âm kém vẫn là evidence *đúng* cho reading comprehension (khung English §4.1, §6).

### 19.4. English Reading flow (lớp 5, không copy Math flow)

| Bước | Mục đích | Construct | Evidence | Mandatory |
|---|---|---|---|---|
| 1. Warm-up | Kích hoạt chủ đề ("Do you like animals?") | — | — | ✅ (ngắn) |
| 2. Vocabulary activation | 3–5 từ then chốt, có hình | language.vocabulary | nhận biết từ | ⚪ (bỏ nếu mastery cao) |
| 3. Pre-reading | Dự đoán từ tiêu đề hoặc hình | — | — | ⚪ |
| 4. Reading | Đọc thầm đoạn 60–80 từ; có thể nghe đọc mẫu | — | thời gian đọc, số lần đọc lại | ✅ |
| 5. Literal / gist | Who/Where/What? + main idea | reading.detail, reading.main_idea | correctness + support | ✅ |
| 6. Connect | Sequence / cause (dùng "because") | reading.sequence, reading.cause_effect | answer + support | ✅ |
| 7. Inference (1 bước) | "How did X feel? Why?" | reading.inference | inference + reasoning | ✅ |
| 8. Evidence | "Which sentence helped you?" | reading.evidence | câu được chỉ ra (khớp span) | ⚪ (khuyến nghị) |
| 9. Retell with prompts | Kể lại 2–3 câu (nói hoặc viết) | reading.retell (+ speaking nếu nói) | key propositions | ✅ |
| 10. Exit check | 2–3 câu trên đoạn mới ngắn, S0/S1 | các subskill trên | independent evidence | ✅ |

Oral reading (đọc to 2–3 câu) là **tùy chọn** và chỉ tạo evidence cho `reading.oral_fluency`.

### 19.5. English Speaking flow (lớp 5)

| Bước | Hoạt động | Construct | Quy tắc sửa lỗi |
|---|---|---|---|
| 1. Warm-up | Chào, 1–2 câu hỏi quen thuộc | interaction | Không sửa |
| 2. Guided speaking | Mẫu câu target có khung ("I like … because …") | vocab_grammar (target) | Recast ngay nếu sai target structure |
| 3. Q&A (mini interview) | 3–5 câu hỏi về chủ đề lesson | semantic, interaction | Hỏi làm rõ nếu không hiểu nghĩa; không ngắt vì lỗi nhỏ |
| 4. Picture story / role play | Kể theo tranh 3 khung hoặc đóng vai tình huống | coherence, fluency, interaction | Để học sinh nói hết lượt |
| 5. Independent speaking | 2–3 câu tự do theo chủ đề | fluency, semantic | Không ngắt |
| 6. Feedback | Chọn 1–2 điểm ưu tiên (meaning-blocking hoặc target) + 1 điểm khen cụ thể | — | Delayed feedback |
| 7. Retry | Nói lại phần được góp ý | target skill | Ghi evidence *sau hỗ trợ* |
| 8. Assessment | 1 prompt mới, S0 (không gợi ý), đánh giá theo rubric 0–4 | tất cả | Không sửa trong lúc nói |

**Interrupt policy:** không bao giờ ngắt khi học sinh đang nói, trừ khi (a) vượt thời lượng lượt tối đa (ví dụ 45s), hoặc (b) lạc đề hoàn toàn quá 15s. Khi đó tutor chen nhẹ bằng một câu hỏi kéo về chủ đề.

**Đánh giá speaking:** mỗi lượt có 3 lớp dữ liệu (audio, transcript, pedagogical). Chấm theo các chiều riêng của khung English §6: semantic adequacy; vocabulary và grammar; pronunciation/intelligibility (từ audio, không từ transcript); fluency; coherence; interaction; support required. Kết quả mỗi chiều là rubric 0–4 + `data_quality`. LLM chấm theo rubric cố định có anchor examples; pronunciation dùng dịch vụ chuyên dụng. **Bắt buộc chấm song song với giáo viên** trước khi dùng cho báo cáo (khung English "Ghi chú triển khai").

### 19.6. Mastery rule English (khung English §10.1)

Skill chỉ đạt "independent mastery" khi có **≥ 2 bằng chứng hợp lệ ở nhiệm vụ hoặc thời điểm khác nhau**, trong đó **≥ 1 lần ở S0/S1** ở độ khó mục tiêu. `reading.inference`, `reading.evidence` và `speaking.interaction` cần thêm một delayed/transfer probe. Đây là luật vận hành cần hiệu chỉnh bằng dữ liệu thực tế, không phải chuẩn chính thức.
