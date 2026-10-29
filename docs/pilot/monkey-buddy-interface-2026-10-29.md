# 29/10/2026 · UI-BUDDY: Nhận diện Monkey Edu và chuyển động biểu đồ

Nội dung ghi sẵn cho Phụ lục E, nhật ký luận văn. Chưa đồng bộ sang Google Docs trong phiên này.

## Yêu cầu và cách làm

- [FACT] Chủ dự án yêu cầu dùng tên sản phẩm **Monkey Edu**, linh vật **Monkey Buddy**, tăng biểu cảm và chuyển động của khỉ, thay favicon, thêm lợi ích và so sánh, vẽ dần đồ thị của giáo viên khi xuất hiện.
- [FACT] Vẽ lại linh vật bằng SVG nhiều lớp: áo xanh, khăn vàng, đuôi cuộn; năm trạng thái chào đón, lắng nghe, suy nghĩ, động viên và ăn mừng. Mỗi trạng thái có nét mặt, tư thế và chuyển động riêng. Avatar nhỏ giảm chuyển động; đồ họa dùng chung trên trang chủ, đăng nhập, học sinh và phụ huynh.
- [FACT] Favicon và biểu tượng ở thanh thương hiệu dùng khuôn mặt Monkey Buddy. Trang chủ bổ sung bộ chọn biểu cảm, nút tạm dừng, lợi ích cho từng vai trò và bảng đối chiếu với cách hỏi đáp AI đa dụng, video/bài tập. Trên điện thoại, bảng chuyển thành các nhóm theo từng tiêu chí.
- [FACT] Bảng so sánh mô tả cách tổ chức học tập, không đưa số đo hoặc tuyên bố vượt trội so với các mô hình AI. Nội dung giới hạn ở hai chương Toán lớp 5 đang có trong dự án.
- [FACT] `PageMotion` quan sát SVG độc lập với khối nội dung: dữ liệu có thể tải sau, đồ thị vẫn chờ đến khi xuất hiện trong màn hình mới chạy. Đường được vẽ trong 1,8 giây, mốc dữ liệu xuất hiện lần lượt; phần tô, cột và radar có hiệu ứng tương ứng. Giữ nguyên tọa độ và số liệu; nhãn tăng trưởng dùng đơn vị điểm trên thang 100.
- [FACT] Khi yêu cầu giảm chuyển động hoặc thiếu `IntersectionObserver`, nội dung và đồ thị hiện đầy đủ, không phụ thuộc vào hiệu ứng để đọc được dữ liệu.

## Kiểm tra

- [FACT] `pnpm build` thành công sau thay đổi cuối, gồm kiểm tra TypeScript.
- [FACT] Toàn bộ 223 kiểm thử web đạt ở lượt kiểm tra đầu; lượt cuối kiểm tra lại 5 tệp liên quan (trang chủ, chuyển động, bộ não gia sư, buổi học và lớp học): 21/21 đạt.
- [FACT] Kiểm thử chuyển động xác nhận: khối nội dung hiện chưa làm chạy đồ thị nằm ngoài màn hình; đồ thị được theo dõi sau khi tải dữ liệu; observer được giải phóng; chế độ giảm chuyển động giữ biểu đồ đọc được.
- [FACT] Kiểm tra bằng trình duyệt ở 375 px và 1440 px: chiều rộng trang bằng chiều rộng màn hình, bộ chọn biểu cảm và tạm dừng hoạt động. Kiểm tra thêm bố cục ở chiều rộng mặc định 734 px.
- [FACT] Kiểm tra đồ thị bằng dữ liệu tổng hợp trong trang thử tạm: trước khi cuộn, `data-visible` chưa có và đường chưa chạy; sau khi cuộn, hiệu ứng `chart-draw` hoàn tất và stroke offset về 0. Trang thử đã được xóa, không nằm trong bản dựng hay giao diện sản phẩm; không ghi dữ liệu người học.
- [FACT] Lint toàn dự án chưa đạt do lỗi ở các kiểm thử giọng nói ngoài phạm vi thay đổi: `recorder.test.ts` và `useVoiceLive.test.ts`. Không sửa các tệp đó trong công việc này.

## Phạm vi

Không thay công thức chấm, ngưỡng, chính sách dạy, model AI hoặc dữ liệu học sinh. Không có phép đo mới về hiệu quả học tập và không có DI sư phạm mới.
