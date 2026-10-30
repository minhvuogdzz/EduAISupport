# Bàn giao triển khai CAVAT

CAVAT chạy bằng Docker Compose: `app` phục vụ web và API cùng cổng, `mongo` lưu database, `voice` chạy VieNeu-TTS trên CPU; Mongo và voice chỉ ở mạng nội bộ. Groq Whisper xử lý nhận dạng giọng nói. Các volume giữ dữ liệu qua các lần cập nhật.

## Triển khai lần đầu

Cần Docker Engine, Compose v2 và Internet để tải image/model và gọi các API đã cấu hình. Chủ dự án chuyển **riêng** gói đầy đủ `cavat-handoff-latest.tar.gz` qua kênh an toàn. Giải nén vào **thư mục mới** trên server: gói đã có mã nguồn đúng commit, Dockerfile, Compose, `.env` điền sẵn và `db-dump/`. Không cần cài Node, Python, Mongo hoặc VieNeu trên host. `.env` chứa khóa API, mật khẩu Mongo, khóa ký token và mật khẩu quản trị; không đưa lên GitHub. `RELEASE.json` ghi SHA mã nguồn và hai lệnh vận hành.

Tại thư mục gốc repo trên server, DevOps chỉ cần chạy:

```sh
# 1. Dựng các image App và Voice
docker compose build --pull

# 2. Nạp dữ liệu, tự khởi chạy và chờ App + Mongo + Voice sẵn sàng
sh deploy/import.sh
```

Không cần sửa `.env` cho lần triển khai mới: khóa API, chuỗi model, OCR/vector, giới hạn lượt, giọng đọc và cấu hình tra cứu được giữ từ máy nguồn; mật khẩu Mongo được sinh riêng. Khóa ký đăng nhập và mật khẩu admin nguồn (nếu đã đổi khỏi mặc định) được giữ. URI Atlas và tên database phát triển không chuyển sang server; đích là Mongo nội bộ `cavat_prod`.

Lệnh import kiểm tra SHA-256, dừng app trong lúc nhập, kiểm tra hai archive, nạp database và storage vào đích trống, tạo chỉ mục, rồi khởi động App và Voice, chờ health check tối đa 15 phút để tải model lần đầu. Nếu nhập thất bại, app có thể vẫn dừng và dữ liệu có thể đã nhập một phần: xem log và kiểm tra trạng thái trước khi quyết định phục hồi; không tự xóa volume. Không chạy lại import khi cập nhật. Gói cấu hình/dữ liệu kiểu cũ vẫn có thể chuẩn bị bằng `python3 deploy/unpack_handoff.py <gói>` từ checkout; gói đầy đủ mới không cần công cụ này.

Mở `http://<server>:8080`. Lấy `ADMIN_PASSWORD` trong `.env` qua kênh riêng. `AUTH_SECRET` được giữ từ cấu hình nguồn nếu đã có; đổi nó sẽ khiến token hiện tại hết hiệu lực. Không thay `MONGO_PASSWORD` sau khi Mongo volume đã được khởi tạo nếu chưa đổi mật khẩu trong Mongo.

## Giọng nói và HTTPS

Voice tải model từ Hugging Face lần đầu và lưu vào volume `voice-models`; việc tải có thể mất nhiều phút và cần thêm dung lượng đĩa. Lệnh import chờ cả App và Voice khỏe trước khi báo thành công. Kiểm tra `docker compose ps` và `docker compose logs voice`; nếu voice không hoạt động khi đang vận hành, trình duyệt dùng giọng dự phòng. Việc nhận dạng giọng nói cần `GROQ_API_KEY`. Cần kiểm thử chất lượng giọng và độ trễ trên phần cứng server thật.

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

Với `services/api/.env` trỏ đúng database nguồn, dừng buổi học và các tiến trình ghi trong suốt quá trình xuất cả database và storage: hai bản này không phải snapshot nguyên tử.

```sh
make db-pack
make storage-pack
services/api/.venv/bin/python deploy/prepare_handoff.py db-dump/cavat-db-<mốc>.tar.gz db-dump/cavat-storage-<mốc>.tar.gz --include-source
```

Chọn đúng hai archive vừa tạo. Với `--include-source`, script từ chối working tree chưa commit; lấy mã nguồn bằng `git archive HEAD`, không sao chép môi trường làm việc. Script tạo thư mục `db-dump/handoff-<mốc>/` và gói nén một tệp `db-dump/cavat-handoff-latest.tar.gz` chứa mã nguồn, `.env`, hai archive và SHA-256. Chỉ xuất gói bàn giao chính thức từ commit đã merge và CI xanh. Chuyển tệp này qua kênh riêng tới DevOps. Archive database là JSONL được `cavat.restore` xử lý; nó không phải `mongodump`. Gói storage gồm tài liệu, âm thanh và hình; model weights được tải riêng vào volume. Tất cả dữ liệu, `.env` và gói bàn giao đều bị Git bỏ qua.

Mỗi lần tạo gói sinh mật khẩu Mongo mới; gói `.env` mới dành cho server khởi tạo lần đầu. Với server đã có volume, giữ nguyên `.env` và mật khẩu hiện hành, chỉ cập nhật mã nguồn/image và không chạy import. Các index do ứng dụng khai báo được tạo lại khi import; metadata và index tùy chỉnh ngoài ứng dụng không được bảo toàn.

CI kiểm tra API, web, đúng hai lệnh build/import trên Linux, App gọi Voice qua mạng Compose và nhận WAV thật; có job voice riêng để phát hiện lỗi thư viện/model. Dependency Python được ghim bằng `constraints.txt` riêng cho API và Voice, web dùng pnpm lock. Thành công trên CI không thay thế việc kiểm tra HTTPS, DNS, keys, quota, model download và tải thực tế trên server.

Sau khi CI của commit trên `main` thành công, workflow Publish images dựng và đưa `cavat-app` và `cavat-voice` lên GitHub Container Registry với tag `latest` và SHA commit. Workflow này không tự triển khai lên server; server vẫn có thể build từ checkout bằng hai lệnh ở trên. Việc publish phụ thuộc quyền ghi Packages của GitHub Actions.
