# Triển khai CAVAT — bản có bộ não BRAIN-1

Web và API cùng một địa chỉ. Một image ứng dụng, MongoDB 7 trên mạng nội bộ Compose; tùy chọn Caddy cho HTTPS. `main` đã có REFORM-1…6, FLOW-1/2, BRAIN-1 và REL-1. FIG-1 (ADR-037) bổ sung ảnh câu hỏi từ PDF và nút duyệt/bỏ/thay hình. Gói dữ liệu sau FIG-1 phải có collection figures và thư mục storage/figures.

## Chạy lần đầu

Cần Docker Engine + Compose v2 trên Linux, Git, kết nối Internet tới Groq/Gemini. Máy này chưa có Docker; job `docker` trên GitHub CI thực hiện quy trình bên dưới trên Linux. Kết quả xác minh của bản bàn giao nằm ở `docs/releases/2026-10-27-deploy.md`.

```sh
git clone https://github.com/minhvuogdzz/EduAISupport.git
cd EduAISupport
sh deploy/setup.sh
nano .env
```

Điền `GROQ_API_KEY` và `GEMINI_API_KEY` do chủ dự án đưa. Setup đã sinh `MONGO_PASSWORD`, `AUTH_SECRET` và giữ chúng khi chạy lại. Gemini cần cho OCR/vector; bộ não trả lời dùng chuỗi Groq mặc định. Không gửi `.env` lên GitHub.

Chủ dự án đưa riêng hai tệp `cavat-db-<mốc>.tar.gz`, `cavat-storage-<mốc>.tar.gz` và `SHA256SUMS`. Đặt tất cả vào `db-dump/`, kiểm tra hash:

```sh
(cd db-dump && sha256sum -c SHA256SUMS)
sh deploy/start.sh cavat-db-<mốc>.tar.gz cavat-storage-<mốc>.tar.gz
```

Đổi `<mốc>` thành tên tệp thực. Lệnh start dựng image của checkout hiện tại, chờ Mongo sẵn sàng, kiểm tra cả hai gói, nạp DB, nạp tệp, tạo chỉ mục rồi chạy app và kiểm tra DB. Tất cả lệnh chạy tại gốc repo. Sau đó mở `http://<server>:8080`. Tài khoản và lịch sử giữ từ bản xuất; mã đăng nhập do chủ dự án giữ.

`docker compose` chỉ mở cổng app; Mongo không có cổng công khai. Dữ liệu tồn tại trong volume `cavat_mongo-data` và `cavat_app-data` khi container được cập nhật hoặc dừng. Bản ghi chưa thể khôi phục chỉ từ source GitHub: cần giữ cả hai gói bàn giao.

## Lệnh import riêng

Nếu DevOps đã dựng stack bằng `docker compose up -d --build`, có thể nhập thủ công:

```sh
docker compose run --rm --no-deps app python -m cavat.restore /dump/cavat-db-<mốc>.tar.gz --dry-run
docker compose run --rm --no-deps app python -m cavat.restore /dump/cavat-db-<mốc>.tar.gz
docker compose run --rm --no-deps app python -m cavat.storage_transfer restore /dump/cavat-storage-<mốc>.tar.gz
```

DB import đọc hết archive trước khi ghi: kiểm tên collection, JSON, `_id` không trùng, số bản ghi. Nó tạo chỉ mục của ứng dụng, đếm lại và trả mã 0 khi khớp. Mặc định từ chối DB đã có bản ghi (mã 2), không xóa dữ liệu. `--db tên` chọn DB khác. `--replace` là thao tác xóa/nạp lại các collection có trong archive, chỉ dùng khi người vận hành chủ động muốn phục hồi từ bản sao lưu đã kiểm tra.

Storage import kiểm tra toàn bộ đường dẫn và payload trước khi ghi, từ chối liên kết/path traversal và thư mục đích không trống. Không tự ghi đè tài liệu hiện có. Dry-run DB chỉ kiểm archive; dry-run storage kiểm cả archive và việc đích trống. Nếu một lần nạp lỗi do hết đĩa/mất mạng, xem log và kiểm trạng thái trước khi nạp lại; không tự xóa volume để thử lại.

Chưa có gói dữ liệu: `sh deploy/start.sh` dựng app với DB trống; chủ dự án phải tự tạo tài khoản/duyệt nội dung. Không seed tự động.

## Kiểm tra bản đang chạy

```sh
curl -fsS http://localhost:8080/health
curl -fsS http://localhost:8080/health/db
docker compose ps
docker compose logs --tail 100 app
```

`/health` có commit `revision` khi dựng bằng `deploy/start.sh`; `/health/db` phải trả `{"status":"ok"}`. Image chỉ được coi là healthy khi DB trả lời được. Web gọi `/v1/*` cùng origin, không phụ thuộc cổng Vite 5173 hay địa chỉ máy phát triển.

