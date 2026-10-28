# ADR-040: Nghe theo ngữ cảnh và giảng lý thuyết bằng kiến thức Toán có kiểm tra

Ngày: 28/10/2026 · BRAIN-4 · DI-91, DI-92, DI-93

## Yêu cầu và vấn đề

[FACT] Chủ dự án yêu cầu model thực sự hiểu lời học sinh, giảng lý thuyết bằng kiến thức nền và internet trong phạm vi an toàn, không chỉ đổi từ của RAG. Vẫn giữ kế hoạch Claude đã làm và Socratic. BRAIN-3 chưa đạt: tại STP-PH01-5, một từ chưa rõ ý sau thời gian chờ dài bị đưa lên H6, lời cô thêm yêu cầu rút gọn, rồi đóng câu khi con nói “không”. Hội thoại trình duyệt và snapshot giáo án được đọc, không sửa dữ liệu thật khi kiểm thử.

## Quyết định

### DI-91 — Nghe trước khi áp luật

`listener.v1` nhận nguyên lời con, câu cô thực sự đã nói, bước đang chờ và hội thoại gần đây. Lời hiện tại đặt riêng sau lịch sử. Model đề xuất PASS / AMBIGUOUS_REPLY / REPAIR / DECLINE, không được chấm hay tự giải bài. Không mặc định “không” là “không biết”; sự từ chối không phải năng lực thấp. PASS có thể trích một đáp số đã xuất hiện trong lời con; số và dạng số phải có thật trong đầu vào, rồi mới qua MathChecker.

`R-CONVERSATION` giữ bước đang chờ. Làm rõ ý, hỏi lại lời cô, sửa hiểu lầm hoặc muốn nghỉ không cộng lượt sai, không kích hoạt H6 do thời gian bỏ trang. Khi thực sự giảng khái niệm, ghi hỗ trợ H2 (giữ mức cũ nếu đã cao hơn); không tạo điểm độc lập giả cho câu đã được cô giúp. Không dùng bộ chọn nước đi cũ để biến bước sửa hiểu lầm thành câu gợi ý khác. Các luật gõ nhầm đã có được tái sử dụng.

Không ép lời giải thích trọn ý hoặc lời tôn trọng muốn nghỉ phải kèm câu hỏi. Vẫn tối đa một câu hỏi cần con hành động; cho phép câu hỏi phản chiếu ngắn “Con chưa hiểu…?” trước đoạn giảng và câu hỏi chính. Bộ conductor không tự tắt model sau hai câu hỏi khi còn dùng được model, và không ép tăng gợi ý cho một lượt sửa hiểu lầm. Chuẩn hoá teen code dùng để phân tích, không thay lời con trước khi model nghe. Có fallback khi gateway không hoạt động; “không” lặp sau làm rõ được giảng một bước thay vì hỏi mãi.

### DI-92 — Được giảng bằng kiến thức ngoài RAG

`ALLOW_TUTOR_KNOWLEDGE=true` mặc định theo yêu cầu trực tiếp của chủ dự án; `false` giữ đường kiểm nguồn nghiêm ngặt cũ. `constitution.v9`, `math_g5.v2`, `brain/1.3.0` cho phép dùng kiến thức Toán chuẩn của chủ đề hiện tại và nền trực tiếp, giải thích theo cách khác và minh hoạ bằng ví dụ mới. Giảng bài, trả lời lý thuyết và sửa hiểu lầm không bị buộc đủ từ trùng với đoạn RAG.

Đường câu hỏi vẫn tìm RAG và ấn phẩm chính thống trước. Cổng nghĩa có thể chọn duy nhất một khái niệm trong danh sách server cho bài hiện tại / tiên quyết; internet chỉ nhận tên khái niệm, không nhận lời/tên học sinh, không URL do model chọn. Vẫn chỉ các ấn phẩm công khai đã xác minh của NXB Giáo dục và ĐH Cần Thơ, không tìm web tự do. Khi nguồn thiếu, model được giảng từ kiến thức nền với kiểm tra riêng, không giả trích dẫn hay nói đã tìm được trên web. Câu hỏi lý thuyết không bị từ chối chỉ vì giống câu cô đang hỏi; bảo vệ đáp án bài đang chờ và assessment vẫn áp dụng.

