# ADR-034: Bộ não hội thoại, nhiều model thay nhau viết lời gia sư (BRAIN-1)

**Trạng thái:** Đã làm, 2026-10-27. Thứ tự model mặc định, các ngưỡng của DI-84 và hiến pháp `constitution.v6` chờ chủ dự án duyệt.
- Chủ dự án yêu cầu (2026-10-26): "làm sửa triệt để, anh muốn cho bộ não trả lời thật; có thể dùng các agent khác Qwen thay thế trả lời, trả lời như người đi". Hai lần thử của chủ dự án ngày 26/10 cho cùng một kết luận: gia sư đọc câu mẫu, không nghe con nói.
- Code:
  - chuỗi model: `ai_gateway/router.py` (`DEFAULT_TUTOR_CHAIN`, `default_chat_chains`, `parse_models`, `ChatDispatcher`), `ai_gateway/gemini.py` (Gemini làm model chat, hết thời gian chờ sau 25 giây), `ai_gateway/groq.py`, `config.py` (`TUTOR_MODELS`);
  - bộ não: `tutor/brain.py` (`BrainPack`, `speech_codes`, `math_errors`, `copied_run`), `tutor/prompts/constitution.v6.md`, `tutor/llm_renderer.py` (`llm-renderer.v9`), `teaching/grounded.py` (vòng dạy), `tutor/renderer.py`, `tutor/item_loop.py`, `teaching/loop.py`;
  - đo: `scripts/compare_tutor_models.py` (`make compare-models`), báo cáo `evals/reports/BRAIN-1-models.md` (thư mục này không lên git; số liệu chính ở bảng dưới);
  - sự kiện: `core/events.py` (model nào đã viết một lượt, để trang giáo viên hiện).
- Liên quan: ADR-017 và ADR-018 (vai trò model: bản này sửa, xem Hệ quả), ADR-019, ADR-032 (ghi lần gọi model), ADR-033 (chuỗi `INTENT_AGENT`), quy tắc 1, 2, 3, 6, 7 và 8 của CLAUDE.md, DI-61, DI-71, DI-81, DI-84

## Bối cảnh

- Đến `llm-renderer.v8` model chỉ *diễn đạt lại một câu mẫu*: câu mẫu của nước đi là "mỏ neo", model phải giữ ý và thuật ngữ. Đo ở REFORM-1: lời do model viết chỉ khoảng 29% ở vòng luyện tập và khoảng 5% ở vòng dạy; phần còn lại là câu cố định hoặc quy tắc đã duyệt đọc nguyên văn.
- Hậu quả chủ dự án nhìn thấy (buổi học `01a17468…` trên `cavat_dev`, đọc bằng `make model-usage SESSION=…`):
  - con viết `9/10` cho "0,9 = ……" và được hỏi "vì sao con đặt dấu phẩy" (câu "vì sao" đầu tiên là câu cố định của cả tiết);
  - con đúng mà không giải thích được, lời đóng chỉ là "Mình sang câu tiếp theo nhé" vì câu không có lời giải thích đã duyệt;
  - bước "con nói lại" bỏ qua "mấy giờ rồi"; đọc cho con mục tiêu của kế hoạch ("Bé nhận ra…", viết cho giáo viên); in lại cả đề dài.
- Chỉ có khóa Groq và Gemini. Qwen trên Groq có 200.000 token/ngày; gpt-oss-120b và gpt-oss-20b là hai model khác của Groq, mỗi model một hạn mức riêng [ASSUME: cùng mức 200.000 token/ngày, chưa đo].

## Quyết định

