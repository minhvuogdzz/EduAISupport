# ADR-053: Bàn giao Compose có voice và dữ liệu riêng

**Trạng thái:** Đề xuất, 29/10/2026. Bổ sung ADR-030 và ADR-036 theo yêu cầu chủ dự án.

- **[FACT]** API và web dùng một image/cổng; MongoDB và VieNeu-TTS chạy trong hai container riêng, không mở cổng ra ngoài. Voice dùng CPU, tải model khi chạy lần đầu và lưu cache ở volume riêng. Groq Whisper vẫn nhận dạng tiếng nói.
- **[FACT]** Archive JSONL database và archive storage được chuyển riêng cùng `.env`, không đưa vào Git hay Docker image. `deploy/prepare_handoff.py` tạo cấu hình server, giữ khóa ký nguồn nếu có, sinh mật khẩu Mongo/admin và ghi checksum cho hai archive.
- **[FACT]** DevOps chạy `docker compose up -d --build` rồi `sh deploy/import.sh`. Import dừng app, kiểm tra archive, từ chối đích có dữ liệu và khởi động app lại sau khi nạp thành công. Nếu lỗi giữa chừng phải kiểm tra trạng thái trước khi khôi phục.
- **[FACT]** CI có job build/import với database test riêng và job build voice, chờ model khởi động rồi yêu cầu tạo WAV. Không dùng secret hoặc dữ liệu thật trong CI.
- **[OPEN]** Chất lượng giọng, thời gian tải model, tài nguyên CPU/RAM và HTTPS phải kiểm tra trên server thực tế; trình duyệt dùng giọng dự phòng nếu dịch vụ voice không sẵn sàng.
