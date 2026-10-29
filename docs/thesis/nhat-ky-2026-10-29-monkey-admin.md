# 29/10/2026 · UI-BUDDY / ADMIN-1: Trải nghiệm Monkey Edu và nhật ký vận hành AI

Mục ghi sẵn cho Phụ lục E của tài liệu phục vụ viết luận. Chưa đồng bộ sang Google Docs trong phiên này.

## Vấn đề và yêu cầu

[FACT] Chủ dự án yêu cầu thêm section và hiệu ứng nhưng giữ giá trị cốt lõi ở đầu; Monkey Buddy cầm bút viết lên bảng; bộ cảm xúc tự chuyển mỗi 2 giây và vẫn bấm chọn được. Thêm nav Admin, mật khẩu `1234`, để quan sát gọi model, usage, RAG và tra cứu internet.

## Thực hiện

- [FACT] Thứ tự trang chủ: lời giới thiệu → giá trị cốt lõi → cách học → lợi ích/so sánh → minh họa tương tác → Buddy và nội dung khám phá. Không đưa phần trang trí lên trước nội dung cốt lõi.
- [FACT] Dùng SVG cùng hệ tọa độ cho bảng, công thức và Buddy cầm bút. Các nét `0,3` và gạch chân xuất hiện lần lượt, có nút viết lại. Không dùng ảnh raster hoặc thêm thư viện chuyển động.
- [FACT] Thêm minh họa kéo thanh số thập phân, vòng dạy 7 bước bám nhãn của hệ thống hiện hành và sơ đồ đồng hành ba vai trò. Đây là nội dung giới thiệu, không chấm hoặc lưu câu trả lời.
- [FACT] Bộ biểu cảm tự chuyển mỗi 2 giây, có chọn trực tiếp, trước/sau và tạm dừng. Dừng khi ngoài màn hình, trang bị ẩn hoặc người dùng yêu cầu giảm chuyển động. Bản cập nhật theo góp ý mới tiếp tục chuyển khi rê chuột/focus. Timer và observer được giải phóng khi rời trang.
- [FACT] Triển khai Admin theo ADR-051: xác thực độc lập tại máy chủ, token ký có scope và school id, giới hạn thử sai, API chỉ đọc, phản hồi không cache. Mật khẩu không được kiểm ở giao diện.
- [FACT] Admin phân biệt nhật ký vận hành và lịch sử sự kiện buổi học; lọc loại/tìm kiếm trước giới hạn dòng. Có từng lượt xử lý kể cả lượt không dùng AI, request/buổi học, thời gian chạy, token, chuỗi fallback và dấu vết nguồn. Usage theo model có thể xem từ lịch sử hoặc nhật ký vận hành.
- [FACT] Các tác vụ model/RAG/web được quan sát tại ranh giới thực; không suy diễn việc model tự dùng công cụ. Lookup web có thể dùng cache. Không có số liệu quota còn lại nếu provider không cung cấp; token thiếu được thể hiện bằng dấu `—`.
- [FACT] Nhật ký JSONL có giới hạn và xoay tệp, chứa metadata; không chứa prompt, lời học sinh, câu trả lời, API key, mật khẩu hay audio. Kiểm thử mặc định tắt ghi nhật ký và dùng bộ nhớ/tệp tạm khi kiểm tra chức năng quan sát.

## Kiểm chứng

