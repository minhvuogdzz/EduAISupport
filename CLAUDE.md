# CLAUDE.md — CAVAT AI Tutor (EduAISupport)

Tài liệu này dành cho mọi phiên Claude Code (local và cloud) làm việc trên repo này. Đọc trước khi làm bất kỳ việc gì.

## Dự án

- **Greenfield.** Không tiếp tục, refactor hay migrate codebase cũ nào (kể cả `MathAIsupport.v2` trên máy local; từ repo đó chỉ lấy 2 tài liệu đánh giá làm chuẩn).
- **Bối cảnh:** đồ án tốt nghiệp. Chủ repo làm một mình cùng AI; sản phẩm nội bộ để kiểm thử. **Chủ repo là giáo viên kiểm soát** và duyệt mọi đặc tả sư phạm, DI, item bank.
- **Pháp lý và dữ liệu trẻ em đã được chủ dự án xử lý** (hợp đồng luật sư đã ký). Không thêm track, bước chờ hay điều kiện chặn vì lý do pháp lý/consent. Được dùng dữ liệu thật, kể cả giọng nói học sinh, cho kiểm thử.
- **Free-first:** mặc định dùng dịch vụ miễn phí (free tier, mã nguồn mở, chạy local); xem ADR-016 và mục Revision trong `docs/blueprint/00-START-HERE.md`.
- **Vai trò model (ADR-017, ADR-018, ADR-034):** bộ não tutor là một chuỗi model cấu hình được (`TUTOR_MODELS`; thứ tự mặc định theo số đo ở ADR-034), không còn cố định Qwen: chủ dự án cho phép dùng model khác Qwen để gia sư trả lời thật (2026-10-26). Gemini vẫn dùng cho ảnh/OCR (hình học, đề bài chụp) và tạo vector embedding cho Hybrid RAG; chỉ vào chuỗi của tutor khi chủ dự án đặt tên model `gemini-*` vào `TUTOR_MODELS`. Không dùng LlamaParse. Prompt gửi Groq phải ≤ 3.000 token và đặt `reasoning_effort` đúng từng model (Qwen "none", gpt-oss "low"; model khác không gửi trường này), vì giới hạn 8.000 token/phút (`docs/poc/free-tier-quota.md`).
- **Phát triển chạy local, không dùng Docker.** Database là **MongoDB Atlas (gói M0)**. File gốc và audio lưu trên ổ đĩa (`var/storage/`, đã gitignore).
- **Triển khai lên server dùng Docker Compose (ADR-036, 2026-10-27, chủ dự án yêu cầu để devops chạy):** một image gồm web và API ở một cổng, kèm MongoDB trong compose (`cavat_prod`, có mật khẩu, không mở cổng ra ngoài). Devops đọc `deploy/README.md`: `sh deploy/setup.sh`, `docker compose up -d --build`, rồi nạp database bằng `docker compose run --rm app python -m cavat.restore /dump/<tệp>.tar.gz`. Chủ dự án tạo tệp database bằng `make db-pack` (chỉ đọc). **Repo là công khai**: tệp database có tài khoản và lời các em đã nói, nên nằm ở `db-dump/` (git bỏ qua) và đi qua kênh riêng, không bao giờ commit.
- **Scope khóa (D-T9):** demo gồm hai chương Toán lớp 5: **Số thập phân** và **Diện tích hình tam giác, hình thang**. English ra khỏi demo. **Giọng nói quay lại demo (D-T12, ADR-030, 2026-10-13):** chế độ "nói chuyện với cô" của học sinh, gồm bộ nghe Groq Whisper và giọng cô VieNeu-TTS chạy local (`make voice-setup`, `make voice`). Không tự mở rộng sang chương, lớp hoặc môn khác.
- **Nguyên tắc cốt lõi:** thiết kế *learning system* trước, đặt AI vào trong. **Socratic Tutor Mode** là mặc định và xuyên suốt: System Prompt + Tutor Policy/State Machine + Multi-level Hint Engine. LLM không tự quản lý session, hint level, completion hay mastery.
- **Blueprint (nguồn sự thật về thiết kế):** `docs/blueprint/00-START-HERE.md` → các file 01–15. Bản hiện hành là **v0.4**; mục Revision ở đầu 00 ghi đè v0.1 khi có mâu thuẫn.
- **Kế hoạch hiện hành (D-T10):** `docs/plan/plan-v1-teaching-knowledge-graph.md`. Gia sư phải **dạy** (lý thuyết và phương pháp) theo vòng 7 bước trên đồ thị tri thức; bài tập chỉ là một bước. Đọc trước khi làm task Mốc 1–3.
- **Tự xây kiến trúc AI (D-T11):** Hybrid RAG, đồ thị tri thức, chấm điểm, chính sách dạy, đọc tài liệu đều tự viết. Chỉ dùng API model qua `ai_gateway`. Không thêm framework RAG hay agent (LangChain, LlamaIndex...), dịch vụ vector database hay dịch vụ đọc tài liệu.
- **Việc giao cho phiên cloud:** `docs/tasks/BACKLOG.md`. Mỗi phiên làm một task. Nhóm tutor dùng chung hợp đồng `cavat/modules/tutor/contracts.py` và `cavat/core/events.py`, không định nghĩa lại.

