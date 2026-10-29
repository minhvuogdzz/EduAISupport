# ADR-046 · AI soạn lời dạy từ mục tiêu, không từ câu thoại mẫu

28/10/2026 · Chủ dự án yêu cầu bỏ việc lấy câu hỏi trong dữ liệu làm câu cô buộc phải nói. Quyết định này thay phần CONTINUE không gọi model của ADR-044 và mở rộng ADR-045 trong **lý thuyết không chấm**.

## Vấn đề đã xác nhận

Log phiên do chủ dự án chỉ định xác nhận: mở bài bị bác rồi rơi về nguyên đoạn dữ liệu, lời “là sao” có Gemini nhưng bị loại bởi ràng buộc câu hỏi, lời model nhỏ sai được reviewer yếu chấp nhận. “À ra vậy” luôn nối lại câu mẫu. Chỉ cho paraphrase cùng câu hỏi không đủ: câu hỏi giáo án vẫn là đích bắt buộc, không có quyền soạn một cách giảng có nghĩa.

## Quyết định

Luồng dạy lý thuyết có author và reviewer riêng, không dùng prompt gợi ý bài tập/assessment. Đầu vào mở bài gồm mục tiêu node, kiến thức thô, lịch sử và ngữ cảnh; **không đưa ask/reply/accept của câu mẫu vào**. AI chọn một ví dụ và một câu hỏi cụ thể phục vụ mục tiêu hiện tại. Reviewer kiểm sự đúng đắn, khả năng hiểu/trả lời từ lời vừa giảng và phạm vi, không ép câu hỏi mới tương đương câu mẫu.

Gemini ưu tiên ở vai trò master khi mở bài/xin giảng; một lời master đã kiểm được dùng trực tiếp, không bắt model yếu viết lại. Tối đa hai bản nháp theo chuỗi nhà cung cấp, mọi request vẫn tính cap. Reviewer ưu tiên Gemini rồi các model còn dùng được. Không fine-tune hay sửa trọng số.

Hệ thống vẫn chọn node, bước học và chính sách chuyển bước. Câu hỏi thực sự đã nói được lưu qua event ref GENERATED/GUIDED_THEORY; restore không sinh lại. Phần đọc ý trong lý thuyết đối chiếu câu thực tế và lời vừa giảng, không dùng đáp án/cách nói mẫu cũ để quyết định câu trả lời cho câu mới. Một đáp số ngắn vẫn được đọc; trích dẫn phải nằm trong lời học sinh. Đây là hội thoại không chấm điểm. Item assessment, retell rubric, mastery, graph và điều kiện mở khóa không thay.

Khi không có đầu ra đã kiểm, không lấy dữ liệu thô giả làm lời AI: thông báo ngắn chưa thể giảng tiếp và giữ bước. Legacy/offline không bật model vẫn giữ hợp đồng cũ để replay. Nhánh hỏi lý thuyết RAG có nguồn vẫn tồn tại; dữ liệu chỉ làm căn cứ cho suy nghĩ, không là kịch bản.

## Kiểm chứng

Tests xác nhận câu mẫu không vào prompt mở bài, câu mới có thể khác dữ kiện/câu hỏi cũ, câu thực tế được lưu/khôi phục, đáp số ngắn được đọc theo câu thực tế, không sinh điểm/mastery từ hội thoại, không đọc raw RAG khi không có model. Thử API thật dùng đúng chương đã cấu hình, đối tượng học synthetic trong bộ nhớ, không viết dữ liệu phiên thật. Kết quả và giới hạn ghi trong nhật ký pilot.
