# Kế hoạch module Tiếng Anh lớp 5, unit "My family" (ENG)

Ngày: 12/11/2026 · Quyết định D-T13 (blueprint 00) · Trạng thái: **chủ dự án duyệt mặc định ngày 12/11/2026** · Khung đánh giá: `docs/adr/ADR-060-english-assessment-framework.md` (DI-106 đến DI-116).

Tài liệu này là **hướng đi** của module Tiếng Anh. **Luật bắt buộc theo từng tầng** (nội dung, RAG, session, prompt, chấm, event, giọng nói, API/web, cấu hình, dữ liệu, kiểm thử, quy trình) và checklist Definition of done nằm ở `docs/plan/english-module-rules.md`; khi hai file khác nhau, file luật thắng. Đọc cùng `CLAUDE.md`, kế hoạch v1 (`plan-v1-teaching-knowledge-graph.md`) và ADR-060 trước khi làm bất kỳ task ENG nào. Khi tài liệu này mâu thuẫn với blueprint v0.1–v0.3 về Tiếng Anh, tài liệu này thắng.

---

## 1. Quyết định của chủ dự án (12/11/2026)

| # | Quyết định | Hệ quả |
|---|---|---|
| E1 | Tiếng Anh là **môn thứ ba có gia sư thật**, chỉ **một unit "My family" lớp 5** | Không tự mở rộng sang unit, lớp hay kỹ năng khác. Unit thứ hai chỉ để chứng minh mở rộng bằng dữ liệu (Mốc ENG-8) |
| E2 | Gia sư **ôn bài ở nhà** sau khi con đã học trên lớp, không phải khóa học kỹ năng | Mục tiêu là đúng từ, đúng mẫu câu của bài; không đo "trình độ" |
| E3 | Dùng **vòng dạy 6 bước** như Toán (ADR-059) | Cùng chính sách dạy node (`node_policy`), cùng luật `N-*`; chỉ khác nội dung |
| E4 | **Cô giảng bằng tiếng Việt**; từ và mẫu câu đích nói bằng tiếng Anh ("Con nói theo cô nhé: *This is my mother.*") | Prompt, validator và TTS phải xử lý câu lẫn hai thứ tiếng |
| E5 | **Không dùng khung kỹ năng kiểu IELTS/CEFR.** Xóa khung English cũ (subskill Reading/Speaking, rubric 0–4, S0–S5, DI-9, DI-10) | Dùng khung Toán ánh xạ lại: ADR-060 |
| E6 | **Nói chỉ là một cách trả lời**, không phải kỹ năng riêng | Không có chiều "speaking"; modality không làm phồng bằng chứng (DI-106) |
| E7 | Đúng/sai do **bộ chấm tất định** so với đáp án chấp nhận (có biến thể "I'm"/"I am") | `EnglishChecker` cạnh `MathChecker` (DI-110) |
| E8 | Giữ hai ý của khung cũ thành DI mới: ASR thấp chỉ được tăng mastery (DI-109); đúng sau mẫu không bằng đúng độc lập (DI-108) | |
| E9 | **Giáo viên và phụ huynh xem kết quả như Toán**; thêm bản chép lời + nghe lại audio + độ tin cậy ASR cho giáo viên; phân biệt đúng nhờ gợi ý và đúng độc lập; phụ huynh không có một điểm số duy nhất | ADR-060 mục 9 |
| E10 | **RAG tách theo môn** | Quy tắc R-ISO ở mục 2 |
| E11 | **Bật `WEB_LOOKUP` cho Tiếng Anh**, vẫn theo luật BRAIN-2/7 | Chỉ gửi khái niệm chuẩn, không gửi lời hay tên học sinh; bật bằng biến riêng của môn (ví dụ `ENGLISH_WEB_LOOKUP`), không đổi `WEB_LOOKUP` của Toán (luật C1) |
| E12 | **Nguồn nội dung làm như Toán** (ADR-020/023/024/025): chủ dự án cung cấp ấn phẩm công khai (SGK/sách giáo viên Tiếng Anh 5, giáo án, bài tập kèm đáp án) | Không tự bịa item hay đáp án |
| E13 | **Giáo viên duyệt:** nội dung soạn trong quá trình làm được chấp nhận mặc định | Ghi rõ "chủ dự án duyệt mặc định ngày 12/11/2026" trên mỗi artifact |
| E14 | **Giọng nói:** đo VieNeu-TTS code-switching Việt–Anh trước khi dùng; Whisper chọn ngôn ngữ theo bước; chưa chấm phát âm theo âm vị | Mốc ENG-6 |
| E15 | **Thứ tự làm:** dữ liệu unit và RAG tách môn → bộ chấm và ánh xạ projector → giọng nói → giao diện nối API thật → unit thứ hai chỉ bằng dữ liệu → eval chéo và regression Toán | Mục 8 |

