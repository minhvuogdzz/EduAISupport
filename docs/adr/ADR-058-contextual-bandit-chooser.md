# ADR-058: Bộ chọn nước đi học từ kết quả bằng contextual bandit (BANDIT-1)

Ngày: 04/11/2026 · DI-101, DI-102, DI-103, DI-104
Chủ dự án yêu cầu thêm Contextual Bandits vào hệ thống (tên đồ án: gia sư AI kiểm chứng được, dùng RAG, Knowledge Tracing và Contextual Bandits). Quyết định này thêm một bộ chọn mới cạnh bộ chọn của model (ADR-031); không thay bộ chọn đó.

## Vấn đề

[FACT] Bộ chọn của ADR-031 để model đọc thực đơn và nêu một nước đi, nhưng không học từ điều xảy ra sau đó: nó không biết nước đã chọn có giúp con làm đúng ở câu trả lời kế tiếp hay không, và không có phần thưởng. ADR-031 ghi rõ chưa đo được AUTO-1 có giúp trẻ học tốt hơn. Một contextual bandit là mô hình đúng cho bài toán này: ở mỗi lượt có vài nước đi được phép (cánh tay), có ngữ cảnh về con, và có kết quả quan sát được sau khi chơi một nước.

## Quyết định

Thêm `BanditChooser` (`cavat/modules/tutor/bandit.py`) cài đặt cùng giao diện `MoveChooser` với `ModelChooser` và `RecordedChooser`. Bật bằng `TUTOR_CHOOSER=bandit`; mặc định vẫn là `llm`.

- **Chính sách vẫn sở hữu thực đơn (quy tắc 1).** `policy.options` cho tối đa ba nước đi, không nước nào giúp nhiều hơn nước của chính sách; `policy.accept` chỉ chơi nước nằm trong thực đơn. Bandit không thể chọn ngoài thực đơn, không chọn lượt kiểm tra cuối tiết, không đụng các luật cố định (R-TIME, R-FULL, R-ASSESS-CAP...). Thực đơn có nước không học được (`VERIFY`, `CONFIRM_ADVANCE`, tức lượt "vì sao" của AUTO-5) giao cho bộ chọn model làm dự phòng, hoặc giữ nước của chính sách khi không có model.
- **Cánh tay:** loại nước đi và bậc của nó (`PROBE`, `OFFER_CHOICE`, `HINT:2`, `COGNITIVE_CONFLICT`, `EXPLAIN:1`...), để cùng một cánh tay mang cùng một nghĩa ở mọi thực đơn.
- **DI-101, ngữ cảnh.** Chín số trong [0, 1] suy từ `situation` của bộ chọn (AUTO-4): hệ số tự do, số lần trả lời, số gợi ý đã nhận, bậc gợi ý cao nhất, số lượt chưa tiến bộ, số lần xin gợi ý, dấu hiệu nản, đã hỏi cách làm chưa, lỗi lặp nhiều nhất. Chỉ là số đếm, không có đáp án hay lời của con (quy tắc 2).
- **DI-102, thuật toán.** LinUCB đĩa (một hồi quy ridge mỗi cánh tay) với độ rộng thăm dò α = 0,5 và ridge = 1. Với xác suất ε = 0,1 bộ chọn chọn ngẫu nhiên đều trong thực đơn (ε-tham lam), để ghi được xác suất của mỗi lượt chọn (`propensity`) và dùng log cho đánh giá ngoài chính sách. Khi hòa điểm, nước đứng đầu thực đơn, tức nước của chính sách, thắng: bộ chọn chưa học gì thì chơi đúng nước của chính sách. Số ngẫu nhiên sinh từ SHA-256 của khóa phiên, số lượt và đề, nên cùng phiên, cùng lượt, cùng thực đơn luôn ra cùng một lựa chọn.
- **DI-103, phần thưởng.** Câu trả lời có chấm kế tiếp của con trên cùng câu: đúng 1, đúng một phần 0,5, sai 0, trừ 0,3 × (mức giúp của nước đi) / 7. Nước giúp ít mà vẫn có tác dụng được thưởng hơn nước giúp nhiều. Lượt chọn không có câu trả lời có chấm theo sau (câu đóng trước) không được trả thưởng; lượt chọn bị chính sách từ chối cũng vậy.
- **DI-104, trạng thái là phép gập của sự kiện.** Bandit giữ ba tổng cộng (Σxxᵀ, Σr·x, n) mỗi cánh tay: cộng được, nên không phụ thuộc thứ tự thưởng, và là một hàm thuần túy của các sự kiện `BANDIT_REWARD` (quy tắc 3). Sự kiện mang đủ cánh tay, ngữ cảnh, thưởng và phiên bản bandit. Collection `bandit_arms` (một document mỗi trường × phiên bản × cánh tay, có `school_id`, quy tắc 5) cập nhật bằng `$inc` nguyên tử sau khi lệnh commit thành công (Atlas M0 không có transaction nhiều document, quy tắc 10) và dựng lại được từ sự kiện (`BanditRepository.rebuild`). Không model nào ghi vào đó.

