# ADR-030: Chế độ nói chuyện với gia sư bằng giọng nói (VOICE-1)

**Trạng thái:** Đề xuất, 2026-10-13.

- **Quyết định của chủ dự án (D-T12):** giọng nói quay lại demo. Repo tham khảo cho giọng cô: [VieNeu-TTS](https://github.com/pnnbao97/VieNeu-TTS) (Apache-2.0).
- **Code:**
  - `cavat/modules/voice/` (API `/v1/voice/*`, `speech_text.py`);
  - `ai_gateway/vieneu.py` (model class `TTS_VI`), `services/voice/server.py`;
  - web `features/student/voice/` (`useVoiceLive`, `VoiceBar`, `recorder`, `browserVoice`).
- **Liên quan:** ADR-016 (free-first), ADR-017 (vai trò model), quy tắc 2, 4, 6, 8 của CLAUDE.md.

## Bối cảnh

Chủ dự án muốn học sinh nói chuyện trực tiếp với gia sư: bé nói thay vì gõ, và nghe cô đọc lời giảng. Hệ thống đã có sẵn một số phần:
- model class `STT_VI` với Groq Whisper (`whisper-large-v3`, free tier);
- trường `modality: TEXT | VOICE` trong lệnh trả lời và trong sự kiện.

Chỉ còn thiếu giọng cô và vòng hội thoại bằng giọng nói.

## Quyết định

1. **Bộ nghe (STT_VI).**
   - Trình duyệt ghi một lượt nói của bé. Lượt dừng khi bé im lặng 1,5 giây, hoặc sau tối đa 20 giây. Nếu 8 giây không có tiếng nói thì bỏ lượt.
   - API `POST /v1/voice/transcribe` lưu bản ghi vào `var/storage/voice/in/<ngày>/<băm của học sinh>/` (như mọi file gốc), rồi gửi Groq Whisper.
   - Groq lỗi hoặc hết hạn mức thì dùng Web Speech API của trình duyệt (vi-VN).
2. **Lời của bé đi đúng đường của chữ gõ.**
   - Lệnh `/responses` gửi kèm `modality: VOICE`. Bộ điều phối, bộ chấm (`MathChecker`) và chính sách dạy giữ nguyên.
   - Whisper viết số bằng chữ số có dấu phẩy ("3,05"), nên bộ chấm đọc được ngay.
3. **Giọng cô (TTS_VI).**
   - VieNeu-TTS v3 Turbo chạy trên CPU qua ONNX Runtime, trong venv riêng `services/voice/.venv` (gói này kéo theo web stack riêng).
   - API gọi sang qua HTTP (`127.0.0.1:8010`), chỉ qua adapter trong `ai_gateway` (quy tắc 6).
   - Giọng mặc định: "Ngọc Huyền" (nữ, miền Bắc, tự nhiên), vì gia sư xưng "cô". Client không chọn được model hay giọng (quy tắc 4).
   - Nếu VieNeu không chạy hoặc `TTS=off`, trình duyệt đọc bằng giọng tiếng Việt của nó.
4. **Đọc đúng Toán** (`speech_text`, tất định): chữ gửi đi để đọc được viết lại theo cách giáo viên đọc.
   - Số và số thập phân: "3,05" thành "ba phẩy không năm". Phân số: "3/10" thành "ba phần mười".
   - Dấu: "<" thành "bé hơn"; "×", ":" thành "nhân", "chia" (dấu ":" chỉ đọc là "chia" khi có khoảng trắng hai bên).
   - Đơn vị: "cm²" thành "xăng-ti-mét vuông". Emoji bị bỏ.
   - Âm thanh được lưu đệm theo nội dung ở `var/storage/voice/tts/`.
5. **Vòng nói chuyện:**
   - Gia sư đọc từng tin mới theo từng câu; câu sau được tạo trong lúc đang phát câu trước.
   - Đọc xong thì tự mở micro nếu bé đang được mời trả lời.
   - Bé vẫn gõ được như thường, và có thể bấm micro để nói hoặc dừng.
   - Khi bé bật chế độ này, gia sư chỉ đọc tin cuối cùng, không đọc lại cả buổi.
6. **Giáo viên thấy:** bản ghi hội thoại gắn chip "Bé nói" cho lời đến từ giọng nói (`STUDENT_MESSAGE.modality = VOICE`).

## Kết quả đo (2026-10-13, Apple M1 Pro, CPU)

- **Tốc độ:** câu đầu sau khi bật server mất 9,1 giây cho 5,5 giây âm thanh (model mới khởi động). Từ câu thứ hai, 5,6 giây âm thanh tạo trong 4,2 giây.
- **Độ rõ:** cho Whisper nghe lại giọng VieNeu, nó chép lại gần đúng từng chữ:
  - "Con so sánh ba phẩy không năm và ba phẩy năm nhé…" nghe thành "Còn so sánh 3,05 và 3,5 nhé…";
  - "S bằng a nhân h chia hai" nghe thành "S bằng A nhân H chia 2".

## Hệ quả và giới hạn

- **Cài đặt:**
  - Lần đầu: `make voice-setup`, khoảng 780 MB cho venv.
  - Lần đầu bật server: model tải từ Hugging Face về `var/storage/voice/hf`, khoảng 540 MB.
  - `make demo` tự bật server giọng nói nếu đã cài.
- **Khóa phiên bản:** `onnxruntime==1.24.4` và `huggingface_hub==1.13.0`, đúng như repo VieNeu khóa. `huggingface_hub` 2.x lưu cache theo kiểu mới mà ONNX Runtime từ chối đọc.
- **Dữ liệu:** Groq nhận bản ghi giọng của bé (D-T3: chủ dự án cho phép dùng giọng thật). Nếu dùng Web Speech API của trình duyệt, âm thanh có thể đi qua máy chủ của hãng trình duyệt.
- **Chưa làm:**
  - Chưa ngắt lời: bé nói trong lúc cô đang đọc thì cô chưa dừng.
  - Phần ước lượng im lặng chỉ dựa vào độ to. Ở chỗ ồn có thể phải bấm micro.
