# Bàn giao đầy đủ — 30/10/2026

## Phạm vi đối chiếu

- Main đã chứa REFORM/FLOW/BRAIN/FIG/REL, triển khai App/Mongo/Voice và các sửa recovery trước đó qua các PR đã merge, mới nhất #132. Các nhánh còn tên là lịch sử squash merge; không có PR đang mở lúc bắt đầu kiểm tra.
- Kiểm tra các worktree cũ: không có mã nguồn chưa commit cần gom; chỉ có các liên kết `.venv` ở snapshot cũ. Giữ main hiện hành, thêm các sửa lỗi của phiên này: trạng thái chờ, lời dẫn chuyển câu, ranh giới hỏi lý do, chặn nhầm ví dụ mở bài và lời nhắc im lặng.
- Kiến trúc: React/TypeScript → API FastAPI cùng origin; các module policy/chấm/mastery tất định; RAG/tài liệu/graph và hội thoại nằm trong database/storage; model ngoài qua gateway có fallback/quota; Groq Whisper nhận dạng lời nói; VieNeu HTTP nội bộ đọc lời cô đã được chuẩn hóa, cache theo giọng/nội dung.

## Dữ liệu đã xuất và kiểm tra

[FACT] Xuất chỉ đọc database nguồn `cavat_dev` lúc 10:02 ngày 30/10/2026 (giờ Việt Nam), khi không có API local đang ghi: 9.063 bản ghi, 16 collection. Gói storage có 340 tệp. Kiểm tra archive database bằng `restore --dry-run` và đọc toàn bộ archive storage không ghi đích: hợp lệ. Database được giữ cả các collection archive.

Các archive và gói `.env` nằm trong `db-dump/`, bị Git và Docker build context bỏ qua. Bản phát hành đầy đủ sẽ lấy mã nguồn theo SHA main sau merge. Không dùng dữ liệu thật làm fixture và không import kiểm thử vào database nguồn/production.

## Vận hành

Sau khi nhận và giải nén gói đầy đủ vào thư mục mới, chạy đúng hai lệnh:

```sh
docker compose build --pull
sh deploy/import.sh
```

Lệnh đầu dựng App + Voice; lệnh sau kiểm checksum, khởi động Mongo, nhập database/storage, tạo index rồi chờ App + Voice khỏe. Xem `deploy/README.md` cho cập nhật, reverse proxy/HTTPS và cách xử lý import vào đích đã có dữ liệu. CI không cần secret thật. Các kết quả CI và SHA phát hành được ghi trong PR và `RELEASE.json` của gói riêng.

## Kiểm tra local

- API và Voice: `pip check` không có dependency hỏng. Các image và CI dùng constraints từ runtime đã kiểm tra.
- Voice thật: VieNeu khởi động trên CPU, trả WAV mono 48 kHz, mẫu thử 2,8 giây. Kiểm tra STT và chuẩn hóa số qua test adapter/voice; nhận dạng trên microphone và độ trễ tải thật phải đo ở server.
- Web: lint, 254 test, typecheck và production build qua. Backend/eval, archive và database isolation: toàn bộ 2.321 test qua, gồm test Atlas trên database tạm có safety guard; không chạy test trên `cavat_dev`/`cavat_prod`. Kết quả Docker/Linux chính thức ở CI.

## Ghi chép luận văn

30/10/2026 · DEPLOY-4: xuất và kiểm tra gói dữ liệu hiện tại; đối chiếu nhánh đã merge; bàn giao source/env/DB/storage thành một gói riêng, triển khai hai lệnh; ghim dependency và kiểm tra voice xuyên mạng Compose trên CI. Giữ cơ chế policy/chấm/mastery và nguồn tài liệu hiện có. ADR-056 giải thích các quyết định triển khai. Mục này chờ chép vào tài liệu luận văn khi có connector Google Docs.