- [FACT] `pnpm lint` và `pnpm build` đạt. Toàn bộ 37 tệp/242 kiểm thử giao diện đạt với `pnpm test --maxWorkers=2`.
- [FACT] Lượt chạy toàn bộ giao diện đồng thời với kiểm thử API có hai ca hội thoại timeout ở mức 5 giây. Chạy lại giới hạn 2 worker đạt, không đổi hoặc bỏ kiểm thử và không tăng timeout.
- [FACT] 275 kiểm thử API liên quan đạt (loại Atlas): Admin, gateway, model usage, model events, RAG, grounded speech, web lookup, tài khoản và session API. Bao gồm 9 ca Admin/quan sát mới: quyền truy cập, hết hạn, đổi cấu hình mật khẩu, giới hạn thử sai, tách trường học, log tác vụ thực trong thread pool, độ bền nhật ký, lọc trước giới hạn và lượt xử lý không gọi AI.
- [FACT] Không test/seed vào `cavat_dev` hoặc `cavat_prod`; không chạy kiểm thử Atlas. Việc kiểm tra giao diện Admin đọc lịch sử có sẵn, không sửa dữ liệu người học.
- [FACT] Kiểm tra trình duyệt: đăng nhập Admin bằng mật khẩu được yêu cầu, xem model và usage thật, lọc được 4 bản ghi RAG cũ; không tạo bản ghi giả để trình diễn. Ở 375 px không tràn ngang; thao tác thanh kéo từ 3 sang 4 cập nhật đúng 4/10 = 0,4.
- [FACT] Quan sát bộ cảm xúc trong trình duyệt xác nhận timer có chu kỳ 2 giây, trước đây tạm dừng khi tương tác; yêu cầu mới ở phần bổ sung bên dưới đã thay cách này. Kiểm thử timer xác nhận tự chuyển, vòng lại, chọn thủ công, dừng và giảm chuyển động.

## Phạm vi

Không đổi chính sách dạy, điểm mastery, ngưỡng qua bài, lựa chọn model hoặc tài khoản người học. Không tuyên bố cải thiện kết quả học tập nếu chưa đo. Nhật ký lịch sử chỉ hiển thị những chi tiết các sự kiện cũ đã lưu; nhật ký vận hành mới có thời gian và mã request từ khi triển khai chức năng này.

## 29/10/2026 · Bổ sung: giao diện trắng–xanh và phân tích nguồn AI

### Vấn đề và yêu cầu

[FACT] Chủ dự án phản ánh phòng quan sát dài, chưa phân biệt RAG/internet, số web là 0 gây khó hiểu; yêu cầu nền trắng, xanh dương chủ đạo và tiếp tục đổi cảm xúc khi hover.

### Thực hiện

- [FACT] Thay bộ màu và tiêu đề sang trắng–xanh, sans serif; đồng bộ áo Buddy, favicon, bảng viết và đường tiến bộ giáo viên. Các màu trạng thái học tập vẫn biểu thị ý nghĩa riêng. Giá trị cốt lõi được giữ ở đầu trang.
- [FACT] Bỏ tự dừng do hover/focus; giữ nút tạm dừng, dừng ngoài khung nhìn/trang bị ẩn và hỗ trợ reduced motion.
- [FACT] Admin chia nhật ký, RAG & Internet, model & usage; phân trang 12 dòng, cuộn giới hạn, chi tiết ở cột cạnh và gộp model theo tên.
- [FACT] Bổ sung ranh giới HTTP thực tế ở ba adapter web: đếm cả HTTP lỗi/timeout, cache riêng và các lý do định tuyến. Bỏ query/headers/body khỏi metadata. Không tạo cuộc gọi hoặc dữ liệu giả.
- [FACT] Lịch sử cũ chỉ lưu nguồn web đã tìm được, không đủ để đếm mọi lần thử. UI ghi “Nguồn web đã lưu”; HTTP chưa theo dõi hiển thị dấu “—”. Không cộng hai phạm vi lịch sử/vận hành. Tham chiếu bổ sung ADR-051.

### Kiểm chứng

- [FACT] 244 kiểm thử giao diện (37 tệp) đạt với 2 worker; lint và production build đạt. Build còn cảnh báo chunk trên 500 kB có sẵn.
- [FACT] 279 kiểm thử API liên quan đạt, 1 Atlas bị loại; hoàn toàn offline/in-memory. Gồm 13 ca Admin/quan sát, bổ sung HTTP 403 và lọc query nhạy cảm, timeout, cache không tính HTTP, lọc trước phân trang và metadata phạm vi.
- [FACT] Cập nhật assertion phiên bản template trong kiểm thử báo cáo từ 0.16.0 sang phiên bản hiện có 0.17.0; không đổi logic dạy trong việc này.
- [FACT] Trình duyệt hiển thị số liệu hiện có: 687 lượt gửi model, 4 RAG; lọc được 4 RAG và đọc tiêu đề đoạn kiến thức ở cột chi tiết. Bảng model còn 6 dòng sau khi gộp vai trò. Ở màn hình 375 px không có tràn ngang toàn trang.
- [FACT] Kiểm thử hồi quy xác nhận Buddy tiếp tục chuyển khi hover và focus, đúng chu kỳ 2 giây; vẫn tạm dừng được bằng nút riêng.
- [FACT] Không có connector Google Docs hay phiên tài liệu kết nối. Ghi sẵn nhật ký trong repo để đồng bộ vào Phụ lục E của tài liệu nguồn ở phiên có connector.

