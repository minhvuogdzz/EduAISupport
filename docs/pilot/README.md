# Buổi thử có giám sát (REL-1)

Cách chạy bản mới nhất ở **một cổng** trên máy của chủ dự án và cho 2–3 học sinh vào thử qua đường hầm Cloudflare (ADR-035). Mọi lệnh chạy ở thư mục gốc của repo (checkout chính, nhánh `main` đã cập nhật).

## Trước buổi thử

1. `git pull` trên `main`, `make setup` nếu `pyproject.toml` đổi.
2. `make doctor`: không được có mục đỏ (✘). Mục vàng (!) đọc và chấp nhận có chủ ý. `make doctor LIVE=1` gọi thử mỗi model một lần (tốn rất ít hạn mức Groq); chạy một lần trước buổi thử.
3. `make backup`: sao lưu trước buổi (xem "Dữ liệu và sao lưu").
4. `make accounts` nếu cần tài khoản giáo viên mới hoặc muốn đặt lại PIN.
5. Trang giáo viên: các chương muốn thử đã được duyệt xuất bản (doctor in danh sách).
6. Terminal 1: `make run` (dựng web nếu mã mới hơn bản dựng, rồi bật API ở cổng 8000; có `make voice-setup` thì bật cả giọng cô, nội bộ).
7. Mở http://localhost:8000, tự đăng nhập thử một vòng: học sinh mới, một câu trả lời, nghe giọng cô.
8. Terminal 2: `make tunnel` in địa chỉ `https://….trycloudflare.com`. Gửi địa chỉ đó cho các em. Địa chỉ mới ở mỗi lần chạy.

Chỉ học trong nhà, cùng máy hoặc cùng mạng? Không cần bước 8: mở http://localhost:8000. Micro chỉ chạy trên HTTPS hoặc localhost.

## Trong buổi thử

- **Người ngồi cạnh:** mỗi em có một người lớn ngồi cạnh (chủ dự án hoặc người được chủ dự án nhờ). Người đó ghi lại điều em không hiểu, chỗ cô nói lạ, lúc em bỏ dở.
- **Dặn các em dừng sau 20–30 phút.** Chưa có trần thời gian của buổi học: nó không tự kết thúc. Mỗi buổi học tối đa 40 lần gọi model (`MAX_LLM_CALLS_PER_SESSION`), sau đó cô chỉ dùng câu mẫu.
- **Máy phải bật, có mạng.** `make tunnel` giữ máy không ngủ (`caffeinate -i`) khi nó đang chạy; đừng gập máy, đừng tắt Wi-Fi.
- **Theo dõi:**
  - trang giáo viên: cờ lo ngại (an toàn) và danh sách buổi học đang diễn ra;
  - terminal 1 (log API) cho lỗi 5xx;
  - `make model-usage DAYS=1`: mỗi buổi dùng bao nhiêu token, bao nhiêu lần 429 và chạm giới hạn nào (hạn mức Groq 8.000 token/phút, 200.000 token/ngày mỗi model);
  - nhiều hơn 2–3 em cùng lúc thì hạn mức phút của Groq là chỗ nghẽn đầu tiên: cô sẽ chuyển sang model dự phòng rồi câu mẫu.
- Một em gõ sai PIN 5 lần bị khóa tên đó 5 phút (`identity`); chờ, đừng khởi động lại server (khởi động lại làm mất cả bộ đếm).

## Sau buổi thử

1. Ctrl+C ở terminal tunnel (địa chỉ công khai chết ngay), rồi Ctrl+C ở terminal `make run`.
2. `make backup`.
3. **Đổi PIN** của giáo viên bằng `make accounts` (ai có địa chỉ và PIN đều vào được; học sinh tự đặt mã bí mật của mình nên mã đó chỉ lộ với người biết tên đăng nhập).
4. `make model-usage DAYS=1` và đọc cờ lo ngại, các buổi học bị bỏ dở; ghi vào nhật ký luận văn (mã câu, không nêu nội dung tài liệu).

## Dữ liệu và sao lưu

- Database là Atlas M0 (không có sao lưu tự động). `make doctor` báo vàng khi đang dùng `cavat_dev`: bài làm của các em nằm chung với dữ liệu phát triển. Chấp nhận được cho vài buổi thử có giám sát nếu có sao lưu trước và sau; học sinh thật lâu dài nên dùng `cavat_prod` (đặt `MONGODB_DB`, rồi `make accounts`, nhập lại tài liệu và duyệt lại).
- `make backup` chỉ đọc. Ghi mỗi bộ sưu tập thành `var/storage/backups/<thời điểm UTC>/<tên>.jsonl` (mỗi dòng một bản ghi, MongoDB extended JSON) cùng `manifest.json` và in số bản ghi. Thư mục này có tài khoản (PIN dạng băm scrypt) và lời các em nói: để trên máy này, quyền chỉ chủ máy đọc.
- Tệp gốc của thư viện tài liệu và âm thanh nằm ở `var/storage/` (không có trong database). Chép cả thư mục `var/storage` sang ổ khác (ví dụ `rsync -a var/storage/ /Volumes/<ổ>/cavat-storage/`).
- **Khôi phục** (DEPLOY-1, ADR-036): `cd services/api && .venv/bin/python -m cavat.restore ../../var/storage/backups/<thời điểm> --db <tên mới trống>`. Lệnh kiểm tra thư mục (hoặc tệp `.tar.gz` do `make db-pack` tạo), từ chối database đã có dữ liệu (thêm `--replace` để nạp đè đúng các bộ sưu tập có trong sao lưu), tạo chỉ mục và đếm lại với `manifest.json`. Khôi phục vào một database trống mới, không đè lên database đang dùng; rồi đặt `MONGODB_DB` sang tên đó, chạy `make doctor` và `make run`.
- **Chuyển lên server:** `make db-pack` tạo `db-dump/cavat-db-….tar.gz`; devops nạp bằng lệnh ở `deploy/README.md`.

## Khi có sự cố

| Dấu hiệu | Làm gì |
| --- | --- |
| Địa chỉ công khai không mở được | `make tunnel` còn chạy không? Đường hầm nhanh hay rớt: Ctrl+C và chạy lại, địa chỉ mới, gửi lại cho các em. |
| Cô trả lời bằng câu mẫu | Hạn mức Groq (429) hoặc buổi học chạm 40 lần gọi: `make model-usage DAYS=1`. Đợi hoặc dừng buổi. |
| Cô không có giọng | Máy chủ giọng chưa chạy: trình duyệt tự đọc bằng giọng máy, học vẫn tiếp tục. |
| Micro không hoạt động | Phải mở bằng địa chỉ HTTPS của đường hầm (hoặc localhost trên chính máy này). |
| Cần dừng gấp | Ctrl+C ở cả hai terminal. Buổi học đã lưu trong database; mở lại thì học tiếp. |
