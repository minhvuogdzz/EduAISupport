# Nhật ký duyệt ngày 2026-10-19 (theo ủy quyền của chủ dự án)

**Ủy quyền:** chủ dự án nhắn "em duyệt cho anh luôn đi" (2026-10-19), sau khi FIX-3 đưa câu "vì sao" của từng tiết và phản ví dụ vào trang duyệt. Mọi quyết định ghi `by = "claude (ủy quyền chủ dự án 2026-10-19)"` kèm lý do (`reason`) trong kế hoạch của từng chương; `make review-export` xuất được.

**Phát hành:** Số thập phân `tl-20261019140524`, Diện tích tam giác, hình thang `tl-20261019140531`. Các bản trước vẫn giữ trong kế hoạch (5 bản mỗi chương). Sao lưu trước khi ghi: `var/storage/backups/teaching_plans-20261019-210514-before-review.json` (không vào git).

## 1. Câu "vì sao" của 19 tiết

Gia sư hỏi câu này sau khi con làm đúng một bài của tiết (R-VERIFY), cho mọi bài của tiết chưa có câu riêng. Qwen soạn nháp 14 tiết; 5 nháp bị bộ kiểm loại. Cách duyệt: đọc tên, quy tắc và đề mẫu ở mọi mức của tiết (kiểm tra hiểu, cùng làm, luyện tập, vận dụng), giữ câu hợp với **mọi** dạng bài của tiết. Kết quả: giữ nháp 4, sửa nháp 10, viết mới 5.

| Tiết | Quyết định | Câu được dùng | Lý do |
|---|---|---|---|
| `STP-T01` | sửa nháp | Đúng rồi! Con giải thích cho cô vì sao con đặt dấu phẩy ở chỗ đó được không? | Nháp hỏi vì sao dấu phẩy ngăn cách hai phần (điều luôn đúng, con khó trả lời); hỏi chỗ đặt dấu phẩy gắn với chính bài con vừa làm (phần mười một chữ số, phần trăm hai chữ số). |
| `STP-T02` | sửa nháp | Đúng rồi! Con giải thích cho cô vì sao con làm như vậy, dựa vào phần nguyên và phần thập phân của số được không? | Tiết có cả bài đọc số và bài xác định hàng, giá trị của chữ số; câu nháp chỉ hợp bài đọc số. |
| `STP-T03` | viết mới (nháp bị loại) | Đúng rồi! Con giải thích cho cô vì sao số con viết vẫn bằng số ban đầu được không? | Nháp bị loại (có số 0). Câu cô viết hợp cả bài bỏ chữ số 0 ở tận cùng và bài viết hỗn số thành số thập phân. |
| `STP-T04` | sửa nháp | Đúng rồi! Con giải thích cho cô con đã so sánh hàng nào để biết số nào lớn hơn được không? | Nhiều bài có phần nguyên bằng nhau, hỏi vì sao so sánh phần nguyên trước không hợp; hỏi hàng con đã so sánh hợp cả bài điền dấu và bài sắp xếp. |
| `STP-T05` | sửa nháp | Đúng rồi! Con giải thích cho cô con đã so sánh các số thế nào để ra kết quả đó được không? | Tiết có cả bài tìm x và bài thực tế có đơn vị đo; câu nháp chỉ hợp bài sắp xếp. |
| `STP-T06` | viết mới (nháp bị loại) | Đúng rồi! Con giải thích cho cô con đã đổi đơn vị thế nào để ra số đó được không? | Nháp bị loại (có số 0). Hỏi cách đổi đơn vị hợp mọi bài viết số đo độ dài. |
| `STP-T07` | viết mới (nháp bị loại) | Đúng rồi! Con giải thích cho cô con đã đổi đơn vị thế nào để ra số đó được không? | Nháp bị loại (có số 0). Cùng câu với tiết số đo độ dài, hợp mọi bài số đo khối lượng. |
| `STP-T08` | sửa nháp | Đúng rồi! Con giải thích cho cô con đã đổi đơn vị thế nào để ra số đó được không? | Câu nháp khó hiểu với trẻ, và không hợp bài vận dụng đổi số thập phân ra đơn vị nhỏ (cm² ra mm²). |
| `STP-T09` | sửa nháp | Đúng rồi! Con giải thích cho cô con đã nhìn chữ số nào để làm tròn như vậy được không? | Câu nháp hỏi vì sao có quy tắc, con dễ đáp 'vì cô dạy vậy' (DI-55); hỏi chữ số con đã nhìn gắn với chính bài vừa làm. |
| `STP-T10` | viết mới (nháp bị loại) | Đúng rồi! Con giải thích cho cô con đã nhìn chữ số nào để làm tròn như vậy được không? | Nháp bị loại (có số 5). Cùng câu với tiết làm tròn đến hàng đơn vị và phần mười. |
| `STP-T11` | giữ nháp | Đúng rồi! Con đã áp dụng quy tắc nào để giải đúng bài tập này? | Giữ nguyên nháp: tiết luyện tập chung gồm nhiều dạng, hỏi quy tắc đã dùng là hợp. |
| `DTTGHT-T01` | sửa nháp | Đúng rồi! Con giải thích cho cô vì sao con chọn như vậy, dựa vào đường cao và đáy tương ứng được không? | Tiết có nhiều bài Đúng/Sai; câu nháp (vì sao chọn cạnh đó làm đáy) chỉ hợp bài chỉ ra đáy và đường cao. |
| `DTTGHT-T02` | giữ nháp | Đúng rồi! Vì sao con nhân độ dài đáy với chiều cao rồi chia cho hai? | Giữ nguyên nháp: hợp mọi bài tính diện tích tam giác và bài điền công thức. |
| `DTTGHT-T03` | sửa nháp | Đúng rồi! Con giải thích cho cô con đã chọn đáy và chiều cao nào để tính diện tích được không? | Câu nháp (vì sao làm các bước theo thứ tự đó) chung chung; hỏi đáy và chiều cao đã chọn hợp cả bài tam giác vuông. |
| `DTTGHT-T04` | viết mới (nháp bị loại) | Đúng rồi! Con giải thích cho cô vì sao con nhân diện tích với hai rồi chia cho đáy hoặc chiều cao đã biết được không? | Nháp bị loại (thuật ngữ ngoài bài). Câu cô viết hợp cả bài tìm chiều cao và bài tìm đáy, chỉ dùng từ của tiết. |
| `DTTGHT-T05` | sửa nháp | Đúng rồi! Con giải thích cho cô vì sao con nhận ra như vậy, dựa vào hai đáy song song và đường cao được không? | Câu nháp sai tiết: hỏi cộng hai đáy để tính diện tích, nhưng tiết này chỉ nhận biết hình thang và đường cao (bài gọi tên, Đúng/Sai). |
| `DTTGHT-T06` | giữ nháp | Đúng rồi! Vì sao con lấy tổng hai đáy nhân chiều cao rồi chia cho hai? | Giữ nguyên nháp: hợp mọi bài tính diện tích hình thang và bài điền công thức. |
| `DTTGHT-T07` | giữ nháp | Đúng rồi! Vì sao con nhân tổng hai đáy với chiều cao rồi chia cho hai? | Giữ nguyên nháp: hợp mọi bài luyện tập diện tích hình thang. |
| `DTTGHT-T08` | sửa nháp | Đúng rồi! Con giải thích cho cô con đã dùng công thức nào và tính theo thứ tự nào được không? | Câu nháp chỉ hợp bài tìm chiều cao; tiết còn có bài tìm đáy lớn và bài hình ghép. |

