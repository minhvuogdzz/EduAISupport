# Lời nói có căn cứ, chạy thật (2026-10-07)

`make eval-grounded` (`services/api/scripts/eval_grounded.py`), `grounded-speech/0.2.0`, prompt `grounded.v1.md`; bộ ca `evals/datasets/grounded-decimals-v1.yaml`. Truy xuất: `gemini-embedding-001`; gia sư: Qwen; giám khảo: `openai/gpt-oss-120b`. Qwen được gọi 5 lần.

## Quyết định với câu con tự hỏi

- Đúng loại (trả lời, mời con tự nghĩ, bài sau, để lại cho giáo viên): 3/3.
- Trả lời bằng lời Qwen đã qua kiểm chứng: 3; trích nguyên văn đoạn nguồn (Qwen bị chặn hoặc không gọi được): 0.
- Ca có câu Qwen bị bộ kiểm chứng chặn: 1.
- Giám khảo chấm các câu trả lời:
  - Số câu được chấm: 3/3
  - Bám nguồn: 5.00/5
  - Đúng trọng tâm: 5.00/5
  - Đúng kiến thức: 5.00/5
  - Hợp với trẻ 10 tuổi: 5.00/5
  - Bịa ngoài nguồn (giám khảo): 0
  - Lộ đáp án câu đang chờ: 0

## Câu nối trước lời giải thích đã duyệt

- Câu nối do Qwen viết và qua kiểm chứng: 1/1; còn lại dùng câu mẫu "Mình cùng xem lại nhé:".
- Giám khảo chấm câu nối:
  - Số câu được chấm: 1/1
  - Bám nguồn: 5.00/5
  - Đúng trọng tâm: 5.00/5
  - Đúng kiến thức: 2.00/5
  - Hợp với trẻ 10 tuổi: 4.00/5
  - Bịa ngoài nguồn (giám khảo): 0
  - Lộ đáp án câu đang chờ: 0

## Từng ca

| Ca | Con nói | Mong đợi | Kết quả | Nguồn | Bị chặn | Lời gia sư | Giám khảo |
|---|---|---|---|---|---|---|---|
| G04 | mẫu số 1000 thì sau dấu phẩy có mấy chữ số? | answer | answer | LLM | – | Mẫu số 1000 có ba chữ số 0, nên sau dấu phẩy có ba chữ số. | faithful 5 / relevant 5 / correct 5 / child_friendly 5 · Lời gia sư đúng với nội dung nguồn và câu hỏi của học sinh, không có thông tin sai hay thêm thắt, giải thích ngắn gọn, dễ hiểu cho trẻ 10 tuổi. |
| G05 | phan nguyen la gi a | answer | answer | LLM | – | Phần nguyên là các chữ số đứng bên trái dấu phẩy, con nhé. | faithful 5 / relevant 5 / correct 5 / child_friendly 5 · Lời giải thích của gia sư hoàn toàn dựa trên đoạn nguồn, trả lời đúng câu hỏi về cách đọc số thập phân và không có thông tin sai hoặc lộ đáp án. Ngôn ngữ thân thiện, dễ hiểu cho học sinh lớp 5. |
| G09 | viết thêm số không đằng sau thì số có to ra không cô | answer | answer | LLM | – | Không, con ạ. Viết chữ số 0 vào tận Cùng không làm số to ra. Nó chỉ để hai số có số chữ số thập分 like nha. | faithful 5 / relevant 5 / correct 5 / child_friendly 5 · Giải thích đúng, phù hợp với câu hỏi và nội dung nguồn, ngôn ngữ dễ hiểu cho học sinh lớp 5. |
| B06 | chữ số 6 chỉ 6 dm | bridge | bridge | LLM | UNATTRIBUTED | Con nghĩ chữ số 6 chỉ 6 dm, mình cùng xem lại nhé. Chữ số 6 ở hàng phần trăm nên chỉ 6 cm; chữ số 5 ở hàng phần mười chỉ 5 dm. | faithful 5 / relevant 5 / correct 2 / child_friendly 4 · Giáo viên lặp lại suy nghĩ sai của học sinh mà không sửa, vì vậy không đúng kiến thức nhưng vẫn trung thực, liên quan và thân thiện. |

## Câu Qwen viết mà bộ kiểm chứng chặn (học sinh không nghe thấy)

- B06 (UNATTRIBUTED): «Cùng xem lại nhé, con đã nhầm hàng của chữ số 6 rồi.»