`curriculum-check.v1` kiểm tra toàn bộ lời giảng bằng một lượt gateway riêng: đúng Toán, đúng phạm vi, giữ yêu cầu đề, đáp đúng ý con và không lộ lời giải khi chưa được phép. Đây là lượt kiểm tra riêng, có thể cùng model trong chuỗi, không phải chứng minh hình thức. Kiểm số học chính xác, điều kiện hình học, dạng đáp án và lộ đáp số vẫn có code. Căn cứ phân biệt tử/mẫu và các đường cao được giữ bên cạnh tri thức node. Lượt xác nhận đúng ngắn, không giảng thêm kiến thức không cần thiết.

### DI-93 — Quyền giảng gắn với hợp đồng câu đang học

- Giữ đề gốc, không lấy rephrase thay yêu cầu. Phân số thập phân không bị đổi thành bài rút gọn. Ví dụ cô giảng được đổi số, nhưng không tự hỏi một bài số khác trong khi hệ thống vẫn chấm bài cũ.
- Câu hỏi nhỏ về số chữ số, tử/mẫu trong đổi số thập phân được chấm tất định theo đúng câu vừa hỏi; đúng bước là PARTIAL, không là sai cả bài. Ví dụ giảng tách khỏi số của bài đang chờ khi cần bảo vệ lời giải và giữ cùng mức khó (số chữ số, số 0 đầu phần thập phân). Câu hỏi có chấm phải gắn với đề hoặc bước nhỏ mà server có hợp đồng chấm; không tạo bài mới không được theo dõi. Ở bước giải thích lý thuyết, model được trả lời trọn ý mà không thêm câu hỏi mới.
- Nếu giáo án NumericAnswer thiếu `form`, input v3 suy ra dạng yêu cầu tường minh từ đề rồi dùng MathChecker hiện có. Input v1/v2 giữ cách đọc cũ, không viết lại lịch sử.
- Một đáp án đúng đã kèm lý do được ghi bằng rubric đang có, không hỏi lại chỉ để đủ lượt. Điều kiện bắt buộc giải thích vẫn phải có bằng chứng; model không cho điểm.
- Phân biệt `answer_revealed` (đáp án đã giảng ở H7) với `solved` (con làm đúng). Không cấm giảng lại đáp án đã hiện, cũng không biến việc thấy đáp án thành làm đúng.
- Replay v3 dùng lời cô thật trong event log để chấm câu hỏi nhỏ, thay vì câu mẫu tái tạo. Nguồn nút gợi ý và gợi ý do conductor tự đưa được ghi riêng; không trừ thống kê thành số âm.

## Giữ nguyên và giới hạn

Không đổi vòng dạy 7 bước, đồ thị, giáo án xuất bản, chính sách node hoặc công thức/ngưỡng mastery. Không đưa khoá assessment vào model, không giao quyền chấm hay qua bài cho model. Event thêm trường có mặc định; không migration/seed/ghi kiểm thử vào database thật. Trần 40/160 và chuỗi model giữ nguyên, nên quota hoặc output bị bác vẫn có thể dùng fallback.

Một lượt kiểm bằng model vẫn có thể sai. Những lỗi thực gặp trong phép thử (đảo tử/mẫu, nhầm điều kiện tam giác, đưa luôn lời giải, đổi sang bài khác, bác phân số vì chưa rút gọn) được đưa vào regression hoặc căn cứ kiểm tra. Không tuyên bố các phép thử ngắn chứng minh mọi hội thoại đều đúng hay đạt chất lượng GPT/Claude trong mọi tình huống.
