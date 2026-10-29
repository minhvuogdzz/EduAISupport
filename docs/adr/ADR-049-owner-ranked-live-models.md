# ADR-049: Thứ tự ưu tiên model hội thoại do chủ dự án chốt

Ngày 29/10/2026, chủ dự án yêu cầu dùng model ưu tiên cao trước, chỉ hạ xuống khi model đó bị giới hạn; thứ tự được xác nhận là **Gemini → GPT-OSS 120B → Qwen → GPT-OSS 20B**. Đây là thứ tự vận hành do chủ dự án chọn, không phải kết luận benchmark mới.

`build_router` dùng chung chuỗi cho đọc ý, chọn bước, viết lời, mentor và kiểm lời. Danh sách Gemini giữ thứ tự cấu hình hiện có (`TUTOR_MENTOR_MODEL`, `GEMINI_TUTOR_FALLBACKS`); chỉ thêm khi có key và model mentor được bật. Không có Gemini thì bắt đầu từ GPT-OSS 120B. Qwen lấy tên từ `GROQ_MODEL` và đứng trước 20B. `TUTOR_MODELS` đặt rõ là toàn bộ chuỗi thay thế theo đúng thứ tự, dùng chung cho các vai trò đang hoạt động. Overrides riêng của bài đánh giá vẫn được giữ.

Mỗi lần gọi duyệt từ đầu, thành công là trả về ngay. Quota được chia sẻ giữa các vai trò, tôn trọng thời điểm reset; khi hồi quota, lượt kế tiếp ưu tiên model đầu trở lại. Giữ fallback vận hành hiện hữu cho timeout, model unavailable và đầu ra không hợp lệ, để không treo phiên học. Không đổi mức quota, key, billing, giới hạn số lần gọi, prompt hay luật chấm/mastery. Câu đóng câu cố định là đường riêng, không được giải quyết chỉ bằng đổi thứ tự model.

Kiểm tra offline: thứ tự thống nhất, dừng ở model đầu thành công, skip model đang cooldown giữa các vai trò, quay về model đầu sau reset, và Qwen được dùng trước 20B khi các nguồn trước bị giới hạn. Không gửi dữ liệu học sinh để probe quota.
