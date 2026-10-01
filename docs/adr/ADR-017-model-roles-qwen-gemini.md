# ADR-017 — Vai trò model: Qwen trên Groq là bộ não tutor, Gemini cho ảnh và giọng nói

**Trạng thái:** Đã chốt (quyết định của chủ dự án, 2026-10-01). Thay mục "mặc định" của TUTOR_REASONING trong PART 12.1 và ADR-016.

## Quyết định

| Model class | Mặc định | Dự phòng |
|---|---|---|
| TUTOR_REASONING (diễn đạt nước đi, phân tích câu "vì sao") | `qwen/qwen3.8-27b` trên Groq, `reasoning_effort: "none"`, JSON schema strict | `openai/gpt-oss-120b` trên Groq, sau đó câu mẫu đã duyệt |
| LIGHTWEIGHT (tóm tắt, phân loại, chuẩn hóa giọng nói) | `qwen/qwen3.8-27b` trên Groq | `openai/gpt-oss-20b` |
| EVAL_JUDGE và học sinh ảo dạng LLM | Groq (Qwen hoặc gpt-oss-120b) | — |
| STT tiếng Việt | `whisper-large-v3` trên Groq | Web Speech API của trình duyệt |
| VISION_OCR (ảnh hình học, đề bài chụp) | `gemini-3.8-flash` | — |
| REALTIME_VOICE (English Speaking) | `gemini-3.8-live` | Cascade: Whisper + Qwen + TTS trình duyệt |
| TTS | `SpeechSynthesis` của trình duyệt | `gemini-3.8-flash-tts` (10 req/ngày) |
| Phân tích tài liệu giáo viên (PDF/PPTX) | LlamaParse (LlamaCloud) | Gemini vision cho trang scan và hình vẽ |

## Lý do

- Hạn mức free của Gemini chỉ 20 request/ngày cho mỗi model, không đủ cho một buổi học. Groq cho 1.000 request/ngày.
- Groq mặc định không lưu dữ liệu suy luận. Gemini free dùng nội dung gửi lên để cải thiện sản phẩm.
- Gemini mạnh ở việc đọc ảnh và giọng nói realtime, Groq không có hai khả năng này.

## Hệ quả và ràng buộc

- **Prompt gọn:** Groq giới hạn 8.000 token/phút, nên mỗi lần gọi ≤ 3.000 token. Context Loading (PART 21.1) đổi thành nạp câu hỏi hiện tại cùng phần liên quan của bài, không nạp nguyên gói bài học.
- **Câu mẫu trước, LLM sau:** mỗi buổi tối đa `MAX_LLM_CALLS_PER_SESSION` lần gọi (mặc định 15). Hết lượt hoặc gặp lỗi 429 thì dùng câu mẫu đã duyệt, buổi học không bao giờ dừng vì nhà cung cấp.
- **Gateway** phải có adapter Groq (API tương thích OpenAI, gọi bằng HTTP) và adapter Gemini. Business logic không import SDK của nhà cung cấp (quy tắc 6).
- **Điều khoản:** điều khoản của Google cấm dùng trong ứng dụng có thể bị người dưới 18 tuổi truy cập. Groq cũng không hướng tới người dùng dưới 18 tuổi. Chủ dự án xác nhận với luật sư; thiết kế giữ được chế độ chỉ dùng câu mẫu, không cần gọi AI, ở luồng học sinh.
- Số đo cụ thể ở `docs/poc/free-tier-quota.md`.
