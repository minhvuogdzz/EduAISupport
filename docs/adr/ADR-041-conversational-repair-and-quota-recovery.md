# ADR-041: Tiếp nối lời học sinh và hồi model đúng hạn mức

Ngày: 28/10/2026 · BRAIN-5 · DI-94, DI-95

## Vấn đề đã quan sát

[FACT] Sau BRAIN-4, phiên thử thật vẫn có xác nhận bị hỏi lại, lời tiếp nhận bị đoán thành lỗi gõ, giảng lại bằng cùng đoạn định nghĩa và fallback do quota. Đã đọc snapshot chỉ đọc với bộ lọc school_id; không công khai lời/tên học sinh hoặc sửa lịch sử. Chưa chạm trần 160; không thể quy mọi lỗi cho hết trần buổi.

[FACT] Bộ nghe ở phần dạy nhận câu hỏi giáo án thay vì lời cô vừa phát. Hàm lấy lịch sử luôn bỏ event cuối ngay cả trước khi thêm lời học sinh, nên có thể thiếu lời cô cần để hiểu xác nhận. Kiểm lặp dùng cả bốn từ mở đầu làm điều kiện loại. Groq khi 429 không có retry-after lấy max của hai reset bucket; một TPM có thể bị khóa theo bucket yêu cầu vẫn còn dư.

## DI-94 — Hiểu hành động hội thoại, giữ quyền chấm

- `listener.v2`, `constitution.v10`, `brain/1.4.0`: câu xin giảng phải được giảng; xác nhận cần giúp không hỏi xác nhận lại; tiếp nhận hướng dẫn chưa là bằng chứng hiểu.
- LiveReader nhận một số tín hiệu hội thoại rõ (xin giảng lại, đồng ý tiếp tục, xác nhận chưa hiểu theo câu cô vừa hỏi) bằng luật, không gọi model cho những tín hiệu không có nội dung Toán này. Câu khác vẫn qua model với nguyên lời và lịch sử. Không đoán “ok” là lỗi gõ. “Phải” trả lời câu Toán về vị trí vẫn để bộ chấm/model đọc, không tự coi là lời đồng ý.
- Phần dạy truyền lời cô thực tế và giữ event cuối trước khi ghi input. RecordedReader tiếp tục dùng nhãn đã lưu. Không viết lại event cũ.
- Khi dùng đường tri thức mới, kiểm lặp chặn nguyên câu của hai lượt gần nhất; không loại chỉ vì trùng cách mở đầu/thuật ngữ. Kiểm Toán, an toàn, phạm vi, lộ đáp án và chấm tất định giữ nguyên. Đường cũ giữ kiểm lặp cũ.
- Thêm ví dụ tương tự cho hướng phân số thập phân → số thập phân, cùng mẫu 10/100/1000. Ví dụ có căn cứ số học cho cả model và validator cuối, không tự mở câu có chấm mới. Yêu cầu giảng một ví dụ đúng chỗ, thay vì liệt kê mọi mẫu. Đường kiểm nghĩa nhận cùng câu giảng phương pháp và căn cứ mà model được giao; bộ chặn đáp số vẫn đối chiếu khóa practice thực. Không đưa khóa assessment vào prompt.

## DI-95 — Hồi đúng bucket hết hạn

Ưu tiên retry-after. Nếu provider nêu TPM/ITPM thì lấy reset tokens, RPD lấy reset requests; không biết bucket giữ cách fallback thận trọng cũ. Thông tin thời gian khóa trả về đúng blocked_until hoặc bucket thật sự hết. Không tăng quota, không đổi chuỗi hay dùng dịch vụ trả phí. Header requests là RPD, tokens là TPM theo [Groq rate limits](https://console.groq.com/docs/rate-limits); không suy header TPM thành thời gian TPD.

## Giữ nguyên và kiểm chứng

Giữ vòng dạy 7 bước, giáo án xuất bản, đồ thị, mastery và điều kiện qua bài của Claude. Không thêm môn/chương, không đổi nguồn internet. Regression kiểm xác nhận theo ngữ cảnh, lỗi gõ, không tăng số lần sai do xin giảng, ví dụ không lộ đáp án, bộ lọc diễn đạt và reset quota. Chạy suite offline với MONGODB_URI rỗng. Thử model thật trong bộ nhớ từ snapshot riêng, không gửi câu thử vào phiên học thật.

[Giới hạn] Model vẫn có thể diễn đạt sai, bị bác hoặc hết quota. Lượt kiểm nghĩa bằng model không phải chứng minh Toán. Một đoạn thử thành công không đủ xác nhận mọi hội thoại đã tự nhiên như GPT/Claude.
