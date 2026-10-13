# ADR-029: Tra nguồn chính thống khi tài liệu không trả lời (WEB-1)

**Trạng thái:** Đề xuất, 2026-10-13.

- **Code:**
  - `cavat/modules/teaching/web.py` (`web-lookup/0.1.0`);
  - `GroundedSpeaker._from_web` (`teaching/grounded.py`);
  - sự kiện `WEB_LOOKED`;
  - cấu hình `WEB_LOOKUP`.
- **Liên quan:** ADR-028 (agent điều phối), RAG-2, DI-50; CLAUDE.md quy tắc 1, 8 (gửi AI dữ liệu tối thiểu), free-first (ADR-016).

## Bối cảnh

Ngày 2026-10-13, chủ dự án định hướng cho agent: ưu tiên RAG. Khi học sinh hỏi câu ngoài tài liệu, mô hình được tra dữ liệu trên internet hoặc nguồn khác, nhưng phải trong tầm kiểm soát và chỉ ở trang chính thống, chính xác.

Thử thật cho thấy tìm toàn văn một câu hỏi trên Wikipedia ra kết quả bất kỳ: "nước sôi ở bao nhiêu độ" ra bài "Hoa Kỳ".

## Quyết định (DI-51)

1. **Thứ tự cố định.** Tài liệu của bài trước, theo phạm vi DI-50.
   - Câu thuộc bài sau không bao giờ được tra: gia sư báo "bài sau mình học".
   - Chỉ câu mà tài liệu không trả lời mới được tra ngoài.
2. **Một nguồn trong danh sách cho phép:** Wikipedia tiếng Việt, qua API chính thức (MediaWiki), miễn phí, không cần khóa.
   - Không tìm kiếm web chung, không theo liên kết trong trang.
   - Trang của host khác bị từ chối.
   - Thêm nguồn là quyết định của chủ dự án.
3. **Chỉ tra khái niệm có tên** ("X là gì", "X nghĩa là gì", "X là con gì"), mở đúng bài có tiêu đề X. Chuyển hướng chính thức của Wikipedia được chấp nhận. Không dùng:
   - trang định hướng;
   - bài có tiêu đề không phải X;
   - câu hỏi về người ("là ai"): lịch sử, chính trị để thầy cô trả lời;
   - các dạng câu hỏi khác.
4. **Chỉ câu hỏi an toàn** (`eligible`): ngắn, không có số điện thoại, email hay đường dẫn, không thuộc các chủ đề để người lớn trả lời (`UNSAFE`: bạo lực, tình dục, chất cấm, vũ khí, tự tử, chính trị, tôn giáo…).
   - Dữ liệu gửi đi chỉ là tên khái niệm, không có tên hay câu chữ khác của học sinh.
5. **Lời bám nguồn.**
   - Đoạn mở đầu của bài viết là bằng chứng. Câu trả lời của Qwen qua cùng bộ kiểm như với tài liệu: số, thuật ngữ, độ phủ, độ dài.
   - Không qua thì dùng nguyên văn câu của bài viết bao được câu hỏi.
   - Không có câu nào bao được thì gác lại cho cô.
   - Bé được nghe rõ nguồn: "Theo Wikipedia tiếng Việt, cô kể con nghe nhé: …".
6. **Ghi lại để kiểm tra.**
   - Mỗi lần tra được ghi thành `WEB_LOOKED`: khái niệm gửi đi, bài viết, đường dẫn, bé có được nghe hay không.
   - Lời đã nói được ghi như mọi lời khác. Khi phát lại, buổi học không tra lại.
7. **Bật/tắt:** `WEB_LOOKUP=wikipedia` (mặc định) hoặc `off`.
   - Kết quả tra được lưu đệm ở `var/storage/web/`, chỉ hỏi Wikipedia một lần cho mỗi khái niệm.
   - Test luôn tắt (`conftest`), không gọi mạng.

## Hệ quả

- Bé hỏi "số nguyên tố là gì", "hình lập phương là gì" khi đang học số thập phân thì được trả lời ngắn, có nguồn, thay vì luôn bị gác. Câu hỏi của bài sau vẫn không được trả lời trước.
- **Giới hạn:**
  - Câu hỏi không theo dạng "X là gì" ("nước sôi ở bao nhiêu độ") vẫn gác cho cô. Cần tìm kiếm có ngữ nghĩa trên nguồn tin cậy mới làm được, đó là việc sau.
  - Lời văn Wikipedia có thể khó với học sinh lớp 5. Qwen viết lại cho dễ hiểu, nhưng bản trích nguyên văn (khi không có model) có thể vẫn khó.
