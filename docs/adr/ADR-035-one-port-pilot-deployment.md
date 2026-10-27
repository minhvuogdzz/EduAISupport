# ADR-035: Triển khai thử: một cổng, đường hầm, máy của chủ dự án (REL-1)

**Trạng thái:** Đã làm, 2026-10-26. Máy chủ 24/7 là việc sau (còn mở).
- Chủ dự án yêu cầu (2026-10-26): "gộp lại thành 1 cổng thôi, đừng có nhiều bản demo", và cuối cùng phải là bản mới nhất, tối ưu, để sau còn triển khai.
- Code: `cavat/webapp.py`, `cavat/webbuild.py`, `cavat/main.py` (`create_app`), `cavat/doctor.py`, `cavat/backup.py`, `cavat/tunnel.py`, `Makefile`, `services/api/scripts/smoke_one_port.py`, job `one-port` của CI.
- Tài liệu vận hành: `docs/pilot/README.md`. Liên quan: D-T6 (chạy trên máy chủ dự án, Cloudflare Tunnel), ADR-011, RK21 (máy tắt hay mất mạng giữa buổi), ADR-030 (giọng).

## Bối cảnh

`make demo` chạy hai tiến trình (Vite dev server ở 5173 chuyển `/v1` sang API ở 8000) cộng máy chủ giọng ở 8010. Dev server không đi qua đường hầm được (`allowedHosts`) và không nên phơi ra ngoài; học sinh dùng máy khác cần HTTPS cho micro. Nhiều lệnh (`demo`, `demo-memory`, `web-live`, `api`) dẫn tới nhiều bản chạy cùng lúc.

## Quyết định

1. **Một cổng.** `make run` dựng web (`VITE_API=http`) khi bản dựng cũ hơn mã hoặc không do lệnh này dựng, rồi chạy API (uvicorn, không `--reload`) ở `PORT` (mặc định 8000). API phục vụ `apps/web/dist`: `assets/*` có băm tên nên cache một năm, các tệp khác `no-cache` (ETag), `index.html` cho đường dẫn của giao diện, JSON 404 cho `/v1`, `/health` và các đường dẫn docs. `make run-memory` là bản không lưu. `make demo`, `make demo-memory` giữ làm bí danh. Máy chủ giọng chạy nội bộ 127.0.0.1:8010 do `make run` bật nếu có; trình duyệt chỉ nói chuyện với một cổng (giọng đã đi qua `/v1/voice`).
2. **Cấu hình chạy thật.** Nén gzip (không nén audio), `X-Content-Type-Options`, `Referrer-Policy: same-origin`, `X-Frame-Options: DENY` và `frame-ancestors 'none'`. Không có CORS: giao diện và API cùng nguồn. `/docs`, `/redoc`, `/openapi.json` tắt trừ khi `API_DOCS=1`. Cách đăng nhập và giới hạn thử PIN không đổi.
3. **Đường hầm: Cloudflare quick tunnel** (`make tunnel`), HTTPS miễn phí, không tài khoản, địa chỉ ngẫu nhiên đổi mỗi lần. `caffeinate -i -w` đi kèm đường hầm. Lý do không chọn: mở cổng trên router (không HTTPS), ngrok (cần tài khoản), tunnel có tên (cần tên miền, để dành cho máy chủ 24/7).
4. **Công cụ buổi thử:** `make doctor` (chỉ đọc; đỏ khi thiếu khóa, đăng nhập không phải `accounts`, Mongo không lên, thiếu tài khoản giáo viên, cổng bận, đĩa dưới 1 GB; vàng cho `cavat_dev`) và `make backup` (xuất JSONL chỉ đọc; chưa có `restore`, cách khôi phục tay ở `docs/pilot/README.md`).
5. **Chưa làm (cố ý):** trần thời gian buổi học (dặn các em dừng sau 20–30 phút), giới hạn tạo tài khoản học sinh (ai có địa chỉ đều tự tạo được), tự khởi động lại, sao lưu tự động, máy chủ 24/7.

## Rủi ro còn lại

- RK21: máy ngủ, tắt hay mất mạng giữa buổi thì cả buổi mất kết nối. `caffeinate` chỉ chống ngủ do nhàn rỗi.
- Địa chỉ công khai: ai có địa chỉ và PIN đều vào; đổi PIN sau buổi thử.
- `cavat_dev` chứa cả dữ liệu thật của các em: sao lưu trước và sau.
- Một process uvicorn, trạng thái khóa PIN nằm trong bộ nhớ: khởi động lại xóa bộ đếm.
