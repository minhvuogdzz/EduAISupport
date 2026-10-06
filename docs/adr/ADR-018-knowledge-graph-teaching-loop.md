# ADR-018 — Gia sư dạy theo đồ thị tri thức, Hybrid RAG tự xây

**Trạng thái:** Đã chốt (chủ dự án duyệt ngày 2026-10-06). Chi tiết ở `docs/plan/plan-v1-teaching-knowledge-graph.md`. Liên quan D-T9, D-T10, D-T11 (mục Revision của `docs/blueprint/00-START-HERE.md`). Thay vai trò LlamaParse trong ADR-017.

## Bối cảnh

- Bản chạy được đến ngày 2026-10-01 mới **kèm làm bài tập**: một buổi học là 8 câu cố định, gia sư gợi ý, chẩn đoán lỗi, hỏi "vì sao". Gia sư chưa **dạy** lý thuyết và phương pháp, và chưa đo được học sinh hiểu thật hay chưa.
- Chủ dự án đưa bài báo 2T-KT (Li và cộng sự, Information Fusion 126, 2026, doi:10.1016/j.inffus.2025.103577) làm tham khảo kiến trúc đồ thị tri thức, và yêu cầu hạn chế kiến trúc của bên thứ ba vì hội đồng đánh giá phần tự thiết kế.

## Quyết định

1. **Vòng dạy 7 bước là trung tâm:** ôn nền → giảng lý thuyết → kiểm tra hiểu → dạy phương pháp (cô làm, cùng làm, con làm) → luyện tập → vận dụng → quyết định qua node hay quay lại. Vòng kèm từng câu hiện có (T02, T04) trở thành bước luyện tập.
2. **Đồ thị tri thức theo khuôn 2T-KT:** node hai tầng (cơ bản, vận dụng); quan hệ tiên quyết, lớp con, tương tự, vận dụng; quan hệ tiên quyết không có vòng lặp. Mỗi node mang nội dung dạy gắn theo 4 mức (Tiếp xúc, Hiểu, Luyện tập, Vận dụng).
3. **Điểm từng node** theo blueprint PART 25.2 và 26.1 (Beta theo chiều, 7 chiều, cổng UNDERSTOOD và DI-6), là projection tất định từ sự kiện. Node mới lấy điểm khởi đầu từ node tiên quyết. LLM không ghi điểm.
4. **Chính sách dạy theo node:** luật tất định có mã `N-*`, có version.
5. **Hybrid RAG tự xây:** lọc theo cấu trúc đồ thị (node, mức, quan hệ), chỉ mục từ khóa BM25 (bản còn dấu và bỏ dấu), chỉ mục vector embedding, hợp nhất bằng Reciprocal Rank Fusion, xếp hạng lại theo luật sư phạm, ghi vết từng lần truy xuất. Đoạn truy xuất được là neo cho lời nói; LLM không trả lời khi không có neo.
6. **Tự xây toàn bộ kiến trúc AI.** Chỉ dùng API model (Qwen trên Groq, Gemini) qua `ai_gateway`, cùng thư viện cấp thấp và hạ tầng web, database. Không dùng framework RAG hay agent, dịch vụ vector database, dịch vụ đọc tài liệu (bỏ LlamaParse), thư viện knowledge tracing có sẵn.

## Không lấy từ 2T-KT

GCN, IRT có giải thích, SHAP (cần dữ liệu huấn luyện lớn); LLM đoán điểm ở mọi bước (tốn token, trái quy tắc 3); kiểm chứng quan hệ bằng Wikipedia và mạng nơ-ron đồ thị (thay bằng một lượt LLM kiểm chứng và giáo viên duyệt).

## Hệ quả

- Buổi học không còn là danh sách câu cố định: chính sách dạy chọn bước tiếp theo trên đồ thị.
- Cần nội dung dạy cho từng node: lý thuyết nhiều cách giảng, ví dụ mẫu, câu kiểm tra hiểu, bài vận dụng. AI soạn nháp, chủ dự án duyệt.
- Thêm model class `EMBEDDING` vào gateway. Hạn mức miễn phí của embedding phải đo; RAG vẫn chạy với từ khóa và cấu trúc khi không có embedding.
- Atlas M0 không có Vector Search (D-T7) không còn là hạn chế: chỉ mục vector tự viết, chạy trong tiến trình API.
- Có thêm các thí nghiệm cho đồ án: bỏ từng thành phần của Hybrid RAG; học sinh ảo; so sánh điểm theo quy tắc với cách đoán kiểu 2T-KT.
