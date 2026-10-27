# ADR-037: Hiển thị hình thật của câu hỏi từ tài liệu giáo viên

**Trạng thái:** triển khai FIG-1 ngày 27/10/2026. Tiếp nối nhánh bị dừng vì quota; chủ dự án báo bản đang học không có hình và yêu cầu hoàn thiện. DI-85 ghi riêng các ngưỡng kỹ thuật, không tự coi là đã được giáo viên duyệt.

## Vấn đề

Pipeline chỉ giữ mô tả `[Hình: …]` trong chữ, không lưu/render ảnh. Một câu yêu cầu xem hình nhưng học sinh chỉ đọc mô tả là thiếu dữ kiện trực quan. Nhánh dở đã có finder/API, chưa nối hết giao diện và chưa nhập ảnh thật.

## Quyết định

- Đọc cấu trúc vector của PDF bằng PDFium, nhóm đường/nhãn thành vùng và render PNG. Không gửi tài liệu tới model/dịch vụ khác, không vẽ hình đoán. Bỏ khung trang, dòng đáp án và phần chữ lời giải. Ảnh PNG vẫn giữ đường cao, dấu vuông, tên đỉnh và số đo của tài liệu nguồn.
- Ghép mô tả với vùng theo thứ tự trang và tập nhãn/số đo (DI-85). Thiếu bằng chứng: chờ duyệt hoặc báo thiếu, không thay bằng hình đoán. PDF scan không có vector có thể cần giáo viên tải hình lên.
- Mỗi hình là document `figures` có school_id, chapter_id, question_id, order, nguồn trang/vùng, hash, trạng thái. PNG nằm dưới storage/figures với tên có hash. Không viết lại item bank, teaching plan hay bản published; các quyết định duyệt chữ vẫn giữ. Hình không còn khớp nguồn khi dựng lại được ẩn chờ kiểm tra, không giữ hiển thị ảnh cũ.
- Học sinh chỉ lấy AUTO/APPROVED từ backend, ảnh cũng yêu cầu đăng nhập. Teacher xem cả hình chờ/bị bỏ, duyệt/bỏ/hoàn tác/thay ảnh tại trang bài học hoặc duyệt phương án; ảnh riêng giáo viên tải lên không bị lần dựng sau ghi đè. API tenant filter và path containment luôn áp dụng.
- Web lấy ảnh cùng origin, token qua request Blob, object URL thu hồi khi unmount/thay version. Mô tả giữ làm alt/fallback; tải ảnh lỗi có nút thử lại. Câu nhỏ dùng hình của câu gốc. Mô tả trùng giữa hai câu không được lấy ảnh theo “cái cuối cùng”; phải ràng đúng mã câu. Hình của câu hiện tại vẫn hiện khi gia sư vừa nói lại đề.
- `make figures DRY=1` đọc nguồn và tạo gallery, không ghi DB. `make figures` là thao tác nhập nội dung rõ ràng, không chạy lúc startup/test. Chỉ áp lên dữ liệu thật sau khi có preview và đối chiếu nguồn; không tự ghi trạng thái APPROVED thay giáo viên.

## Đối chiếu dữ liệu hiện hành

Đọc nguồn thật, chỉ đọc: 15 câu hình học có 15 mô tả hình, ghép được 15 ảnh, không thiếu/thừa vùng. Cả 15 tag duy nhất trong kế hoạch hiện đang phát hành đều có ảnh tương ứng. Gallery được đưa cho chủ dự án xem trong chat trước khi áp dụng. Câu STP-BT-30 ở chương Số thập phân có thêm một hình ghép được nhưng đợt này chỉ gắn 15 hình hình học theo lỗi người dùng báo.

## Kiểm chứng và giới hạn

Test PDF tự dựng, không chứa tài liệu thật: tìm/ghép, nhiều panel, cắt đúng nhãn, lưu/duyệt/thay và tenant isolation; nguồn lệch khỏi thư viện bị từ chối, hình cũ không còn khớp bị ẩn. Web test ảnh theo câu nhỏ, tag trùng không lấy nhầm, lỗi tải/retry, thao tác giáo viên; kiểm cả regression của kế hoạch và chương.

Tệp thật nằm ngoài git/build context. Backup/restore và storage transfer của ADR-036 tự mang theo collection/ảnh mới; Docker CI phải xanh trước merge. Chưa có GC cho PNG phiên bản cũ. Chất lượng vùng cắt trên PDF khác/scan chưa được bảo đảm; giáo viên có thể thay ảnh PNG/JPG/WebP, tối đa 5 MB.
