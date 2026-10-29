# Bàn giao triển khai CAVAT

CAVAT chạy bằng Docker Compose: `app` phục vụ web và API cùng cổng, `mongo` lưu database, `voice` chạy VieNeu-TTS trên CPU; Mongo và voice chỉ ở mạng nội bộ. Groq Whisper xử lý nhận dạng giọng nói. Các volume giữ dữ liệu qua các lần cập nhật.

## Triển khai lần đầu

Cần Docker Engine và Compose v2, Internet để tải image/model và gọi các API đã cấu hình. Chủ dự án chuyển **riêng** `.env` và thư mục `db-dump/` từ gói bàn giao; đặt chúng vào thư mục gốc của checkout. `.env` chứa khóa API, mật khẩu Mongo, khóa ký token và mật khẩu quản trị; không đưa lên GitHub. Nếu có dữ liệu đang được ghi khi export, dừng buổi học và xuất lại cả database lẫn storage để có ảnh chụp nhất quán.

Tại thư mục gốc repo trên server, chạy hai lệnh:

```sh
docker compose up -d --build
sh deploy/import.sh
```

Lệnh thứ hai kiểm tra SHA-256, dừng app trong lúc nhập, kiểm tra hai archive, nạp database và storage vào đích trống, tạo chỉ mục, rồi khởi động lại app và chờ health check. Nó từ chối ghi đè dữ liệu. Nếu nhập thất bại, app có thể vẫn dừng và dữ liệu có thể đã nhập một phần: xem log và kiểm tra trạng thái trước khi quyết định phục hồi; không tự xóa volume. Không chạy lại import khi cập nhật.

Mở `http://<server>:8080`. Lấy `ADMIN_PASSWORD` trong `.env` qua kênh riêng. `AUTH_SECRET` được giữ từ cấu hình nguồn nếu đã có; đổi nó sẽ khiến token hiện tại hết hiệu lực. Không thay `MONGO_PASSWORD` sau khi Mongo volume đã được khởi tạo nếu chưa đổi mật khẩu trong Mongo.

## Giọng nói và HTTPS

Voice tải model từ Hugging Face lần đầu và lưu vào volume `voice-models`; việc tải có thể mất nhiều phút và cần thêm dung lượng đĩa. App không chờ voice, để giao diện có thể chạy trong lúc model khởi động. Kiểm tra `docker compose ps` và `docker compose logs voice`; nếu voice chưa sẵn sàng hoặc không hoạt động, trình duyệt dùng giọng dự phòng. Việc nhận dạng giọng nói cần `GROQ_API_KEY`. Cần kiểm thử chất lượng giọng và độ trễ trên phần cứng server thật.

Microphone trong trình duyệt cần HTTPS (hoặc localhost). Trỏ DNS về server, cấu hình `DOMAIN` trong `.env`, mở cổng 80 và 443, rồi bật Caddy:

```sh
docker compose --profile https up -d
```

Có thể dùng reverse proxy HTTPS sẵn có. Đặt `PORT=127.0.0.1:8080` để app chỉ nhận kết nối từ máy chủ; proxy phải ghi đè các header `X-Forwarded-*` và không cho truy cập trực tiếp từ mạng không tin cậy.

## Kiểm tra và vận hành

```sh
curl -fsS http://localhost:8080/health
curl -fsS http://localhost:8080/health/db
docker compose ps
docker compose logs --tail 100 app voice
```

`docker compose down` giữ volumes; không dùng `down -v` trên server có dữ liệu. Cập nhật bằng `git pull --ff-only` và `docker compose up -d --build`. Sao lưu cả Mongo và `app-data` trước cập nhật, và dừng ghi trong lúc lấy cặp backup. Các key Gemini và Tavily là tùy chọn; thiếu Gemini làm mất OCR/vector. `TTS=off` dùng giọng trình duyệt.

## Tạo gói bàn giao trên máy chủ dự án

Với `services/api/.env` trỏ đúng database nguồn, không có buổi học đang ghi:

```sh
make db-pack
make storage-pack
services/api/.venv/bin/python deploy/prepare_handoff.py db-dump/cavat-db-<mốc>.tar.gz db-dump/cavat-storage-<mốc>.tar.gz
```

Chọn đúng hai archive vừa tạo. Script tạo thư mục `db-dump/handoff-<mốc>/` có `.env`, hai archive và SHA-256. Chuyển nội dung thư mục này qua kênh riêng tới DevOps. Archive database là JSONL được `cavat.restore` xử lý; nó không phải `mongodump`. Gói storage gồm tài liệu, âm thanh và hình; model weights được tải riêng vào volume. Tất cả dữ liệu, `.env` và gói bàn giao đều bị Git bỏ qua.

CI kiểm tra API, web, build/import Compose và build/khởi động voice cùng một mẫu WAV. Thành công trên CI không thay thế việc kiểm tra HTTPS, DNS, keys, quota, model download và tải thực tế trên server.
