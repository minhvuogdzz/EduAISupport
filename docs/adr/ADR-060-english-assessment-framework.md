# ADR-060: Khung đánh giá mức độ hiểu bài môn Tiếng Anh, Unit 11 "Family time" lớp 5 (ENG-1)

Ngày: 12/11/2026 · Quyết định D-T13 (blueprint 00) · DI-106 đến DI-116 · Trạng thái: **chủ dự án duyệt mặc định ngày 12/11/2026** (nội dung soạn trong quá trình làm được chấp nhận mặc định; chủ dự án có thể sửa bất kỳ lúc nào, mọi sửa đổi đi qua ADR mới hoặc mục Revision của file này).

- Kế hoạch đi kèm (hướng đi, mốc): `docs/plan/plan-english-g5-unit11-family-time.md`. Luật bắt buộc khi cài đặt (cô lập môn, không đổi Toán, kiểm thử mỗi PR): `docs/plan/english-module-rules.md`.
- Thay thế: khung English cũ trong blueprint (09 mục 26.2; 06 PART 19; Support Ladder S0–S5, rubric 0–4, DI-9, DI-10). Chủ dự án yêu cầu xóa khung đó ngày 12/11/2026.
- Dựa trên: khung Toán (blueprint 09 PART 25, 26.1, 26.3–26.6, PART 27), `services/api/cavat/modules/assessment/projector.py` (`node-mastery/0.3.0`), ADR-018 (đồ thị tri thức), ADR-059 (vòng dạy 6 bước), ADR-024/025 (nội dung từ tài liệu giáo viên).

---

## 1. Bối cảnh

**[FACT]** Chủ dự án chốt ngày 12/11/2026: Tiếng Anh là môn thứ ba có gia sư thật, chỉ **một unit**. Unit được chốt là **Unit 11 "Family time"**, SGK Tiếng Anh 5 Global Success tập hai (chủ đề "Me and my family"); bộ sách này không có unit "My family" như bản đầu của ADR ghi. Đây là gia sư **ôn bài ở nhà** sau khi con đã học trên lớp, không phải khóa học kỹ năng. Cô giảng bằng tiếng Việt; từ và mẫu câu đích nói bằng tiếng Anh, luôn nằm trong một câu ("Con nói theo cô nhé: We ate seafood.").

