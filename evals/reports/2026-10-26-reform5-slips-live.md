# Học sinh khó, chạy thật (2026-10-26)

Chạy bằng `make eval-hard` (`services/api/scripts/eval_hard_students.py`, TQ-2).

- **Gia sư:** Qwen (`tutor-prompt.v2`) qua policy và renderer thật, có validator và câu mẫu dự phòng.
- **Giám khảo:** `openai/gpt-oss-120b`, chấm thang 1–5.

## Tổng hợp

- Số lượt: 6.
- Lời do Qwen viết: 2.
- Lời từ câu mẫu (Qwen bị chặn hoặc nước đi chỉ dùng câu mẫu): 4.
- Giám khảo thấy lộ đáp án: 0 lượt.
- Câu gõ nhầm, bấm bừa hoặc chỉ nói không: 6 lượt; khen sai ("Đúng rồi" và tương tự): 0 lượt (phải là 0).
- Trong đó đọc bằng model: 1 lượt, bằng luật: 3 lượt.
- Đáp đúng ý học sinh: trung bình 4.67/5.
- Socratic: trung bình 4.33/5.
- Hợp với trẻ 10 tuổi: trung bình 4.83/5.
- Bám bài: trung bình 5.00/5.

## Từng lượt

| Vai | Câu | Con nói | Ý định | Nước đi | Nguồn | Lời gia sư | Ý | Soc | Trẻ | Bài | Lộ | Nhận xét |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Kiên, gõ nhầm phím | TP-PR-01 | kt | AMBIGUOUS_TYPO | ASK_CONFIRM | LLM | Cô đoán con muốn nói là không biết làm, đúng không ạ? | 3 | 2 | 4 | 5 | không | Cô đã nhận diện cảm xúc và trấn an, nhưng chưa đưa câu hỏi gợi ý Socratic để học sinh tự tìm đáp án. |
| Kiên, gõ nhầm phím | TP-PR-01 | ể | GIBBERISH | OFFER_CHOICE | TEMPLATE | Không sao đâu, mình cùng nghĩ từng bước nhé. Con muốn cô gợi ý thêm hay con muốn tự thử lại một lần nữa? | 5 | 5 | 5 | 5 | không | Câu trả lời an ủi, khuyến khích tự làm, không đưa đáp án, phù hợp với phong cách Socratic. |
| Tuấn, bấm bừa và cười | TP-PR-01 | kkk | GIBBERISH | ASK_CONFIRM | TEMPLATE | Hình như bàn phím của con vừa gõ ra mấy chữ lạ. Con gõ lại ý của mình giúp cô nhé? | 5 | 4 | 5 | 5 | không | Cô đã an ủi, nhận xét cảm xúc và yêu cầu học sinh nhập lại, phù hợp và không đưa đáp án. |
| Tuấn, bấm bừa và cười | TP-PR-01 | tt | GIBBERISH | OFFER_CHOICE | TEMPLATE | Không sao đâu, mình cùng nghĩ từng bước nhé. Con muốn cô gợi ý thêm hay con muốn tự thử lại một lần nữa? | 5 | 5 | 5 | 5 | không | Câu trả lời an ủi, đặt câu hỏi khuyến khích tự làm, không đưa đáp án. |
| Linh, chỉ nói không | TP-PR-01 | không | HELP_REQUEST | OFFER_CHOICE | TEMPLATE | Không sao đâu, mình cùng nghĩ từng bước nhé. Con muốn cô gợi ý thêm hay con muốn tự thử lại một lần nữa? | 5 | 5 | 5 | 5 | không | Câu trả lời an ủi, khuyến khích học sinh tự suy nghĩ, không đưa đáp án, phù hợp với phong cách Socratic. |
| Linh, chỉ nói không | TP-PR-01 | chưa | HELP_REQUEST | HINT | LLM | Chưa sao, mình cùng làm nhé. Con hãy đọc to phân số 9/10 cho cô nghe, rồi xem mẫu số 10 gợi cho con điều gì? | 5 | 5 | 5 | 5 | không | Câu hỏi gợi ý, khuyến khích học sinh tự nghĩ, không đưa đáp án, phù hợp với yêu cầu Socratic. |
