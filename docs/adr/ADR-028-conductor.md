# ADR-028: Bộ điều phối hội thoại (agent chính) đứng trước và sau vòng dạy (CTX-2)

**Trạng thái:** Đề xuất, 2026-10-12.

- **Code:**
  - `cavat/modules/teaching/conductor.py` (`conductor/0.1.0`);
  - `session/chapter_service.py` (`_conducted`, `_side_replies`);
  - `assessment/student_intent.py` (`student-intent/0.2.0`: thêm teen code, `keyword_dump`);
  - sự kiện `CONTEXT_ROUTED` (`core/events.py`).
- **Giáo viên:**
  - bản ghi hội thoại có chip "Bé gõ «…»";
  - báo cáo học sinh có mục "Các tình huống trong hội thoại".
- **Liên quan:** ADR-019 (ý định của học sinh), CTX-1 (bộ đọc ngữ cảnh), ADR-018; CLAUDE.md quy tắc 1, 2, 3.

## Bối cảnh

Ngày 2026-10-12, chủ dự án yêu cầu một "agent chính" để kiểm soát ngữ cảnh cuộc trò chuyện. Mục tiêu là gia sư không rơi vào bế tắc khi học sinh nói quá nhiều từ khóa hoặc viết teen code khó kiểm soát.

Phiên học thử và học sinh giả lập Vương cho thấy ba kiểu bế tắc thật:

1. **Câu nhắc bị lặp.**
   - Câu đáp án mở chưa có cách chấm, gia sư nói "Con đọc lại đề bài thật chậm…" 12 lần rồi dừng bài.
   - Học sinh không hiểu câu nhắc thì nhận lại đúng câu nhắc đó.
2. **Câu kể lại bị hiểu là câu hỏi.** Câu kể lại "bỏ số 0 ở giữa thì không" kết thúc bằng "không", nên bị coi là câu hỏi. Gia sư trả lời "Cô ghi lại các câu con hỏi…" hơn 200 lần.
3. **Tin nhắn lạ hoặc dồn từ khóa.** Tin có emoji, chữ kéo dài ("đúnggggg"), chữ o thay số 0, hoặc dồn từ khóa không có câu hỏi hay câu trả lời. Các bộ đọc hiện có (bộ chấm, danh sách ý định, CTX-1) mỗi bộ chỉ đọc tốt một kiểu.

## Quyết định

1. **Bộ điều phối đọc mọi tin nhắn trước vòng dạy** (`clean`). Vòng dạy chấm trên chữ đã làm sạch:
   - bỏ emoji và ký hiệu trang trí, giữ ký hiệu Toán (< > = × : ² /);
   - thu chữ kéo dài về một chữ;
   - đổi "o,5" thành "0,5";
   - cắt tin quá 300 ký tự, giữ phần cuối, vì trẻ thường viết đáp án ở cuối.

   Teen code chỉ được giải mã ở bước đọc ý định (`expand_short_forms`), không bao giờ ghi đè vào câu trả lời, vì "k", "m", "s" có thể là đơn vị hoặc chữ "Sai".
2. **Dồn từ khóa là "chưa hiểu đề"** (`keyword_dump`, R-CLARIFY): ít nhất 3 thuật ngữ, không có số, không phải câu hỏi, và bỏ thuật ngữ đi thì không còn chữ nào khác.
   - Câu có từ nối ("trước", "rồi", "vì") là lời giải thích, không phải dồn từ khóa.
   - Câu đáp án mở được chấm trước: một danh sách thuật ngữ có thể chính là đáp án.
3. **Gỡ bế tắc sau vòng dạy** (`UNSTICK`).
   - **Khi chờ trả lời câu hỏi:** nếu câu gia sư sắp nói trùng một trong các câu vừa nói ở cùng câu hỏi, bộ điều phối xin gợi ý bậc kế tiếp thay học sinh. Bậc gợi ý vẫn do chính sách gợi ý chọn (quy tắc 1).
   - **Khi chờ trả lời câu hỏi lý thuyết hoặc kể lại:** nếu gia sư đã trả lời hoặc nhắc lại hai lần, tin tiếp theo được đọc là câu trả lời, không hỏi RAG nữa.
   - Câu khen "Đúng rồi!…" lặp ở câu mới không phải bế tắc. Lỗi này từng làm học sinh giả lập nhận gợi ý ở mọi câu kế tiếp, nên đã có test riêng.
4. **Câu phủ định ở cuối là câu kể** ("… thì không", "… cũng chưa"), không phải câu hỏi.
5. **Mọi việc bộ điều phối làm đều được ghi lại** (`CONTEXT_ROUTED`): chữ bé gõ, chữ vòng dạy đọc, các dấu hiệu tìm thấy, có gỡ bế tắc hay không.
   - Khi phát lại, buổi học chỉ đọc sự kiện của vòng dạy và không chạy lại bộ điều phối (quy tắc 3).
   - Bộ điều phối là luật tất định, không gọi model. Tin nhắn còn chưa rõ vẫn qua CTX-1: Qwen đề xuất nhãn, bộ chấm chấm (quy tắc 1, 2).

## Hệ quả

- Giáo viên thấy được bé gõ gì và gia sư đã đọc ra sao.
- Báo cáo học sinh thống kê các tình huống: teen code, emoji, dồn từ khóa, gỡ bế tắc, lạc đề, than chán, xin giúp, hỏi về bài.
- `scripts/simulate_learner.py` cho một học sinh giả lập ban đầu hiểu ít đi qua đúng API thật, để kiểm các tình huống trên.
- **Chưa làm:**
  - Bộ điều phối chưa tóm tắt ngữ cảnh dài cho Qwen. Prompt vẫn dùng vài lượt gần nhất (`prompt_builder`).
  - Teen code mới chỉ có một bảng tĩnh khoảng 70 dạng; dạng mới phải thêm vào bảng và tăng phiên bản.
