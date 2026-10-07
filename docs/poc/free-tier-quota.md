# Hạn mức free tier đã đo (2026-10-01)

Nguồn: ảnh chụp trang AI Studio của chủ dự án (project `Aldevhouse`, Free level), header `x-ratelimit-*` trả về khi gọi thật Groq, và [trang rate limits của Groq](https://console.groq.com/docs/rate-limits). Hạn mức có thể đổi, cần đo lại trước mỗi đợt kiểm thử.

## Groq (Qwen, bộ não chính của tutor; Whisper)

Hạn mức tính theo **tổ chức**, không theo khóa.

| Model | Req/phút | Req/ngày | Token/phút | Token/ngày | Ghi chú |
|---|---|---|---|---|---|
| `qwen/qwen3.8-27b` | 30 | 1.000 | **8.000** | 200.000 | Header thật xác nhận 1.000 req/ngày và 8.000 token/phút |
| `openai/gpt-oss-120b`, `gpt-oss-20b` | 30 | 1.000 | 8.000 | 200.000 | Dự phòng |
| `whisper-large-v3`, `whisper-large-v3-turbo` | 20 | 2.000 | — | — | 7.200 giây âm thanh/giờ, 28.800 giây/ngày |
| `canopylabs/orpheus-v1-english` (TTS) | 10 | 100 | 1.200 | 3.600 | Quá nhỏ để làm giọng đọc chính |

**Hệ quả thiết kế:**
- **Prompt phải gọn**, mục tiêu ≤ 3.000 token mỗi lần gọi. Một request vượt 8.000 token sẽ không bao giờ chạy được. Không nạp nguyên gói bài học vào prompt.
- **Suy luận của Qwen phải tắt** (`reasoning_effort: "none"`). Đo thật trên cùng một câu hỏi: để mặc định thì bị trừ khoảng **392 token** (phần suy luận vẫn bị tính dù đã ẩn), tắt thì chỉ **148 token**, câu trả lời vẫn đúng ý.
- `response_format: json_schema` với `strict: true` hoạt động với Qwen trên Groq.
- 200.000 token/ngày với khoảng 2.000 token mỗi lần gọi cho khoảng 100 lần gọi mỗi ngày, và với trần 15 lần gọi mỗi buổi cho khoảng **6–7 buổi học dùng LLM mỗi ngày**. Các buổi khác chạy bằng câu mẫu.

## Gemini embedding (Hybrid RAG, đo 2026-10-07)

- `gemini-embedding-001`, 768 chiều.
- Gửi liền 67 request, mỗi request một câu, trong khoảng 37 giây: 8 request bị **429**.
- Gom lô (tối đa 64 văn bản mỗi request): 3 request cho 113 văn bản, không lỗi.
- Hạn mức theo ngày chưa thấy trên AI Studio **[OPEN]**.
- **Hệ quả:** RAG gom lô khi dựng chỉ mục và lưu đệm mọi vector, nên mỗi đoạn và mỗi câu chỉ gọi một lần. Lúc học, mỗi câu học sinh hỏi tốn một request. Gặp 429 thì lượt đó chạy bằng từ khóa và cấu trúc.

## Gemini (chỉ dùng cho ảnh/OCR hình học và giọng nói)

Hạn mức tính theo **project**, nên tạo thêm khóa trong cùng project **không** tăng hạn mức.

| Model | Req/phút | Token/phút | Req/ngày |
|---|---|---|---|
| Gemini 3.8 Flash | 5 | 250K | **20** |
| Gemini 2.5 Flash | 5 | 250K | 20 |
| Gemini 2.5 Flash Lite | 10 | 250K | 20 |
| Gemini 2.5 Flash TTS | 3 | 10K | 10 |
| `gemini-3.8-live` và các model còn lại | **[OPEN]** | | Ảnh bị cắt, cần chụp thêm |

## Giọng nói tiếng Việt (Whisper trên Groq), thử nhanh

Đầu vào là giọng đọc tiếng Việt có sẵn trên macOS (giọng người lớn, **không phải giọng trẻ em**), câu "Không phẩy hai lăm bé hơn không phẩy ba, vì ở hàng phần mười, hai bé hơn ba."

| Model | Kết quả |
|---|---|
| `whisper-large-v3` | "0,25 bớ hơn 0,3, vì ở hàng phần 10, 2 bớ hơn 3." |
| `whisper-large-v3-turbo` | "0,25 bớ hơn 0,3, vì ở hàng phần 10, hay bớ hơn 3." |

**Nhận xét:**
- Số thập phân ra đúng dạng vi-VN (0,25).
- "bé" bị nghe thành "bớ", nên bộ chuẩn hóa giọng nói phải sửa các lỗi này. Bước xác nhận lại câu trả lời bằng giọng nói (PART 20.2) là bắt buộc.
- Bản turbo đọc sai "hai" thành "hay", nên mặc định dùng `whisper-large-v3`.
- Chưa thử giọng trẻ em thật. Việc này thuộc spike STT ở T11.

## Điều khoản cần chủ dự án lưu ý (không chặn kỹ thuật)

- **Gemini API** ([Terms](https://ai.google.dev/gemini-api/terms)):
  - Mục "Age Requirements" cấm dùng trong ứng dụng hướng tới hoặc có khả năng bị người dưới 18 tuổi truy cập.
  - Mục "Unpaid Services": nội dung gửi lên gói free được dùng để cải thiện sản phẩm.
- **Groq:** [Terms of Use](https://groq.com/terms-of-use) không nói về tuổi. [Privacy Policy](https://groq.com/privacy-policy) ghi dịch vụ không hướng tới trẻ dưới 18 tuổi. Theo [trang dữ liệu](https://console.groq.com/docs/your-data), Groq mặc định không lưu dữ liệu suy luận và có chế độ Zero Data Retention.
