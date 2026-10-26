# ADR-033: Tầng đọc ý định cho vài chữ không ai đọc được (REFORM-5)

**Trạng thái:** Đã làm, 2026-10-26. Các câu hỏi lại mới và danh sách từ ngắn chờ chủ dự án duyệt (DI-77).
- Chủ dự án yêu cầu (2026-10-25, kế hoạch cải tổ, Task 3.1): con gõ "ki", "kkk", "tt", "ể", "không" mà gia sư vẫn khen "Đúng rồi! Con đã suy nghĩ và kiểm tra rất cẩn thận".
- Code:
  - luật không tốn token: `assessment/student_intent.py` (`is_bare_negation`, `is_gibberish_or_ambiguous_short`, `is_keyboard_mash`, `guess_typo`), `teaching/conductor.py` (`clean`);
  - bộ đọc: `tutor/reader.py` (`read_unclear`, `ModelReader`, `clarification_problems`), `ai_gateway/base.py` và `router.py` (`ModelClass.INTENT_AGENT`);
  - chính sách và vòng lặp: `tutor/policy.py` (`R-ASK-CONFIRM`), `tutor/item_loop.py` (`_on_unclear`), `teaching/loop.py` (`_ask_confirm`);
  - sự kiện: `core/events.py` (`MessageRead`).
- Liên quan: ADR-017 (vai trò model), ADR-019 (hiểu con trước khi chấm), ADR-022 (đọc theo ngữ cảnh), ADR-028 (conductor), ADR-032 (ghi lần gọi model), quy tắc 1, 3, 6, 7 và 8 của CLAUDE.md, DI-76, DI-77, DI-78.

## Bối cảnh

- Sau REFORM-2, gia sư không còn khen "Đúng rồi!" khi con không giải thích được, nhưng vẫn chấm "ki", "tt", "ể" như câu trả lời hay lời giải thích. Đo trên `main` (be00192): ở pha trả lời 12/13 chuỗi của kế hoạch bị tính là lượt không tiến bộ hoặc câu sai, ba chuỗi liền nhau mở lời giải mẫu H6.
- Các chuỗi này không cùng một loại: "ko", "chưa" là xin giúp; "ki" là gõ trượt phím; "kt" là gõ tắt; "ể", "êr" là lỗi bộ gõ; "kkk" là cười hay giữ phím. Ý của con ở cả bảy chuỗi đều không chắc.
- Free tier Groq: 8.000 token/phút và 200.000 token/ngày cho mỗi model (`docs/poc/free-tier-quota.md`). Không thể gọi model cho mọi tin nhắn.

## Quyết định

1. **Hai tầng.** Tầng 1 là luật, không tốn token: "không", "chưa" đứng một mình là xin giúp (trừ khi câu hỏi nhận "không" làm câu trả lời); dãy gõ lặp và từ cách một phím so với "ko" được luật đọc. Tầng 2 là model, chỉ cho chuỗi vài chữ mà luật không đọc được.
2. **Model đoán, chính sách quyết định (quy tắc 1).** Bộ đọc trả `AMBIGUOUS_TYPO` (kèm ý đoán) hay `GIBBERISH` và một câu hỏi lại. Chính sách chọn `ASK_CONFIRM` ở lần đầu; ở lần hai liền sau nó coi tin nhắn là xin giúp, không hỏi lần ba. Không tin nhắn nào của loại này được chấm, tính là lượt không tiến bộ hay khen, ở mọi pha (câu đang làm, "vì sao", "con giảng lại", câu hỏi lý thuyết, nói lại).
3. **Câu hỏi của model phải qua kiểm.** `clarification_problems` và `validate_message`; không qua thì dùng câu mẫu. Lời con và lời gia sư đưa vào prompt được che số điện thoại và e-mail.
4. **Ghi để phát lại (quy tắc 3).** Nhãn, ý đoán và câu hỏi nằm trong `MESSAGE_READ`. Buổi dựng lại không gọi model, và nói lại đúng câu hỏi con đã thấy. Trạng thái "vừa hỏi lại" nằm trong sự kiện (`ItemState.confirm_open`, tin nhắn `ASK_CONFIRM` của vòng dạy), nên buổi học tiếp vẫn biết.
5. **Chuỗi model riêng** `INTENT_AGENT`: `openai/gpt-oss-120b` → model của gia sư → `openai/gpt-oss-20b`, qua `AIRouter`, mỗi model nhận `reasoning_effort` nó chấp nhận (Qwen "none", gpt-oss "low").
6. **Ngân sách.** Mỗi câu tối đa 2 lần gọi, chỉ trong nửa đầu trần 40 lần của buổi học; lần hai liền sau và dãy gõ lặp không gọi. Lượt đó gia sư không gọi Qwen thêm để nói. Đo xấu nhất offline: 93 lần gọi xuống 20 cho một con gõ nhầm ở mọi câu của cả chương.

## Phương án đã cân nhắc

- **Thêm Gemini vào chuỗi ("khi có khóa", như kế hoạch).** Không làm: ADR-017 giao Gemini ảnh và vector; hạn mức 20 lần/ngày mỗi model đã dùng cho đọc tài liệu; gói miễn phí dùng nội dung gửi lên để cải thiện sản phẩm và cấm ứng dụng cho dưới 18 tuổi, mà đây là lời của trẻ. Cần thêm một bộ chuyển model theo nhà cung cấp. Chủ dự án có thể quyết định lại.
- **Qwen đứng đầu chuỗi.** Trên 5 chuỗi đo thật, Qwen đọc ngang gpt-oss-120b, ít hơn khoảng 37% token và nhanh hơn. Giữ gpt-oss-120b đứng đầu theo kế hoạch vì hạn mức riêng; đổi thứ tự là một dòng ở `default_chat_chains`.
- **Cho model đọc mọi tin nhắn ngắn.** Tốn token và có thể đổi cách chấm; luật đã đọc được phần lớn.
- **Coi "ki" là "ko" luôn.** Có thể sai. Gia sư đoán nhưng luôn hỏi lại ("đúng không, hay con định gõ ý khác?").

## Hệ quả

- Con gõ nhầm không bị tính là làm sai hay bị cho xem lời giải mẫu vì ba lần gõ nhầm; cũng không nghe lời khen sai.
- Thêm một lượt hỏi lại ở lần gõ nhầm đầu tiên; lần thứ hai liền sau thì không hỏi nữa.
- Danh sách từ ngắn (`_KNOWN_WORDS`) và các câu hỏi lại mới là nội dung sư phạm, chờ chủ dự án duyệt. Từ ngoài danh sách bị hỏi lại một lần (sai thì tốn một lượt, không bao giờ chấm sai).
- Chưa làm: chữ tiếng Việt cho hai nhãn mới ở trang hội thoại của giáo viên (`apps/web`).
