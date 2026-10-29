# ADR-051 · Admin quan sát model và nguồn truy xuất

Ngày: 29/10/2026. Trạng thái: triển khai theo yêu cầu chủ dự án.

## Bối cảnh

Chủ dự án yêu cầu một mục Admin riêng, mật khẩu `1234`, để xem khi nào gọi model, token usage, khi nào truy xuất RAG hoặc internet, lỗi và chuyển model. Việc quan sát cần dựa trên thao tác thực, gồm cả các lượt không dùng AI; không tạo thêm lượt AI chỉ vì mở bảng quản trị.

## Quyết định

- Đường dẫn web `/admin`; API `/v1/admin/login` và `/v1/admin/overview`. Admin đăng nhập riêng, không cần tài khoản học sinh, phụ huynh hoặc giáo viên. Mật khẩu được kiểm tại máy chủ qua `ADMIN_PASSWORD` (mặc định theo yêu cầu là `1234`), không nằm trong mã giao diện.
- Token ký HMAC có miền chữ ký riêng, scope `observability`, school id, hạn 8 giờ và dấu kiểm cấu hình mật khẩu. Token của giáo viên không mở được Admin; token Admin không được coi là tài khoản người học. Có giới hạn thử sai giống cơ chế PIN hiện hành. API Admin trả `Cache-Control: no-store`.
- Admin chỉ đọc dữ liệu. Truy vấn lịch sử luôn lọc `school_id`, giới hạn 50 buổi cập nhật gần nhất; không chỉnh tài khoản, nội dung sư phạm hay dữ liệu học sinh.
- Hai nguồn được hiển thị riêng: nhật ký vận hành mới và sự kiện buổi học có sẵn (`MODEL_CALLED`, `RAG_RETRIEVED`, `WEB_LOOKED`). Không cộng hai nguồn vì cùng tác vụ có thể nằm trong cả hai. Bộ lọc loại và tìm kiếm chạy trước giới hạn số bản ghi trả về, để RAG/web cũ không bị che bởi nhiều lượt gọi model mới.
- Dùng `ContextVar` và context được truyền qua thread pool hiện hành để liên kết request, buổi học và tác vụ cha. Ghi các lượt POST vào API buổi học, lời gọi gateway, truy xuất chỉ mục RAG và lookup nguồn web. Phân biệt đang chạy, thành công, không tìm thấy nguồn phù hợp, lỗi, dự phòng, không gửi provider và gián đoạn.
- Token là số provider báo về; thiếu số liệu ghi `null`, không suy đoán bằng 0. Đếm các lượt gửi provider riêng với lời gọi gateway và giữ chuỗi thử model, lỗi, loại quota, mốc thử lại. Bảng quota phản ánh bộ theo dõi của gateway, không giả là hạn mức còn lại trong tài khoản provider.
- Nhật ký lưu JSONL ở `var/storage/observability/operations.jsonl`, tối đa 3.000 tác vụ trong bộ nhớ; xoay tệp ở 5 MB, giữ tệp trước. Các mốc này là lựa chọn vận hành, không phải ngưỡng đánh giá sư phạm. Lỗi ghi tệp giữ nhật ký trong bộ nhớ; lỗi đọc metadata quan sát không thay kết quả dạy học.
- Không ghi prompt, câu trả lời, lời học sinh, mật khẩu, API key hoặc audio. Dấu vết nguồn chỉ gồm mã đoạn, tiêu đề, kết quả đối chiếu và URL do adapter hiện hành trả về. Lookup web có thể đọc cache, nên không được hiểu mọi bản ghi lookup là một HTTP request ra internet mới.
- `OBSERVABILITY_ENABLED=false` tắt ghi mới. Mọi test mặc định tắt ghi; test quan sát chủ động bật với nhật ký và database trong bộ nhớ riêng, không ghi vào nhật ký của người dùng hoặc Atlas thật.

## Tác động

Thêm quan sát tại các ranh giới gateway/retrieval và middleware API, không đổi quyết định dạy học, công thức mastery hay model được ưu tiên. Giao diện tự đọc lại mỗi 5 giây, có nút dừng, làm mới, bộ lọc, dấu vết chi tiết và đăng xuất. Nhật ký được giới hạn dung lượng; lịch sử cũ chỉ có mức chi tiết mà các sự kiện cũ đã lưu.

## Bổ sung 29/10/2026 · Phân biệt tra cứu và kết nối mạng

Theo góp ý chủ dự án, tách các sự kiện `network`, `cache`, `decision` bên cạnh `model`, `rag`, `web`, `command`. Ghi HTTP ngay tại ranh giới gửi request của SearchEducation, OfficialEducation và WikipediaVi; lỗi HTTP/timeout vẫn được quan sát, đọc cache không được tính là HTTP. URL HTTP được bỏ userinfo, query và fragment; không lưu header/body. Các điểm định tuyến trong GroundedSpeaker ghi mã lý do, không ghi câu hỏi. Không thay điều kiện tra cứu hoặc luồng dạy.

API hỗ trợ `offset` sau bộ lọc; trả tổng phù hợp và metadata phạm vi. Giao diện dùng 12 dòng/trang, vùng bảng cuộn giới hạn, cột chi tiết, ba tab và gộp model theo tên. Lịch sử `WEB_LOOKED` chỉ có nguồn đã lưu, nên không thể diễn giải là mọi lần thử tìm web. Lịch sử không lưu kết nối HTTP: hiển thị “Chưa theo dõi”, không hiển thị 0. Bộ đếm HTTP chỉ tính tìm nguồn web, không gồm kết nối tới model provider.
