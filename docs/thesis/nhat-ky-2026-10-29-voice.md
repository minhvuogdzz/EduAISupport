# Ghi chép luận văn — chờ bổ sung vào Phụ lục E

Phiên này không có connector Google Docs; nội dung dưới đây được lưu trong repo để bổ sung vào tài liệu nguồn.

## 29/10/2026 · VOICE-3: tránh tự gửi lời nhận nhầm khi mở micro

- **Vấn đề:** chủ dự án báo chưa nói nhưng hệ thống xuất hiện lời học sinh “Cảm ơn các bạn đã theo dõi và hẹn gặp lại.” Kiểm tra code cho thấy một mẫu âm lượng lớn có thể kích hoạt gửi bản ghi; đường nhận dạng dự phòng còn gửi kết quả tạm thời.
- **Cách làm:** yêu cầu tiếng kéo dài trước khi giữ bản ghi; lọc segment STT đồng thời có xác suất không có tiếng nói cao và độ tin cậy thấp; chỉ gửi kết quả cuối của Web Speech; bỏ kết quả khi hủy và đóng micro. Chi tiết và ngưỡng DI (VOICE-3) tại [ADR-030](../adr/ADR-030-voice-live.md).
- **Kết quả kiểm thử:** 21 test frontend về voice qua; toàn bộ 238 test web qua, lint và build qua. 92 test backend về AI gateway và voice qua bằng provider giả/in-memory. Không chạy kiểm thử Atlas. Kiểm thử bao gồm im lặng, click, câu ngắn, hủy, lỗi thu âm và lọc segment nhiễu, không cấm lời cảm ơn thật.
- **Giới hạn:** chưa đo trên tập giọng thật; các ca trên dùng tài nguyên giả để tái hiện lỗi. Không khẳng định độ chính xác thực địa. Bộ lọc năng lượng vẫn có thể nhận tiếng nền kéo dài. Giữ nguyên chấm Toán, mastery và lịch sử hội thoại.