**Kiểm tra trước khi ghi:**
- Bộ kiểm của bộ soạn nháp (một câu hỏi, không có số, thuật ngữ có trong tiết, xưng "con", không mở đầu bằng lời khen): 19/19 câu qua. Câu đầu tiên viết cho `DTTGHT-T04` bị bắt vì dùng "độ dài" (không có trong tiết) và đã viết lại.
- Bộ kiểm của gia sư, chạy với từng bài của tiết (294 bài): không bài nào bị chặn.

## 2. Phản ví dụ

- `DTTGHT-L7` (quên nhân 2 khi tìm chiều cao từ diện tích): **sửa**. Phản ví dụ cũ dùng đúng số của bài `DTTGHT-BT-14`, nên nói ra đáp án bài đó, và trùng đáp án của `DTTGHT-BT-03a`, `DTTGHT-BT-15`. Bản mới giữ ý "kiểm tra ngược", dùng đáy 14 cm, chiều cao 3 cm, diện tích 21 cm², và kết thúc bằng câu hỏi. Quét trên 59 bài có thể hiện phản ví dụ này: không bài nào bị chặn (đã thử 5 bộ số; bộ đầu tiên vẫn trùng đáp án 2 bài).

## 3. Đã xem, quyết định không sửa

- **8 đề có câu hỏi ở giữa hoặc nhiều câu hỏi** (`STP-BT-09a–d`, `STP-BT-31`, `STP-BT-33`, `DTTGHT-PH08-7`, `DTTGHT-PH08-8`) và **đề `STP-BT-36` xưng "em"**: sửa đề thì gợi ý đã duyệt của chính câu đó mất (gợi ý gắn với đề) và phải soạn, duyệt lại. Lỗi chỉ lộ ở lượt "kéo về bài" (rất hiếm) và ở chữ "em" trong đề. Để chủ dự án quyết khi có thời gian.
- **`DTTGHT-BT-17b`**: bộ kiểm báo đề có sẵn đáp án, nhưng đó là trùng số (chiều cao h = 0,6 m, đáp án S = 0,6 m²). Đề không lộ đáp án.

## 4. Sau khi phát hành

- `make trial` (bốn học sinh viết sẵn, đọc database, không ghi): cả 4 học xong cả hai chương (11/11 và 8/8 tiết), không gợi ý bị loại nào lọt ra.
- Câu dự phòng trong buổi mô phỏng (học sinh Vương, chỉ câu mẫu, cùng chuỗi lượt như lần đo FIX-2): **54/444 → 3/444**. Cả 50 câu "vì sao" là câu đã duyệt của tiết. Ba câu còn lại: `STP-BT-15a` thiếu gợi ý bậc 1, `STP-BT-36` (chữ "em"), `DTTGHT-PH08-7` (đề nhiều câu hỏi).
