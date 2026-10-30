# ADR-056: Gói bàn giao đầy đủ và hai lệnh trên server

Ngày: 30/10/2026. Theo yêu cầu chủ dự án, bổ sung ADR-036 và ADR-053.

- Gói riêng chứa mã nguồn từ đúng commit đã kiểm tra, `.env` điền sẵn, database JSONL, storage, SHA-256 và `RELEASE.json`. `git archive` tránh lấy khóa/tệp runtime ngoài ý muốn; công cụ từ chối working tree chưa commit. Không đẩy gói, dữ liệu hoặc secret lên GitHub công khai.
- Sau khi nhận và giải nén vào thư mục mới, devops chạy `docker compose build --pull` và `sh deploy/import.sh`. Lệnh import tự khởi động Mongo, nạp đích trống, tạo index, khởi động và chờ App + Voice khỏe. Không cần Node/Python/Mongo/voice cài trên host.
- API/web dùng chung image và origin. Mongo và VieNeu CPU ở mạng nội bộ, có volume riêng. Giữ cấu hình model/vision/embedding từ nguồn, giữ auth secret và admin đã đổi khỏi mặc định, sinh mật khẩu Mongo riêng. Không chuyển URI Atlas sang server. Giữ `.env` server hiện có khi cập nhật; không import lại vào volume đã có dữ liệu.
- Ghim dependency API và Voice bằng constraints riêng, web dùng pnpm lock. CI kiểm build/import cả stack, tạo WAV thật qua mạng từ app tới voice, cùng API/web/eval và voice riêng. Chỉ publish image sau CI thành công trên main; tag commit cho phép truy nguyên/rollback mã nguồn. Không tự ghi dữ liệu production từ CI.
- Các nhánh trước đã squash merge không được merge lại bản cũ. Bản release dựa trên main đã chứa các PR tương ứng, cộng sửa lỗi được kiểm tra trong phiên này. Không đưa môi trường `.venv` của các worktree cũ vào bản phát hành.

Giới hạn: cần Internet cho model API và lần tải weights đầu; microphone từ xa cần HTTPS/reverse proxy. Backup database và storage không phải snapshot nguyên tử: ngừng các tiến trình ghi khi xuất. Import không ghi đè database có dữ liệu; lỗi giữa chừng cần kiểm tra trước khi phục hồi. Kiểm chứng Docker/Linux thực hiện trên GitHub Actions vì máy phát triển không có Docker.