## 2. Quy tắc bắt buộc

Các quy tắc này bổ sung cho 25 quy tắc của `CLAUDE.md`, không thay chúng. Đây là bản tóm tắt theo chủ đề; bản bắt buộc có cách kiểm cho từng luật là `docs/plan/english-module-rules.md`.

### R-ISO: cô lập môn

1. **`subject` bắt buộc** (`"math"` | `"english"`) ở `ChapterPackage`, `LessonPackage`, tài liệu giáo viên (`TeacherDocument`), mọi `Chunk` của RAG và mọi đoạn tra cứu web. Thiếu `subject` là lỗi validate, không có giá trị mặc định ngầm.
2. **Backend đặt `subject` cho buổi học** từ gói chương/unit mà buổi học chạy (ngữ cảnh buổi học, blueprint PART 24). Client không bao giờ gửi hay chọn `subject` (giống quy tắc 4 về model).
3. **RAG lọc `subject` trước mọi bước khác, lọc chặt:** đoạn khác môn hoặc thiếu môn không bao giờ lọt vào kết quả. Không lặp lại lỗ hổng hiện tại của `chapter_id` (`retrieve.py`: chunk có `chapter_id` rỗng vẫn qua bộ lọc, đoạn tài liệu chưa gắn node có `UNASSIGNED_DISTANCE = 1`). [REC] Mỗi môn một `RagIndex` riêng thay vì một chỉ mục chung lọc lúc truy xuất.
4. **Tokenizer theo môn:** BM25 của Toán dùng `core/vi_text` (bỏ dấu, gập chữ tiếng Việt). Tiếng Anh cần tokenizer riêng (chữ thường, tách từ tiếng Anh, giữ dạng rút gọn, không bỏ dấu kiểu tiếng Việt). Embedding Gemini dùng chung được.
5. **Prompt riêng theo môn:** `constitution`, `listener`, `curriculum-check` có bản cho tiếng Anh (ví dụ `constitution-en.v1.md`); không nhồi điều kiện "nếu là tiếng Anh" vào prompt Toán. Prompt Toán giữ nguyên version.
6. **Câu hỏi khác môn trong buổi học** (hỏi Toán trong buổi tiếng Anh và ngược lại) được gác như câu ngoài bài, không trả lời bằng nội dung môn kia.
7. **Eval chéo bắt buộc** trước khi merge mọi thay đổi chạm RAG/prompt/session của một môn: 0 đoạn khác môn ở top-k, 0 prompt lẫn môn (DI-116).

### R-CONTENT: nguồn nội dung, không bịa đáp án

1. Từ, mẫu câu, lý thuyết, item và đáp án **chỉ lấy từ tài liệu chủ dự án cung cấp** (ấn phẩm công khai: SGK/sách giáo viên Tiếng Anh 5, giáo án, bài tập kèm đáp án), qua đường ingest như Toán (ADR-023/024/025), kèm trang nguồn.
2. **Không tự bịa item hay đáp án.** Câu thiếu đáp án hoặc đáp án mâu thuẫn với đề thì **không dạy** (đánh dấu trong báo cáo ingest, như ADR-024).
3. Biến thể đáp án chấp nhận ngoài bảng chuẩn hóa DI-110 phải được chủ dự án duyệt trước khi vào `accept`.
4. Lời giảng do AI soạn (ADR-026/046) phải bám tài liệu và có trạng thái nháp đến khi duyệt (ở đây: duyệt mặc định, E13), nhưng **không bao giờ tạo đáp án mới cho item assessment**.
5. Bộ đọc ingest hiện nhắm vào khung giáo án Toán ("Phần k · mức", "Phiếu k · Tiết k", "Đề số k"). **Phải xem mẫu giáo án Tiếng Anh thật** trước khi viết bộ đọc; không đoán khung.

