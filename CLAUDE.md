# CLAUDE.md — CAVAT AI Tutor (EduAISupport)

Tài liệu này dành cho mọi phiên Claude Code (local và cloud) làm việc trên repo này. Đọc trước khi làm bất kỳ việc gì.

## Dự án

- **Greenfield.** Không tiếp tục, refactor hay migrate codebase cũ nào (kể cả `MathAIsupport.v2` trên máy local; từ repo đó chỉ lấy 2 tài liệu đánh giá làm chuẩn).
- **Bối cảnh:** đồ án tốt nghiệp. Chủ repo làm một mình cùng AI; sản phẩm nội bộ để kiểm thử. **Chủ repo là giáo viên kiểm soát** và duyệt mọi đặc tả sư phạm, DI, item bank.
- **Pháp lý và dữ liệu trẻ em đã được chủ dự án xử lý** (hợp đồng luật sư đã ký). Không thêm track, bước chờ hay điều kiện chặn vì lý do pháp lý/consent. Được dùng dữ liệu thật, kể cả giọng nói học sinh, cho kiểm thử.
- **Free-first:** mặc định dùng dịch vụ miễn phí (free tier, mã nguồn mở, chạy local); xem ADR-016 và mục Revision trong `docs/blueprint/00-START-HERE.md`.
- **Chạy local, không dùng Docker.** Database là **MongoDB Atlas (gói M0)**. File gốc và audio lưu trên ổ đĩa (`var/storage/`, đã gitignore).
- **Scope khóa:** Math Grade 5 + English Grade 5 (Reading + Speaking). Không tự mở rộng sang lớp hoặc môn khác.
- **Nguyên tắc cốt lõi:** thiết kế *learning system* trước, đặt AI vào trong. **Socratic Tutor Mode** là mặc định và xuyên suốt: System Prompt + Tutor Policy/State Machine + Multi-level Hint Engine. LLM không tự quản lý session, hint level, completion hay mastery.
- **Blueprint (nguồn sự thật về thiết kế):** `docs/blueprint/00-START-HERE.md` → các file 01–15. Bản hiện hành là **v0.3**; mục Revision ở đầu 00 ghi đè v0.1 khi có mâu thuẫn.
- **Việc giao cho phiên cloud:** `docs/tasks/BACKLOG.md`. Mỗi phiên làm một task.

## Chạy dự án

- Python 3.11+, venv ở `services/api/.venv`. Lệnh: `make setup`, `make test`, `make lint`, `make fmt`, `make api`, `make db-ping`.
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

## Quy ước tài liệu

- Viết tiếng Việt; thuật ngữ kỹ thuật giữ tiếng Anh.
- Nhãn: **[FACT]**, **[REC]**, **[ASSUME]**, **[OPEN]**, **DI-n**.
- Quyết định kiến trúc mới → file ADR trong `docs/adr/`. Kết quả POC → `docs/poc/<tên>-decision.md`.
- Code POC nằm trong `poc/` và không được import vào `services/` hoặc `apps/`.

## Git

- Nhánh mặc định: `main`. Mỗi task làm trên nhánh `task/<mã>-<tên-ngắn>`, mở PR vào `main`, CI phải xanh.
- Không commit `.env` hoặc secret.
