# ADR-066: Buổi học Tiếng Anh Unit 11 chạy đầu-cuối qua session thật (ENG-5b)

Ngày: 15/11/2026 · DI-140, DI-141, DI-142, DI-143 · Task ENG-5b (`docs/tasks/BACKLOG.md`, ENG-5) · Luật `docs/plan/english-module-rules.md` (S1–S4, P1–P5, C1–C3, E1–E3) · Liên quan: ADR-061 (RAG theo môn), ADR-062 (bộ nạp, schema), ADR-063 (bộ chấm, `node-mastery-en/0.1.0`), ADR-064 (giọng nói), ADR-065 (prompt, validator)

## Bối cảnh

Các phần của module Tiếng Anh đã vào `main` riêng lẻ, mỗi phần có test riêng, nhưng chưa có buổi học Tiếng Anh nào chạy qua session thật. **Ràng buộc trên hết: luồng Toán đang ổn định, không được đổi** (chủ dự án, luật cứng).

## Khảo sát (chỗ còn ngầm giả định Toán)

| Chỗ | Trước ENG-5b |
|---|---|
| `session/api.py::create_session` | chỉ tìm chương trong `chapters()` (Toán); `lesson_id` của unit rơi sang `_package` rồi 404 |
| `_chapter`, `_summaries` | chỉ đọc chương Toán |
| `CurrentItem.answer_format` | Literal không có `phrase`, `word_order`: state view của item Tiếng Anh lỗi 500 |
| `_command` | renderer luôn là bộ não Toán (`service.llm_renderer`), reader là `listener.v6` + `READ_SYSTEM` Toán, chooser là prompt "cô giáo dạy Toán lớp 5", ngân sách `MAX_LLM_CALLS_PER_CHAPTER`, web `WEB_LOOKUP` |
| `_chapter_speaker` | đã dùng chỉ mục RAG theo môn (ENG-2), nhưng prompt và lưới kiểm của `GroundedSpeaker` là của Toán (`grounded.v3`, constitution, `math_errors`) |
| `TeachingLoop` | validator mặc định là `validate_message` của Toán; không có cửa gác câu lệch môn |
| Đã theo môn sẵn | chấm (`answer_check`, ADR-063), projector (`policy_for`), giọng nói (`voice_turns`, ADR-064), chọn ngôn ngữ Whisper |

## Quyết định

1. **Môn của buổi học do backend đặt từ gói** (S1). `POST /v1/sessions` tìm `lesson_id` trong chương của mọi môn (`chapter_service.teachable_chapter`, Toán tìm trước nên id Toán tìm đúng như cũ); body không có trường `subject` (gửi lên là 422 vì model cấm trường lạ). Buổi không phải Toán ghi `activity.subject` trong document (DI-142); mọi chỗ đọc lại buổi học dùng `chapter_service.subject_of(session)`.
2. **Khác biệt là cấu hình theo môn, không phải nhánh rải trong policy** (S2): `tutor/english_session.py` gom các phần đã merge. `chapter_service._loop_options(chapter)` trả `{}` cho Toán (vòng dạy dựng y như cũ) và cho Tiếng Anh: validator phiên (DI-141) và luật gác câu lệch môn `english_off_topic` (DI-139). `TeachingLoop` chỉ **thêm** tham số `off_topic` (mặc định `None`).
3. **Đường gọi model của buổi Tiếng Anh** (DI-140): renderer `EnglishRenderer` (`build_english_request`, `constitution-en` + `english_g5`, kiểm bằng validator Tiếng Anh, dự phòng template), reader `EnglishLiveReader` (`listener-en`, nhãn OFF_TOPIC; đọc câu không rõ chỉ bằng luật). Không gửi prompt Toán nào: chooser bị tắt, `GroundedSpeaker` chạy không model.
4. **Cấu hình riêng** (C1, C2): `ENGLISH_WEB_LOOKUP` (mặc định `off`, DI-143), `ENGLISH_MAX_LLM_CALLS_PER_UNIT` (160). Biến của Toán giữ nghĩa và mặc định.
5. **Câu lệch môn** (P4, DI-141): vòng dạy gác trước mọi đường khác; ghi `STUDENT_MESSAGE` với `item_id` đuôi `:OFF_TOPIC` (ngoài replay của item và ngoài đếm lượt chờ), một lời cô `ref = "OFF_SUBJECT"` nhắc lại đúng câu đang chờ. Không chấm, không evidence, không gợi ý, không RAG, không web, không gọi model.
6. **API cho web (ENG-7b)** — chỉ thêm trường tùy chọn (F1): `SessionStateView.subject`, `SessionSummaryView.subject`, `answer_format` thêm `phrase`/`word_order`, endpoint mới `GET /v1/sessions/chapters` → `[{chapter_id, title, subject}]` (học sinh). Không đổi API báo cáo giáo viên/phụ huynh (`_named_chapter`, `taught-chapters`, overview vẫn chỉ Toán; đó là việc của ENG-7b).
7. **`make teach-en`**: như `make teach` cho Unit 11, offline, vòng dạy dựng đúng như buổi Tiếng Anh.