## Chạy dự án

- Python 3.11+, venv ở `services/api/.venv`. Lệnh: `make setup`, `make test`, `make lint`, `make fmt`, `make api`, `make db-ping`, `make ai-ping`. `make api-memory` chạy API với database trong bộ nhớ (không ghi gì lên Atlas, dừng là mất). **Một cổng (REL-1, ADR-035):** `make run` dựng web nếu cần rồi chạy API phục vụ luôn giao diện ở http://localhost:8000 (đặt cổng bằng `PORT`; Ctrl+C dừng); buổi học và hội thoại được lưu vào database của `.env` (`cavat_dev`). `make run-memory` giống vậy nhưng database trong bộ nhớ (không lưu gì). `make demo` và `make demo-memory` là tên cũ của hai lệnh đó. Cho buổi thử có giám sát: `make doctor` (kiểm trước, chỉ đọc; `LIVE=1` gọi thử model), `make tunnel` (địa chỉ HTTPS công khai), `make backup` (xuất JSONL chỉ đọc), `make smoke`; xem `docs/pilot/README.md`. `make teach` trò chuyện với gia sư ngay trong terminal (vòng dạy chương Số thập phân, offline, không lưu gì). **Tài khoản (ACC-1, ACC-3):** giáo viên cố định đăng nhập bằng mã PIN (`make accounts`). Học sinh tự tạo tài khoản bằng tên đăng nhập + mã bí mật 4-8 chữ số (`POST /v1/auth/student/register`), lần sau nhập lại đúng cặp đó (`POST /v1/auth/login`), lịch sử lưu trong database. Phụ huynh dùng chung tài khoản của con (đăng nhập của con cho cả token phụ huynh, `role: PARENT`). Học sinh Vuong cũ của `make accounts` vẫn vào bằng tên "Vuong" hoặc `hocsinh` kèm PIN cũ. Khi deploy phải đặt `AUTH_SECRET` để token sống qua lần khởi động lại; tạo hoặc cập nhật bằng `make accounts` (ghi vào database của `.env`, không bao giờ tự tạo lúc khởi động hay trong test). `AUTH_MODE=demo` (header `X-Demo-*`) chỉ dùng cho test offline và `make run-memory`.
- Web app ở `apps/web` (React + TypeScript + Vite, pnpm, Node ≥ 22.13): `make web` (dev server, mock API), `make web-live` (dev server nối API thật ở cổng 8000, chỉ khi sửa giao diện; chạy thử thì dùng `make run`), `make web-check` (lint + test + build, như job `web` của CI). Đọc `apps/web/README.md` trước khi sửa.
- Secret nằm ở `services/api/.env` (gitignore; mẫu ở `.env.example`). Phiên cloud **không có** secret, nên test phải chạy offline, không cần Atlas hay Gemini. Test cần Atlas thật đánh dấu `@pytest.mark.atlas` và tự skip khi thiếu `MONGODB_URI`.

