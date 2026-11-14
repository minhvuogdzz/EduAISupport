# ADR-065: Bộ prompt và validator Tiếng Anh (ENG-5a)

Ngày: 14/11/2026 · DI-136, DI-137, DI-138, DI-139 · Task ENG-5a (`docs/tasks/BACKLOG.md`, ENG-5) · Luật `docs/plan/english-module-rules.md` mục 4 (P1–P5), mục 7 (V2b)

Module Tiếng Anh thật cho Unit 11 "Family time" (D-T13, ADR-060) cần gia sư nói theo khuôn Toán: policy quyết nước đi, model chỉ diễn đạt, không chấm, không ghi mastery. Khác Toán ở ba chỗ: cô giảng tiếng Việt nhưng câu đích là tiếng Anh; câu trả lời đích là một câu tiếng Anh nên luật "lộ đáp án" phải đọc được câu lẫn Việt–Anh; giọng cô (VieNeu) đọc sai một từ tiếng Anh đứng riêng (POC PR #139) nên lời gửi TTS phải biết đâu là đoạn tiếng Anh. **Ràng buộc trên hết: luồng Toán đang ổn định, không được đổi.**

## Khảo sát

| Đường | File | Prompt Toán hiện hành |
|---|---|---|
| Bộ não gia sư (BRAIN-1…8), cả vòng bài tập và vòng dạy | `tutor/brain.py` (`system_prompt`, `build_request`, `_lines`, `TASKS`) | `constitution.v18.md` + `math_g5.v2.md` |
| Lắng nghe trước khi chấm (DI-91) | `tutor/conversation.py::listen` | `listener.v6.md` |
| Kiểm lời cô (DI-92) | `teaching/curriculum.py::verification` | `curriculum-check.v12.md` |
| Renderer cũ (T06b) | `tutor/prompt_builder.py::system_prompt`, `build_request` | `constitution.v5.md` + `SUBJECT_MODULES[("math", 5)]` |
| Validator lời cô (PART 13.4) | `tutor/validator.py::validate_message` (+ `brain.speech_codes`) | lộ đáp án (số, so sánh, thứ tự, lựa chọn, `leak_patterns`), một câu hỏi, độ dài, xưng hô, khen sai, nhại lời con, PII, khen trí thông minh, chữ nước ngoài, số không có căn cứ |

`reasoning_effort` do adapter Groq đặt theo tên model (`groq.reasoning_effort_for`: Qwen `none`, gpt-oss `low`, model khác không gửi), `ChatRequest` không có trường này; giới hạn 3.000 token do gateway kiểm (`check_prompt_size`) và từng builder tự cắt lịch sử/căn cứ. Renderer cũ, nếu nhận một gói `english`, sẽ gửi constitution **Toán** (không có nhánh theo môn): lỗ hổng cần đóng.

## Quyết định

1. **Bộ prompt riêng theo môn, chọn bằng một bảng** (`prompt_builder.PROMPT_SETS`, `prompt_set(subject)`, `tutor_system_prompt(subject)`). Bộ Toán liệt kê đúng tên file mà code Toán đang đọc; code Toán **không đọc bảng này** và không đổi một dòng (test so tên và chuỗi). Bộ Tiếng Anh là bốn file mới: `constitution-en.v1.md`, `english_g5.v1.md` (L2), `listener-en.v1.md`, `curriculum-check-en.v1.md`. Môn lấy từ gói của buổi học do backend đặt (luật S1); thiếu hoặc sai môn là `ValueError`, không bao giờ rơi về Toán. Thay đổi duy nhất trong file dùng chung: `prompt_builder.system_prompt(package)` trả bộ Tiếng Anh khi `package.subject != "math"`; nhánh Toán đi đúng đường cũ.
2. **Bộ não Tiếng Anh dùng lại khung của Toán, khác lời** (`tutor/english.py`): cùng `BrainPack`, schema, nhiệt độ, cách cắt khi quá 3.000 token; riêng phần lời: việc từng move (`TASKS_EN`, đủ mọi move của `brain.TASKS`), thang gợi ý H0–H7 (`HINT_LADDER_EN`, DI-112), dòng `[TỪ VÀ MẪU CÂU CỦA BÀI]` lấy từ dữ liệu unit đã duyệt (`unit_targets`), việc "nói theo cô" (DI-108) và việc đưa con về bài khi hỏi lệch môn. Builder lắng nghe (`listen_request_en`, thêm nhãn `OFF_TOPIC`) và kiểm lời cô (`check_request_en`, trường `english_correct`, `duoc_doc_mau`). Prompt không viết cứng unit nào: thêm unit chỉ là dữ liệu (ENG-8).
3. **Validator Tiếng Anh là module mới** (`tutor/english_validator.py`), gọi `validate_message` của Toán **không sửa** trên phần tiếng Việt của lời cô, rồi thêm các kiểm của Tiếng Anh. `validator_for("math")` trả đúng `validate_message`.
4. **Quy ước đánh dấu tiếng Anh `[[en: …]]`** (khoảng trống G9 của ENG-3): model được dặn tự viết; server chạy `mark_english` tất định để thêm dấu còn thiếu, rồi mới kiểm. `display_text` bỏ dấu cho màn hình, `speech_segments` tách đoạn `vi`/`en` cho TTS (ENG-6), `english_speech` trả cả hai.

## Các DI

- **DI-136 (bộ prompt Tiếng Anh v1 và lời thang gợi ý):** nội dung bốn file prompt mới, lời từng bậc H0–H7 (`hint-ladder-en/1`) và lời từng move. Giữ nguyên các luật BRAIN dùng được cho Tiếng Anh: hệ thống quyết bài/move/mức gợi ý/chấm/mastery; không đọc nhãn nội bộ; một câu hỏi ở cuối; không hỏi "hiểu chưa"; "ok" chỉ là tiếp nhận; đúng một phần giữ phần đúng; không khen câu sai hay trí thông minh; xin nghỉ thì tôn trọng; cô sai thì nhận và sửa. Bỏ: mọi luật về số, phép tính, hình. Thêm: câu đích luôn sau câu dẫn tiếng Việt có dấu hai chấm, chỉ từ/mẫu câu của bài, không chấm phát âm. Lời cụ thể là DI vì khung đánh giá chỉ cho tên bậc (ADR-060 §7), không cho câu chữ.
- **DI-137 (thuật ngữ môn khác bị chặn):** danh sách `MATH_TERMS_BLOCK` (số thập phân, phân số, diện tích, tam giác, hình thang, phép tính… và decimal, fraction, area…) cộng phép tính có số (`0,5 + 0,25`). Hẹp hơn `assessment.math_terms` có chủ ý: "so sánh", "hàng", "cộng", "giây" là từ thường mà bài Tiếng Anh dùng ("so sánh do và did"). Tên môn "Toán" không bị chặn để cô nói được "câu đó của môn Toán, mình để lúc khác nhé". Chiều ngược lại không cần code mới: validator Toán vốn chặn chữ tiếng Anh trong lời cô (`FOREIGN_TEXT`, test `"We ate seafood"`).
- **DI-138 (tiếng Anh trong lời cô):** (a) **lộ đáp án** chỉ xét item có câu đích tiếng Anh (câu mẫu toàn chữ ASCII, có từ tiếng Anh; nhóm `facts.phrases` toàn ASCII). Lộ khi lời cô chứa nguyên câu đích, hoặc chứa một cách nói của **mọi** nhóm bắt buộc mà ít nhất một cách nói không có sẵn trong đề; so sau chuẩn hóa DI-110 (chữ thường, bỏ dấu câu, mở rút gọn) và theo ranh giới từ ("eat seafood" không phải "ate seafood"). Item trả lời bằng tiếng Việt (mức C, "vì sao") dùng `leak_patterns` như Toán. Không xét lộ: item "nói theo cô" (DI-108; người gọi báo qua danh sách `completion` của nút, hoặc `Item.kind == "say_after_me"` khi ENG-3b thêm trường), move được phép nêu đáp án (H7), sau khi con đã giải đúng, sau khi đáp án đã hiện. (b) **ngoài unit:** mọi từ trong `[[en: …]]` phải thuộc `unit_lexicon` = từ tiếng Anh trong dữ liệu unit đã duyệt (đoạn tiếng Anh, chữ trong ngoặc trích, câu trả lời tiếng Anh) cộng 82 từ chức năng lớp 5 (`BASE_WORDS`). (c) **từ trơ trọi (V2b):** lượt chỉ có tiếng Anh, không có câu tiếng Việt nào, bị từ chối; một từ tiếng Anh nằm trong câu tiếng Việt thì được (đoạn được đánh dấu để TTS đọc giọng Anh). (d) đánh dấu hỏng (`[[en:` không đóng, chữ tiếng Việt trong dấu) bị từ chối. (e) câu hỏi tiếng Anh được trích ("Bạn hỏi: Did you swim? Con trả lời thế nào?") không tính là câu hỏi thứ hai của cô; nếu nó kết thúc lượt thì là câu hỏi của lượt.
- **DI-139 (câu hỏi lệch môn trong buổi Tiếng Anh):** `english_off_topic` tất định, chạy trước model: phép tính có số, "bằng mấy/bao nhiêu" sau một số, hoặc thuật ngữ/cụm "bài toán, môn toán, diện tích…" → `OFF_TOPIC`. Không là lượt trả lời, không chấm, không evidence, không đổi mức gợi ý (P4). Lời của con **không được gửi** cho model (thay bằng một câu giữ chỗ): model không giải được điều nó không thấy, và prompt Tiếng Anh không chứa nội dung môn kia (P2). Câu lệch môn mà quy tắc không bắt được thì listener Tiếng Anh gán `OFF_TOPIC`.

## Bằng chứng Toán không đổi

- Golden `services/api/tests/golden/math-prompts-before-eng5a.json` ghi **từ bản sạch của `main` (6ac53b9) trước khi sửa code** (commit 783d2ab và 812413d của nhánh): system prompt và request đầy đủ của bộ não (có và không có `correction`), listener, curriculum-check; **thân request Groq gửi đi cho từng model của chuỗi mặc định** (gpt-oss-120b, qwen3.8-27b, gpt-oss-20b; gồm `reasoning_effort`, `max_completion_tokens`, schema); request renderer cũ cho mọi item × move HINT/EXPLAIN của ba bài Toán; kết quả `validate_message` trên 10 câu mẫu × 6 move × 55 item. Test `test_math_prompts_identical_to_before_eng5a` so từng chuỗi; golden không bao giờ được ghi lại sau khi sửa code.
- Không file prompt Toán nào đổi; `validator.py`, `brain.py`, `conversation.py`, `teaching/curriculum.py` không đổi.

## Hệ quả và việc còn lại (ENG-5b)

- Chưa nối vào buổi học: ENG-5b gọi `prompt_set`/`build_english_request`/`validator_for` từ phiên học khi bộ nạp theo môn (ENG-3b) và bộ chấm Tiếng Anh (ENG-4) đã vào `main`; truyền `say_after_me` từ `completion` của nút; chạy `english_off_topic` trước listener; lưu `speech_text` có dấu `[[en: …]]` cho TTS (ENG-6) và `display_text` cho màn hình.
- Chuẩn hóa DI-110 có hai bản (ở đây cho lộ đáp án, ở bộ chấm ENG-4); ENG-5b nên gộp về một hàm nếu hai bản khác nhau.
- `ENGLISH_WEB_LOOKUP` (luật C1) và ngân sách model call riêng (C2) thuộc ENG-5b.
- Eval cần model (học sinh mô phỏng tiếng Anh, `make eval-hard` kiểu Tiếng Anh) chưa chạy: **[cần kiểm tra]** ở ENG-5b/ENG-9.