## Các DI

- **DI-140 (model trong buổi Tiếng Anh):** model chỉ diễn đạt nước đi của item (bộ não Tiếng Anh) và lắng nghe (`listener-en`). Ba đường Toán bị tắt trong buổi Tiếng Anh vì prompt của chúng là của Toán: (a) chooser AUTO-1/bandit → buổi Tiếng Anh dùng nước của chính sách (như `TUTOR_CHOOSER=policy`); bandit cũng không học từ câu trả lời Tiếng Anh; (b) `GroundedSpeaker` chạy không router: lý thuyết, câu hỏi của con và lời nối là đoạn đã duyệt và lời dẫn template, câu hỏi của con được trả lời bằng đoạn RAG của chỉ mục Tiếng Anh; (c) đọc câu không rõ (`READ_SYSTEM`) chỉ bằng luật. Viết bản Tiếng Anh cho ba đường này là việc sau nếu chủ dự án muốn (**[OPEN]**).
- **DI-141 (validator phiên và câu lệch môn):** lời model qua đủ validator Tiếng Anh DI-138; lời đã duyệt (template từ dữ liệu unit chủ dự án duyệt) chỉ bị kiểm thuật ngữ môn khác (`MATH_TERM`), dấu `[[en:` hỏng và lời trống. Lý do đo được: validator viết cho model bắt nhầm 259 câu đã duyệt của Unit 11 (tên riêng "Co To", câu hỏi tiếng Anh trong câu mẫu làm mất dấu hỏi phần Việt, gợi ý H4 của giáo viên cho một phần câu). Item loop đánh dấu lời model bằng `free_numbers`, nên validator phiên phân biệt được mà không đổi hợp đồng. Lời đưa con về bài khi hỏi lệch môn: "Cô nghe rồi, nhưng câu đó không thuộc bài «…» mình đang học, mình để lúc khác nhé. Bây giờ con trả lời giúp cô câu này nhé: …" (soạn chờ chủ dự án duyệt).
- **DI-142 (môn trong document buổi học):** chỉ buổi không phải Toán ghi `activity.subject`; document buổi Toán giữ đúng byte như trước (S4); thiếu trường là Toán, giá trị lạ là lỗi (không rơi về Toán).
- **DI-143 (`ENGLISH_WEB_LOOKUP` mặc định `off`):** ADR-065 để biến này cho ENG-5b. Bộ tra cứu hiện có tìm nguồn SGK Toán/giáo dục tiếng Việt; chưa kiểm cho Tiếng Anh, nên tắt tới khi chủ dự án bật (`official`/`search`/`wikipedia` dùng đúng bộ tra cứu đang có).

## Bằng chứng Toán không đổi

- Golden mới `services/api/tests/golden/math-session-before-eng5b.json`, **ghi trên `main` sạch (b0310d0) trước khi sửa code** (commit riêng đầu nhánh): một học sinh Toán đi hết chương Số thập phân qua session API (đúng, sai, xin gợi ý, chuyện ngoài lề, lượt nói, lý thuyết chưa hiểu): mọi state view (mã băm theo đúng các trường cũ), mọi ack, document đã lưu, sổ cái sự kiện, lịch sử và overview. Test `test_math_session_identical_to_before_eng5b` xanh sau thay đổi.
- Golden cũ (`math-projection-before-eng4.json`, `math-prompts-before-eng5a.json`, `rag-math-before-eng2.json`) xanh, không ghi lại.
- Test `test_math_and_english_sessions_of_one_student_do_not_mix`: buổi Toán xen kẽ buổi Tiếng Anh của cùng học sinh cho sự kiện giống hệt buổi Toán chạy một mình.

## Hệ quả

- Unit 11 chạy hết vòng 6 bước qua API offline: test qua ≥ 1 nút (bản chạy thử: 4/6 nút PASSED).
- Lời cô Tiếng Anh do template nói đúng dữ liệu đã duyệt; khi có model, bộ não Tiếng Anh diễn đạt nước đi item. Eval cần model (học sinh mô phỏng Tiếng Anh, eval-hard kiểu Tiếng Anh) **[cần kiểm tra]** ở ENG-9.
- Item `say_after_me` vẫn có thể bị hỏi "vì sao" khi R-VERIFY lấy mẫu trúng (chính sách chung, không đổi ở ENG-5b) — **[OPEN]** cho chủ dự án: nếu muốn bỏ, cần một luật policy riêng có tên, chỉ bật cho Tiếng Anh (S3).
