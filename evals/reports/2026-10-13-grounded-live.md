# Lời nói có căn cứ, chạy thật (2026-10-13)

`make eval-grounded` (`services/api/scripts/eval_grounded.py`), `grounded-speech/0.2.2`, prompt `grounded.v1.md`; bộ ca `evals/datasets/grounded-decimals-v1.yaml`. Truy xuất: `gemini-embedding-001`; gia sư: Qwen; giám khảo: `openai/gpt-oss-120b`. Qwen được gọi 19 lần.

## Quyết định với câu con tự hỏi

- Đúng loại (trả lời, mời con tự nghĩ, bài sau, để lại cho giáo viên): 15/15.
- Trả lời bằng lời Qwen đã qua kiểm chứng: 8; trích nguyên văn đoạn nguồn (Qwen bị chặn hoặc không gọi được): 0.
- Ca có câu Qwen bị bộ kiểm chứng chặn: 5.
- Giám khảo chấm các câu trả lời:
  - Số câu được chấm: 8/8
  - Bám nguồn: 5.00/5
  - Đúng trọng tâm: 4.62/5
  - Đúng kiến thức: 4.88/5
  - Hợp với trẻ 10 tuổi: 5.00/5
  - Bịa ngoài nguồn (giám khảo): 0
  - Lộ đáp án câu đang chờ: 0

## Câu nối trước lời giải thích đã duyệt

- Câu nối do Qwen viết và qua kiểm chứng: 6/6; còn lại dùng câu mẫu "Mình cùng xem lại nhé:".
- Giám khảo chấm câu nối:
  - Số câu được chấm: 6/6
  - Bám nguồn: 5.00/5
  - Đúng trọng tâm: 5.00/5
  - Đúng kiến thức: 5.00/5
  - Hợp với trẻ 10 tuổi: 5.00/5
  - Bịa ngoài nguồn (giám khảo): 0
  - Lộ đáp án câu đang chờ: 0

## Từng ca

