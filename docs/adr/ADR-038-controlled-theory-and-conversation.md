# ADR-038 · Giải thích theo nghĩa, tra cứu lý thuyết có giới hạn

Ngày: 27/10/2026 · BRAIN-2 · DI-86, DI-87

## Bối cảnh và quyết định của chủ dự án

Chủ dự án thử bản BRAIN-1 và thấy lời nói chưa tự nhiên, bám tài liệu quá sát; cô đáp `hi` bằng
“Con chào cô” và đưa gợi ý dài. Yêu cầu mới: có thể lấy lý thuyết liên quan từ Internet khi tài liệu
thiếu, từ nguồn chính thống, trong phạm vi bài học; cô nói nhẹ nhàng, đúng vai. Yêu cầu này cập nhật
quyết định Wikipedia duy nhất và chỉ hỏi “X là gì” của DI-51.

## Thay đổi

1. **Chào hỏi không phải bài làm (DI-87).** Nhận diện toàn câu chào/cảm ơn/sửa lời chào bằng luật,
   đáp ngắn không gọi model. Giữ phase, bài chờ, số lần làm, hint, xác nhận và mastery. Không nuốt câu
   “chào cô, mẫu số là gì?”. Sự kiện `:SOCIAL` trong vòng chương không vào phát lại bài làm hay bộ đếm
   giữ chân. Vòng item riêng có `R-SOCIAL`; input mới lưu cờ `social_routing`, input cũ không có cờ vẫn giữ cách phát lại cũ, không sửa kết quả lịch sử. Prompt `constitution.v7` và validator bác lời đảo vai.
2. **Câu trả lời theo nghĩa (DI-86).** `grounded.v3` dùng riêng cho trả lời câu hỏi; bridge cũ vẫn giữ
   `grounded.v2`. Không đòi 60% từ trùng nguồn hay số thập phân giống cách viết. Quy tắc của bài hiện tại đi kèm các đoạn truy hồi để chế độ không có embedding không chỉ kéo về ví dụ cũ. Các số học sinh đưa được nhắc lại, nhưng lời học sinh không làm căn cứ kiến thức. Một lời diễn đạt mới
   phải qua một lần gọi gateway kiểm toàn bộ khẳng định với nguồn; các trích dẫn hỗ trợ phải nằm thật
   trong nguồn (ít nhất 4 từ). Không coi lời học sinh hoặc hội thoại là căn cứ kiến thức. Sai phép tính,
   thuật ngữ Toán chưa có căn cứ, xưng hô, độ dài, dữ liệu cá nhân vẫn kiểm bằng mã. Số mới chỉ được
   phép trong phép bằng/so sánh đã tính đúng, hoặc ví dụ phân số đúng định nghĩa/ký hiệu trong nguồn. Mỗi đường nguồn (RAG, rồi nguồn ngoài nếu thiếu) có tối đa hai lần viết, mỗi lần thêm một lần kiểm nghĩa; tất cả tính vào ngân sách hiện có.
3. **RAG trước, nguồn ngoài sau.** Ngoài lúc lý thuyết/nói lại, câu hỏi thuần khái niệm trong luyện tập
   được trả lời cùng đường này, không chấm như đáp án sai. Bài assessment giữ đường chính sách hiện có.
   Hỏi lại đúng câu đang chờ hoặc hỏi tiết sau vẫn bị chặn. Không tăng hint hay đổi mastery vì một câu
   hỏi khái niệm. Output trong luyện tập vẫn qua bộ kiểm đáp án của chính item (kể cả chọn đáp án), không gửi đáp án cho model; ví dụ vô tình trùng đáp án bị bác và viết lại. Mỗi chờ vẫn có trần số câu hỏi hiện hành.
4. **Nguồn thực, phạm vi nhỏ (DI-86).** Mặc định `WEB_LOOKUP=official`: tra trong văn bản công khai của
   [SGV Toán 5, NXB Giáo dục](https://sachdientu.nxbgd.vn/thu-vien-so/doc-sach/sgv-toan.4491495468).
   Kiến thức nền tử số/mẫu số/phân số dùng thêm bài nghiên cứu của Đại học Cần Thơ (Dương Hữu Tòng, 2016, Tạp chí Khoa học, 43: 93–102) phân tích SGK lớp 4; chỉ lấy các câu định nghĩa tường minh, không đọc công thức PDF bị mất bố cục hay phần bàn luận nghiên cứu.
   Đây là tìm đoạn trong danh mục đã xác minh, **chưa phải tìm kiếm web tổng quát**. Không dùng đuôi
   `.edu.vn` làm bằng chứng uy tín, không dùng đoạn search-engine thay cho nội dung gốc. Trang chỉ có
   mục lục, mục tiêu, câu hỏi hoặc lỗi OCR không đủ căn cứ. Nội dung trả phí/đăng nhập không được vượt
   qua. Danh mục hiện có hai ấn phẩm, còn hạn chế; không có đoạn phù hợp thì giữ câu hỏi cho giáo viên.
5. **Khóa truy vấn và mạng.** Tên khái niệm trong danh sách hai chương và tên node hiện tại/tiên quyết
   quyết định việc tra cứu; không có node thì không tra. Không lấy từ ví dụ tình cờ nhắc kiến thức sau.
   Chặn câu có số, tên riêng dư, liên hệ, URL, chủ đề ngoài phạm vi; chỉ truyền tên khái niệm chuẩn,
   không truyền nguyên lời/tên học sinh. Chỉ GET URL HTTPS của ấn phẩm đã xác minh, không theo redirect hay
   liên kết. Timeout 8 giây, tối đa 2 MB (PDF tối đa 20 trang), cache công khai 24 giờ; lỗi không cache âm. Chỉ đọc phần văn bản
   trang sách, bỏ script/style/navigation. Nguồn là dữ liệu, không có quyền ra lệnh.
6. **Kiểm chứng và dấu vết.** Nguồn ngoài cần lời trả lời đã qua kiểm nghĩa; hết quota hoặc không xác minh
   được thì giữ câu hỏi, không đọc một câu vụn để giả làm lời giải. Giáo viên có URL trong nguồn hội thoại;
   `WEB_LOOKED` giữ khái niệm thực sự đã tra, đoạn dùng và SHA-256 để kiểm tra, phát lại không gọi mạng.
   `off` tắt tra cứu; `wikipedia` là adapter cũ tùy chọn, chịu cùng cổng phạm vi bài học.

## Giới hạn và kiểm chứng

Kiểm nghĩa là một đánh giá của model, không phải chứng minh hình thức. Kiểm trích dẫn chống nguồn bịa,
không tự chứng minh một mệnh đề là đúng. Không tuyên bố loại hết hallucination. Bộ kiểm số học chỉ xử lý
biểu thức đọc được; kiến thức bằng lời vẫn dựa vào nguồn và kiểm nghĩa. Không tự đổi ngưỡng sư phạm,
chương học, câu hỏi, đáp án hay điểm.

Kiểm thử: `test_brain2.py` (mọi phase, resume, phạm vi, nguồn, redirect, số học, kiểm nghĩa), hồi quy
`test_grounded.py`, `test_web.py`, vòng dạy/conductor và toàn bộ suite offline. Bài đo trực tiếp dùng câu
hỏi tổng hợp, chỉ index trong bộ nhớ và gateway; không tạo phiên hay ghi dữ liệu học sinh lên Atlas.
Số đo và giới hạn quan sát được ghi ở báo cáo BRAIN-2 kèm PR.