**Nguồn:** SGK, sách giáo viên và tài liệu tập huấn trên trang tập huấn của NXB Giáo dục (https://taphuan.nxbgd.vn/tap-huan/chi-tiet-sach/tieng-anh-5-global-success-tap-hai-939704277.939704277). Phiên ENG-3 trích nội dung vào `docs/pedagogy/english-g5/`.

**[FACT]** Khung English cũ (subskill Reading/Speaking, rubric 0–4, Support Ladder S0–S5) mô tả năng lực kỹ năng kiểu CEFR/IELTS. Nó không khớp mục tiêu "ôn đúng bài đã học", không dùng chung được projector của Toán và không có đáp án tất định. Chủ dự án yêu cầu bỏ hẳn.

**Quyết định gốc:** dùng lại **khung Toán, ánh xạ lại** cho nội dung một unit tiếng Anh: nút kiến thức (node) của unit, item mức A–E và DIAG, bảy chiều C R A T I S D, cùng một projector node-mastery. **Nói chỉ là một cách trả lời** (modality), không phải kỹ năng riêng được chấm 0–4. Đúng/sai do **bộ chấm tất định** so với danh sách đáp án chấp nhận lấy từ tài liệu của chủ dự án.

Từ khung cũ chỉ giữ hai ý, viết lại thành DI mới: (1) câu nói có độ tin cậy ASR thấp thì giảm trọng số và chỉ được làm tăng, không được làm giảm mastery (DI-109); (2) đúng sau khi cô đọc mẫu không bằng đúng độc lập (DI-108).

## 2. Nguyên tắc "đầu ra trước"

Khung này viết ngược từ cái giáo viên và phụ huynh nhìn thấy. Mỗi con số, nhãn hay lời nhận xét trên trang phải truy ngược được tới: **chỗ hiển thị → trường API → hàm tính → chiều/công thức → evidence → sự kiện trong event log**. Mục 9 là bảng truy ngược đầy đủ. Chỗ nào không truy ngược được thì không được hiển thị.

Hệ quả:
- Không có "điểm Tiếng Anh" tổng kiểu `English = 8,2`. Giáo viên thấy M theo từng nút (như Toán); phụ huynh chỉ thấy trạng thái định tính (DI-14, DI-113), không có một điểm số duy nhất.
- Mọi đúng/sai, mọi trọng số đều là code tất định; LLM chỉ được *đề xuất nhãn* (ví dụ chất lượng lời giải thích bằng tiếng Việt) qua validation layer 26.5.

## 3. Nút kiến thức và item (DI-106)

### 3.1. Đồ thị của unit

**[ASSUME, cần kiểm lại]** Nội dung dưới đây đọc từ Book map của SGK qua ảnh; danh sách cụm từ, mẫu câu và tên bài phải đối chiếu với SGK/sách giáo viên (ENG-3) trước khi dùng. Mã node là đề xuất.

- **Mẫu câu (thì quá khứ đơn):** "Did you …? – Yes, I did. / No, I didn't." và "What did your family do in …? – We …".
- **Từ vựng (cụm hoạt động):** buy souvenirs, collect seashells, eat seafood, see some interesting places, take a boat trip around the bay, walk on the beach. Dạng quá khứ cần dùng trong câu trả lời: bought, collected, ate, saw, took, walked (bốn động từ bất quy tắc, hai có quy tắc).

| Node | Tầng (2T-KT) | Nội dung (điền theo SGK) | Tiên quyết / quan hệ |
|---|---|---|---|
| `ENG5-U11-VOCAB` | BASIC | Sáu cụm hoạt động trong kỳ nghỉ và dạng quá khứ của động từ | Điểm bắt đầu |
| `ENG5-U11-DIDYOU` | BASIC | Hỏi và trả lời "Did you …? – Yes, I did. / No, I didn't."; sau "Did" động từ giữ nguyên mẫu | PREREQUISITE từ VOCAB |
| `ENG5-U11-WHATDID` | BASIC | "What did your family do in …? – We …" với động từ quá khứ | PREREQUISITE từ VOCAB |
| `ENG5-U11-TALK` | IMPLEMENT | Hội thoại kể kỳ nghỉ cùng gia đình: 2–3 lượt hỏi đáp dùng hai mẫu trên | APPLICATION từ DIDYOU và WHATDID |

Nếu SGK có thêm mẫu ở phần Lesson 3 hay Project, thêm node BASIC tương ứng và nối APPLICATION vào `ENG5-U11-TALK`. Thêm node chỉ bằng dữ liệu (`chapter.yaml`), không sửa code.

### 3.2. Item mức A–E và chiều mà đáp án làm evidence

Dùng nguyên `answer_dimension()` của projector: A, B → C; C → R; D → A; E hoặc item `transfer ≠ none` → T; DIAG → D.

| Mức | Dạng item (tiếng Anh, lớp 5) | Ví dụ (minh họa, item thật lấy từ tài liệu) | Chiều |
|---|---|---|---|
| A — Nhận biết | Chọn nghĩa/tranh của cụm từ; nghe cô đọc rồi chọn tranh | "'collect seashells' là gì? A. nhặt vỏ sò B. ăn hải sản C. mua quà lưu niệm" | C |
| B — Theo mẫu | Nói/viết câu theo mẫu với từ cho sẵn hoặc theo tranh | (tranh mua quà, có dấu tích) "Bạn hỏi 'Did you buy souvenirs?'. Con trả lời theo tranh nhé." | C |
| C — Hiểu vì sao | Phân biệt có lý do, trả lời "vì sao" bằng tiếng Việt | "Bạn hỏi bằng 'Did you…?', vì sao con trả lời 'Yes, I did' mà không phải 'Yes, I do'?" | R |
| D — Vận dụng | Dùng mẫu trong tình huống của bài (tranh kỳ nghỉ, câu hỏi của bạn) | "Bạn hỏi: 'What did your family do in …?' (tranh đi thuyền quanh vịnh). Con trả lời thế nào?" | A |
| E — Bối cảnh mới | Kể kỳ nghỉ trong tranh chưa gặp, ghép hai mẫu trong một lượt | "Đây là kỳ nghỉ của gia đình bạn Mai. Con kể hai việc gia đình bạn đã làm." | T |
| DIAG — Tìm lỗi | Phát hiện và sửa câu sai | "Bạn Nam viết: 'Last summer, we eat seafood.' Đúng chưa? Sửa giúp bạn." | D |

**DI-106 (ánh xạ và "dạng câu hỏi"):**
1. Mỗi node phải có item ở ít nhất hai mức trong A–D và một item C (để có evidence R, xem DI-111); node IMPLEMENT phải có item D.
2. **"Dạng câu hỏi" của gate UNDERSTOOD (§52) là kiểu đáp án** (`choice`, `boolean`, `phrase`, `order` (xếp từ thành câu), `open`), **không phải modality**. Gõ rồi nói lại cùng một câu không thành hai dạng. Lý do: nói chỉ là một cách trả lời (quyết định gốc), nên modality không được làm phồng bằng chứng.
3. Item nói theo mẫu ("con nói theo cô") là item *cùng làm* (`completion` của node), không phải item luyện tập (xem DI-108).

## 4. Bảy chiều C R A T I S D

| Chiều | Nghĩa trong unit tiếng Anh | Evidence | Trọng số §20 [FACT] |
|---|---|---|---|
| C — Correctness | Nhận biết và dùng đúng từ, đúng mẫu câu | Item A, B | 0,20 |
| R — Reasoning | Hiểu vì sao: hỏi bằng "Did" thì trả lời bằng "did/didn't"; kể việc đã qua thì dùng động từ quá khứ; sau "did" động từ giữ nguyên mẫu; phân biệt cụm từ dễ nhầm | Item C, "vì sao" sau câu đúng (`EXPLANATION_SUBMITTED`), "con nói lại" (`RETELL_JUDGED`); R = 0 khi lỗi CONCEPTUAL không được sửa, đoán mò, hoặc không giải thích được | 0,20 |
| A — Application | Dùng mẫu trong tình huống của bài | Item D | 0,15 |
| T — Transfer | Dùng ở bối cảnh mới, ghép mẫu | Item E, item `transfer` near/far | 0,15 |
| I — Independence | Tự làm, không cần gợi ý | Bậc gợi ý cao nhất trước lần đúng đầu tiên, bảng §11 + DI-2, thang gợi ý tiếng Anh DI-112 | 0,10 |
| S — Stability | Còn nhớ sau vài ngày | **Chỉ** delayed probe (T1/T3/T7/T30) | 0,10 |
| D — Diagnostic | Phát hiện và sửa câu sai | Item DIAG | 0,10 |

**Chiều để trống và vì sao (DI-1):**
- **S để trống** ở phiên bản đầu, giống Toán: chưa có lịch delayed probe (Mốc 2 của kế hoạch v1). Theo DI-1, S có `effective_evidence < 1` nên bị loại khỏi M và trọng số còn lại được chuẩn hóa lại. Thiếu S làm confidence thấp hơn và chặn `MASTERED_STABLE` (chỉ tới `PROVISIONALLY_MASTERED`).
- **T có thể trống** nếu tài liệu không có item bối cảnh mới cho một node. Không bịa item E để lấp chiều này (plan quy tắc R-CONTENT). Gate APPLIED theo DI-6 dựa vào evidence ứng dụng A **hoặc** T (`APPLICATION_DIMENSIONS`), nên T trống không chặn qua bài.
- **D có thể trống** ở node từ vựng nếu tài liệu không có bài tìm lỗi.
- **Không có chiều phát âm, độ trôi chảy hay "speaking".** Phát âm không cản nghĩa không bị phạt (DI-107); chấm phát âm theo âm vị nằm ngoài phạm vi (plan mục 6).

**Công thức composite:** giữ nguyên §20 + DI-1:
`M = Σ_{d∈avail} w_d·μ_d / Σ_{d∈avail} w_d`, mỗi chiều là Beta(α, β) với prior DI-12/DI-16.

## 5. Phân loại lỗi và mức phạt (DI-107)

Bảng tương ứng §34 + DI-3 của Toán. Cột "Lớp chung" là `ErrorClass` mà projector đọc; cột "Mã tiếng Anh" là nhãn chi tiết ghi kèm để giáo viên đọc và để đếm hiểu lầm.

| Mã tiếng Anh | Ví dụ | Lớp chung | Ảnh hưởng C/A/T (điểm s) | Ảnh hưởng R | Hiểu lầm ghi nhận |
|---|---|---|---|---|---|
| `EN_SHORT_ANSWER` trả lời ngắn không khớp trợ động từ của câu hỏi | "Did you walk on the beach?" – "Yes, I do." | CONCEPTUAL | s = 0 | s = 0 | `ENG5-U11-M01`, **CRITICAL** ở node DIDYOU |
| `EN_TENSE` dùng động từ nguyên mẫu khi kể việc đã qua | "What did your family do …?" – "We eat seafood." | CONCEPTUAL | s = 0 | s = 0 | `ENG5-U11-M02`, **CRITICAL** ở node WHATDID |
| `EN_MEANING` nhầm nghĩa cụm từ | "collect seashells" cho tranh ăn hải sản; nhầm "seashells"/"seafood" | CONCEPTUAL | s = 0 | s = 0 | `ENG5-U11-M03` (theo cặp), NORMAL |
| `EN_STRUCTURE` sai mẫu đích của node | quên "did" ("What your family do …?", "You buy souvenirs?"), chia quá khứ sau "did" ("Did you bought …?"), sai trật tự | PROCEDURAL ở node mà mẫu đó là mục tiêu; FORMAT ở node khác | s = 0 (node mục tiêu) / s = 0,7 (node khác) | s = 0,5 nếu giải thích một phần đúng | `ENG5-U11-M04` khi lặp ≥ 2 lần |
| `EN_VERB_FORM` biết phải dùng quá khứ nhưng chia sai động từ bất quy tắc | "We buyed souvenirs", "We eated seafood" | PROCEDURAL ở node WHATDID; FORMAT ở node khác | s = 0 / s = 0,7 | không trừ | `ENG5-U11-M05` khi lặp ≥ 2 lần |
| `EN_SLIP` lỗi nhỏ, nghĩa và mẫu đúng | gõ "mothr", "grandmoter" (sai 1 ký tự, từ ≥ 5 chữ cái) | FORMAT | s = 0,7 | không trừ | — |
| `EN_PRONUNCIATION` phát âm chưa chuẩn, không cản nghĩa | Whisper ghi "seafood" từ giọng "xi-phút" | không phải lỗi | s = 1 (chấm theo bản chép lời đã xác nhận) | không trừ | — |
| `EN_L1` trả lời đúng nghĩa bằng tiếng Việt ở item yêu cầu nói tiếng Anh | "nhà con ăn hải sản" thay cho "We ate seafood." | L1 (lớp mới) | lần đầu không chấm, cô mời nói bằng tiếng Anh; nếu item đóng mà vẫn tiếng Việt: s = 0,3 | không trừ | — |
| `GUESS` | đúng nhưng không nói được vì sao khi được hỏi | (như Toán) | s = 1, w × 0,5 | s = 0 | — |
| `REASONING` | câu đúng, lý do sai ("trả lời 'did' vì 'did' nghĩa là có") | REASONING | s = 1 | s = 0 | — |

Quy tắc kèm theo:
- Viết hoa, dấu câu, khoảng trắng thừa, dạng rút gọn ("didn't"/"did not", "I'm"/"I am", "it's"/"it is") **không phải lỗi**: bộ chấm chuẩn hóa trước khi so (DI-110).
- Ở item mức A (chọn nghĩa), trả lời bằng tiếng Việt là đúng thể thức, không phải `EN_L1`.
- Một câu có nhiều lỗi lấy lỗi nặng nhất theo thứ tự: CONCEPTUAL > PROCEDURAL > L1 > FORMAT.
- `ErrorClass` có thêm thành viên `L1` (điểm 0,3 trong `MasteryPolicy` của tiếng Anh); Toán không dùng nó nên phép chiếu Toán không đổi.

**Phản ví dụ cho hiểu lầm** (dùng ở `COGNITIVE_CONFLICT`, như bảng misconception của Toán): M01 "Bạn hỏi 'Did you…?' tức là hỏi chuyện đã qua; con trả lời 'Yes, I do' thì bạn nghe như con đang nói chuyện bây giờ, đúng không?"; M02 "Hôm qua nhà con ăn hải sản, hay ngày nào nhà con cũng ăn? Câu 'We eat seafood' nghe như ngày nào cũng thế"; M03 dùng hai tranh vỏ sò và đĩa hải sản cạnh nhau; M04 "Câu hỏi về chuyện đã qua cần từ nào đứng đầu con nhỉ?". Lời thật lấy từ tài liệu hoặc do chủ dự án duyệt.

## 6. Trọng số, gate, pass rule, mastery, confidence

| Thành phần | Toán | Tiếng Anh | Ghi chú |
|---|---|---|---|
| Trọng số độ khó | DI-4: đúng `0,5 + d`, sai `1,5 − d` | giữ nguyên | |
| Trọng số hỗ trợ | DI-5: `w × max(independence, 0,3)` | giữ nguyên, independence theo DI-112 | |
| Item cùng làm | `completion_factor` 0,5, không tính thành công | giữ nguyên; item "nói theo cô" thuộc nhóm này (DI-108) | |
| Nhãn LLM | 26.5: confidence < 0,6 → w × 0,3 | giữ nguyên (lời giải thích tiếng Việt) | |
| Dữ liệu giọng nói | (Toán chưa dùng `asr_confidence`) | DI-109 | mới |
| Gate UNDERSTOOD | §52: ≥ 3 thành công, ≥ 2 mức, ≥ 2 dạng | giữ nguyên số; "dạng" theo DI-106; thành công loại trừ thêm theo DI-111 | |
| Pass rule | DI-15: M ≥ 75, UNDERSTOOD, R ≥ 0,6, có ứng dụng, không hiểu lầm CRITICAL đang mở | giữ nguyên, R của node từ vựng theo DI-111 | |
| Gate theo chiều | DI-6 | giữ nguyên | |
| Mastery tạm thời | §53 + DI-59: M ≥ 85, confidence ≥ 75, μ_A ≥ 0,8, không CRITICAL → `PROVISIONALLY_MASTERED` | giữ nguyên | S trống nên chưa có `MASTERED_STABLE` |
| Confidence | DI-11 | **giữ nguyên DI-11**, không chỉnh | evidence giọng nói trọng số thấp tự làm `N_eff` nhỏ hơn |
| Mức và dải | §4–§8, vùng màu §25 | giữ nguyên | |

**[REC] `MasteryPolicy` riêng cho tiếng Anh**, version `node-mastery-en/0.1.0`, khác `node-mastery/0.3.0` của Toán. Cùng code projector, khác tham số (lớp `L1`, DI-108, DI-109). Phép chiếu Toán giữ byte-for-byte (quy tắc 3, quy tắc 7).

**DI-111 (gate và pass rule cho node tiếng Anh):**
1. Một lần đúng **không** tính là thành công cho §52 nếu: là item cùng làm (nói theo cô), đúng sau bậc H4 trở lên (`success_max_hint = 3` như Toán), hoặc evidence có ASR thấp (DI-109).
2. Node từ vựng vẫn `require_explanation = true`. Evidence R của nó đến từ item C phân biệt cặp dễ nhầm có lý do ("vì sao *seashells* là vỏ sò mà *seafood* là hải sản?") và từ "con nói lại" bằng tiếng Việt. Lý do: nếu bỏ R, DI-6 sẽ chặn node ở mức 2 và node không bao giờ đạt CONCEPTUAL.
3. Lời giải thích "vì sao" được nói/gõ **bằng tiếng Việt**; không đòi giải thích bằng tiếng Anh ở lớp 5.

## 7. Dữ liệu giọng nói và đúng sau mẫu

**[FACT] hiện trạng code (12/11/2026):** `POST /v1/voice/transcribe` gọi Whisper với `language="vi"` cố định; bản ghi âm lưu ở `var/storage/voice/in/<ngày>/<băm học sinh>/<uuid>.<đuôi>` nhưng sự kiện `STUDENT_MESSAGE` không giữ tham chiếu tới tệp đó; `ItemResolved` đã có `modality` và `asr_confidence` nhưng không nơi nào điền `asr_confidence`, và projector không đọc hai trường này. Adapter Groq đọc `avg_logprob` và `no_speech_prob` của từng segment chỉ để bỏ đoạn im lặng.

**DI-109 (độ tin cậy ASR, thay DI-10 cũ):**
1. Mỗi lượt nói có `asr_confidence = q ∈ [0, 1]`, tính tất định từ các segment Whisper: `q = exp(trung bình avg_logprob có trọng số độ dài segment)`, đặt `q = 0` nếu mọi segment có `no_speech_prob > 0,6`. Công thức là **[ASSUME]**, phải hiệu chỉnh bằng tập vàng (mục 10).
2. `q ≥ 0,6`: evidence bình thường.
3. `q < 0,6` và câu trả lời **đúng**: evidence được ghi với `w × 0,3`, không tính là thành công cho §52 (DI-111).
4. `q < 0,6` và câu trả lời **sai hoặc không chấm được**: **không ghi evidence nào** (không có điểm 0), chỉ ghi lý do `ASR_UNCERTAIN`. Cô mời con nói lại hoặc gõ (không tăng bậc gợi ý, như `CLARIFY_REQUEST`).
5. Câu trả lời bằng giọng nói chỉ thành evidence sau khi qua bước xác nhận hiện có của Toán (blueprint 04, 20.2) khi bản chép lời có từ khác nghĩa với đáp án gần nhất (ví dụ nghe "seafood" trong khi đáp án là "seashells").
6. Ngưỡng 0,6 lấy theo ý của khung cũ; chưa có số đo cho giọng trẻ em Việt nói tiếng Anh, nên đây là DI chờ hiệu chỉnh.
7. **[FACT] từ POC giọng nói (PR #139, `docs/poc/english-voice-decision.md`):** khi gọi Whisper với `en`, Whisper có thể *dịch* câu tiếng Việt sang từ đích ("anh trai" thành "brother"), nên một câu trả lời tiếng Việt có thể bị ghi thành câu đích đúng mà q vẫn cao. Bộ chấm chấm tất định trên các từ đích, và cho tới khi tỉ lệ nhận nhầm (false accept) được đo trên audio trẻ thật (ENG-9), evidence giọng nói của item câu đích tính như q thấp (mục 3 ở trên: đúng thì w × 0,3, không tính thành công). Bản chép lời của Whisper không phải điểm phát âm.

Hệ quả cần nói rõ trên trang giáo viên: luật "chỉ tăng không giảm" làm M có thiên lệch đi lên với em nói không rõ. Bù lại: trọng số 0,3, không tính thành công, và cảnh báo `ASR_LOW` ở mục "cần chú ý" (DI-114).

**DI-108 (đúng sau mẫu không bằng đúng độc lập):**
1. "Mẫu" là khi cô nói nguyên câu đích (hoặc nguyên đáp án) trước câu trả lời của con trong cùng item.
2. Item "nói theo cô" (con nhắc lại câu cô vừa đọc) nằm trong `completion` của node: projector cho `w × 0,5`, độc lập tối đa theo H6 (0,20, nâng sàn lên 0,3 theo DI-5) và không bao giờ là thành công.
3. Trong một item thường, gợi ý đọc nguyên câu mẫu là H7 (`FULL_EXPLANATION`); con đúng sau đó thì kết quả là `WORKED`.
4. Con nói lại đúng câu **mà không có mẫu trong cùng item** (ví dụ ở item sau, hay sau ít nhất một lượt khác) là đúng độc lập bình thường.

**DI-112 (thang gợi ý tiếng Anh trên H0–H7, thay Support Ladder S0–S5 và DI-9 cũ):** dùng chung `HintLevel` và bảng độc lập §11 + DI-2 của Toán; chỉ đổi nội dung từng bậc:

| Bậc | Nội dung gợi ý trong unit tiếng Anh | Độc lập |
|---|---|---|
| H0 | Không gợi ý | 1,00 |
| H1 | Câu hỏi định hướng ("Câu hỏi bắt đầu bằng 'Did' thì mình trả lời bằng từ nào con nhỉ?") | 0,85 |
| H2 | Nhắc khái niệm ("Hỏi bằng *Did* thì trả lời *Yes, I did* hoặc *No, I didn't*") | 0,70 |
| H3 | Gợi ý chiến lược ("Con nhớ mẫu 'We …' và đổi động từ sang chuyện đã qua nhé") | 0,60 |
| H4 | Cho một phần ("We b… souvenirs.") | 0,50 |
| H5 | Cho lựa chọn ("*buy* hay *bought*?") | 0,35 |
| H6 | Cùng làm (cô nói nửa câu, con nói tiếp) | 0,20 |
| H7 | Cô đọc nguyên câu mẫu, con nói lại | 0,00 |

Cô nhắc lại câu hỏi hoặc nói chậm lại (con xin "cô nói lại") **không phải gợi ý**, giữ nguyên bậc, như `CLARIFY_REQUEST` của Toán.

## 8. Nhận định: mức hiểu, hành động, điểm mạnh/yếu, khuyến nghị, lời cho học sinh và phụ huynh

**Mức hiểu và dải:** giữ 6 mức §4–§8 và vùng màu §25. Tên mức ở trang giáo viên đọc theo nội dung tiếng Anh:

| Mức | Dải M | Nghĩa trong unit tiếng Anh |
|---|---|---|
| 0 NOT_LEARNED | 0–19 | Chưa nhận ra từ/mẫu |
| 1 RECOGNITION | 20–39 | Nhận ra cụm từ khi thấy tranh hay nghe cô đọc |
| 2 PROCEDURAL | 40–59 | Nói/viết được theo mẫu khi có gợi ý |
| 3 CONCEPTUAL | 60–74 | Tự dùng đúng mẫu và nói được vì sao (trả lời bằng did, động từ quá khứ) |
| 4 APPLIED | 75–89 | Dùng được trong tình huống của bài |
| 5 PROVISIONALLY_MASTERED | M ≥ 85 kèm §53 | Vững trong buổi ôn; chờ kiểm tra lại sau vài ngày |

**Hành động gia sư theo dải** (dùng lại DI-8 và `PracticeSupport`, không thêm DI):

| Dải M | `PracticeSupport` | Trong unit tiếng Anh |
|---|---|---|
| < 40 | EXPLAIN_FIRST | Cô giảng lại cụm từ/mẫu bằng tiếng Việt kèm tranh, rồi "con nói theo cô" (item cùng làm) |
| 40–59 | GUIDED | Hỏi gợi mở, gợi ý sớm theo DI-112, item A/B |
| 60–74 | ASK_WHY | Con tự nói câu, kèm "vì sao lại là *bought*?" |
| 75–89 | TRANSFER | Tình huống của bài, item D/E |
| ≥ 90 | CHALLENGE | Hội thoại 2–3 lượt, item tìm lỗi |

**Điểm mạnh, điểm yếu, rủi ro** (giữ DI-23, DI-20, DI-27): điểm mạnh là chiều ở vùng xanh (≥ 75), điểm yếu là chiều < 60, hiển thị bằng tên chiều theo nghĩa tiếng Anh (bảng mục 4). Rủi ro theo DI-20 (hiểu lầm lặp ≥ 2 lần, điểm yếu, không học 7 ngày, cờ an toàn), cộng `ASR_LOW` (DI-114).

**Khuyến nghị** (§50, `recommendation` của `teacher_view.py`): giữ ánh xạ DI-8 theo dải; với hiểu lầm `ENG5-U11-M01` hoặc `M02` đang mở, khuyến nghị đầu tiên luôn là "Ôn lại cách trả lời câu hỏi *Did you…?*" hoặc "Ôn lại động từ quá khứ khi kể chuyện đã qua" (mã DIAGNOSE).

**DI-113 (trạng thái định tính cho học sinh và phụ huynh, viết lại cột English của DI-14):** vì tiếng Anh dùng cùng projector, ánh xạ là **một bảng chung cho cả hai môn**, đọc từ `NodeState`:

| Nhãn | Điều kiện (giống Toán, `progress.quality`) |
|---|---|
| Chưa học | chưa có M |
| Chưa đủ dữ liệu | confidence < 30 và chưa qua node (DI-7) |
| Đang làm quen | mức 0–1 |
| Làm được khi có hỗ trợ | mức 2 |
| Tự làm được | mức 3–4 |
| Vững và vận dụng | mức 5 |
| Cần ôn lại | `AT_RISK`/`FORGOTTEN` (khi có delayed probe) |

Lời cho phụ huynh: tên bài bằng tiếng Việt kèm mẫu câu tiếng Anh ("Kể việc gia đình đã làm trong kỳ nghỉ: *We …*"), "Con làm tốt / Con cần luyện thêm / Cách giúp con ở nhà". Không có điểm số tổng, không nói "trình độ A1", không tuyên bố chuẩn Bộ. Lời cho học sinh: "Con đã nói được / Mình ôn thêm nhé / Mục tiêu tiếp theo", không có số.

**Teacher override:** giữ 26.6. Thêm một trường hợp riêng của tiếng Anh: giáo viên nghe lại audio và sửa kết quả một lượt nói (ví dụ ASR nghe nhầm). Override là prior mới tại thời điểm đó, có lý do, có audit, và nhãn "đã được giáo viên điều chỉnh"; lượt đó được đưa vào tập vàng.

## 9. Bảng truy ngược chỗ hiển thị → nguồn dữ liệu

Cột "Thêm cho tiếng Anh" là việc của Mốc ENG-7 (plan mục 8); các dòng khác dùng lại nguyên code Toán khi trang nhận `?chapter=<unit tiếng Anh>`.

### 9.1. Trang học sinh của giáo viên (`StudentReportPage.tsx`, `GET /v1/teachers/students/{id}`, `TeacherStudentView`)

| Chỗ hiển thị | Trường API | Hàm tính | Chiều / công thức | Evidence / sự kiện | Thêm cho tiếng Anh |
|---|---|---|---|---|---|
| Mức hiểu tổng + độ phủ | `overall` | `teacher_view.overall` | trung bình M các node có điểm, độ phủ (DI-21) | `NodeState.mastery` ← §20 + DI-1 | — |
| Radar theo chiều | `dimensions` | `teacher_view.dimensions` | trung bình μ_d có trọng số các node mà chiều có trong M (DI-22) | `DimensionState` | nhãn trục theo nghĩa mục 4; S hiện "chưa có dữ liệu" |
| Điểm mạnh / điểm yếu | `strengths`, `weaknesses` | `student_detail` | chiều ≥ 75 / < 60 (DI-23) | như trên | tên chiều theo nghĩa tiếng Anh |
| Rủi ro / cần chú ý | `attention` | `teacher_view.attention` | DI-20 | `ItemResolved.misconception_ids`, cờ an toàn, ngày học | thêm `ASR_LOW` (DI-114) |
| Cây tri thức | `nodes`, `relations` | `_nodes_info`, `group` | nhóm PASSED/UNSTABLE/WEAK/INSUFFICIENT/NOT_STARTED (DI-27), pass rule DI-15 | `NodeState.passed_at`, `pass_now` | — |
| Chi tiết node | `nodes[].dimensions`, `misconceptions`, `trend`, `recommendation` | `student_detail` | DI-24 (xu hướng), DI-8 (khuyến nghị) | evidence của node | tên hiểu lầm tiếng Anh (`ENG5-U11-M0x`) |
| Dòng thời gian, vận tốc | `timeline`, `velocity` | `_timeline`, `_velocity` | DI-26, DI-25 | M tổng cuối ngày | — |
| Hoạt động theo ngày | `activity` | `_activity` | đếm `ItemResolved.resolution` | `ITEM_RESOLVED` | nhãn DI-114: tự làm / nhờ gợi ý / sau khi cô đọc mẫu / chưa xong; thêm số lượt nói và số lượt ASR thấp |
| Đường cong mastery | `curve` | `_curve` | `ChapterProjection.trace` | mọi evidence | — |
| Hành trình | `journey` | `_journey` | thứ tự item, resolution, gợi ý | `ITEM_RESOLVED` | modality của từng item |
| Hội thoại | `conversation` + `TranscriptView` | `_conversation`, transcript buổi | đếm tín hiệu | `STUDENT_MESSAGE`, `TUTOR_TURN` | **bản chép lời + nút nghe lại audio + độ tin cậy ASR + ngôn ngữ Whisper nhận** cho mỗi lượt nói |
| Các buổi | `session_list` | `progress.sessions_list` | — | session | — |

### 9.2. Trang lớp (`ClassPage.tsx`, `GET /v1/teachers/class`, `ClassOverviewView`)

| Chỗ hiển thị | Trường API | Hàm tính | Công thức | Thêm cho tiếng Anh |
|---|---|---|---|---|
| Heatmap học sinh × node | `students[].cells` | `_cell` | M, confidence (DI-7), mức, pass | — |
| Hiểu lầm nổi bật | `misconceptions` | `class_misconceptions` | tỉ lệ trên tổng số lần phát hiện (§28) | mã `ENG5-U11-M0x` |
| Học sinh cần chú ý | `students[].attention` | `attention` | DI-20 | `ASR_LOW` |
| Theo node | `by_node` | `class_overview` | trung bình M (§45) | — |
| KPI | `kpis` | `class_overview` | đếm | thêm "% câu trả lời bằng giọng nói" (chỉ mô tả, không chấm) |

### 9.3. Trang phụ huynh (`ParentPages.tsx`, `GET /v1/parents/me/child`, `ParentChildView`)

| Chỗ hiển thị | Trường API | Hàm tính | Công thức | Thêm cho tiếng Anh |
|---|---|---|---|---|
| Tình hình của con | `sessions`, `streak`, `this_week` | `progress.overview` | đếm buổi, ngày học | — |
| Con làm tốt | `going_well` | `progress.overview` | trạng thái INDEPENDENT/SOLID (DI-113) | tên bài kèm mẫu câu |
| Con cần luyện thêm | `to_practise` | `progress.overview` | hiểu lầm đang mở, mức thấp | lời theo hiểu lầm (ví dụ "con hay quên đổi động từ sang quá khứ") |
| Gợi ý ở nhà | `home_tips` | `progress.home_tips` | `Node.home_tip` (do chủ dự án duyệt) | gợi ý nói tiếng Anh ở nhà, có câu mẫu |
| Xu hướng 4 tuần | `trend` | `progress.trend` | số node bắt đầu/qua mỗi ngày | — |
| Các buổi | `session_list` | `progress.sessions_list` | — | — |

Phụ huynh **không** có bản chép lời, audio hay điểm M (PART 27.4).

**DI-114 (chỉ số hiển thị riêng của tiếng Anh):**
1. Bốn nhóm kết quả item cho giáo viên: "tự làm" = `INDEPENDENT`, "nhờ gợi ý" = `SUPPORTED` (H1–H5), "sau khi cô đọc mẫu" = `WORKED` (H6–H7, gồm item nói theo cô), "chưa xong" = `UNRESOLVED`. Không gộp ba nhóm đầu thành "đúng".
2. Độ tin cậy ASR hiển thị ba mức: ≥ 0,8 "nghe rõ", 0,6–0,8 "nghe tạm", < 0,6 "nghe chưa rõ (không trừ điểm)".
3. Cảnh báo `ASR_LOW` khi trong 7 ngày gần nhất ≥ 40% lượt nói của em có q < 0,6 và có ít nhất 5 lượt nói.

## 10. Kế hoạch kiểm chứng

| Kiểm chứng | Cách làm | Ngưỡng đạt |
|---|---|---|
| **Tập vàng chấm tay** | Chủ dự án chấm tay ≥ 200 câu trả lời của unit (≥ 60 lượt nói, có giọng thật của học sinh, đủ mọi mã lỗi ở mục 5), lưu `evals/english/gold-*.yaml` (không chứa tên học sinh) | **DI-116:** độ khớp đúng/sai của bộ chấm với giáo viên ≥ 95% và Cohen κ ≥ 0,8; độ khớp mã lỗi ≥ 80%; lượt ASR thấp mà giáo viên nghe là đúng: không lượt nào bị ghi điểm 0 |
| **Hiệu chỉnh ASR** | Trên các lượt nói của tập vàng, so `q` với việc giáo viên nghe đúng/sai bản chép lời | Chọn lại ngưỡng DI-109 nếu ở 0,6 tỉ lệ bản chép lời sai mà vẫn q ≥ 0,6 vượt 10% |
| **Replay** | Test golden: cùng event log → `ChapterProjection` giống byte-for-byte; đổi `MasteryPolicy` tiếng Anh thì chiếu lại toàn bộ, lưu song song | 100% |
| **Học sinh mô phỏng** | Tám hồ sơ: trả lời "Yes, I do", dùng nguyên mẫu sau "We", quên "did", nhầm nghĩa cụm từ, trả lời tiếng Việt, chỉ nói theo cô, nói không rõ (q thấp), học tốt | Chỉ-nói-theo-cô không qua node nào; q thấp sai không bao giờ làm M giảm; hồ sơ "Yes, I do" không qua DIDYOU khi M01 còn mở; hồ sơ nguyên mẫu không qua WHATDID khi M02 còn mở; học tốt qua cả unit trong trần lượt |
| **Rò rỉ giữa hai môn** | Eval chéo: câu hỏi tiếng Anh vào RAG chỉ ra đoạn `subject=english`, câu Toán chỉ ra đoạn `math`; prompt buổi tiếng Anh không chứa đoạn Toán và ngược lại; câu hỏi Toán trong buổi tiếng Anh được gác như ngoài bài | **DI-116:** 0 đoạn khác môn ở top-k; 0 prompt lẫn môn |
| **Regression Toán** | `make test`, `make eval-hard`, `make eval-rag-published`, phép chiếu Toán trên replay cũ | Không đổi so với `main` trước ENG-2 |
| **Rò rỉ đáp án** | Validator: câu trả lời mẫu của item assessment không có trong prompt, không có trong lời cô trước khi con trả lời (trừ item cùng làm và H7) | 0 |

**DI-115 (cỡ tập vàng):** 200 câu và 60 lượt nói là cỡ tối thiểu để ước lượng κ với khoảng tin cậy chấp nhận được cho một unit; chưa có căn cứ thống kê riêng cho bài toán này, nên là DI.

**DI-116 (ngưỡng nghiệm thu):** độ khớp ≥ 95%, κ ≥ 0,8, mã lỗi ≥ 80%, rò rỉ khác môn = 0. Đây là ngưỡng dự án tự đặt cho bộ chấm tất định có đáp án đóng (cao hơn mức κ ≥ 0,6 mà blueprint cũ đặt cho chấm rubric mở).

**DI-110 (chuẩn hóa của bộ chấm tất định):** so sau khi: chữ thường; bỏ dấu câu và khoảng trắng thừa; mở rộng rút gọn theo bảng cố định (didn't, I'm, we're, it's, what's, isn't, wasn't, weren't); bỏ "yes,"/"no," ở đầu khi item không hỏi có/không; chấp nhận địa danh hay tên riêng khác với đáp án ở chỗ trống "in …" nếu đáp án cho phép (`allow_name`). Lỗi một ký tự ở từ ≥ 5 chữ cái là `EN_SLIP` (s = 0,7), ở từ ngắn hơn là sai. Danh sách đáp án chấp nhận lấy từ đáp án của tài liệu; biến thể ngoài bảng phải được chủ dự án duyệt trước khi thêm, không tự suy.

## 11. Danh sách DI mới

| DI | Nội dung | Mục |
|---|---|---|
| DI-106 | Đồ thị node của unit, ánh xạ mức A–E → chiều; "dạng câu hỏi" là kiểu đáp án, không phải modality; item nói theo mẫu là item cùng làm | 3 |
| DI-107 | Phân loại lỗi tiếng Anh và điểm phạt; lớp chung `L1` (s = 0,3) | 5 |
| DI-108 | Đúng sau mẫu: item nói theo cô là cùng làm (w × 0,5, không là thành công); mẫu nguyên câu trong item là H7 | 7 |
| DI-109 | Độ tin cậy ASR: công thức q, ngưỡng 0,6, đúng → w × 0,3, sai → không ghi evidence (thay DI-10 cũ) | 7 |
| DI-110 | Chuẩn hóa và biến thể chấp nhận của bộ chấm tất định | 10 |
| DI-111 | Gate UNDERSTOOD và pass rule cho node tiếng Anh; R của node từ vựng; giải thích bằng tiếng Việt | 6 |
| DI-112 | Thang gợi ý H0–H7 cho tiếng Anh (thay Support Ladder S0–S5 và DI-9 cũ) | 7 |
| DI-113 | Trạng thái định tính chung hai môn cho học sinh/phụ huynh (viết lại cột English của DI-14) | 8 |
| DI-114 | Chỉ số hiển thị: bốn nhóm kết quả, ba mức ASR, cảnh báo `ASR_LOW` | 9 |
| DI-115 | Cỡ tập vàng tối thiểu | 10 |
| DI-116 | Ngưỡng nghiệm thu bộ chấm và rò rỉ khác môn | 10 |

**DI-9 và DI-10 bị bỏ** cùng khung English cũ; số hiệu không được dùng lại.

## 12. Hệ quả

- Projector không cần nhánh riêng cho tiếng Anh: chỉ cần (a) `MasteryPolicy` tiếng Anh, (b) đọc `asr_confidence` theo DI-109, (c) lớp lỗi `L1`. Toán giữ nguyên version và kết quả.
- Trang giáo viên/phụ huynh dùng lại gần như toàn bộ; việc thêm là transcript + audio + ASR, nhãn chiều theo môn và bỏ dữ liệu minh họa của bản xem trước.
- Nội dung (từ, mẫu, item, đáp án) là việc của dữ liệu và của chủ dự án; khung này không bịa nội dung.
- Mọi thay đổi ngưỡng ở đây đều là thay đổi policy có version, phải chạy eval regression (quy tắc 7).
- Cài đặt khung này phải tuân theo `docs/plan/english-module-rules.md`, đặc biệt mục 5 (chấm và mastery: không đổi công thức, ngưỡng hay version của Toán) và mục 6 (event: chỉ thêm loại mới).