| Ca | Con nói | Mong đợi | Kết quả | Nguồn | Bị chặn | Lời gia sư | Giám khảo |
|---|---|---|---|---|---|---|---|
| G01 | sao thêm số 0 vào cuối mà số không đổi ạ | answer | answer | LLM | NEW_MATH_TERM | Con xem đoạn dây 0,2 m. Viết thêm 0 thành 0,20 m, đoạn dây vẫn dài như cũ. Vì vậy giá trị số không đổi. | faithful 5 / relevant 2 / correct 4 / child_friendly 5 · Lời giải đúng và dựa trên đoạn nguồn, nhưng không trả lời trực tiếp câu hỏi về 0,02 và 0,2, nên mức liên quan thấp. Ngôn ngữ thân thiện với trẻ. |
| G02 | cô ơi 0,5 với 0,50 có bằng nhau không | later | later | TEMPLATE | – | (bài sau: Số thập phân bằng nhau) | – |
| G03 | so sánh phần nguyên trước hay phần thập phân trước ạ | answer | answer | LLM | – | Con so sánh phần nguyên trước nhé. Nếu phần nguyên khác nhau thì số có phần nguyên lớn hơn sẽ lớn hơn, không cần xét phần thập phân. | faithful 5 / relevant 5 / correct 5 / child_friendly 5 · Giải thích đúng, dựa trên nguồn, trả lời câu hỏi của học sinh một cách rõ ràng, thân thiện. |
| G04 | mẫu số 1000 thì sau dấu phẩy có mấy chữ số? | answer | answer | LLM | – | Mẫu số 1000 có ba chữ số 0, nên sau dấu phẩy có ba chữ số. | faithful 5 / relevant 5 / correct 5 / child_friendly 5 · Câu trả lời đúng với nội dung nguồn, phù hợp và dễ hiểu cho học sinh lớp 5. |
| G05 | phan nguyen la gi a | answer | answer | LLM | – | Con ơi, phần nguyên là các chữ số đứng bên trái dấu phẩy. Ví dụ trong số 2,7, chữ số 2 chính là phần nguyên. | faithful 5 / relevant 5 / correct 5 / child_friendly 5 · Giải thích đúng, phù hợp với câu hỏi và nội dung nguồn, ngôn ngữ ấm áp, dễ hiểu cho học sinh lớp 5. |
| G06 | hàng phần nghìn là chữ số thứ mấy sau dấu phẩy? | answer | answer | LLM | – | Con à, từ dấu phẩy đếm sang phải, chữ số thứ ba là hàng phần nghìn nhé. | faithful 5 / relevant 5 / correct 5 / child_friendly 5 · Giải thích đúng, phù hợp với câu hỏi và nguồn, ngôn ngữ ấm áp, dễ hiểu cho học sinh lớp 5. |
| G07 | sao chạy ít giây hơn lại là nhanh hơn ạ | answer | answer | LLM | – | Vì hai bạn chạy cùng một quãng đường. Ai về đích sau ít giây hơn thì người đó chạy nhanh hơn, con ạ. | faithful 5 / relevant 5 / correct 5 / child_friendly 5 · Giải thích đúng, dựa trên đoạn nguồn, phù hợp với câu hỏi của học sinh và dễ hiểu cho trẻ. |
| G08 | xếp từ lớn đến bé thì làm thế nào ạ | answer | answer | LLM | – | Con tìm số lớn nhất viết trước, rồi tìm số lớn nhất trong các số còn lại để xếp tiếp nhé. | faithful 5 / relevant 5 / correct 5 / child_friendly 5 · Lời gia sư đúng với nội dung nguồn, trả lời đúng câu hỏi của học sinh, kiến thức chính xác và diễn đạt dễ hiểu, ấm áp cho trẻ 10 tuổi. |
| G09 | viết thêm số không đằng sau thì số có to ra không cô | answer | answer | LLM | – | Không đâu An, viết thêm số 0 vào tận cùng bên phải phần thập phân thì giá trị của số không đổi. | faithful 5 / relevant 5 / correct 5 / child_friendly 5 · Câu trả lời đúng nguồn, giải thích rõ ràng, phù hợp với câu hỏi và dễ hiểu cho học sinh. |
| G10 | viết thêm chữ số 0 nữa thì đoạn dây có dài hơn không cô | same | same | TEMPLATE | – | – | – |
| G11 | quả dưa nào nặng hơn hả cô | same | same | TEMPLATE | – | – | – |
| G12 | chu vi hình chữ nhật tính thế nào ạ | park | park | TEMPLATE | – | – | – |
| G13 | phân số 2/3 và 4/6 có bằng nhau không | park | park | TEMPLATE | – | – | – |
| G14 | diện tích hình tròn tính sao cô | park | park | TEMPLATE | – | – | – |
| G15 | cô bao nhiêu tuổi ạ | park | park | TEMPLATE | – | – | – |
| B01 | dài hơn ạ vì có thêm số 0 | bridge | bridge | LLM | UNATTRIBUTED | Con nghĩ thêm số 0 sẽ dài hơn, mình cùng xem lại nhé. Không đâu. 0,2 m = 0,20 m = 0,200 m: viết thêm chữ số 0 vào tận cùng bên phải phần thập phân thì giá trị không đổi. | faithful 5 / relevant 5 / correct 5 / child_friendly 5 · Câu nối vừa nhắc lại suy nghĩ của học sinh và mời cùng xem lại, không thêm thông tin sai, phù hợp và thân thiện. |
| B02 | 4/10 ạ | bridge | bridge | LLM | UNATTRIBUTED | Con vừa nói 4/10 ạ, mình cùng xem lại nhé. Tô 4 ô trong 100 ô bằng nhau thì phần tô màu là 4/100 hình vuông, viết là 0,04. | faithful 5 / relevant 5 / correct 5 / child_friendly 5 · Câu nối chỉ nhắc lại câu của học sinh và đề nghị xem lại, không thêm thông tin sai, phù hợp và thân thiện. |
| B03 | số có nhiều chữ số hơn thì lớn hơn ạ | bridge | bridge | LLM | UNATTRIBUTED | Con nghĩ số nhiều chữ số hơn là lớn hơn, mình cùng xem lại nhé. Không chắc đâu. 0,9 có ít chữ số hơn 0,87 nhưng lại lớn hơn, vì mình so sánh lần lượt từng hàng, bắt đầu từ hàng phần mười. | faithful 5 / relevant 5 / correct 5 / child_friendly 5 · Câu nối chỉ nhắc lại ý của học sinh mà không khẳng định đúng sai, phù hợp với nguồn và thân thiện với trẻ. |
| B04 | sáu hai lăm | bridge | bridge | LLM | – | Con đọc chưa đúng, cô và con cùng xem lại cách đọc nhé. Số 6,25 đọc là sáu phẩy hai mươi lăm: đọc phần nguyên, đọc chữ phẩy, rồi đọc phần thập phân. | faithful 5 / relevant 5 / correct 5 / child_friendly 5 · Câu nối khéo léo nhắc lại rằng cách đọc chưa đúng, khuyến khích xem lại, phù hợp và dễ hiểu cho học sinh. |
| B05 | Hùng chạy nhanh hơn vì 8,6 lớn hơn | bridge | bridge | LLM | – | Con nói Hùng nhanh hơn, nhưng mình cùng xem lại nhé. Dũng chạy nhanh hơn, vì Dũng chạy hết 8,45 giây, ít thời gian hơn Hùng. | faithful 5 / relevant 5 / correct 5 / child_friendly 5 · Câu nối chỉ nhắc lại ý của học sinh và đề nghị xem lại, không thêm thông tin sai, phù hợp và thân thiện. |
| B06 | chữ số 6 chỉ 6 dm | bridge | bridge | LLM | UNATTRIBUTED | Con nghĩ 6 chỉ 6 dm, mình cùng xem lại nhé. Chữ số 6 ở hàng phần trăm nên chỉ 6 cm; chữ số 5 ở hàng phần mười chỉ 5 dm. | faithful 5 / relevant 5 / correct 5 / child_friendly 5 · Câu nối chỉ nhắc lại suy nghĩ của học sinh và mời cùng xem lại, không thêm thông tin sai, phù hợp và thân thiện. |

## Câu Qwen viết mà bộ kiểm chứng chặn (học sinh không nghe thấy)

- G01 (NEW_MATH_TERM): «Vì 0,2 m bằng 20 cm, còn 0,20 m cũng bằng 20 cm. Cùng một độ dài nên giá trị không đổi.»
- B01 (UNATTRIBUTED): «Cùng xem lại nhé, An, vì thêm số 0 vào cuối không làm giá trị đổi.»
- B02 (UNATTRIBUTED): «Con thử xem lại nhé, cô cùng con xem lại cách viết phân số đó.»
- B03 (UNATTRIBUTED): «Cùng xem lại nhé, An ạ, vì điều đó chưa chắc đúng.»
- B06 (UNATTRIBUTED): «Cùng xem lại nhé, con đã nhầm hàng của chữ số 6 rồi.»