### R-LANG: ngôn ngữ của cô

1. Cô nói tiếng Việt, xưng "cô", gọi "con", như Toán.
2. Từ và câu đích luôn viết đúng chính tả tiếng Anh, đánh dấu để TTS và giao diện biết là tiếng Anh (ví dụ `<en>This is my mother.</en>` trong `speech_text`, in nghiêng trên màn hình).
3. Lời giải thích "vì sao" của con được nói/gõ bằng tiếng Việt (DI-111).
4. Không dùng thuật ngữ ngữ pháp nặng với trẻ lớp 5 ("đại từ nhân xưng ngôi thứ ba số ít"); dùng lời của sách giáo viên.
5. Validator lộ đáp án phải hiểu câu lẫn hai thứ tiếng: câu đích của item assessment không được xuất hiện trong lời cô trước khi con trả lời, trừ item cùng làm ("nói theo cô") và gợi ý H7 (DI-108).

### R-VOICE: giọng nói

1. Whisper chọn `language` **theo bước**, do backend quyết: item nói theo mẫu và item yêu cầu câu tiếng Anh → `en`; hỏi đáp, "vì sao", xin gợi ý → tự nhận dạng (không gửi `language`). Hiện code cố định `language="vi"` (`voice/api.py`).
2. Mỗi lượt nói ghi `asr_confidence` theo DI-109 và **tham chiếu tới tệp audio** đã lưu (trong một loại sự kiện mới, luật E1), để giáo viên nghe lại. Audio vẫn ở `var/storage/` (gitignore), không vào database và không vào `db-dump` công khai.
3. Lượt có q thấp: không trừ mastery, mời nói lại hoặc gõ (DI-109).
4. **Không chấm phát âm theo âm vị**, không dùng dịch vụ chấm phát âm. Phát âm chưa chuẩn mà không cản nghĩa không phải lỗi (DI-107).
5. **VieNeu-TTS code-switching:** PyPI mô tả có hỗ trợ trộn Việt–Anh, nhưng bản v3 Turbo trong repo **chưa được kiểm**. Phải đo trước (Mốc ENG-6) và ghi `docs/poc/vieneu-codeswitch-decision.md`. Nếu không đạt: phương án dự phòng là tách câu thành đoạn Việt/Anh và đọc đoạn tiếng Anh bằng giọng tiếng Anh miễn phí chạy local (chọn trong POC), hoặc TTS của trình duyệt.

### R-QUOTA: hạn mức

1. Giữ mọi giới hạn của Toán: prompt gửi Groq ≤ 3.000 token, `reasoning_effort` đúng từng model, `MAX_LLM_CALLS_PER_SESSION`, `MAX_LLM_CALLS_PER_CHAPTER`.
2. Unit tiếng Anh ngắn: [REC] dùng trần một buổi (40 lượt gọi) cho cả unit cho tới khi đo được nhu cầu thật.
3. Whisper dùng chung hạn mức Groq; đo số lượt nói mỗi buổi trong Mốc ENG-6 và ghi vào `docs/poc/free-tier-quota.md`.
4. Tra cứu web cho tiếng Anh chỉ gửi khái niệm chuẩn (ví dụ "possessive adjective my", "he she pronoun"), không gửi lời hay tên học sinh; snippet không phải bằng chứng; không tự nạp trang vào RAG (BRAIN-2/7, ADR-038/043).

### R-ASSESS: đánh giá

1. Khung đánh giá là ADR-060. Mọi ngưỡng hoặc công thức không có trong ADR-060 hay khung Toán phải là DI mới, đánh số tiếp từ DI-117.
2. `MasteryPolicy` tiếng Anh có version riêng (`node-mastery-en/…`); phép chiếu Toán (`node-mastery/0.3.0`) không được đổi kết quả.
3. LLM không chấm đúng/sai câu tiếng Anh và không ghi mastery. LLM chỉ được đề xuất nhãn cho lời giải thích tiếng Việt, qua validation layer 26.5.
4. Đáp án item assessment không vào prompt (quy tắc 2 của `CLAUDE.md`).

