# ADR-054: Tự khôi phục lượt dở, chào bằng lời và giữ giới hạn Socratic

29/10/2026 · Bổ sung ADR-050 và ADR-052 theo phản hồi thử vai học sinh của chủ dự án.

## Vấn đề

[FACT] Cổng model-only có thể từ chối lời Toán mẫu sau khi model đã bị kiểm nội dung bác, dù provider vẫn hoạt động. Câu “Con chờ cô một chút nhé” trước đây được dùng cho cả tình huống đó và lỗi dịch vụ, nhưng không có tác vụ tiếp tục sau thông báo. Học sinh phải gửi thêm lời để kích hoạt lại. Chốt này còn nhận nhầm lời chào/cảm ơn thuần túy thành lời giảng dự phòng.

[FACT] Join phiên ACTIVE chỉ trả state cũ. Chế độ nói khi mới bật đánh dấu mọi tin cũ đã đọc, gồm lời chào tách riêng trước lời mở bài. Vì vậy lời chào có trong transcript nhưng học sinh có thể không nghe được.

[FACT] Validator cũ miễn câu hỏi cho một số lượt REPAIR. Reviewer lý thuyết lại được chỉ dẫn mặc định `solution_leaked=false`; reviewer luyện tập có lúc nhận nhiệm vụ giảng đã trừu tượng hóa thay cho đề thực tế, thiếu giới hạn gợi ý có cấu trúc.

## Cách xử lý

- Server giữ lệnh thất bại và nguyên lời học sinh trong state của chính phiên. Client chỉ nhận trạng thái khôi phục, không nhận nội dung lệnh nội bộ, khóa assessment hoặc quyền chọn model. `POST /recover` thực hiện lại lệnh đã lưu, có kiểm chủ phiên, lifecycle, state version, Idempotency-Key và ngân sách gọi model như lệnh ban đầu.
- [DI] Thử tự động tối đa ba lần, chờ lần lượt 2/4/8 giây khi màn hình phiên còn mở. Đây là lựa chọn vận hành, không phải ngưỡng đánh giá học tập. Sau đó thông báo rõ đã thử mà chưa tiếp tục được; không để spinner hay lời hứa chờ vô hạn. Mở lại phiên cho phép bắt đầu lượt thử kết nối mới. Lỗi mạng của trình duyệt cũng có giới hạn ba lần.
- Không commit bằng chứng chấm, hint hoặc chuyển bước của lượt chưa phát được. Chỉ giữ chi phí model và input cần khôi phục. Input phát lại được lưu cho replay nhưng ẩn khỏi transcript học sinh để tránh cảm giác con đã nói hai lần. Thông báo vận hành và input chờ không chen vào lịch sử hội thoại dùng để viết lời giảng kế tiếp.
- Lời chào và định hướng tên bài còn được gửi ngay cả khi mở bài thất bại. Khi quay lại phiên ACTIVE, chào mừng và nêu đúng bài hiện tại, giữ nguyên câu hỏi/tiến trình. Phiên cũ chỉ có thông báo chờ được khôi phục từ input đã lưu khi có thể xác định chắc chắn. Không đoán lại yêu cầu hint/choice của phiên cũ nếu thiếu dữ liệu.
- `entry_greeting` là metadata trình bày: chế độ nói đọc lời chào cùng lời mở khi chưa có câu trả lời đầu tiên. Sau khi học sinh đã trả lời, không đọc lại lời chào cũ. Chỉ bật âm thanh theo chế độ nói đã có; không tự xin quyền micro hoặc đổi cài đặt trình duyệt.
- Lời chào/cảm ơn và điều hướng về câu đang chờ là phép lịch sự, không phải lời giảng Toán. Chúng không bị cổng model-only nhận thành lỗi. Nội dung Toán vẫn phải do model viết và qua kiểm tra như ADR-050.
- Mọi move đang cần câu trả lời phải kết thúc bằng đúng một câu hỏi trong luồng live, kể cả REPAIR. Xin nghỉ rõ ràng, chuyển bước và kết thúc giữ ngoại lệ hiện hành.
- `lesson-teacher.v4` và `lesson-review.v4` yêu cầu để lại một bước học sinh tự làm, không giải sẵn rồi mời chép/xác nhận. Kiểm tất định bổ sung chặn việc cho số thập phân của chính phân số đang hỏi; vẫn cho làm mẫu bằng ví dụ khác. Trường hợp khái niệm/số viết bằng chữ dựa thêm vào kiểm nghĩa.
- Câu hỏi chỉ hỏi đã hiểu/nhớ/sẵn sàng chưa bị bác thay vì được tính là bước học tiếp. Lời mở không được tự bịa buổi học hôm trước. [DI] Ngưỡng nhận diện chép nguyên văn trong luồng author tăng từ 14 lên 24 từ liên tiếp: định nghĩa chuẩn ngắn có thể trùng lời nguồn, nhưng đoạn chép dài vẫn bị chặn và reviewer nghĩa vẫn phải duyệt.
- `curriculum-check.v11` nhận đề thực tế và hợp đồng move/hint level từ server. Reviewer không được tăng mức hỗ trợ dù lời Toán đúng; lượt kiểm dùng vai trò `EVAL_JUDGE`. Mentor và model chính cùng chịu chốt. Không đổi luật chấm, mastery, KC graph hoặc đưa khóa assessment vào prompt.

