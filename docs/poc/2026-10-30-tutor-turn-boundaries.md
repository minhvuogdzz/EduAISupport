# Sửa ranh giới lượt gia sư — 30/10/2026

## Hiện tượng và nguyên nhân

[FACT] Ảnh thử trên bản deploy cho thấy thông báo thử lại xuất hiện trước lời học sinh đầu tiên; sau đáp án `0,5`, câu kiểm tra `7/10` chỉ xuất hiện ở thẻ đề; sau đáp án `0,7`, gia sư tự giải thích cách đổi trước khi nghe con nói lý do.

[FACT] Trong code, cơ chế giữ lượt khi model lỗi dùng thông báo có giả định con đã gửi câu trả lời. Bộ lọc live loại `PRESENT` khỏi hội thoại. Lượt `VERIFY` được lấy lời giải mẫu vì đáp số đã đúng, trong khi kiểm nghĩa chưa kiểm riêng việc nói hộ lý do ở lượt này.

## Thay đổi

- Thông báo chờ không giả định học sinh đã trả lời. Phép chiếu hội thoại ẩn thông báo đã hết hiệu lực khi có lời hướng dẫn tiếp theo; sự kiện gốc vẫn còn để giáo viên kiểm tra và replay. Nhận diện cả thông báo cũ khi mở lại buổi học.
- Web nhận bản chụp mới theo khoảng sequence có thẩm quyền, bỏ thông báo mà server đã ẩn; vẫn giữ lịch sử ngoài khoảng đó khi bản chụp chỉ chứa bài hiện tại.
- Giữ câu hỏi `PRESENT` từ ngân hàng đã duyệt trong hội thoại, theo đúng thứ tự sau phản hồi của cô. Không thêm model call để đọc lại đề, không cho model sửa đề.
- `VERIFY` không nhận lời giải mẫu, các bước làm hoặc ví dụ chuyển đổi chỉ vì đáp số đúng. Chỉ dẫn yêu cầu hỏi mở cách con nghĩ. Bộ kiểm tra tất định chặn dấu hiệu nói hộ lý do; bộ kiểm nghĩa cũng kiểm lượt này theo hợp đồng đang chờ lý do và không được giải hộ.
- Không đổi node policy, cách chấm đáp số, công thức mastery hoặc các ngưỡng qua bài. Luồng lỗi vẫn giữ lượt thay vì đưa lời model bị bác cho học sinh.

## Kiểm chứng và giới hạn

[FACT] Regression bằng provider giả tái hiện câu giải hộ trong ảnh và một cách giải hộ gián tiếp. Sau khi bị bác, model được thử lại; câu hỏi hợp lệ được kiểm nghĩa rồi mới xuất hiện. Vòng `ItemTutor` dừng ở `VERIFYING`, không tự ghi lời giải thích của học sinh hoặc `ITEM_RESOLVED` từ đáp số đơn lẻ.

[FACT] Các test hồi phục kiểm tra giữ lời chào, câu hỏi chờ, tiến độ, sự kiện gốc và khả năng replay; test web kiểm tra bỏ thông báo cũ trong cả bản chụp và dòng sự kiện. Backend và eval offline: `pytest -q -m 'not atlas'` — 2.281 test qua, 37 test Atlas không được chọn. Web: 252 test qua, lint và build qua. Ruff trên các tệp Python sửa đổi qua.

[OPEN] Chưa kiểm chứng lại bằng model thật trên server deploy. Kiểm thử provider giả chứng minh luồng chặn/thử lại và ranh giới state, không chứng minh mọi cách diễn đạt của model đều được nhận diện đúng. Thay đổi trong repository chưa được deploy và không sửa các phát ngôn lịch sử đã lưu.

## Kiểm tra tiếp bằng buổi local

[FACT] Buổi local tiếp theo bị chặn mở đầu với `ANSWER_LEAK` qua nhiều model dự phòng. Mục tiêu bài chứa ví dụ `3/10 → 0,3`, nhưng bộ kiểm tra đã dùng toàn bộ mục tiêu như câu hỏi đang chờ. Sửa đường mở bài để chỉ bảo vệ câu hỏi mới thực sự được phát ra; đường trả lời câu đang chờ vẫn giữ kiểm tra cũ.

[FACT] Gọi model thật, chỉ đọc giáo án và không ghi buổi thử vào database: mở bài thành công, không có mã từ chối, giảng ví dụ `3/10 = 0,3` rồi hỏi `7/10`. Regression vẫn bác lời giảng đã nói đáp án của chính câu hỏi mới. 45 test backend liên quan và 254 test web qua; web build qua.

[DI] Giao diện nhắc nhẹ một lần sau 45 giây không tương tác khi có câu hỏi thật, không bận tạo lời, không có lỗi phục hồi. Không nhắc khi đang soạn câu trả lời, tab bị ẩn hoặc giọng cô đang phát/đang thu âm; không gửi im lặng thành lời học sinh, không tự tăng gợi ý hoặc chấm. Lời nhắc này hiển thị bằng chữ. Khi thử lại thất bại, có nút Thử lại trong buổi và tạm ẩn ô trả lời cho tới khi lời hướng dẫn sẵn sàng.