## 3. Hiện trạng code chạm tới (khảo sát 12/11/2026)

**[FACT]** Những chỗ đang gắn cứng với Toán hoặc chưa sẵn cho tiếng Anh:

| Chỗ | Hiện trạng | Việc cần làm | Mốc |
|---|---|---|---|
| `content/chapter_package.py` | `ChapterPackage.subject: Literal["math"]` | thêm `"english"`; validate theo môn | ENG-2 |
| `content/lesson_package.py` | `subject: Literal["math", "english"]` đã có; `AnswerType` chưa có kiểu câu tiếng Anh | thêm kiểu đáp án `phrase` (danh sách câu chấp nhận, `allow_name`) và `order` cho xếp từ | ENG-3/4 |
| `rag/service.py` `_build` | gom mọi chương vào một `RagIndex` | chỉ mục theo môn, `subject` ở `Chunk` | ENG-2 |
| `rag/retrieve.py` (khoảng dòng 368) | `chapter_id` rỗng lọt qua; `UNASSIGNED_DISTANCE = 1` | lọc `subject` chặt trước; đoạn chưa gắn node chỉ trong cùng môn | ENG-2 |
| `rag/bm25.py`, `core/vi_text` | tokenizer tiếng Việt | tokenizer tiếng Anh | ENG-2 |
| `assessment/math_checker.py` | chỉ chấm Toán | `assessment/english_checker.py` (DI-110, DI-107) | ENG-4 |
| `assessment/projector.py` | không đọc `asr_confidence`/`modality`; `ErrorClass` chưa có `L1` | `MasteryPolicy` tiếng Anh, DI-108/109, lớp `L1` | ENG-4 |
| `core/events.py` | `ItemResolved.asr_confidence` có nhưng không ai điền; `StudentMessage` không có tham chiếu audio | điền q; thêm **loại sự kiện mới** (ví dụ `VOICE_TURN_RECORDED`: `audio_ref`, q, ngôn ngữ) thay vì sửa event cũ (luật E1) | ENG-6 |
| `voice/api.py` | `language="vi"` cố định; trả `Transcript(text, model)` không có độ tin cậy | ngôn ngữ theo bước, trả q | ENG-6 |
| `ai_gateway/groq.py` | đọc `avg_logprob`/`no_speech_prob` chỉ để bỏ im lặng | trả q theo DI-109 | ENG-6 |
| `tutor/prompts/` | prompt Toán (`constitution.v18`…) | bộ prompt tiếng Anh riêng | ENG-5 |
| `session/chapter_service.py` | `DEFAULT_CHAPTER_ID` là chương Toán | buổi tiếng Anh mở theo unit, không đổi mặc định của Toán | ENG-5 |
| `session/teacher_view.py`, `progress.py` | dùng được cho mọi `Chapter` (nhận `?chapter=`) | thêm nhóm DI-114, `ASR_LOW`, tham chiếu audio | ENG-7 |
| Web giáo viên | `Method` ghi "khung Toán §…"; `DocumentsPage`, `LessonsPage` gắn cứng chương hình học; nhãn radar theo Toán | chữ theo môn; lọc chương theo môn | ENG-7 |
| Web `features/english/` | bản xem trước, dữ liệu minh họa `content.ts` (`SAMPLE_CLASS`…), không gọi API | thay bằng trang thật nối API; bỏ dữ liệu minh họa của unit đã có thật | ENG-7 |

## 4. Kiến trúc mục tiêu (tóm tắt)

- **Một unit = một `ChapterPackage` với `subject: english`.** Mỗi node là một nút kiến thức của unit (ADR-060 mục 3). Gói nằm ở `docs/pedagogy/english-g5/unit-my-family/chapter.yaml` cùng các `lesson.yaml`.
- **Cùng vòng dạy, cùng chính sách node, cùng projector.** Khác ở: bộ chấm (`EnglishChecker`), `MasteryPolicy` tiếng Anh, bộ prompt, tokenizer RAG, thang gợi ý theo nội dung DI-112.
- **Ngữ cảnh buổi học mang `subject`** (backend đặt từ gói), và mọi thành phần đọc từ đó: RAG, prompt, tra cứu web, chọn ngôn ngữ Whisper, TTS.
- **Trang giáo viên/phụ huynh dùng chung**, chọn unit qua `?chapter=` như hiện nay; phần riêng của tiếng Anh là transcript + audio + ASR (ADR-060 mục 9).

