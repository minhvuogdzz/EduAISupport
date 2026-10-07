# ADR-022: Gia sư hiểu và đáp theo ngữ cảnh (CTX-1)

**Trạng thái:** Đề xuất, 2026-10-07.
- Chủ dự án chờ duyệt:
  - prompt `constitution.v3.md`;
  - câu mẫu `explain_lead`;
  - DI-42.
- Code:
  - đọc câu của con: `tutor/reader.py`;
  - nước đi EXPLAIN: `tutor/policy.py`, `tutor/renderer.py`;
  - kiểm chứng: `tutor/llm_renderer.py`.
- Liên quan: ADR-017 (Qwen bám câu mẫu), ADR-019 (đọc ý định), ADR-021 (lời nói có căn cứ).

## Bối cảnh

Chủ dự án chạy thử và thấy gia sư "trả lời theo một mẫu gì đó, chưa thông minh, không bắt theo ngữ cảnh tại chỗ".

**[FACT] Buổi học trong ảnh chụp** (đọc từ sự kiện trong `cavat_dev`):
- Cô gợi ý "Phân số thập phân có mẫu số đặc biệt…". Con hỏi "mẫu như nào". Cô đáp: "Mình quay lại câu đang làm nhé. [đề bài]".
- Ở câu lý thuyết "phần tô màu là phân số nào?", con gõ "ko" (ý là không biết). Gia sư lại hiểu là con trả lời sai.

**Ba nguyên nhân trong thiết kế:**
1. **Câu của con được đọc bằng danh sách cụm từ cứng.** Danh sách có "như thế nào" mà thiếu "như nào", nên câu này rơi vào "trả lời không đọc được" và chính sách chọn nước đi "kéo về bài" (R-REDIRECT).
2. **Qwen phải chép lại ít nhất 60% chữ của câu mẫu** (`llm-renderer.v2`), nên không đáp được điều con thật sự hỏi.
3. **Chính sách không có nước đi "giải thích điều con hỏi".**

Chủ dự án cũng nói bước sau sẽ cấu hình gia sư với "mô hình Qwen tự chủ".

## Quyết định

1. **Đọc câu của con theo ngữ cảnh.**
   - Chỉ chạy khi bộ chấm và danh sách cụm từ không đọc được: câu trả lời không phân tích được, hoặc câu "là gì" có kèm từ có nghĩa.
   - Khi đó Qwen (model class `LIGHTWEIGHT`, JSON chặt) đọc câu cùng đề bài và lời gia sư vừa nói, rồi **đề xuất** nhãn: trả lời, hỏi về điều cô vừa nói, chưa hiểu đề, không biết, ngoài bài, cảm xúc.
   - **Luật dự phòng** chạy cả khi không có Qwen: một câu hỏi lặp lại từ trong lời cô vừa nói ("mẫu như nào" sau "mẫu số đặc biệt") là con hỏi về chính điều đó.
   - Đúng quy tắc 1 và 2: nhãn chỉ là đề xuất, chính sách chọn nước đi; câu trả lời Qwen tìm thấy trong lời con do `MathChecker` chấm.
   - Mỗi lần đọc được ghi vào sự kiện `MESSAGE_READ`. Khi dựng lại buổi học, nhãn được đọc từ bản ghi, không gọi model lần nữa.
2. **Nước đi EXPLAIN** (luật R-EXPLAIN, DI-42).
   - Con hỏi về gợi ý hay nghĩa một từ: cô giải thích đúng điều đó từ nội dung đã duyệt (gợi ý của chính câu bài tập, đoạn RAG), không nói đáp án, rồi hỏi một câu để con làm tiếp.
   - EXPLAIN tính là trợ giúp ở bậc gợi ý tiếp theo, để gợi ý sau không lặp lại và câu được ghi nhận là "có trợ giúp".
   - Bài kiểm tra cuối bài: chỉ nhắc lại đề.
   - Hỏi quá 2 lần trong một câu: chuyển sang gợi ý tiếp theo.
3. **Qwen viết theo ngữ cảnh, bị chặn theo ý chứ không theo chữ** (`llm-renderer.v3`).
   - Câu mẫu là ý cần giữ. Qwen phải giữ ít nhất 60% thuật ngữ Toán của câu mẫu; câu mẫu chỉ có 1–2 thuật ngữ thì giữ đủ.
   - Không được thêm thuật ngữ Toán hay con số ngoài đề bài, câu mẫu, lời cô vừa nói, đoạn RAG và lời con.
   - Vẫn giữ bộ kiểm tra cũ: lộ đáp án, một câu hỏi, độ dài, không khen trí thông minh, chỉ tiếng Việt, không lặp lại.
4. **Lỗ hổng tìm thấy khi làm CTX-1, đã vá.** Với câu trắc nghiệm không khai báo mẫu lộ đáp án, bộ kiểm tra không bắt được câu Qwen nói "đáp án là 7/10" hay "con chọn 7/10 là đúng". Lỗi này có từ T03. Nay câu Qwen nhắc riêng phương án đúng mà không nhắc phương án khác thì bị chặn, trừ khi chính câu mẫu đã nói như vậy.
5. **Prompt `constitution.v3.md`.**
   - Có mục "Đáp theo ngữ cảnh": câu đầu tiên đáp đúng điều con vừa nói, dùng lời của con, không lặp nguyên câu cũ.
   - Có hai ví dụ, với con số không trùng câu bài tập nào.
   - Prompt dài thêm khoảng 90 token. Phần cố định vẫn chừa ít nhất 1.300 token cho hội thoại dưới trần 3.000.
6. **Ở câu lý thuyết:** "ko" trả lời câu hỏi không phải dạng có/không thì hiểu là "con không biết". Với câu hỏi có/không, "ko" được chấm là "không".
7. **Câu con tự hỏi** (RAG-2): Qwen thấy thêm 4 lượt gần nhất.

## Hướng tới "Qwen tự chủ"

CTX-1 tách hai việc mà một gia sư tự chủ cần:
- **đọc tình huống:** nhãn đọc câu của con;
- **nói theo tình huống:** lời viết tự do trong giới hạn của nước đi.

Hai việc này giờ có giao diện, có ghi vết và có kiểm chứng.

**Bước tiếp theo (CTX-2):** chính sách đưa ra các nước đi được phép kèm giới hạn của từng nước; Qwen chọn một nước và nói lý do; chính sách kiểm lại và có quyền chặn với đáp án, bài kiểm tra và an toàn.

**Nếu muốn Qwen tự chủ hơn nữa** (tự quyết cả việc nói đáp án, tự ghi điểm) thì phải đổi quy tắc 1–3 của dự án. Việc đó cần một ADR riêng do chủ dự án quyết.

## Hệ quả

- **Chi phí:**
  - Mỗi câu không rõ tốn thêm tối đa 1 lần gọi `LIGHTWEIGHT` (prompt khoảng 300 token), tính vào trần 15 lần mỗi buổi.
  - Hết hạn mức thì luật dự phòng đọc thay, và câu mẫu của EXPLAIN là gợi ý của câu bài tập.
- **Đo lường:**
  - Offline: 14 test, trong đó có đúng ca trong ảnh chạy qua API.
  - Chạy thật: thêm 3 ca vào `make eval-hard`, gồm ca của chủ dự án. Chạy khi có hạn mức Qwen ngày mới, so với báo cáo TQ-2.
- **Giáo viên:** tab Hội thoại hiện "Gia sư hiểu: con hỏi về «mẫu» (Qwen đọc)" dưới câu của con, và nước đi "Giải thích điều con hỏi".