Artifact: `brain/1.10.0`, `llm-renderer.v16`, `teaching-templates/0.18.0`; giữ các prompt cũ để tra cứu.

## Kiểm chứng và giới hạn

Kiểm thử tổng hợp qua API và repository trong bộ nhớ: khôi phục mở bài không cần input mới; giữ nguyên lời đã nói; không hiện trùng; giới hạn số lần; khởi động lại khi quay về; từ chối phiên người khác hoặc version cũ; idempotency; event replay; tương thích phiên chờ cũ; lời chào không bị coi là lời giảng lỗi. Kiểm frontend dùng timer mô phỏng, gồm cả mất mạng, rời trang và thứ tự đọc lời chào/giới thiệu bài. Các kiểm Socratic có tình huống lời giảng hợp lệ, lộ đáp án, REPAIR thiếu câu hỏi và hợp đồng H1.

[OPEN] Không bảo đảm model/ngân sách nhà cung cấp luôn khả dụng. Reviewer nghĩa vẫn có sai số; kiểm tất định chỉ bao phủ dạng đã nhận diện. Tự khôi phục chạy khi trang phiên mở, tiếp tục được từ state đã lưu khi vào lại. Chưa phải worker nền hoặc SSE. Kết quả thử model thật nhỏ không thay cho nghiệm thu một buổi đầy đủ với học sinh.

[FACT] Một lượt hồi quy đầy đủ đạt 2.276 kiểm thử, gồm Atlas trên namespace test có guard. Sau đó bổ sung hồi quy về câu hỏi sẵn sàng và định nghĩa ngắn; số liệu chốt ghi ở PR. Frontend đạt 251 kiểm thử, lint và TypeScript. Lượt tổng hợp qua model thật đã có lời mở từ Gemini 2.5 Flash và lời hỗ trợ từ GPT-OSS 120B; các lần thử cũng bộc lộ câu hỏi chung chung, bịa lịch sử và bác nhầm định nghĩa, được dùng để thêm các chốt nêu trên. Không xem lần thử đó là nghiệm thu cả buổi hoặc bảo đảm mọi đầu ra của Gemini.

## Ghi chép luận văn

29/10/2026 · TUTOR-RECOVERY: sửa luồng chờ và giới hạn Socratic. Vấn đề: lỗi model/kiểm lời bị biến thành câu chờ không có hành động kế tiếp; lời chào không được đọc; lời giải thích có thể thiếu câu dẫn hoặc cho đáp án sớm. Cách làm: lưu lệnh dở, retry có giới hạn và kiểm đồng thời, metadata lời chào cho TTS, kiểm câu hỏi và giới hạn gợi ý độc lập model. Kết quả kiểm thử cụ thể ghi ở báo cáo PR. Không có connector Google Docs trong phiên này; mục này chuẩn bị để chép vào Phụ lục E của tài liệu luận văn.