## 29/10/2026 · Điều chỉnh thẩm mỹ theo phản hồi chủ dự án

- [FACT] Chủ dự án yêu cầu giảm saturation xanh, pha cyan; khôi phục font bản trước và dùng đỏ đô cho chữ nhấn/chi tiết. Khôi phục Georgia 400 và nét nghiêng của các tiêu đề; giữ Be Vietnam Pro cho nội dung và dữ liệu. Hệ màu chính chuyển sang xanh/cyan dịu, ví dụ nút #3d748c; chữ nhấn và nét viết trên bảng dùng #863b4f.
- [FACT] Sửa nền banner bị cắt theo khung 1320 px bằng lớp nền ngoài phủ toàn chiều ngang, giữ khung nội dung bên trong. Đo bằng DOM ở viewport 1920 px: nền rộng 1905 px (trừ scrollbar), bắt đầu x=0; nội dung rộng 1320 px. Ở viewport 375 px, nền và document đều rộng 360 px, không tràn ngang.
- [FACT] Dòng bản quyền đổi đúng yêu cầu: `© 2026 Monkey Edu · Devhouse Software`.
- [FACT] Lint, production build và 8 kiểm thử liên quan trang chủ/Admin/Buddy đạt. Không đổi API hay logic sư phạm trong lần chỉnh này. Ảnh kiểm tra: `monkey-cyan-burgundy.png` trong thư mục hình của chat.

### Điều chỉnh tiếp theo yêu cầu chủ dự án

- [FACT] Tăng sắc blue của màu chính từ #3d748c sang #3f76a3, đồng bộ nút/áo Buddy/favicon và các sắc độ liên quan. Nền banner đầu trang đổi thành trắng tinh #ffffff, giữ chiều rộng toàn trang. Giữ nguyên font Georgia và điểm nhấn đỏ đô.

### Đồng bộ cách gọi trên giao diện

- [FACT] Theo yêu cầu chủ dự án, thay nhãn AI bằng Gia sư Buddy trên trang giới thiệu, Admin, nhãn trạng thái và các màn giáo viên (duyệt nội dung, RAG, transcript, bộ não gia sư). Cột so sánh công cụ khác dùng nhãn trung tính “Công cụ hỏi đáp đa dụng” để không nhầm với Buddy. Không đổi identifier, API contract, tên provider/model hoặc prompt.

### Bổ sung thông tin liên hệ và điều hướng cuối trang

- [FACT] Footer hiển thị email hỗ trợ khẩn cấp, email nhà phát hành, hotline và địa chỉ văn phòng dưới dạng các khối liên hệ rõ ràng. Email và số điện thoại dùng liên kết `mailto:`/`tel:` để thao tác trực tiếp.
- [FACT] Nút quay lại đầu trang xuất hiện sau khi cuộn 480 px, dùng phần tử `button` có nhãn truy cập, cuộn mượt và tự chuyển sang cuộn tức thời khi người dùng bật giảm chuyển động.
- [FACT] Theo phản hồi kiểm tra trực quan, nút quay lại đầu trang được thu thành nút tròn 48 px chỉ có biểu tượng để không che nội dung cuối trang; tên truy cập và tooltip vẫn được giữ.
- [FACT] Tên tài khoản trên thanh điều hướng được bọc trong badge bo tròn có biểu tượng người dùng, nền xanh rất nhạt và viền nhẹ; tên dài được rút gọn thay vì làm vỡ bố cục.