1. **Model viết cả lượt, chính sách vẫn chọn nước đi (quy tắc 1).** Một lượt được viết từ *gói ngữ cảnh* (`BrainPack`): câu hỏi và lời con, kết luận của máy chấm, các gợi ý đã đưa, vài lượt gần nhất, việc chính sách chọn (nước đi, mức gợi ý) và phần đã duyệt của bài học làm *căn cứ* để dựa vào, không phải để đọc. Giọng nói nằm ở `constitution.v6.md`. Cả hai vòng dùng: vòng luyện tập qua `LLMRenderer`, vòng dạy qua `GroundedSpeaker`.
2. **Tự do có lưới.** Vẫn cứng (validator và `brain.speech_codes`): không nêu đáp án câu chưa giải, không khen câu sai, không nhại lời con, xưng hô cô–con, một câu hỏi, độ dài, an toàn trẻ em, và câu hỏi phải nhắc điều con vừa viết (`OFF_TARGET`). Mới và tất định: mọi phép bằng hoặc so sánh số trong lời model phải đúng, so theo giá trị (`WRONG_MATH`); một đoạn từ 9 từ giống y căn cứ là đọc lại chứ không nói (`COPIES_GROUND`); bốn từ đầu giống một trong hai lượt cô gần nhất bị bác. Bỏ các kiểm tra từ khóa của v8 (`BEYOND_ANCHOR`, `KEY_IDEA_MISSING`, `OFF_ANCHOR`). Lượt bị bác được thử lại một lần kèm lý do, rồi nói phần đã duyệt, rồi mới đến câu mẫu.
3. **Câu của bài kiểm tra (EXIT) không đổi:** câu đã duyệt nguyên văn, đáp án không bao giờ vào prompt (quy tắc 2).
4. **Ba lỗi đã thấy có test đỏ trước:** "vì sao" đầu tiên do model viết từ lời con; con đúng mà không giải thích được thì cô giảng lại bằng chính các số của câu (nếu model hỏng thì dùng lời giải thích đã duyệt hoặc các bước làm, không bao giờ chỉ "Mình sang câu tiếp theo nhé"); mục tiêu bài học viết cho giáo viên không bao giờ đọc cho con; đề dài hơn 60 từ khi nhắc lại chỉ nhắc câu hỏi chính; lời ngoài bài được đáp ngắn rồi rủ con quay lại.
5. **Nhiều model, một dòng cấu hình.** `TUTOR_MODELS` (các tên cách nhau dấu phẩy, từ trước ra sau) đặt chuỗi `TUTOR_REASONING`; tên bắt đầu bằng `gemini` đi bằng khóa Gemini, tên khác đi bằng khóa Groq (`ChatDispatcher`); mỗi model nhận `reasoning_effort` nó chấp nhận. Để trống thì dùng chuỗi mặc định ở điểm 6. Gemini chỉ có trong chuỗi khi chủ dự án gọi tên nó.
6. **Thứ tự mặc định theo số đo:** `openai/gpt-oss-120b` → `openai/gpt-oss-20b` → `GROQ_MODEL` (Qwen). Ba model Groq, mỗi model một hạn mức, nên cùng giữ khoảng 600.000 token/ngày [ASSUME].
7. **Ghi để người đọc kiểm:** sự kiện của mỗi lượt do model viết mang tên model đã viết (`core/events.py`), để trang giáo viên có thể hiện ai đã nói.

## Số đo

Hai mươi sáu lượt thật khó (đọc `cavat_dev`, chỉ đọc), cùng prompt (`constitution.v6` và gói ngữ cảnh), mỗi model một lần, không thử lại. "Qua bộ kiểm" là bộ kiểm tự động của ADR này, không phải người đọc.

| Model | Có lời | Qua bộ kiểm | Từ trung bình | Token trung bình |
|---|---|---|---|---|
| `openai/gpt-oss-120b` | 25/26 | 17/26 | 45 | 2.149 |
| `openai/gpt-oss-20b` | 26/26 | 18/26 | 39 | 2.124 |
| `qwen/qwen3.8-27b` | 1/26 | không so được | 29 | 1.785 |
| `gemini-3.8-flash` | 1/26 | 1/26 | 31 | 1.913 |

- Qwen: 25 lượt trả `QuotaExceeded` vì 200.000 token/ngày đã dùng hết trong ngày (các bài đo và buổi thử của chủ dự án); kết quả của nó **chưa so được**.
- Gemini: 25 lượt không có lời (HTTP 503, 504 hoặc hết hạn mức của gói miễn phí), nên không vào chuỗi mặc định.
- Mã bác nhiều nhất: `HAS_QUESTION`, `MISSING_QUESTION`, `OFF_TARGET` (gpt-oss-120b); `HAS_QUESTION`, `WRONG_PRAISE` (gpt-oss-20b).

## Phương án đã cân nhắc

- **Giữ Qwen đứng đầu (ADR-017).** Chưa có số đo của Qwen trên cùng 26 lượt: hạn mức ngày đã hết. Qwen ở cuối chuỗi vẫn nói được khi hai model kia hết hạn mức. Đo lại khi có hạn mức hoặc khóa `GROQ_API_KEY_EVAL`, rồi đổi thứ tự bằng một dòng `TUTOR_MODELS`.
- **Gemini đứng đầu.** Trả lời tốt ở lượt hiếm hoi đến được (lượt 5), nhưng 25/26 lần là 503/504 ở gói miễn phí; ADR-017 giao Gemini ảnh và vector.
- **Giữ câu mẫu làm mỏ neo, nới validator.** Đã thử ở REFORM-1b (lời do model viết ở vòng luyện tập tăng từ 14% lên khoảng 29%): các nước đi chủ chốt vẫn là câu mẫu, nên câu "vì sao" vẫn không dính vào điều con viết.

## Hệ quả và hạn chế

- ADR-017 và ADR-018 đổi: bộ não gia sư là *một chuỗi model*, không cố định Qwen; Gemini vẫn dành cho ảnh, chữ trong ảnh và vector, ngoại trừ khi chủ dự án đặt nó vào `TUTOR_MODELS`. Dòng "Vai trò model" của CLAUDE.md đã sửa theo.
- Một lượt có lịch sử tốn khoảng 2.000 đến 2.200 token mỗi lần gọi (đo ở bảng trên), nên một buổi 25 đến 40 lượt do model viết là khoảng 55.000 đến 90.000 token. Ba model Groq chịu được vài buổi mỗi ngày; thử với nhiều em cùng lúc cần khóa trả phí [cần kiểm tra].
- Chỉ 26 lượt, mỗi model một lần; chưa có người đọc chấm giọng điệu. Bộ kiểm tự động bắt số sai và khen sai, không bắt được cách nói gượng. Chủ dự án nên đọc vài buổi thật trước khi mời học sinh.
- Hạn mức gpt-oss là giả định đến khi đo.
