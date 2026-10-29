# ADR-048 · Nhận đúng quota ngày/phút và thời điểm hồi của Gemini

28/10/2026 · Chủ dự án yêu cầu xác định nguyên nhân gián đoạn và ưu tiên API ổn định, chấp nhận chi phí; chưa chọn ngân sách hay nguồn API thay thế.

[FACT] Kiểm trực tiếp API hiện tại: Gemini 2.5 Flash trả 429 ở RequestsPerDay, quotaValue=20, RetryInfo khoảng 62.425 giây. Gemini 4 cũng trả 429 với các bucket free-tier và thời gian tương tự. Không phải chỉ cần chờ một phút hoặc tạo thêm key trong cùng project. Google áp hạn mức theo project, không theo key; RPD hồi lúc nửa đêm Pacific: https://ai.google.dev/gemini-api/docs/rate-limits.

Adapter chat đọc QuotaFailure/RetryInfo của SDK, chuyển loại giới hạn RPD/TPD/RPM/TPM và reset_at cho router. Router nhớ đúng thời gian và bỏ qua ở mọi vai trò, thay vì coi tất cả 429 là nghỉ 10 phút. Khi RPD không có RetryInfo, tính lần nửa đêm Pacific tiếp theo có DST. Lỗi không có metadata vẫn dùng fallback cũ. Không lặp gọi API để kiểm quota trong tests.

[FACT] 77 tests gateway/model-calls/conversation đạt, gồm daily 17 giờ, minute 32,5 giây, reset Pacific mùa hè/đông và bỏ qua model sau hơn 10 phút ở vai trò khác. Đã khởi động lại local, HTTP 200. Không đổi secret, billing, scoring hoặc dữ liệu học sinh.

[OPEN] UI AI Studio cho thấy key EduAI thuộc project AIdevhouse, đang Free level. Chưa tạo key mới hoặc bật billing. Hộp cấu hình billing của AI Studio lỗi tải; đã đóng, không submit. Chờ chủ dự án làm rõ muốn key Gemini mới hay nhà cung cấp khác, cùng ngân sách trước khi thực hiện bước phát sinh chi phí/quyền truy cập.
