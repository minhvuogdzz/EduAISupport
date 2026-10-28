# ADR-042: Nói gọn và động viên phù hợp với trẻ

Ngày: 28/10/2026 · BRAIN-6 · DI-96

## Yêu cầu của chủ dự án

[FACT] Gia sư đã tự nhiên hơn nhưng còn vòng vo, dễ làm trẻ khó chịu. Chủ dự án yêu cầu điều tiết lời nói, biết khen, dỗ dành và động viên trẻ. Giữ giáo án và Socratic làm cốt lõi.

## DI-96 — Nhịp nói ngắn, ấm, bám vào bằng chứng

- `constitution.v11`, `brain/1.5.0`: thường 1–3 câu ngắn, nhắm 20–40 từ; chuyển bước/tiếp nhận chỉ cần một câu. Đây là nhịp diễn đạt, không ép model viết đủ số từ hay cắt cụt lời giải. Lý thuyết mới hoặc yêu cầu giảng kỹ vẫn được dài hơn trong trần hiện có.
- Mỗi lượt một ý/bước, nhiều nhất một ví dụ. Trả lời thẳng, bỏ lời dẫn dài, không kể lại lịch sử và không lặp cùng ý. Hỏi một bước vừa sức, không yêu cầu con xác nhận lại đáp số sai.
- Cho phép động viên cách thử có thật cả khi kết quả sai. Khi con nản/bực: trấn an ngắn rồi giúp ngay một bước. Không khen sai thành đúng, không gán trí thông minh hoặc tự suy diễn con đã làm đúng bước/chọn đúng cách khi con chưa nói cách làm. Lời “ok” chưa là bằng chứng hiểu. Khen đúng điều vừa làm được thay vì kết luận nắm vững cả bài.
- `listener.v3` nhận phản hồi cách giảng (dài quá, nói ngắn hơn) là REPAIR, không hỏi xác nhận lại ý muốn học/nghỉ. `curriculum-check.v2` kiểm cả căn cứ của lời động viên và quy tắc bằng lời đi kèm một ví dụ số học.
- Phần lý thuyết trả lời đúng: nhánh tri thức mới chỉ nói lời công nhận ngắn, không nối lại toàn bộ lời giải thích đã duyệt. Fallback cũng giữ lời công nhận ngắn. Điều này không tự bỏ câu hỏi hay bằng chứng mà vòng dạy yêu cầu.
- Ví dụ mẫu đổi số thập phân thành phân số thập phân viết gọn và có thể nói thẳng với con, giữ nguyên số học và yêu cầu không rút gọn. Chấm Toán, đồ thị, giáo án xuất bản, mastery, hint/completion và nguồn internet không đổi.

## Kiểm chứng và giới hạn

Regression kiểm phản hồi đúng không bị nối bài giảng, fallback ngắn và ranh giới động viên/khen đáp án sai/lộ đáp án. Chạy bộ regression offline với MONGODB_URI rỗng. Thử model thật bằng tình huống tổng hợp trong bộ nhớ, không gửi câu thử vào phiên học thật.

[FACT] Các lượt thử ban đầu vẫn gặp suy diễn cách làm, hỏi lại ý đã rõ và lời động viên không có bằng chứng; có bản nháp phải loại và dùng fallback. Không đánh đồng nói ngắn với dạy đúng hay coi vài lượt thử là chứng minh chất lượng mọi hội thoại. Quota và chất lượng từng model trong chuỗi vẫn ảnh hưởng kết quả.
