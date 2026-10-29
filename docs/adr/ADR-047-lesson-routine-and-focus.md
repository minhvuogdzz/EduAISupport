# ADR-047 · Vào buổi có định hướng, sai thì ôn đúng ý, nói vui vẫn giữ mạch học

28/10/2026 · Theo yêu cầu chủ dự án, bổ sung ADR-046. Đối thoại tự nhiên vẫn phải phục vụ giờ học.

## Công tác đầu buổi

Lời đầu chào học sinh, dùng tên gọi khi có; không lặp chào ở từng node/lượt hoặc khi join lại. Trước ví dụ, author phải trả hai phần có cấu trúc: knowledge_recall (một định nghĩa/tính chất/quy tắc cần nhớ) và practice_plan (mảng ôn và việc sẽ luyện). Server ghép hai phần theo thứ tự trước phần ví dụ/câu hỏi. Reviewer kiểm riêng recall_explains_knowledge và plan_names_practice; chỉ nói tên chủ đề không phải đã ôn lý thuyết. Không thêm lượt gọi model hoặc bước chấm/readiness giả. Không khẳng định đã học/nắm vững trên lớp hôm nay nếu không có dữ liệu.

## Khi học sinh trả lời sai

Trong lý thuyết không chấm, một kết quả sai được xác nhận dẫn đến nhắc ngắn một ý lý thuyết liên quan trước khi hỗ trợ sửa. Không nhầm thất bại của model đọc ý với một đáp án sai. Phần luyện tập nhắc kiến thức trong mức hỗ trợ policy đã chọn, không thêm quy trình/đáp số vào một lượt PROBE và không đưa khóa assessment vào prompt. Công thức mastery/chấm, hint level, policy chọn nước đi và điều kiện qua bài giữ nguyên.

## Giữ mạch học khi đùa hoặc lạc đề

REACTION được đáp vui tối đa một ý ngắn rồi hướng ngay tới một việc/câu hỏi trong bài. Không mở chuyện riêng, không mời chia sẻ chuyện vui hoặc bịa thấy nét mặt. Khi con phủ nhận tâm trạng hoặc nhắc cô đang trong giờ học, cô nhận lỗi ngắn rồi trở về bài, không hỏi làm rõ điều đã rõ. Xin nghỉ rõ ràng và đường an toàn vẫn giữ cơ chế hiện hành; không dùng lời đe dọa/trách ép.

Cập nhật đồng bộ listener, author, mentor, reviewer và fallback: việc chỉ sửa một prompt trong khi prompt khác bảo “không ép làm bài” đã làm hành vi mâu thuẫn. Cờ return_to_lesson giúp backend bác lời mời tán gẫu trước khi gửi; khi không dùng được model, fallback vẫn đưa về việc đang học. Đọc yêu cầu trở lại bài đủ rõ bằng luật bảo thủ để không lặp “cô chưa rõ” ở tình huống model hết quota. Không dùng luật đó để chấm Toán, chấm cảm xúc hoặc tăng gợi ý.

## Kiểm chứng

Bộ tests cover thứ tự lời chào/nhắc kiến thức/kế hoạch/ví dụ; bác phần recap chỉ có tên bài; không chào lại khi restore; nhắc lý thuyết đúng lỗi; từ chối câu mời kể chuyện và giữ node/phase; nhận lời quay lại bài kể cả khi có tiếng lóng/lời thô và gateway vắng. Lượt live dùng đúng cấu hình chương và lịch sử được chỉ định, chạy synthetic trong bộ nhớ, không ghi vào phiên thật. Kết quả và giới hạn cập nhật ở nhật ký pilot.
