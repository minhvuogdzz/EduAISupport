# ADR-027: Giáo viên duyệt phương án dạy, gia sư dạy bản đã phát hành (INGEST-4a)

**Trạng thái:** Đề xuất, 2026-10-12.
- Code: `cavat/modules/ingest/review.py`; `ingest/service.py` (`decide`, `undo`, `publish`); `session/chapter_service.py` (sổ phương án đã phát hành).
- API giáo viên: `POST/DELETE …/teaching-plans/{chương}/decisions`, `POST …/publish`.
- Liên quan: ADR-025, ADR-026; CLAUDE.md (chủ dự án duyệt mọi nội dung sư phạm; quy tắc 3 về phát lại).

## Bối cảnh

Phương án dạy được dựng tự động từ tài liệu (INGEST-3a) và phần Qwen soạn (INGEST-3b). Chủ dự án quyết ngày 2026-10-12: giáo viên duyệt trước khi dạy; lúc Claude chạy thử thì Claude tự duyệt.

Vẫn còn những việc chỉ giáo viên làm được:
- sửa đáp án Gemini đọc sai;
- loại gợi ý lộ đáp án bằng lập luận;
- thêm cách giảng mà tài liệu không có.

## Quyết định

1. **Quyết định của giáo viên là dữ liệu riêng, được áp lên mỗi lần dựng lại**, nên không bao giờ mất.

   | Đích | Thao tác |
   |---|---|
   | `item:<mã>` | duyệt, loại |
   | `item:<mã>/stem`, `item:<mã>/answer` | sửa đề, sửa đáp án |
   | `item:<mã>/stage` | chuyển sang mức khác (kiểm tra hiểu, cùng làm, luyện tập, vận dụng) |
   | `hint:<mã>:H<n>` | duyệt, loại, sửa; viết mới nếu Qwen chưa có |
   | `node:<mã>` | duyệt cả bài |
   | `node:<mã>/<phần>` | sửa lý thuyết, quy tắc, ý chính, bài mẫu; thêm cách giảng hoặc bài mẫu bằng lần sửa đầu tiên |

2. **Câu giáo viên sửa đáp án có trạng thái TEACHER.**
   - Câu này được dạy, kể cả khi đáp án trong tài liệu lệch hoặc mâu thuẫn.
   - Các bước kiểm vẫn chạy trên chữ của giáo viên, và kết quả được hiển thị.
3. **Dựng lại khi giáo viên quyết định không gọi model.** Phần Qwen soạn chỉ lấy từ bộ đệm trên đĩa.
4. **Phát hành chỉ được khi:**
   - mọi bài đã duyệt;
   - bộ kiểm hợp lệ của gia sư không còn báo thiếu.

   Khi phát hành, phương án nhận version `tl-<thời điểm>`. Mọi version đã phát hành đều được giữ lại.
5. **Gia sư dùng sổ phương án đã phát hành.**
   - Buổi học mới dùng version hiện hành. Chưa có version nào thì dùng file chương soạn tay như trước.
   - Buổi học cũ phát lại đúng version nó đã bắt đầu (`lesson_version`), nên phát lại không bao giờ đổi (quy tắc 3).
   - Sổ được nạp một lần cho mỗi database ở request đầu tiên của các router phiên học. Không có gì được ghi lúc khởi động.

## Hệ quả

- **INGEST-4b:** trang `/teacher/plans/:chương`, mở từ tab Bài học, dùng API `GET …/view`.
  - Mỗi bài hiện kèm trang nguồn của nó.
  - Mỗi câu hiện trạng thái kiểm và trang gốc.
  - Gợi ý do Qwen soạn có nhãn "AI soạn".
  - Có mục "Câu chưa được dạy" để sửa đáp án đọc lệch.
  - Nút phát hành bị khóa khi còn việc chờ.
- RAG đọc nội dung chương qua `chapter_service.chapters()`, nên sau khi phát hành sẽ tìm trong nội dung đã được giáo viên duyệt.
- **[OPEN]** Chưa có bước gỡ một version đã phát hành. Nếu cần quay lại thì phát hành một version mới.
