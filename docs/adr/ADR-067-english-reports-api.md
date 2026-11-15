# ADR-067: API báo cáo Tiếng Anh và nghe lại lượt nói (ENG-7b)

Ngày: 15/11/2026 · Trạng thái: **đề xuất, chờ chủ dự án duyệt** · Liên quan: ADR-059, ADR-060 (mục 8–9, DI-109, DI-113, DI-114), ADR-062, ADR-063, ADR-064, `docs/plan/english-module-rules.md` (F1–F5, S1, V3)

## 1. Bối cảnh

ENG-7a (PR #146) dựng giao diện Tiếng Anh Unit 11 bằng chính các trang của Toán, chạy trên mock, và liệt kê các trường API còn thiếu. ENG-7b nối các trang đó với API thật. Luật cứng của chủ dự án: luồng Toán không được đổi. API báo cáo của Toán phải trả JSON y hệt, trang Toán render y hệt.

## 2. Quyết định

**[REC] 2.1. Không viết view song song.** Trang Tiếng Anh gọi đúng các endpoint báo cáo của Toán với `?chapter=<unit>`: `GET /v1/students/me/overview`, `/v1/parents/children/{code}`, `/v1/parents/me/child`, `/v1/teachers/class`, `/v1/teachers/students/{id}`. Server tìm unit trong `chapter_service.chapters("english")` khi id không thuộc Toán. Môn lấy từ gói unit, client không gửi môn (S1). Các con số chung (projector, nhóm nút, DI-20, DI-113, bốn nhóm kết quả trong `activity`) đi qua đúng code của Toán.

**[REC] 2.2. Phần riêng của Tiếng Anh nằm ở module mới `cavat/modules/reports/english.py`.** Module này nhận view Toán đã tính xong và chỉ *thêm* trường. Mỗi endpoint chỉ có thêm một nhánh `if english_report.is_english(chapter)`, nên chương Toán không bao giờ đi qua module này.

**[REC] 2.3. Trường mới đều tùy chọn và không có mặt trong JSON khi trống.** Mixin `_OmitNone` trong model trả về bỏ các trường mới khi giá trị là `None`. Nhờ vậy response của Toán giống từng khóa với trước (kiểm bằng golden `tests/golden/math-reports-before-eng7b.json`, ghi trên `b0310d0` trước khi sửa).

| Trường | Ở đâu | Nguồn (event log, quy tắc 3) |
|---|---|---|
| `chapter.subject`, `chapters` | các view của unit | gói unit; `chapters` chỉ liệt kê unit Tiếng Anh |
| `nodes[]/going_well[]/to_practise[].pattern` | học sinh, phụ huynh | `Node.pattern` của unit (DI-144) |
| `current_step` | học sinh | `STEP_OF` của NODE_DECISION cuối trong buổi đang dở (ADR-059) |
| `home_tips[].example` | phụ huynh | câu tiếng Anh trích từ `home_tip` đã duyệt (DI-144) |
| `attention[]` kind `ASR_LOW`, `voice_turns`, `share`, `count` | giáo viên (lớp, học sinh) | VOICE_TURN_RECORDED.asr_confidence (DI-114 mục 3, DI-145) |
| `kpis.voice_share` | lớp | STUDENT_MESSAGE.modality (DI-145) |
| `activity[].voice_turns`, `asr_low` | học sinh (giáo viên) | VOICE_TURN_RECORDED theo ngày địa phương |
| `journey[].modality` | học sinh (giáo viên) | ITEM_RESOLVED.modality (ADR-064, E2) |
| `voice_turns[]` | học sinh (giáo viên) | VOICE_TURN_RECORDED + ANSWER_SUBMITTED + stem của item (DI-146) |

Phụ huynh không nhận `voice_turns`, bản chép lời, `audio_ref`, q hay điểm M (F4, PART 27.4). Trạng thái định tính DI-113 dùng chung bảng của Toán (`progress.quality`), không thêm gì. Nhãn "Cần ôn lại" chờ delayed probe.

**[REC] 2.4. `GET /v1/teachers/taught-chapters?subject=english`.** Lệnh này chọn danh sách để hiện (các unit, mỗi mục có `subject`). Không có tham số thì trả danh sách Toán như cũ (DI-124). Tham số không quyết nội dung view hay buổi học.

**[REC] 2.5. Nghe lại lượt nói: `GET /v1/teachers/voice/{audio_ref}`** (`cavat/modules/voice/replay.py`). Thứ tự kiểm, xong cả bốn bước mới đọc byte:

1. người gọi là giáo viên, còn học sinh và phụ huynh nhận 401/403;
2. `audio_ref` đúng dạng server ghi: `in/<ngày>/<16 hex>/<32 hex>.<webm|ogg|m4a|wav>`;
3. có một buổi học **của trường** (repository lọc `school_id`) đã ghi VOICE_TURN_RECORDED với đúng `audio_ref` đó, và mã băm trong đường dẫn khớp học sinh của buổi;
4. đường dẫn sau `resolve()` vẫn nằm trong `var/storage/voice/in`, kể cả khi có symlink.

Sai bất kỳ bước nào đều trả 404 với cùng một thông điệp. Response có `Cache-Control: private, no-store`. Audio vẫn nằm trên đĩa (V3).

**[REC] 2.6. Web.** `httpApi.getTurnAudio` gọi endpoint trên. `getTaughtChapters(subject?)` nhận thêm môn cho trang Tiếng Anh; trang Toán gọi không tham số như cũ. Mock Tiếng Anh (`englishDemo`) chỉ có trong `make web`; bản dựng cho API thật không nạp mock. Theo quyết định Q-E7 của chủ dự án, nhãn "Bản xem trước" của Tiếng Anh được bỏ: ô chọn môn ghi "Unit 11 · Family time", trang chủ ghi "Đang học được" và "Vào học Tiếng Anh".

## 3. Declared Interpretation

- **DI-144 (mẫu câu và câu nói ở nhà):** `pattern` là trường mới của `Node`, rỗng với Toán, điền cho 6 nút Unit 11 từ `name`/`description` đã duyệt (version unit 0.2.0 → 0.2.1). `example` là đoạn đầu tiên trong `home_tip` nằm giữa hai dấu nháy đơn và chỉ gồm chữ Latin, khoảng trắng và dấu câu. Đoạn tiếng Việt như 'hôm nay con làm gì?' bị bỏ qua. Không có đoạn nào như vậy thì không có `example`.
- **DI-145 (đếm lượt nói):** lượt "nghe chưa rõ" là lượt có q đã biết và q < 0,6. Lượt không có q (provider không trả metadata) không tính là thấp. Lượt đã sửa chữ (`edited`) vẫn tính vào số lượt nói. Cửa sổ 7 ngày của `ASR_LOW` gồm hôm nay và 6 ngày trước theo ngày Hà Nội. `share` làm tròn 2 chữ số. `voice_share` = số STUDENT_MESSAGE có `modality: VOICE` chia tổng STUDENT_MESSAGE của các em trong lớp, tính theo %, 1 chữ số thập phân; chưa có tin nhắn nào thì là `null`. Chỉ số này chỉ mô tả, không dùng để chấm.
- **DI-146 (danh sách lượt nói cho giáo viên):** sắp mới nhất trước, tối đa 50 lượt. `prompt` là stem của item khi `message_ref` là item của unit, nếu không thì là lời cô ngay trước lượt nói; cắt ở 240 ký tự theo ranh giới từ. `transcript` là `heard` nguyên văn. `outcome` lấy từ ANSWER_SUBMITTED đầu tiên của cùng item sau lượt nói, trước tin nhắn kế tiếp; không có thì là `null`. `teacher_override` luôn `false` vì chưa có chức năng giáo viên sửa lượt (ADR-060 mục 8).

## 4. Hệ quả

- Toán: golden API báo cáo khớp 7/7 response. DOM 256 test web Toán so với `main`: 231 giống hệt, 23 chỉ khác nhãn "Bản xem trước" đã bỏ (Q-E7), 2 chỉ khác giờ chạy test.
- Khi buổi học Tiếng Anh thật chạy (ENG-5b), danh sách buổi chung của giáo viên (`GET /v1/sessions`) cũng sẽ có buổi Tiếng Anh. Việc lọc hoặc gắn `subject` cho buổi là phần của ENG-5b; trang Tiếng Anh đã lọc theo `subject` khi server gửi trường này.
- `audio_ref` được tìm bằng truy vấn `events.payload.audio_ref` (không có index, quét theo trường). Cách này đủ cho quy mô một trường thử nghiệm; khi cần nhanh hơn thì thêm index.
