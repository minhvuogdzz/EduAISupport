# BRAIN-3 · 28/10/2026 · Kiểm tra nhịp gia sư

[FACT] Giữ kế hoạch dạy của dự án, chỉ sửa các lỗi hội thoại theo ADR-039. Bài thử thực tế được đọc tại trình duyệt đang mở; mã nội dung liên quan: DTTGHT-BT-01, DTTGHT-PH01-2, DTTGHT-T01. Không xuất lời hoặc danh tính người học lên repo.

## Regression

`services/api/tests/test_brain3.py`: đọc phản ví dụ bằng lời; không suy diễn so sánh khi đảo toán hạng hoặc đổi điều kiện; đúng từng phần không tăng gợi ý; rút lại một ý không dùng lại ý cũ; quan hệ nền hình học và số thập phân; giữ chấm assessment; giải thích bắt buộc; phiên cũ; trần dùng chung giữa các thành phần; chặn nhận định hình học sai và lời model không có căn cứ. Toàn bộ test dùng dữ liệu tổng hợp và không ghi Atlas.

Các kiểm thử kế hoạch cũ vẫn chạy: vòng dạy đủ chương, quay lại bài yếu trong cùng buổi, học qua nhiều buổi, hỏi vì sao khi cần, replay và báo cáo giáo viên. Những assertion cũ chờ đọc `node.description` đổi sang `method.rule`: lời nhắc phải là kiến thức, không phải mục tiêu giáo viên.

## Thử model thật, trạng thái riêng trong bộ nhớ

Chuỗi model cấu hình hiện hành gpt-oss-120b → gpt-oss-20b → Qwen; không đổi nhà cung cấp. Snapshot giáo án xuất bản chỉ đọc; không gọi API gửi bài hay tạo phiên trong database thật.

| Tình huống | Lượt học sinh | Kết quả kiểm tra thủ công |
|---|---:|---|
| Hai phần của DTTGHT-BT-01 | 2 | Nhận đúng phần hình, chỉ hỏi nốt phân loại; hoàn thành sau phần còn lại, không tăng mức gợi ý |
| Sai ban đầu rồi đưa phản ví dụ DTTGHT-PH01-2 | 3 | Không còn coi phản ví dụ đúng là lạc đề; chấp nhận và chuyển câu, không bắt gõ thêm nhãn đúng/sai |
| Câu hỏi nhỏ về vị trí phần nguyên, sau đó viết số thập phân (ca tổng hợp) | 2 | Công nhận đúng bước, trở lại bài hiện tại; nhận kết quả đúng và chuyển câu |

Lần chạy cuối đủ ba tình huống: 7 lượt, 16 cuộc gọi (gồm kiểm chứng/thử lại), 6 lời model, 1 câu dự phòng vì vượt giới hạn độ dài. Lời được hiển thị đều được đọc lại; không phát hiện khẳng định Toán sai trong 7 lời này. Đây là phép thử ngắn, không phải tỷ lệ chất lượng đại diện cho mọi học sinh.

Trong hai lần chạy phát triển trước đó, model vẫn sinh lời sai về đường cao hoặc tự mâu thuẫn. Vì vậy đã bổ sung căn cứ hình học, kiểm phép khẳng định và kiểm nghĩa, thay vì chỉ sửa giọng văn. Bộ kiểm nghĩa bằng model vẫn có thể sai; ca đã gặp được giữ thành regression tất định.

Kết quả đầy đủ kiểm tra API/offline và CI được ghi trong PR BRAIN-3. Không thay đổi công thức mastery để làm test qua.

Sau khi cho phép tối đa 60 từ ở lượt gợi ý, chạy riêng lại tình huống phản ví dụ: 3 lượt / 12 cuộc gọi. Lượt gợi ý có 58 từ, giảng đúng vị trí ba đường cao trước khi hỏi con quan sát; con sửa đúng được công nhận và chuyển câu. Có 2 lời model và 1 lời dự phòng. Quota/phần kiểm chứng vẫn có thể dẫn đến lời dự phòng; không tuyên bố mọi lượt đều do model viết.

Kiểm tra local: toàn bộ API 2.006 passed, 37 skipped (Atlas được tách riêng); sau hai ca bảo vệ bổ sung, nhóm regression liên quan 164 passed. Ruff lint và format đều đạt. CI chạy lại toàn bộ bản commit cuối.
