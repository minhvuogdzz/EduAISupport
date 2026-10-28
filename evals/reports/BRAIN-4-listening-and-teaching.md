# BRAIN-4 · 28/10/2026

Yêu cầu: model nghe và giảng thực sự, dùng kiến thức nền/nguồn internet có giới hạn; giữ kế hoạch dạy. ADR-040, DI-91–93.

## Tái hiện và kiểm thử

- Đọc phiên trình duyệt và snapshot riêng: STP-PH01-5, STP-PH01-6. Khôi phục đúng AWAITING_REASON, không restart câu. Thử sửa hiểu lầm trong bộ nhớ giữ nguyên số lần trả lời; sau đó đáp án đúng có lý do giải quyết được câu đang dở. Không gửi lời thử vào phiên thật.
- Regression tổng hợp: nghe nguyên văn và ngữ cảnh, từ chối/nghỉ, câu ngắn đa nghĩa, fallback không lặp vô hạn, giữ assessment, không sáng tác đáp số cho học sinh, trích đáp số nằm sau lời giải thích, không hỏi lặp lý do, suy dạng đáp án khi metadata thiếu, chấm đúng câu hỏi nhỏ và replay lời cô thật.
- Kiến thức: lượt kiểm riêng phải đạt Toán/phạm vi/yêu cầu/đáp ý; không giả citation khi dùng kiến thức model; cổng khái niệm không cho model chọn URL; kiểm điều kiện hình học và lộ đáp số bằng code.

## Model thật

Dùng snapshot giáo án chỉ đọc và đối tượng Python trong bộ nhớ, không test/seed trên database học sinh. Chỉ lưu snapshot và trace đầy đủ ở `var/storage/` đã gitignore; repo không có nguyên giáo án hoặc hội thoại người học.

Các lần phát triển đã bắt được model hiểu nhầm lời cũ, cho đáp số thay con, chuyển sang bài số khác mà bộ chấm chưa biết, và lượt kiểm model bác một phân số đúng vì chưa rút gọn. Các lỗi này dẫn đến sửa hợp đồng ngữ cảnh, công cụ ví dụ/câu hỏi nhỏ và bộ kiểm Toán, không chỉ đổi prompt cho giọng mềm hơn.

Lần thử hội thoại số thập phân sau sửa: từ chưa rõ ý được hỏi lại (không tính sai/H6); câu chưa hiểu được giảng quy trình và ví dụ khác; thắc mắc về rút gọn được giải thích rằng đề không yêu cầu rút gọn. Có lượt fallback khi output không đạt số câu hỏi, không giấu điều đó.

Tra cứu lý thuyết thật: cổng nghĩa chọn tên khái niệm, truy xuất ấn phẩm công khai của ĐH Cần Thơ và cho lời giải thích mẫu số kèm nguồn. Một phép thử thiếu nguồn dùng kiến thức model và lượt kiểm riêng; gắn LLM, không giả gắn WEB. Nguồn thật: https://sj.ctu.edu.vn/ql/docgia/download/baibao-28144/12-GD-DUONG%20HUU%20TONG%2893-102%29.pdf .

Toán hình dùng DTTGHT-PH01-2, kiểm riêng việc hỏi lý thuyết và trả lời có phản ví dụ. Các lỗi đổi nhầm loại tam giác được đưa vào guard/regression. Các phép thử ngắn được đọc thủ công; không suy ra tỷ lệ chất lượng đại diện cho một lớp học hoặc mọi cách diễn đạt.

Kết quả toàn bộ API, lint/format, CI và commit cuối được ghi trong PR BRAIN-4. Test offline/in-memory; Atlas integration chủ động skip.

Kiểm tra cuối local: **2.039 passed, 37 skipped**, Ruff lint/format đạt. Toán hình sau sửa guard theo mệnh đề/đỉnh cụ thể: lượt model đã giảng đúng đường cao từ đỉnh góc tù ở trong, hai đường còn lại ở ngoài; không chấm câu hỏi lý thuyết thành lượt sai. Lượt này cần thử lại một lần sau khi bộ kiểm bác bản đầu. Điều đó cũng cho thấy fallback/thử lại là giới hạn thực tế, không phải mọi lần gọi model đều có thể đưa thẳng cho học sinh.
