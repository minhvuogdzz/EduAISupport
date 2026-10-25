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

## Token thật của prompt gia sư (đo 2026-10-25, CFG-2, ADR-032)

Nguồn: `make simulate` với `--measure` (học sinh mô phỏng chạy qua API thật, database trong bộ nhớ, Qwen thật), mỗi chương một buổi, đủ 15 lần gọi của trần. Mỗi lần gọi là một sự kiện `MODEL_CALLED` có số token Groq tính (`usage`), ước lượng của gateway và số ký tự. Số liệu thô: `var/storage/reports/model-calls.jsonl` (không commit).

**Mẫu nhỏ:** 35 lần gọi, 2 buổi, một con mô phỏng. Chỉ để kiểm tra ước lượng, chưa đủ để hiệu chỉnh.

| Model | Số lần | Ký tự lời nhắn / token thật | Ước lượng / thật (TB, nhỏ nhất–lớn nhất) | Prompt thật lớn nhất |
|---|---|---|---|---|
| `qwen/qwen3.8-27b` | 11 | 3,15 (2,85–3,24) | 1,14 (1,06–1,34) | 1.976 |
| `openai/gpt-oss-120b` | 8 | 2,76 (2,49–2,85) | 0,97 (0,92–0,99) | 2.294 |
| `openai/gpt-oss-20b` | 4 | 2,07 (1,83–2,38) | 0,87 (0,84–0,88) | 785 |

**Đọc kết quả:**
- Với Qwen, 3 ký tự/token **đếm dư** 14% (không lần nào đếm thiếu). Với gpt-oss-120b gần đúng, với gpt-oss-20b **đếm thiếu** khoảng 13%. Các lần gọi ngắn (`reading`, `move_choice`) tách ra ít ký tự/token hơn, vì phần lời nhắn cố định chiếm nhiều.
- Hồi quy `token = a + b × ký tự` trên Qwen: b = 0,2996 (tức 3,34 ký tự/token), a ≈ 60 token. Schema JSON chỉ có 3 kích thước nên không tách được phần của nó **[OPEN]**.
- Giữ `CHARS_PER_TOKEN = 3` (an toàn cho Qwen, bộ não chính). Prompt thật lớn nhất 2.294 token, dưới trần 3.000.
- Một lần gọi Qwen tốn trung bình 1.126 token (cả prompt và kết quả), thấp hơn con số ~2.000 ở trên. Một buổi 15 lần gọi tốn 13.000–16.000 token, nên 200.000 token/ngày đủ cho khoảng **12–15 buổi dùng LLM mỗi ngày** nếu chỉ tính Qwen (trước đây ước 6–7) **[ASSUME: 2 buổi]**.
- 12/35 lần gọi không model nào trả lời (`quota_exceeded`); 8 lần Groq trả 429 và 28 lần bị bỏ qua vì router biết model đang hết hạn mức. Con mô phỏng trả lời liên tục nên chạm hạn mức theo phút; trẻ thật chậm hơn. Nội dung lỗi 429 chưa được lưu nên chưa phân biệt được hạn mức phút và ngày **[OPEN]**.

## Gemini (chỉ dùng cho ảnh/OCR hình học và giọng nói)

Hạn mức tính theo **project**, nên tạo thêm khóa trong cùng project **không** tăng hạn mức.

| Model | Req/phút | Token/phút | Req/ngày |
|---|---|---|---|
| Gemini 3.8 Flash | 5 | 250K | **20** |
| Gemini 2.5 Flash | 5 | 250K | 20 |
| Gemini 2.5 Flash Lite | 10 | 250K | 20 |

**[FACT] 2026-10-12 (INGEST-1):**
- `gemini-2.5-flash-lite` trả 404 "no longer available to new users", và Google đề nghị dùng `gemini-3.5-flash-lite`.
- Đã thử `gemini-3.5-flash-lite` đọc trang PDF: đọc đúng cả hỗn số, qua kiểm chứng số (DI-43). Hạn mức của model này **[OPEN]**.
- Đọc ảnh và OCR dùng chuỗi `gemini-3.8-flash` → `gemini-2.5-flash` → `gemini-3.5-flash-lite`. Mỗi model có hạn mức ngày riêng.
- Đọc 31 trang tài liệu của chủ dự án làm hết 20 lần/ngày của `gemini-3.8-flash`.
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
