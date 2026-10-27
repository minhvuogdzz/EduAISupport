# ADR-036: Bàn giao bản có bộ não bằng Docker Compose

**Trạng thái:** triển khai theo yêu cầu trực tiếp của chủ dự án ngày 27/10/2026. Thay quy định không Docker của D-T6 chỉ cho môi trường server; phát triển local vẫn dùng venv/Atlas.

Chủ dự án yêu cầu gom bản có bộ não, đóng Docker Compose, đưa code lên GitHub, xuất DB tại máy và cung cấp lệnh nạp trên server để DevOps ít thao tác nhất. BRAIN-1 (#118) đã merge. REL-1 (#119) cung cấp web/API cùng origin. FIG-1 dở dang được giữ riêng, không chặn bản có bộ não.

- Multi-stage image Node 22 → Python 3.11, chứa bản web HTTP cùng code API và nội dung đã có. Chạy user không phải root, một worker vì lockout và quota tracker đang trong bộ nhớ.
- Compose chạy app và Mongo 7 có mật khẩu trên mạng riêng, dữ liệu ở named volumes. Caddy là profile tùy chọn. Không kèm VieNeu; đọc bằng fallback của trình duyệt, nghe qua Whisper.
- `deploy/setup.sh` sinh bí mật bền vững, không ghi đè giá trị đã có. `deploy/start.sh` dựng từ checkout hiện tại, có thể nạp hai archive lần đầu; update không truyền archive. Health kiểm cả DB, `/health` in revision của build.
- `backup --archive` xuất JSONL extended JSON kèm manifest; `restore` xác minh tên/tệp/JSON/ID/count trước ghi, mặc định chỉ nhận DB trống, tạo chỉ mục repository và kiểm đếm lại. Không ghi/seed vào nguồn. Một DB không có snapshot transaction xuyên collection; xuất khi đã dừng nhận lượt học mới.
- `storage_transfer` chuyển cả file tài liệu/âm thanh/runtime caches, không đưa backup và preview chưa duyệt vào gói. Kiểm archive, không nhận link/traversal, không ghi đè đích có dữ liệu.
- Repo GitHub công khai: code và hướng dẫn lên git, `.env`/DB/storage không vào build context hoặc git. Hai archive và hash bàn giao riêng cho DevOps.
- CI Linux chạy đúng script dựng/import; kiểm web, DB, tài khoản, file payload và từ chối import lần hai. Test dùng DB `cavat_test`, không dùng dữ liệu thật.

**Giới hạn:** chưa có tự động rollback import giữa DB và filesystem; lỗi I/O phải kiểm trạng thái trước khi tiếp tục. Compose trên một máy không phải HA. Ngưỡng dạy học và fallback model không đổi; thứ tự mặc định chỉ được đo trên 26 lượt, chưa có giáo viên chấm chất lượng giọng. Không phát hành lại kế hoạch hay tự duyệt DI/nội dung.