## 5. Đánh giá

Toàn bộ ở ADR-060. Tóm tắt cho phiên sau:
- Bảy chiều C R A T I S D, công thức §20 + DI-1; S trống cho tới khi có delayed probe.
- Gate §52, pass rule DI-15, mastery tạm thời §53 + DI-59, confidence DI-11: **giữ nguyên số**.
- Mới: DI-106 (node, item, dạng câu hỏi), DI-107 (lỗi), DI-108 (đúng sau mẫu), DI-109 (ASR), DI-110 (chuẩn hóa), DI-111 (gate), DI-112 (thang gợi ý), DI-113 (trạng thái định tính), DI-114 (chỉ số hiển thị), DI-115 (cỡ tập vàng), DI-116 (ngưỡng nghiệm thu).

## 6. Ngoài phạm vi

- Unit, lớp, kỹ năng khác (Reading/Listening/Writing như kỹ năng riêng); "trình độ" CEFR/IELTS.
- Chấm phát âm theo âm vị, độ trôi chảy, ngữ điệu.
- Hội thoại tự do không theo bài; realtime speech-to-speech.
- Tự soạn item hay đáp án không có trong tài liệu.

## 7. Định nghĩa "xong" của cả module

1. Một học sinh ôn hết unit "My family" từ web (gõ và nói), qua 6 bước ở từng node, với dữ liệu lưu database của `.env`.
2. Giáo viên xem trang học sinh và trang lớp của unit, nghe lại audio từng lượt nói, thấy độ tin cậy ASR và bốn nhóm kết quả (DI-114). Phụ huynh xem trang của con không có điểm số tổng.
3. Bộ chấm đạt DI-116 trên tập vàng; replay byte-for-byte; học sinh mô phỏng đạt mục 10 ADR-060.
4. Eval chéo hai môn: 0 rò rỉ. Regression Toán: không đổi.
5. Unit thứ hai thêm được chỉ bằng dữ liệu (không sửa code).
6. Mọi mốc có mục nhật ký Phụ lục E trong tài liệu luận văn.

## 8. Thứ tự các mốc (mỗi mốc một hoặc vài phiên, task chi tiết ở `docs/tasks/BACKLOG.md`; mọi PR phải qua checklist của `english-module-rules.md`)

| Mốc | Task | Nội dung | Phụ thuộc |
|---|---|---|---|
| ENG-1 | (xong khi PR này gộp) | ADR-060, kế hoạch này, dọn blueprint, `CLAUDE.md`, BACKLOG | — |
| ENG-2 | Môn trong gói và RAG tách môn | `subject` bắt buộc, chỉ mục theo môn, lọc chặt, tokenizer tiếng Anh, eval chéo cơ bản; Toán không đổi | ENG-1 |
| ENG-3 | Dữ liệu unit "My family" | Đọc mẫu giáo án Tiếng Anh thật, bộ đọc ingest cho khung đó, `chapter.yaml` + `lesson.yaml` của unit, báo cáo câu thiếu/mâu thuẫn đáp án | ENG-2, tài liệu của chủ dự án |
| ENG-4 | Bộ chấm tiếng Anh và ánh xạ projector | `EnglishChecker` (DI-110, DI-107), lớp `L1`, `MasteryPolicy` tiếng Anh (DI-108, DI-111), test golden | ENG-3 |
| ENG-5 | Vòng dạy và prompt tiếng Anh | Bộ prompt tiếng Anh, thang gợi ý DI-112, validator lộ đáp án hai thứ tiếng, `WEB_LOOKUP` cho tiếng Anh, buổi học chạy trong `make teach`/API | ENG-4 |
| ENG-6 | Giọng nói | Whisper theo bước, q (DI-109), sự kiện lượt nói mới có `audio_ref`, POC VieNeu code-switching và dự phòng | ENG-5 |
| ENG-7 | Giao diện nối API thật | Trang học sinh tiếng Anh thật; trang giáo viên/phụ huynh theo môn; transcript + audio + ASR; bỏ dữ liệu minh họa của unit | ENG-6 |
| ENG-8 | Unit thứ hai chỉ bằng dữ liệu | Thêm một unit khác của SGK lớp 5 do chủ dự án chọn, không sửa code | ENG-7, tài liệu |
| ENG-9 | Eval chéo, tập vàng, regression Toán | Tập vàng DI-115/116, hiệu chỉnh ngưỡng ASR, học sinh mô phỏng, eval rò rỉ hai môn, regression Toán; số liệu cho luận văn | ENG-8, chủ dự án chấm tay |