Bộ não được bật rõ bằng `TUTOR_RENDERER=llm`. `TUTOR_MODELS` trống dùng gpt-oss-120b → gpt-oss-20b → Qwen (ADR-034); có thể cấu hình lại thứ tự. Đây vẫn là hệ thống có fallback: model hết quota, lời bị validator bác hoặc buổi học chạm `MAX_LLM_CALLS_PER_SESSION` (buổi một bài: 40, DI-71) / `MAX_LLM_CALLS_PER_CHAPTER` (cả chương: 160, DI-90) thì dùng nội dung đã duyệt/câu mẫu. Không có bảo đảm mọi lượt đều do model viết. Thay đổi ngưỡng dạy/học vẫn thuộc quyền chủ dự án.

Giọng VieNeu nặng không nằm trong image này; phần nghe vẫn dùng Groq Whisper, phần đọc dự phòng dùng giọng trình duyệt khi máy có giọng tiếng Việt. Gói này không hứa giọng giống máy local. Hình học thật do FIG-1 cung cấp: nhập gói dữ liệu mới có ảnh; các hình REVIEW/REJECTED không hiện cho học sinh.

## HTTPS

Micro cần HTTPS (trừ localhost). Trỏ reverse proxy có sẵn vào app hoặc đặt `DOMAIN=ten-mien.vn` trong `.env`, trỏ DNS về máy chủ, mở 80/443 rồi chạy:

```sh
docker compose --profile https up -d
```

Dùng `PORT=127.0.0.1:8080` nếu chỉ reverse proxy trên máy cần truy cập app. App tin `X-Forwarded-*`, vì vậy reverse proxy phải ghi đè các header này và cổng backend chỉ được truy cập qua đường tin cậy.

## Cập nhật và vận hành

```sh
git pull --ff-only
sh deploy/start.sh                 # không truyền archive khi cập nhật: không nạp lại dữ liệu
docker compose logs -f app
docker compose down              # dừng, giữ nguyên volume
docker compose run --rm -it app python -m cavat.accounts
docker compose run --rm app python scripts/model_usage.py --days 1
```

Backup trước khi cập nhật, giữ lại commit/image trước để quay về khi cần. Không đổi `MONGO_PASSWORD` trong `.env` của volume Mongo đã khởi tạo: biến đó chỉ dùng tạo user lần đầu.

Sao lưu DB đang chạy (không đụng bản ghi):

```sh
docker compose exec -T mongo sh -c 'mongodump -u "$MONGO_INITDB_ROOT_USERNAME" -p "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin --db "$1" --archive --gzip' sh cavat_prod > cavat-mongo.archive.gz
```

Đổi tên DB cuối lệnh nếu đã đổi `MONGODB_DB`. Đây là archive của `mongodump`, phục hồi bằng `mongorestore`, không đưa cho `cavat.restore` (công cụ này chỉ nhận gói JSONL do `make db-pack` tạo). Sao lưu cả volume app-data; ngừng nhận lượt học mới trong lúc lấy cặp snapshot DB/tệp để tránh lệch thời điểm.

## Tạo gói từ máy chủ dự án

Tại checkout chính, với `services/api/.env` trỏ đúng DB nguồn và không có buổi học đang ghi:

```sh
make db-pack
make storage-pack
(cd db-dump && shasum -a 256 cavat-db-*.tar.gz cavat-storage-*.tar.gz > SHA256SUMS)
```

Nếu có nhiều lần xuất, chỉ giữ trong `SHA256SUMS` hai tên của lần bàn giao. Export chỉ đọc DB. Gói storage giữ documents, voice, rag, web, cache, figures; bỏ backup cũ, báo cáo thử nghiệm, model weights VieNeu ở `voice/hf` và hình preview chưa duyệt. Không có tài khoản API/`.env` trong image hay các archive này. Repo công khai nên dữ liệu được chuyển riêng tới DevOps, không commit, không đính vào PR/Release công khai.

BRAIN-4 (ADR-040): `ALLOW_TUTOR_KNOWLEDGE=true` cho gia sư giảng kiến thức Toán chuẩn ngoài đoạn RAG với lượt kiểm riêng, trong bài hiện tại và nền cần thiết. `false` giữ kiểm nguồn cũ. `WEB_LOOKUP=official` vẫn chỉ tra các ấn phẩm đã xác minh, không web tự do; `off` tắt truy xuất internet, không tự tắt kiến thức nền của model.

### Tìm lý thuyết trên web (BRAIN-7)

`WEB_LOOKUP=search` tìm trang mới liên quan bài học, đọc trang gốc rồi kiểm nguồn/Toán. Nguồn ưu tiên là SGK, nhà xuất bản, cổng/trường giáo dục trong danh mục; nguồn tham khảo được ghi riêng. Không mặc định tin mọi trang `.edu.vn` và không dùng snippet làm lời giảng.

Có thể đặt `TAVILY_API_KEY` trong `.env` server để dùng Search API; adapter dùng basic, không yêu cầu generated answer. Để trống thì thử công cụ tìm kiếm công khai, có thể bị chặn/trả sai chủ đề, rồi quay về các ấn phẩm cũ/tri thức nền có kiểm tra. Đây là fallback có giới hạn, không bảo đảm tương đương Search API. Không đưa key vào repo hoặc frontend. `WEB_LOOKUP=official` giữ đường hai ấn phẩm cũ; `off` tắt web. Trang lấy được không tự thêm vào RAG hoặc giáo án.
