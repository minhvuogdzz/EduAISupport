# ADR-044: Gia sư giữ câu hỏi tiếp theo, không mắc ở vòng tiếp nhận

Ngày: 28/10/2026 · BRAIN-8 · DI-98

## Vấn đề và yêu cầu

[FACT] Chủ dự án thử tiếp và phản ánh gia sư chưa cải thiện, cần chủ động hỏi và dẫn buổi học. Đọc snapshot mới nhất chỉ đọc theo school_id cho thấy các lời tiếp nhận bị đưa vào REPAIR: lặp lý thuyết, không có câu hỏi kế tiếp. Bộ điều khiển vẫn chờ câu kiểm tra cũ nhưng phần lời nói đã không dẫn học sinh về câu đó. Nới yêu cầu câu hỏi trước đây đã làm mất nhịp dạy trong đường hội thoại, không thể giải quyết chỉ bằng thêm web/RAG hoặc sửa giọng nói.

## DI-98 — Lời tiếp nhận quay về việc học đang chờ

- `CONTINUE` là nhãn hội thoại riêng: đồng ý/đã hiểu/muốn tiếp tục nhưng chưa có nội dung Toán. Tín hiệu rõ được đọc tại chỗ; câu khác có thể do `listener.v4` đề xuất. Câu còn đáp số/lý do Toán vẫn PASS, không coi là lời tiếp nhận. Phân biệt chữ A/U trong Toán với à/ừ; đáp đúng/sai/có/không của câu Toán đóng giữ đường chấm cũ.
- Ở bước lý thuyết/nói lại, CONTINUE nói ngắn rồi hỏi câu giáo án đang chờ; không giảng lại, tự chuyển bài, chấm đạt hoặc gọi model. Hoạt động cả khi trần model hết; không ép dùng thêm quota cho một lời đồng ý. Chỉ câu trả lời có nội dung mới đi qua rubric/chấm như trước.
- Xin giảng lại: ưu tiên căn cứ của biến thể lý thuyết hiện tại thay vì cả đoạn phương pháp chung. Model giảng một bước ngắn, server nối câu hỏi kiểm tra đang chờ. Câu hỏi lý thuyết tra RAG/web cũng quay lại câu kiểm tra đó sau khi được trả lời.
- Trong luyện tập, policy R-CONVERSATION chọn REDIRECT cho CONTINUE; giữ phase và không ghi gợi ý H2 hay lần sai vì lời đồng ý. Câu tiếp theo do server chọn theo loại bằng chứng đang chờ: đáp án, cách làm, probe được duyệt hoặc lựa chọn hỗ trợ. Câu hỏi nhỏ đã có hợp đồng chấm được giữ khi học tiếp; sau giải thích thiếu câu hỏi, server nối câu tiếp tục phù hợp thay vì tự tạo bài số mới.
- Không thêm câu hỏi khi con rõ ràng xin nghỉ. Con trả lời đúng/đã giải thích đủ thì các luật đi tiếp hiện có vẫn chạy, không hỏi lại để đủ thủ tục.

Artifact: `brain/1.6.0`, `constitution.v12`, `listener.v4`, `context-reader/0.7.0`, `hint-policy/0.15.0`, `teaching-templates/0.12.0`, `grounded-speech/0.10.0`. Prompt cũ không ghi đè. MessageRead nhận thêm CONTINUE; RecordedReader đọc nhãn đã lưu. Node :DIALOGUE không vào bằng chứng nói lại; replay không gọi AI/web. Không migration, sửa hội thoại hoặc ghi kiểm thử vào database thật.

## Kiểm chứng và giới hạn

Regression dùng luồng thật với provider giả: chuỗi lời tiếp nhận → câu hỏi chờ → đáp Toán đúng → chuyển bước; không gọi AI/chấm/gợi ý do ACK, kể cả hết trần; giữ phase giải thích, probe và hợp đồng câu hỏi nhỏ; tôn trọng nghỉ. Các kiểm tra chấm/mastery và replay cũ vẫn phải qua.

[FACT] Bản sao phiên đang mở được khôi phục đúng version giáo án, không restart bài. Năm lời tiếp nhận được trả về câu chờ với 0 model call, không ghi đáp án; sau nội dung Toán phù hợp, chuyển tới bài tập. Một lượt xin giảng bằng model thật cho lời giải thích rồi đúng một câu hỏi chờ, không bị bác. Đây là kiểm chứng lỗi đã quan sát, chưa chứng minh chất lượng mọi hội thoại.

Giữ vòng dạy bảy bước, node policy, giáo án, công thức/ngưỡng mastery và nguồn web của BRAIN-7. Phân loại đúng ACK làm tránh ghi hỗ trợ giả cho câu chưa cần trợ giúp; REPAIR thật vẫn ghi hỗ trợ như trước. Không tự coi con đã hiểu chỉ vì con nói đã hiểu.