`MOVE_CHOSEN` thêm `source = BANDIT`, `arm`, `propensity`, `context`, `scores`; các trường đó bị bỏ khỏi payload khi rỗng, nên lượt chọn của model giữ nguyên dạng cũ. Phát lại đọc bản ghi (`RecordedChooser` giữ cánh tay và ngữ cảnh), không hỏi bandit lại và không trả thưởng hai lần.

## Giữ nguyên

Chính sách quyết định nước đi, `accept` kiểm lại mọi lựa chọn, bộ kiểm chứng lời gia sư, bộ chấm tất định, công thức mastery và ngưỡng, prompt, thứ tự model (ADR-049) và đồ thị tri thức không đổi. Đáp án câu hỏi không đi vào bandit.

## Kiểm chứng

Test offline `tests/test_bandit.py` (22 test) và toàn bộ 2.347 test backend qua. Các test kiểm: ngữ cảnh chín số trong [0, 1]; cánh tay và phần thưởng; mô hình học được nước nào hợp với trẻ nào; thứ tự thưởng không đổi trạng thái; trạng thái là phép gập của sự kiện và của các số gia; xác suất lựa chọn; bandit chưa học chơi nước của chính sách; lựa chọn luôn nằm trong thực đơn và tái lập được; tần suất thăm dò khớp ε; thực đơn không học được chuyển cho dự phòng; thưởng trả đúng một lần sau câu trả lời kế tiếp và không trả khi lựa chọn bị từ chối; phát lại cùng nước; lượt kiểm tra không hỏi bandit; kho lưu trữ cộng gia, tách theo trường, bỏ qua thưởng của phiên bản khác và dựng lại được; một buổi đi qua API trả thưởng đúng một lần.

Đánh giá ngoại tuyến `make eval-bandit` (`scripts/eval_bandit.py`, báo cáo `docs/thesis/data/bandit-eval.json`) chạy trên một môi trường mô phỏng khai báo: xác suất con làm đúng ở câu kế tiếp phụ thuộc trạng thái của con và nước đi, nên nước tốt nhất đổi theo con (nước tốt nhất là `PROBE` ở 44% ngữ cảnh, `HINT:1` ở 38%, `HINT:2` ở 18%). Mỗi chính sách chạy 3.000 lượt trên 30 hạt giống, trung bình ± khoảng tin cậy 95%:

| Chính sách | Hối tiếc tích lũy | Tỉ lệ chọn nước tốt nhất (quý cuối) | Thưởng trung bình (quý cuối) |
|---|---|---|---|
| Nước của chính sách | 878,9 ± 5,8 | 0,315 ± 0,005 | 0,488 ± 0,007 |
| Ngẫu nhiên | 621,1 ± 5,6 | 0,389 ± 0,005 | 0,573 ± 0,006 |
| Giúp ít nhất | 368,6 ± 5,0 | 0,693 ± 0,006 | 0,657 ± 0,006 |
| Bandit (α 0,5; ε 0,1) | 93,5 ± 3,0 | 0,833 ± 0,009 | 0,759 ± 0,004 |
| Bandit không thăm dò (ε 0) | 73,9 ± 41,0 | 0,841 ± 0,046 | 0,763 ± 0,015 |
| Oracle | 0 | 1 | 0,783 ± 0,004 |

Bandit không thăm dò có hối tiếc trung bình thấp hơn nhưng khoảng tin cậy rộng gấp hơn mười lần: có hạt giống kẹt ở một cánh tay xấu. Thăm dò ε = 0,1 giữ độ rộng ở mức ±3 và còn cho xác suất để đánh giá ngoài chính sách. Ước lượng IPS từ log của bandit (ε = 0,3) cho giá trị của chính sách "giúp ít nhất" là 0,665 ± 0,007 so với giá trị thật 0,661, và của oracle là 0,788 ± 0,006 so với 0,782, tức không lệch đáng kể.

## Giới hạn

- [OPEN] Môi trường là mô phỏng khai báo, không đo trên trẻ. Kết quả cho biết thuật toán học được một lựa chọn phụ thuộc ngữ cảnh và học nhanh ra sao; không cho biết nước đi nào giúp trẻ thật. Bảng trên không là bằng chứng sư phạm, và mức yếu của "nước của chính sách" xuất phát từ cách khai báo môi trường chứ không từ dữ liệu.
- [OPEN] Phần thưởng chỉ nhìn một câu trả lời kế tiếp, không nhìn mức hiểu bài lâu dài, nên có thể ưa nước làm con đúng ngay hơn nước giúp con hiểu sâu. Hệ số 0,3 (DI-103) và các tham số của DI-102 chờ chủ dự án duyệt. Chưa chạy `TUTOR_CHOOSER=bandit` trên buổi học thật; mặc định vẫn là `llm` cho tới khi chủ dự án duyệt và có dữ liệu.
- [OPEN] Bandit gộp dữ liệu của cả trường, chưa tách theo từng học sinh. Thực đơn có `HINT:3` hay `COGNITIVE_CONFLICT` hiếm nên các cánh tay đó học chậm. Đánh giá ngoài chính sách bằng IPS đòi xác suất lựa chọn khác 0 và chính sách đích tất định, và có phương sai lớn khi đích khác xa chính sách log.
