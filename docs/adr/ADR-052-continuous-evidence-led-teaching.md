# ADR-052: Giữ mạch giảng và chỉ chuyển khi có bằng chứng học tập

Ngày 29/10/2026, chủ dự án yêu cầu giảm tình trạng model đang hoạt động nhưng học sinh liên tục thấy thông báo chờ; sau khi giải thích phải hỏi tiếp một bước vừa sức, đi sâu vào chỗ chưa hiểu và chỉ chuyển khi đủ bằng chứng cho nội dung/KC đang học.

[FACT] Đọc log vận hành và log phiên gần nhất cho thấy có cả hạn mức API lẫn lỗi tích hợp: Gemini báo RPD; các model Groq trả lời được nhưng có lúc báo TPM/ITPM; mentor có yêu cầu 3.255 token vượt trần 3.000; lời mẫu ghép vào một lượt có AI hợp lệ làm chốt model-only từ chối toàn bộ lượt. Các trường hợp này không đồng nghĩa model đã tắt.

[REC] Giữ nguyên quy chế ADR-050: không dùng lời mẫu để giảng Toán, không bỏ kiểm Toán/nguồn để tránh thông báo chờ. Sửa nguyên nhân trước chốt xuất lời:

- `lesson-teacher.v3`, `lesson-review.v3`, `constitution.v17`: giảng đúng chỗ vướng rồi hỏi một việc cụ thể, không chỉ hỏi “hiểu chưa”; không nâng độ khó khi con đang chưa hiểu; giữ KC và đề đang chờ. Xin nghỉ rõ ràng, an toàn và bước chuyển có câu kế tiếp trong cùng lượt là ngoại lệ hợp lý.
- Bỏ điều kiện “đã giảng lại một lần” như một lý do để bỏ qua câu trả lời lý thuyết sai hoặc lời nói lại chưa đạt. Lượt nói lại/nhớ kiến thức nền chưa đủ tiếp tục được giúp trong cùng mục tiêu; lời “ok/à ra vậy” không là bằng chứng đã hiểu.
- Không thay công thức mastery, ngưỡng đạt, đồ thị KC hoặc luật chấm assessment. Một câu lý thuyết đúng chỉ cho phép đi tới bước kiểm tra kế tiếp, không tự công nhận thành thạo cả KC.
- Lời xác nhận sau nói lại đạt và lời mời nhớ kiến thức nền do model diễn đạt, không ghép câu Toán cố định. Bỏ lời chuyển NODE/PASS/STOP dư thừa khi bước tiếp đã trình bày bài/đề; tránh tốn thêm hai model call và tránh chặn cả lượt vì lời chuyển không cần thiết.
- Rút gọn prompt, bỏ lịch sử cũ trước khi vượt trần; luôn giữ nguyên toàn bộ lời đang được kiểm, lời con hiện tại và nhiệm vụ. Tính phần chỉ dẫn mentor vào ngân sách trước khi ghép. Lời mentor qua cùng bộ kiểm được dùng trực tiếp, không bắt model yếu hơn viết lại.
- Router live thử hồi phục một lần khi toàn chuỗi vừa lỗi và thời gian hết cooldown nhỏ hơn hoặc bằng 6 giây. Không chờ hạn mức ngày hoặc lặp vô hạn; vẫn tính đủ số request và giữ session cap. Đây là lựa chọn vận hành cục bộ, không phải nâng quota nhà cung cấp.
- Log lưu mã bác lời thực tế và lý do fallback từ renderer khi lượt bị giữ, không gán mọi lần chờ thành lỗi quota.

[FACT] Kiểm thử dùng dữ liệu tổng hợp và repository trong bộ nhớ; đọc giáo án đã xuất bản để thử model nhưng không gửi lệnh buổi học thật, không ghi DB học sinh, đổi key, billing hay hạn mức. Báo cáo ở `evals/reports/tutor-release/continuity-*.json` và `continuity-release-tests.txt`.

[OPEN] Free quota vẫn hữu hạn. Lần thử nhanh liên tiếp có thể làm hết hạn mức phút của cả chuỗi. Lần thử có khoảng cách 15 giây giữa lời học sinh đạt 8/8 lượt có AI trên hai chương, không có thông báo chờ, nhưng không chứng minh tải nhiều học sinh hoặc cả ngày ổn định. Kiểm riêng lượt tiếp nhận phát hiện một lời khen “đã nắm ý” không có bằng chứng; đã thêm chốt `UNSUPPORTED_UNDERSTANDING` và kiểm hồi quy. Không tuyên bố chất lượng sư phạm của mọi lời model đã hoàn hảo hoặc API đã hết giới hạn.
