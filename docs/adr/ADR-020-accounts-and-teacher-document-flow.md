# ADR-020 — Tài khoản cố định, luồng giáo viên tải tài liệu, rồi mới tới RAG

**Trạng thái:** Đã chốt theo yêu cầu của chủ dự án (2026-10-07). Liên quan ADR-018, kế hoạch v1 (M1-5, M1-9, Mốc 2), T12.

## Bối cảnh

Chủ dự án chạy thử và chỉ ra:
- **Mỗi lần vào web lại nhập một học sinh mới.** Danh tính tạm `X-Demo-Student` là mã ngẫu nhiên lưu trong trình duyệt.
- **Giáo viên không tải được bài và tài liệu lên, không xem được nội dung bài.**
- **Chưa rõ RAG lấy dữ liệu từ đâu.**

Sự thật lúc đó:
- **RAG chưa được xây** (M1-5 "Chưa").
- **Nội dung bài lấy từ file YAML trong repo,** do AI soạn nháp.
- **Qwen chỉ viết lại câu mẫu,** nên lời gia sư giống khuôn mẫu.

## Quyết định

1. **Đúng 3 tài khoản để thử hệ thống:** 1 học sinh, 1 phụ huynh (gắn với học sinh), 1 giáo viên.
   - Tạo bằng `make accounts`; không có đường nào khác tạo tài khoản.
   - Đăng nhập bằng mã PIN. PIN lưu dạng scrypt.
   - Token ký HMAC; máy chủ chỉ tin danh tính trong token (quy tắc 4).
   - Tên của học sinh lấy từ tài khoản, web không còn hỏi tên.
   - `AUTH_MODE=demo` chỉ còn cho test offline và demo trong bộ nhớ.
2. **Giáo viên là nguồn của nội dung.** Luồng đúng:
   1. giáo viên tải tài liệu lên (SGK, giáo án, phiếu bài tập kèm đáp án);
   2. hệ thống đọc tài liệu và chia đoạn;
   3. giáo viên xem và duyệt nội dung bài, câu hỏi;
   4. RAG lập chỉ mục;
   5. gia sư truy xuất đúng đoạn và nói theo đoạn đó, có ghi nguồn; giáo viên xem được gia sư đã dùng đoạn nào.
3. **Làm theo thứ tự, mỗi bước một PR:**
   1. ACC-1: tài khoản;
   2. DOC-1: thư viện tài liệu của giáo viên và trang xem nội dung bài;
   3. RAG-1: đọc, chia đoạn, chỉ mục BM25 và vector, truy xuất kết hợp, trang tra cứu, bộ câu hỏi đo Recall@k và MRR;
   4. RAG-2: gia sư nói theo đoạn truy xuất (M1-9);
   5. DATA: dựng hai chương từ tài liệu thật của chủ dự án.

## Hệ quả

- Buổi học, điểm và tài liệu đều thuộc về một người cụ thể.
- **Dữ liệu cũ:** các buổi học cũ trong `cavat_dev` mang mã học sinh ngẫu nhiên không thuộc tài khoản nào. Không xóa tự động; chủ dự án quyết định có dọn hay không.
- **Phụ thuộc tài liệu thật:** chất lượng RAG phụ thuộc tài liệu thật, nên chủ dự án chuẩn bị tài liệu của hai chương song song với DOC-1 và RAG-1.
