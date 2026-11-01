# ADR-057: Chuỗi model không làm gia sư "vấp" khi model vẫn hoạt động

Ngày: 01/11/2026 · STEADY-1 · DI-99, DI-100

Chủ dự án phản ánh: gia sư hay báo lỗi, "chưa thể trả lời lúc này" hoặc "cô đang suy nghĩ" dù model vẫn ổn định.

## Dấu vết thực tế

[FACT] Đọc (chỉ đọc) 40 buổi gần nhất trong `cavat_dev`, từ 25/10 đến 30/10/2026: 739 lần gọi model, **95 lần (13%) không model nào trả lời**. Lý do: 46 lần hết hạn mức (`quota_exceeded`), 33 lần model không phản hồi (`model_unavailable`), 16 lần prompt quá dài. Học sinh thấy 17 thông báo chờ và 2 lần "Cô chưa thể giải thích tiếp".

[FACT] Hầu hết lỗi hạn mức là giới hạn **theo phút** của Groq: gpt-oss-120b 38 lần TPM, gpt-oss-20b 35 lần TPM, Qwen 18 lần ITPM. Groq báo thử lại sau khoảng 13–14 giây (`retry-after`). Router cũ chỉ chờ khi mốc hồi phục ≤ 6 giây, nên trả về rỗng và học sinh thấy "Con chờ cô một chút nhé".

[FACT] `gemini-3.8-flash` trả 503/504 liên tục: 25 lần gửi thật bị lỗi, 111 lần bị bỏ qua. Router cũ cho nghỉ 30 giây rồi gửi lại, mỗi lần tốn tới 10 giây timeout. Đo lại ngày 01/11: Groq trả lời trong 0,3–0,8 giây, `gemini-2.5-flash` 1,2 giây, `gemini-4-argon` hết hạn mức ngày, `gemini-3.8-flash` lỗi 503 rồi 504.

## Quyết định

- **DI-99.** Model không phản hồi (5xx, timeout, lỗi mạng) nghỉ 30 giây, mỗi lần lỗi liên tiếp nhân đôi, tối đa 5 phút; trả lời được một lần thì đếm lại từ đầu. Hạn mức (429) vẫn theo mốc provider báo, không đổi.
- **DI-100.** Khi cả chuỗi chỉ bị giữ bởi giới hạn ngắn, router chờ tới mốc hồi phục gần nhất rồi thử lại một lần: tối đa 15 giây cho một lần gọi (trước là 6 giây) và 20 giây cho cả một lệnh của học sinh (`RecordingRouter`), để một lượt có nhiều lần gọi không chờ cộng dồn quá lâu. Hạn mức ngày và mốc xa hơn vẫn trả về ngay như ADR-055.

Giữ nguyên thứ tự model của ADR-049, trần lượt gọi, prompt, chấm và mastery. Lệnh chạy trong threadpool nên việc chờ không chặn các học sinh khác.

## Kiểm chứng và giới hạn

Test offline: model lỗi liên tiếp nghỉ 30 → 60 giây và được đếm lại khi trả lời; giới hạn phút 13 giây được chờ và trả lời; mốc 40 giây trả về ngay; một lệnh không chờ quá 20 giây qua nhiều lần gọi.

[OPEN] Khi chạy song song nhiều học sinh, tổng token theo phút của ba model Groq (mỗi model 8.000) vẫn có thể không đủ; cách này chỉ giảm "vấp" do chờ quá ngắn chứ không tăng hạn mức. Groq tính hạn mức theo tổ chức: nếu server và máy phát triển dùng chung một khóa thì việc thử ở local ăn vào hạn mức của học sinh. Cần đo lại trên server sau khi triển khai.