## 9. Câu hỏi còn mở [OPEN]

| # | Câu hỏi | Ai trả lời | Chặn mốc |
|---|---|---|---|
| Q-E1 | Bộ SGK Tiếng Anh 5 nào, unit số mấy, danh sách từ và mẫu câu chính xác của "My family" | Chủ dự án (qua tài liệu) | ENG-3 |
| Q-E2 | Mẫu giáo án Tiếng Anh thật trình bày thế nào (tiết, hoạt động, đáp án) | Chủ dự án gửi file | ENG-3 |
| Q-E3 | Mẫu "He/She is ___" của bài nói về tuổi, nghề hay tính từ | Theo SGK | ENG-3 |
| Q-E4 | VieNeu-TTS v3 Turbo đọc câu trộn Việt–Anh có nghe được không; nếu không thì giọng tiếng Anh dự phòng nào | POC ENG-6 | ENG-6 |
| Q-E5 | Công thức q và ngưỡng 0,6 của DI-109 có khớp giọng trẻ em Việt nói tiếng Anh không | Tập vàng ENG-9 | ENG-9 |
| Q-E6 | Unit thứ hai để chứng minh mở rộng là unit nào | Chủ dự án | ENG-8 |
| Q-E7 | Trang chủ học sinh: chọn môn thế nào khi có hai môn thật (giữ `SubjectSwitch` hiện có?) | Chủ dự án, khi duyệt ENG-7 | ENG-7 |

## 10. Rủi ro

| Rủi ro | Ảnh hưởng | Giảm thiểu |
|---|---|---|
| Whisper nghe sai giọng trẻ nói tiếng Anh | Chấm sai, M sai | DI-109 (q thấp không trừ), xác nhận khi từ khác nghĩa, giáo viên nghe lại và override, tập vàng |
| "Chỉ tăng không giảm" làm M thiên lệch lên với em nói không rõ | Báo cáo lạc quan | Trọng số 0,3, không tính thành công, cảnh báo `ASR_LOW` |
| Rò rỉ Toán vào buổi tiếng Anh (hoặc ngược lại) qua RAG/prompt | Cô giảng sai môn | R-ISO, eval chéo bắt buộc, chỉ mục riêng |
| Tài liệu thiếu đáp án hoặc thiếu item mức C/E | Node thiếu chiều R/T | Không bịa (R-CONTENT); node thiếu item C thì ghi vào báo cáo ingest để chủ dự án bổ sung; T trống được (DI-1) |
| Bộ chấm tất định quá chặt với biến thể hợp lệ | Chấm sai câu đúng | DI-110, tập vàng, chủ dự án duyệt biến thể |
| VieNeu đọc sai tiếng Anh | Con học theo phát âm sai | POC trước, dự phòng giọng tiếng Anh riêng |
| Sửa code chung làm đổi kết quả Toán | Mất số liệu đã báo cáo | Policy version riêng, regression Toán ở mỗi PR |
| Hạn mức Groq bị chia cho Whisper | Hết lượt giữa buổi | Đo ở ENG-6, giữ trần lượt gọi |

## 11. Ghi chép luận văn

Mỗi mốc ENG-n khi gộp thêm một mục vào "Phụ lục E. Nhật ký công việc" của Google Doc luận văn theo quy tắc trong `CLAUDE.md`; phiên không có connector viết sẵn mục trong mô tả PR dưới tiêu đề "Ghi chép luận văn".
