# ADR-043: Tìm tài liệu mới trên web trong phạm vi bài học

Ngày: 28/10/2026 · BRAIN-7 · DI-97

## Quyết định của chủ dự án

[FACT] Chủ dự án yêu cầu mở rộng tìm kiếm internet, thay vì chỉ tìm trong hai tài liệu cố định, và tiếp tục công việc theo luồng đã có. Yêu cầu cập nhật giới hạn nguồn của ADR-038; vẫn chỉ lý thuyết bài đang học và kiến thức nền cần thiết của hai chương, nguồn có kiểm soát.

## DI-97 — Khám phá trang mới, đọc nguồn gốc và kiểm lời giảng

1. `WEB_LOOKUP=search` là mặc định mới. RAG trước; khi thiếu, giữ cổng chọn khái niệm hiện tại/tiên quyết của BRAIN-4 rồi tìm trang mới theo tên khái niệm và cấp học. Truy vấn do server tạo, không gửi nguyên lời, tên, số trong bài hay lịch sử học sinh. Model không chọn URL hoặc mở rộng chương.
2. Adapter tự viết bằng httpx, không thêm framework RAG/agent. Khi có `TAVILY_API_KEY`, dùng endpoint Search mức basic, không lấy generated answer hay raw content; nếu không có/key lỗi thì thử Bing RSS và DuckDuckGo HTML. Không vượt challenge/captcha hoặc nội dung cần đăng nhập/trả phí. Công cụ công khai có thể không dùng được; cuối cùng giữ nguồn cố định cũ và đường tri thức Toán có kiểm tra. Không tự đăng ký/mua dịch vụ.
3. Danh mục theo tên miền (có kiểm ranh giới host): NXB Giáo dục, Bộ GDĐT, học liệu Cánh Diều/Học 10, các cổng giáo dục TP.HCM/Hà Nội và ba trường sư phạm/đại học được chỉ định. VnDoc/VietJack là nguồn **tham khảo**, ghi rõ loại, xếp sau các nguồn trước. Không coi toàn bộ `.edu.vn` là có thẩm quyền. Không chấp nhận tên miền giả mạo, URL chứa credentials, HTTP, cổng lạ hoặc IP nội bộ.
4. Tối đa sáu ứng viên, đọc tối đa hai trang mới/lượt. Lọc liên quan qua tiêu đề/URL, loại lớp khác được ghi rõ; sau đó đọc HTML/PDF của chính trang. Không dùng snippet hay câu trả lời của máy tìm kiếm làm bằng chứng. Chỉ trích đoạn lý thuyết có khái niệm liên quan, bỏ quảng cáo/script/navigation và dòng bài tập/đáp án. Không chạy nội dung trang, không tải tài nguyên phụ hoặc theo redirect; có giới hạn dung lượng, timeout và số trang PDF.
5. Câu trả lời vẫn qua kiểm nguồn, Toán, phạm vi, dạng đề và lộ đáp án hiện có. Thiếu nguồn hoặc nguồn không đủ thì dùng tri thức nền có kiểm tra, không giả citation. Ghi WEB_LOOKED với URL, đoạn trích/hash, tên công cụ và loại `search`/`fixed`; nếu lời cuối từ kiến thức model thì giữ nhãn LLM, không gán WEB chỉ vì từng mở một trang. Replay đọc event, không tìm lại. Không tự đưa trang tìm được thành giáo án hay nạp vào RAG; nội dung muốn dùng lâu dài vẫn qua đường tài liệu/duyệt hiện có.
6. Cache nguồn thành công trong một ngày, kiểm URL/khái niệm/hash khi đọc lại; không cache thất bại. `official` giữ hai ấn phẩm cũ, `wikipedia` giữ adapter cũ, `off` tắt web. Giữ giáo án, vòng dạy, chấm, hint/mastery và prompt giọng dạy của BRAIN-6.

## Kiểm chứng và giới hạn thực tế

Regression dùng MockTransport: tìm URL mới → tải trang gốc → trả lời có URL; không dùng snippet, không gửi câu cá nhân, chống URL sai/redirect, cache, lỗi provider và nguồn cũ. Suite offline dùng MONGODB_URI rỗng. Không ghi thử vào database học thật.

[FACT] Thử công cụ công khai thật: có kết quả lệch chủ đề hoặc challenge. Sau lọc nguồn/độ liên quan, ba chủ đề thử cuối chưa tìm thêm trang đạt tiêu chí: hai dùng ấn phẩm đã xác minh, một không có đoạn. Không báo các kết quả này như đã chứng minh độ phủ tìm kiếm rộng. API Tavily chưa được kiểm live nếu chưa có key; đường đó kiểm bằng mock. Cần đo tiếp với key/provider thực trước khi tuyên bố chất lượng tìm kiếm ổn định.

Tham khảo kỹ thuật: [Tavily Search](https://docs.tavily.com/documentation/api-reference/endpoint/search), [gói API miễn phí](https://www.tavily.com/pricing). Key là cấu hình server riêng, không vào repo, URL, trình duyệt hoặc log học sinh.
