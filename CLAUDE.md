# CLAUDE.md — CAVAT AI Tutor (EduAISupport)

Tài liệu này dành cho mọi phiên Claude Code (local và cloud) làm việc trên repo này. Đọc trước khi làm bất kỳ việc gì.

## Dự án

- **Greenfield.** Không tiếp tục, refactor hay migrate codebase cũ nào (kể cả `MathAIsupport.v2` trên máy local; repo đó chỉ chứa 2 tài liệu đánh giá được dùng làm chuẩn).
- **Scope khóa:** Math Grade 5 + English Grade 5 (Reading + Speaking). Không tự mở rộng sang lớp hoặc môn khác.
- **Nguyên tắc cốt lõi:** thiết kế *learning system* trước, đặt AI vào trong. **Socratic Tutor Mode** là mặc định và xuyên suốt: System Prompt + Tutor Policy/State Machine + Multi-level Hint Engine. LLM không tự quản lý session, hint level, completion hay mastery.
- **Blueprint (nguồn sự thật về thiết kế):** `docs/blueprint/00-START-HERE.md` → các file 01–15.

## Quy tắc thiết kế không được vi phạm

1. Policy quyết định *nước đi* (move, hint target × level); LLM chỉ *diễn đạt* và *đề xuất nhãn*. Mọi output LLM qua validator (lộ đáp án, một câu hỏi/lượt, độ dài, grounding, safety).
2. Đáp án item **assessment** không bao giờ nằm trong prompt. Đúng/sai Toán do `MathChecker` tất định (locale vi-VN, dấu phẩy thập phân).
3. Assessment và Student Model là **projection tất định, có version, replay được** từ event ledger append-only. LLM không bao giờ ghi trực tiếp mastery.
4. Backend enforce mọi ràng buộc session (SessionContext). Không bao giờ chỉ ẩn nút ở frontend. Client không bao giờ được chọn model.
5. Mọi bảng dữ liệu người học có `school_id` + RLS.
6. Business logic gọi AI qua `ai_gateway` theo *model class*. Không import SDK của vendor ngoài adapter.
7. Prompt, policy và mastery policy là artifact có version trong repo. Thay đổi chúng thì phải chạy eval regression.
8. Không đưa dữ liệu học sinh thật lên free tier của bất kỳ provider nào. Chỉ gửi AI dữ liệu tối thiểu (tên gọi, không họ, không PII khác).
9. Công thức hoặc ngưỡng không có trong hai khung đánh giá phải được đánh dấu **DI (Declared Interpretation)**.

## Quy ước tài liệu

- Viết tiếng Việt; thuật ngữ kỹ thuật giữ tiếng Anh.
- Nhãn: **[FACT]**, **[REC]**, **[ASSUME]**, **[OPEN]**, **DI-n**.
- Quyết định kiến trúc mới → file ADR trong `docs/adr/`. Kết quả POC → `docs/poc/<tên>-decision.md`.
- Code POC nằm trong `poc/` và không được import vào `services/` hoặc `apps/`.

## Git

- Nhánh mặc định: `main`. Làm việc trên nhánh riêng cho mỗi nhiệm vụ, mở PR.
- Không commit `.env` hoặc secret.
