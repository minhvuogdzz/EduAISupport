# ADR-050: Câu mẫu chỉ chào hỏi và thông báo chờ

Ngày 29/10/2026, chủ dự án yêu cầu câu mẫu không được tham gia giảng kiến thức Toán; phạm vi được chốt là **chào hỏi và thông báo chờ**.

Router do live factory tạo bật `model_only_speech`. Phiên tài khoản luôn đi qua router này, kể cả khi không có key; các engine template giữ riêng cho scaffold offline và replay lịch sử. Không có lời model đạt kiểm tra thì không phát lời giảng, câu hỏi gợi mở, lời nhắc lại hay gợi ý cố định.

Chốt kiểm tra trước commit kiểm toàn bộ lời của lượt, không chỉ lời cuối và không bỏ qua vì trong lượt có một lời LLM khác thành công. Một đoạn dự phòng `TEMPLATE`, `EXTRACT` hoặc `WEB` sẽ giữ state trước lượt, chỉ ghi lời học sinh ngoài luồng chấm, chi phí model, lý do bác và thông báo “Con chờ cô một chút nhé.”. Không áp dụng chấm, tăng gợi ý hay chuyển bước của lượt chưa có lời hợp lệ. Lý do `MODEL_ONLY_SPEECH` và mã kiểm như `QUESTION_COUNT` được giữ trong log, không gán nhầm lỗi chất lượng thành hết quota.

Lời chào đầu buổi tách khỏi nội dung kiến thức. Chuyển bước, ví dụ làm mẫu và kết thúc buổi được model tự diễn đạt và qua kiểm tra. Bridge không được chỉ viết lời dẫn rồi ghép nguyên phần giải thích cố định dưới nhãn LLM. Các lượt luyện tập CLOSE_ITEM/CONTINUE không còn được tự bỏ qua model trong live mode.

Đề bài/ngân hàng câu hỏi đã duyệt là dữ liệu cấu trúc bất biến, hiện ở QuestionCard; không phát lại dưới dạng câu mẫu trong hội thoại. Luật chấm assessment và nội dung đề không đổi. Phản hồi an toàn cho tình huống nguy hiểm vẫn ưu tiên theo quy chế hiện có. Không viết lại lịch sử hội thoại, giáo án hay dữ liệu học sinh.

Kiểm chứng offline gồm: nhà cung cấp vẫn hoạt động nhưng lời bị bác; lượt trộn LLM với câu Toán cố định; giữ prompt/input_id/tiến độ/mức gợi ý; ghi đúng modality; giữ số lần gọi model; chào hỏi được phép; bridge không ghép thêm nội dung tĩnh; ví dụ lấy dữ kiện đã duyệt để model soạn lời. Kiểm tổng API tách các test Atlas, không gọi provider thật hay ghi DB học sinh.
