# ADR-019 — Hiểu học sinh đang nói gì trước khi chấm

**Trạng thái:** Đề xuất (2026-10-06), chờ chủ dự án duyệt các DI-32 đến DI-38. Nguồn tham khảo: kiến trúc gia sư của repo Edubot (trang web gia sư lịch sử của chủ dự án): bộ chuẩn hóa câu chữ, nhận diện ý định theo thứ tự ưu tiên, các nước đi theo ý định, chống lặp, bộ kịch bản 10 vai học sinh.

## Bối cảnh

Chủ dự án chạy thử ngày 2026-10-06 và chỉ ra:
- gia sư chưa xử lý khi con nói "không biết", "là sao", không hiểu, hay nói sang chuyện khác;
- gia sư nói cứng, quá ít lời;
- các bài test quá dễ, không ép được gia sư.

Chạy thử bằng kịch bản trên vòng dạy thật (offline) cho thấy:
- Ở bước giảng lý thuyết, mọi câu trả lời, kể cả "con không biết", "là sao ạ", "cho con đáp án đi", "con chơi game được không", đều nhận "Cô cảm ơn con." rồi gia sư đi tiếp.
- Ở câu hỏi:
  - "là sao", câu lạc đề và câu than chán bị chấm là "không đọc được" (UNPARSEABLE) và tính là một lượt bí. Ba lượt như vậy kích hoạt R-FRUSTRATION, gia sư đưa lời giải từng bước. Nói lạc đề ba lần là lộ cách làm.
  - "Không biết" lặp lại làm gia sư hỏi đi hỏi lại "gợi ý thêm hay tự thử lại?".
  - Gợi ý chung của bài ("viết vào bảng hàng") được dùng cả cho câu chọn phân số, nơi nó không liên quan.
  - Câu viết tắt như "ko bit" không được nhận ra.
- Không có câu nào công nhận cảm xúc hoặc từ chối đưa đáp án một cách có lý do.

## Quyết định

1. **Đọc ý định trước khi chấm.** Bộ đọc ý định tất định (`assessment/student_intent.py`):
   - chuẩn hóa chữ: viết tắt kiểu teencode như "ko", "k", "bít", "j", "z"; thiếu dấu;
   - xếp lời học sinh vào một trong: im lặng, đòi đáp án, cảm xúc tiêu cực, hỏi lại đề, không biết hoặc xin gợi ý, lạc đề, hoặc một lần trả lời thật;
   - thứ tự ưu tiên như Edubot. Câu vừa nói "không biết" vừa có số ("chắc là 0,7") vẫn là một lần trả lời.
2. **Ba kết quả mới, không chấm và không tính là "bí":** `CLARIFY_REQUEST`, `OFF_TOPIC`, `NEGATIVE_AFFECT`. Chỉ trả lời sai, câu không đọc được và im lặng mới làm tăng `unproductive_turns`. Nói lạc đề hay hỏi lại đề không bao giờ dẫn tới lời giải.
3. **Luật mới của chính sách kèm câu (`hint-policy/0.5.0`):** vẫn là policy chọn nước đi và mức gợi ý; lý do (reason code) cho biết vì sao.
   - R-CLARIFY: hỏi lại đề thì nói lại đề bằng gợi ý TASK mức H1. Hỏi lại lần nữa thì lên mức gợi ý tiếp theo.
   - R-OFF-TOPIC: đáp ngắn rồi đưa về câu đang làm, không tính lượt, không tăng mức gợi ý.
   - R-AFFECT: công nhận cảm xúc, rồi gợi ý thêm mức (tối đa +2 theo R-ESCALATE).
   - R-HELP-REQUEST đổi: chỉ hỏi "gợi ý thêm hay tự thử lại?" một lần mỗi câu; những lần "không biết" sau thì gợi ý mức tiếp theo luôn.
   - R-ANSWER-DEMAND: từ chối nhẹ nhàng, nói vì sao, rồi gợi ý mức tiếp theo.
   - Hết gợi ý dùng được cho câu này thì chuyển sang làm mẫu từng bước (R-FRUSTRATION, LADDER_EXHAUSTED).
4. **Gợi ý chung theo loại câu.** Gợi ý chung của bài có thể khai báo `answer_types`. Gợi ý "bảng hàng" chỉ dùng cho câu điền số, so sánh, sắp xếp.
5. **Câu hỏi trong lời giảng có lời đáp.** Mỗi cách giảng (`theory`) có thêm `reply` (lời giải thích câu hỏi cuối) và `accept` (các cách viết đáp án đúng). Gia sư:
   - trả lời "đúng rồi" hoặc "chưa đúng lắm" rồi giải thích;
   - khi con không biết hoặc hỏi lại thì giải thích luôn (lời giảng không phải câu kiểm tra);
   - khi lạc đề thì hỏi lại câu đó.
   Phần "con nói lại" cũng nhắc một ý chính khi con nói không biết.
6. **Lời nói ấm hơn, vẫn Socratic.** Mỗi lời có thể mở đầu bằng một câu ngắn: trấn an, nói rõ hơn, công nhận cảm xúc, hoặc từ chối có lý do. Sau đó mới tới gợi ý và đúng một câu hỏi.
   - Câu mẫu cố định ở renderer (`template-renderer.v3`).
   - Prompt v2 cho Qwen nói rõ ý nghĩa từng lý do và cho phép một câu như vậy.
   - Validator vẫn chặn lộ đáp án, nhiều câu hỏi và quá dài.
7. **Bộ kịch bản học sinh khó.**
   - Mười vai học sinh lớp 5: hay nói "không biết", không hiểu đề, đòi đáp án hoặc thử phá luật, lạc đề, chán và tự ti, sai mà tự tin, viết tắt không dấu, đoán bừa, nhờ làm hộ bài về nhà, đúng mà lý do sai.
   - Mỗi kịch bản chạy nhiều lượt trên vòng dạy thật và kiểm tra tất định:
     - không lộ đáp án;
     - lời gia sư đáp đúng ý định;
     - không lặp một câu ba lần;
     - mỗi lời một câu hỏi;
     - không kẹt mãi.
   - Kịch bản chạy offline trong CI. Bản chạy với Qwen thật và giám khảo LLM làm sau (TQ-2).

## Không lấy từ Edubot

- LLM tự chấm từng lượt trong luồng chính: trái quy tắc 3.
- Câu mẫu "Robot …" và cách ghép chuỗi trực tiếp trong code: câu chữ của mình là template có version, chủ dự án duyệt.

## Hệ quả

- Contract web thêm ba kết quả mới (enum khớp `core/pedagogy.py`).
- Chính sách và câu mẫu đổi version, phải chạy lại toàn bộ test và kịch bản (quy tắc 7).
- Nội dung `reply`, `accept` của lời giảng và câu mẫu mới là bản nháp chờ chủ dự án duyệt.
