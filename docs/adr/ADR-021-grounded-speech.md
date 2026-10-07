# ADR-021: Gia sư nói có căn cứ (RAG-2)

**Trạng thái:** Đề xuất, 2026-10-07.
- Chủ dự án chờ duyệt: các câu mẫu mới (`teaching-templates/0.3.0`), prompt `grounded.v1.md`, DI-39 và DI-40.
- Code ở `services/api/cavat/modules/teaching/grounded.py`.
- Liên quan: ADR-018 (Hybrid RAG tự xây), ADR-019 (đọc ý định trước khi chấm), plan v1 mục 5.5 và 5.6.

## Bối cảnh

- **Phản hồi của chủ dự án:** gia sư "trả lời theo khuôn mẫu, không có tính suy luận về phản hồi theo ngữ cảnh".
- **[FACT] Hiện trạng:** trong buổi học theo chương, những lời sau đều là câu mẫu cố định: lời giảng, lời đáp câu hỏi của cách giảng, lời nhận xét phần nói lại, và mọi câu con tự hỏi. Qwen chỉ diễn đạt nước đi trong bài tập, khi `TUTOR_RENDERER=llm`.
- **Yêu cầu:** RAG và LLM phải "chuẩn và kĩ càng", theo tinh thần bài 2T-KT:
  - LLM dựa trên tri thức có cấu trúc đã được kiểm chứng;
  - khẳng định của LLM được đối chiếu với bằng chứng;
  - mỗi thành phần có thí nghiệm chứng minh.

## Quyết định

1. **Qwen chỉ viết hai loại lời:**
   - **Trả lời câu con tự hỏi về bài:** dựa trên tối đa 3 đoạn Hybrid RAG truy xuất trong phạm vi bài đang học (bài đó, các bài nó dựa vào, bài tương tự).
   - **Câu nối:** một câu nối điều con vừa nói với lời giải thích đã duyệt khi con trả lời câu hỏi của cách giảng chưa đúng. Lời giải thích được nói nguyên văn ngay sau câu nối.
2. **Kiểm chứng tất định trước khi con nghe** (lớp "khẳng định và bằng chứng" của 2T-KT):
   - mọi con số có trong nguồn (số thập phân so đúng cách viết);
   - mọi thuật ngữ Toán có trong nguồn;
   - ít nhất 60% từ có nghĩa có trong nguồn (DI-40);
   - không có chữ hay từ ngoài tiếng Việt;
   - không đặt câu hỏi, không quá số từ cho phép;
   - không hỏi thông tin cá nhân, không khen trí thông minh;
   - câu nối không chép lời giải thích.

   Câu bị chặn được thử lại một lần, kèm lý do. Vẫn bị chặn thì:
   - với câu trả lời: dùng nguyên văn câu của đoạn nguồn phủ nhiều nhất câu hỏi, nếu câu đó phủ ít nhất một nửa;
   - với câu nối: dùng câu mẫu.
3. **Không trả lời khi không có căn cứ**, và ghi lại cho giáo viên (`QUESTION_PARKED`):
   - không đoạn nào làm căn cứ (cosine Gemini dưới 0,65, hoặc độ phủ từ khóa dưới 50% khi không có vector);
   - Qwen thấy các đoạn không trả lời được;
   - không câu nào của đoạn phủ được câu hỏi.

   Hai trường hợp đặc biệt:
   - Câu hỏi thuộc **bài học sau:** gia sư nói tên bài đó và không dạy trước.
   - Con hỏi lại đúng câu gia sư đang hỏi: gia sư mời con tự nghĩ.
4. **Câu đáng lo được xét trước mọi thứ khác** (DI-41): bị đánh, bị bắt nạt, muốn làm đau mình… Gia sư nói câu ân cần và ghi cờ an toàn cho giáo viên, không bao giờ coi là câu ngoài bài.
5. **Chính sách vẫn quyết định** (quy tắc 1):
   - Phần nói có căn cứ chỉ chạy khi vòng dạy đang chờ con trả lời câu hỏi của cách giảng hoặc nói lại bài.
   - Tối đa 2 câu hỏi mỗi lượt chờ (DI-39).
   - Đòi đáp án, than chán, lạc đề giữ đường riêng của ADR-019, kể cả khi viết thành câu hỏi.
   - Câu hỏi trong lúc làm bài tập giữ luồng hiện có (RAG-3).
6. **Không lộ đáp án:**
   - Lời đáp của câu đang chờ con trả lời bị bỏ khỏi đoạn nguồn đưa cho Qwen.
   - Đáp án bài tập không vào kho RAG.
7. **Ghi vết:**
   - Sự kiện `RAG_RETRIEVED` ghi đoạn được chọn và điểm từng tín hiệu.
   - Sự kiện `QUESTION_PARKED` ghi lý do không trả lời.
   - `TEACH_MESSAGE_SENT` ghi thêm `source`, `sources`, `rejected`.
   - Tab Hội thoại của giáo viên hiện:
     - ai viết câu: câu mẫu, Qwen đã kiểm chứng, hay trích nguyên văn;
     - nguồn của câu;
     - câu có căn cứ hay không;
     - lý do để lại câu hỏi;
     - các lần Qwen bị chặn.

## Hệ quả

- **Đo bằng `make eval-grounded`:**
  - Qwen thật và vector Gemini thật;
  - giám khảo `openai/gpt-oss-120b` chấm bám nguồn, đúng trọng tâm, đúng kiến thức, hợp với trẻ, có bịa không, có lộ đáp án không.
  - Kết quả và giới hạn ghi ở plan v1 mục 5.6.
- **Chi phí:** tối đa 2 lần gọi Qwen cho mỗi câu con hỏi hoặc mỗi câu trả lời lý thuyết chưa đúng, tính vào trần 15 lần mỗi buổi.
- **Không có Qwen** (`TUTOR_RENDERER=template`, hết hạn mức, lỗi mạng): câu hỏi vẫn được trả lời bằng câu nguyên văn của đoạn nguồn, câu nối dùng câu mẫu. Buổi học không dừng.
- **Lịch sử bộ kiểm chứng (đo thật, plan v1 mục 5.6.2):**
  - `0.1.0` đòi 80% mọi từ (trọng số idf) và chặn oan câu đúng;
  - `0.2.0` kiểm thuật ngữ Toán và con số, cộng 60% từ có nghĩa;
  - `0.2.1` thêm kiểm tra ngôn ngữ, sau khi Qwen sinh câu lẫn chữ Trung và chữ Anh. Kiểm tra này áp cho cả câu gợi ý trong bài tập.
- **Kiểm chứng tất định chặt hơn suy luận:** một câu trả lời đúng mà cần suy thêm một bước (mẫu số 1000 thì phần thập phân có ba chữ số) có thể bị chặn. Gia sư thà nói nguyên văn nguồn còn hơn nói điều nguồn không có.