## Quy tắc thiết kế không được vi phạm

1. Policy quyết định *nước đi* (move, hint target × level); LLM chỉ *diễn đạt* và *đề xuất nhãn*. Mọi output LLM qua validator (lộ đáp án, một câu hỏi/lượt, độ dài, grounding, safety).
2. Đáp án item **assessment** không bao giờ nằm trong prompt. Đúng/sai Toán do `MathChecker` tất định (locale vi-VN, dấu phẩy thập phân).
3. Assessment và Student Model là **projection tất định, có version, replay được** từ event log append-only. LLM không bao giờ ghi trực tiếp mastery.
4. Backend enforce mọi ràng buộc session (SessionContext). Không bao giờ chỉ ẩn nút ở frontend. Client không bao giờ được chọn model.
5. Mọi document dữ liệu người học có `school_id`; repository bắt buộc lọc theo `school_id` (MongoDB không có RLS).
6. Business logic gọi AI qua `ai_gateway` theo *model class*. Không import SDK của vendor ngoài adapter.
7. Prompt, policy và mastery policy là artifact có version trong repo. Thay đổi chúng thì phải chạy eval regression.
8. Mặc định dùng lựa chọn miễn phí cho mọi model class (ADR-016); dịch vụ trả phí chỉ dùng khi chủ dự án yêu cầu hoặc làm mốc so sánh. Thiết kế phải chịu được hạn mức free tier (fallback chain, template, routing). Vẫn chỉ gửi AI dữ liệu tối thiểu (tên gọi, không họ).
9. Công thức hoặc ngưỡng không có trong hai khung đánh giá phải được đánh dấu **DI (Declared Interpretation)**.
10. Atlas M0 không có multi-document transaction: state và event của một buổi học nằm trong **một document** (ghi atomic), dùng `state_version` cho optimistic concurrency.

## Quy tắc bắt buộc về Database Test / Seed / Dữ liệu thật

11. **Tuyệt đối tách database test, demo và dữ liệu thật.** Không test, fixture, script seed hoặc migration nào được phép ghi vào `cavat_dev` hoặc `cavat_prod`.

12. **Atlas integration test:** mọi test chạm MongoDB Atlas thật phải được đánh dấu `@pytest.mark.atlas`. Test Atlas chỉ được phép chạy trên database riêng thuộc họ **`cavat_test`**: tên `cavat_test`, hoặc `cavat_test_<12 ký tự hex>` khi mỗi test dùng một database tạm riêng để cách ly (cách T07 đang làm).

13. Test Atlas phải có safety guard dạng **allow-list**: chỉ chấp nhận tên khớp `cavat_test` hoặc `cavat_test_<12 ký tự hex>`; tên khác thì test phải fail ngay trước khi thực hiện bất kỳ thao tác ghi hoặc xóa nào. Không viết guard dạng deny-list có hard-code tên `cavat_dev`/`cavat_prod` (xem quy tắc 20).

14. Test Atlas phải **tự dọn dữ liệu sau khi chạy**, kể cả khi assertion/test bị fail giữa chừng. Dùng fixture có cleanup trong `finally` hoặc cơ chế tương đương. Không để test data tồn dư làm ảnh hưởng lần chạy sau.

15. Phiên cloud mặc định **không có secret và không chạm Atlas**. Khi thiếu cấu hình Atlas, các test `@pytest.mark.atlas` phải tự `skip`; `make test` trong cloud vẫn phải chạy bình thường với test offline/in-memory.

16. Dữ liệu demo chỉ được tạo bằng lệnh explicit **`make seed`**. Không được:

* tự seed khi application startup;
* tự seed khi chạy test;
* tự seed trong migration;
* tự seed khi chạy `make test`;
* tự seed khi chạy `make api`.

17. **Mọi bản ghi do `make seed` tạo phải có `is_demo: true`.** Không được gắn `is_demo: true` cho dữ liệu học sinh thật.

18. Script `make seed` phải có khả năng xác định và xóa toàn bộ demo data dựa trên `is_demo: true` mà không ảnh hưởng dữ liệu thật.

19. Database dành cho phát triển thông thường là **`cavat_dev`**. Database production sau này là **`cavat_prod`**. Hai database này **không được dùng làm test database**.

20. Code test, fixture, POC và script cleanup không được chứa hard-code hoặc fallback tới `cavat_dev` / `cavat_prod`. Test phải có database name riêng và có safety guard.

21. Khi phát triển hoặc review T07/T08, phải phân biệt rõ:

* **in-memory repository test**: chạy offline;
* **Atlas integration test**: chạy MongoDB Atlas thật trên `cavat_test`;
* **demo seed**: chỉ chạy thủ công bằng `make seed`;
* **real development data**: nằm ở `cavat_dev`.

22. Trước khi merge PR của **T07 hoặc T08**, chủ repo phải chạy `make test` ở máy local với Atlas test database được cấu hình đúng. Điều kiện merge phải bao gồm kết quả xác nhận các test `@pytest.mark.atlas` đã chạy trên **`cavat_test`** và không có test/seed nào chạm `cavat_dev` hoặc `cavat_prod`.

23. Nếu phát hiện bất kỳ script/test nào có nguy cơ chọn nhầm database, **không được sửa bằng cách bỏ qua test**. Phải thêm safety guard hoặc sửa cơ chế chọn database trước khi merge.

24. Khi cần tạo test data trên Atlas, ưu tiên namespace/document IDs riêng cho test run và luôn cleanup sau test. Không sử dụng dữ liệu demo hoặc dữ liệu thật để làm fixture cho integration test.

25. Mọi thay đổi liên quan tới database isolation, test database, seed hoặc cleanup phải được xem là **infrastructure/data-safety change**, cần được ghi rõ trong PR description.


## Quy ước tài liệu

- Viết tiếng Việt; thuật ngữ kỹ thuật giữ tiếng Anh.
- Nhãn: **[FACT]**, **[REC]**, **[ASSUME]**, **[OPEN]**, **DI-n**.
- Quyết định kiến trúc mới → file ADR trong `docs/adr/`. Kết quả POC → `docs/poc/<tên>-decision.md`.
- Code POC nằm trong `poc/` và không được import vào `services/` hoặc `apps/`.

## Ghi chép cho luận văn (bắt buộc)

Chủ dự án yêu cầu ngày 2026-10-23: mọi việc làm được đều phải ghi vào tài liệu nguồn để viết luận văn, Google Doc "Tài liệu phục vụ viết luận" (https://docs.google.com/document/d/1SwopBTZyZ0ScSMqDLLpJBBd2x2OAvkFY4T37eumTJRc/edit, tab `t.0`).

- **Khi nào ghi:**
  - sau mỗi PR được merge;
  - sau mỗi bài đo, lần duyệt nội dung hay quyết định của chủ dự án, kể cả khi không có PR.
- **Ghi gì:**
  - thêm một mục vào cuối "Phụ lục E. Nhật ký công việc", tiêu đề `dd/mm/yyyy · MÃ-VIỆC (#PR): tóm tắt`;
  - mục gồm các ý vấn đề, cách làm, kết quả đo, kèm DI hoặc ADR liên quan;
  - nếu việc đó làm đổi nội dung các chương (kiến trúc, số liệu đánh giá, danh sách DI hoặc ADR, việc còn mở), sửa luôn chỗ đó trong chương tương ứng.
- **Cách ghi:**
  - dùng connector Google Docs và đọc tài liệu trước khi sửa;
  - không ghi đè phần chủ dự án viết;
  - nội dung tài liệu của giáo viên chỉ ghi bằng mã câu;
  - thông tin chưa kiểm chứng đánh dấu [cần kiểm tra].
- **Phiên không có connector Google Docs** (ví dụ phiên cloud):
  - viết sẵn mục nhật ký trong mô tả PR, dưới tiêu đề "Ghi chép luận văn";
  - phiên local kế tiếp chép mục đó vào tài liệu.

## Git

- Nhánh mặc định: `main`. Mỗi task làm trên nhánh `task/<mã>-<tên-ngắn>`, mở PR vào `main`, CI phải xanh.
- Không commit `.env` hoặc secret.
