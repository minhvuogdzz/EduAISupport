# Lời nói có căn cứ, chạy thật (2026-10-07)

`make eval-grounded` (`services/api/scripts/eval_grounded.py`), `grounded-speech/0.1.0`, prompt `grounded.v1.md`; bộ ca `evals/datasets/grounded-decimals-v1.yaml`. Truy xuất: `gemini-embedding-001`; gia sư: Qwen; giám khảo: `openai/gpt-oss-120b`. Qwen được gọi 20 lần.

## Quyết định với câu con tự hỏi

- Đúng loại (trả lời, mời con tự nghĩ, bài sau, để lại cho giáo viên): 15/15.
- Trả lời bằng lời Qwen đã qua kiểm chứng: 7; trích nguyên văn đoạn nguồn (Qwen bị chặn hoặc không gọi được): 1.
- Ca có câu Qwen bị bộ kiểm chứng chặn: 5.
- Giám khảo chấm các câu trả lời:
  - Số câu được chấm: 8/8
  - Bám nguồn: 4.12/5
  - Đúng trọng tâm: 3.62/5
  - Đúng kiến thức: 4.12/5
  - Hợp với trẻ 10 tuổi: 4.12/5
  - Bịa ngoài nguồn (giám khảo): 1
  - Lộ đáp án câu đang chờ: 0

## Câu nối trước lời giải thích đã duyệt

- Câu nối do Qwen viết và qua kiểm chứng: 5/6; còn lại dùng câu mẫu "Mình cùng xem lại nhé:".
- Giám khảo chấm câu nối:
  - Số câu được chấm: 5/5
  - Bám nguồn: 5.00/5
  - Đúng trọng tâm: 5.00/5
  - Đúng kiến thức: 4.40/5
  - Hợp với trẻ 10 tuổi: 4.80/5
  - Bịa ngoài nguồn (giám khảo): 2
  - Lộ đáp án câu đang chờ: 1

## Từng ca

| Ca | Con nói | Mong đợi | Kết quả | Nguồn | Bị chặn | Lời gia sư | Giám khảo |
|---|---|---|---|---|---|---|---|
| G01 | sao thêm số 0 vào cuối mà số không đổi ạ | answer | answer | LLM | – | Con xem, 0,2 m bằng 20 cm. Viết thêm 0 thành 0,20 m vẫn là 20 cm. Giá trị không đổi vì 0 ở tận cùng bên phải không làm số lớn hơn. | faithful 5 / relevant 5 / correct 5 / child_friendly 5 · Giải thích đúng, dựa trên đoạn nguồn, dễ hiểu và phù hợp với câu hỏi của học sinh. |
| G02 | cô ơi 0,5 với 0,50 có bằng nhau không | later | later | TEMPLATE | – | (bài sau: Số thập phân bằng nhau) | – |
| G03 | so sánh phần nguyên trước hay phần thập phân trước ạ | answer | answer | LLM | – | Con so sánh phần nguyên trước nhé. Nếu phần nguyên bằng nhau thì mới so sánh phần thập phân. | faithful 5 / relevant 5 / correct 5 / child_friendly 5 · Giải thích đúng, phù hợp với nội dung nguồn và câu hỏi của học sinh, ngôn ngữ dễ hiểu cho trẻ. |
| G04 | mẫu số 1000 thì sau dấu phẩy có mấy chữ số? | answer | answer | EXTRACT | UNSUPPORTED_CLAIM; UNSUPPORTED_CLAIM | Cô trả lời con nhé: Mẫu số 10 thì sau dấu phẩy có một chữ số, mẫu số 100 thì có hai chữ số. | faithful 5 / relevant 1 / correct 5 / child_friendly 5 · Câu trả lời đúng thông tin nhưng không trả lời câu hỏi của học sinh, vì vậy không liên quan. |
| G05 | phan nguyen la gi a | answer | answer | LLM | – | Con ơi, phần nguyên là chữ số đứng bên trái dấu phẩy. Ví dụ trong số 2,7, phần nguyên là 2. | faithful 1 / relevant 1 / correct 1 / child_friendly 1 · BỊA · Không có câu trả lời của gia sư để đánh giá; nếu trả lời, cần dựa vào đoạn nguồn và hỏi của học sinh, tránh đưa thông tin không có trong nguồn. |
| G06 | hàng phần nghìn là chữ số thứ mấy sau dấu phẩy? | answer | answer | LLM | – | Con đếm từ dấu phẩy sang phải, hàng phần nghìn là chữ số thứ ba. | faithful 5 / relevant 5 / correct 5 / child_friendly 5 · Câu nối đúng nội dung nguồn, trả lời đúng câu hỏi và dễ hiểu cho học sinh. |
| G07 | sao chạy ít giây hơn lại là nhanh hơn ạ | answer | answer | LLM | – | Vì hai bạn chạy cùng một quãng đường. Bạn nào về đích sau ít giây hơn, tức là tốn ít thời gian hơn, thì bạn đó chạy nhanh hơn. | faithful 2 / relevant 2 / correct 2 / child_friendly 2 · Giáo viên chưa trả lời đúng câu hỏi của học sinh và chưa liên hệ tới nội dung nguồn; thông tin chưa đầy đủ và chưa thân thiện với trẻ. |
| G08 | xếp từ lớn đến bé thì làm thế nào ạ | answer | answer | LLM | – | Con tìm số lớn nhất trước, viết ra rồi gạch đi. Sau đó, con tìm số lớn nhất trong các số còn lại và viết tiếp nhé. | faithful 5 / relevant 5 / correct 5 / child_friendly 5 · Giải thích đúng, dựa trên nội dung nguồn, phù hợp với câu hỏi của học sinh và dễ hiểu cho trẻ 10 tuổi. |
| G09 | viết thêm số không đằng sau thì số có to ra không cô | answer | answer | LLM | UNSUPPORTED_CLAIM | Viết thêm số 0 vào tận cùng bên phải để hai số có cùng số chữ số ở phần thập phân rồi mới so sánh. | faithful 5 / relevant 5 / correct 5 / child_friendly 5 · Giải thích đúng, dựa trên nội dung nguồn, trả lời phù hợp và dễ hiểu cho học sinh. |
| G10 | viết thêm chữ số 0 nữa thì đoạn dây có dài hơn không cô | same | same | TEMPLATE | – | – | – |
| G11 | quả dưa nào nặng hơn hả cô | same | same | TEMPLATE | – | – | – |
| G12 | chu vi hình chữ nhật tính thế nào ạ | park | park | TEMPLATE | – | – | – |
| G13 | phân số 2/3 và 4/6 có bằng nhau không | park | park | TEMPLATE | – | – | – |
| G14 | diện tích hình tròn tính sao cô | park | park | TEMPLATE | – | – | – |
| G15 | cô bao nhiêu tuổi ạ | park | park | TEMPLATE | – | – | – |
| B01 | dài hơn ạ vì có thêm số 0 | bridge | bridge | LLM | UNSUPPORTED_CLAIM,UNATTRIBUTED | Con nghĩ thêm số 0 là dài hơn, mình cùng xem lại nhé. Không đâu. 0,2 m = 0,20 m = 0,200 m: viết thêm chữ số 0 vào tận cùng bên phải phần thập phân thì giá trị không đổi. | faithful 5 / relevant 5 / correct 5 / child_friendly 5 · Câu nối lặp lại ý của học sinh và sau đó giải thích đúng rằng việc thêm số 0 ở cuối không làm thay đổi độ dài. |
| B02 | 4/10 ạ | bridge | bridge | TEMPLATE | UNSUPPORTED_CLAIM,UNATTRIBUTED; UNSUPPORTED_CLAIM,UNATTRIBUTED | Mình cùng xem lại nhé: Tô 4 ô trong 100 ô bằng nhau thì phần tô màu là 4/100 hình vuông, viết là 0,04. | – |
| B03 | số có nhiều chữ số hơn thì lớn hơn ạ | bridge | bridge | LLM | – | Con nghĩ nhiều chữ số hơn thì lớn hơn, nhưng mình cùng xem lại nhé. Không chắc đâu. 0,9 có ít chữ số hơn 0,87 nhưng lại lớn hơn, vì mình so sánh lần lượt từng hàng, bắt đầu từ hàng phần mười. | faithful 5 / relevant 5 / correct 5 / child_friendly 5 · Câu nối vừa nhắc lại suy nghĩ của học sinh, sau đó giải thích đúng rằng nhiều chữ số không đồng nghĩa với giá trị lớn hơn. Nội dung hoàn toàn dựa trên nguồn và không gây nhầm lẫn. |
| B04 | sáu hai lăm | bridge | bridge | LLM | – | Con đọc chưa đúng, cô cùng con xem lại cách đọc nhé. Số 6,25 đọc là sáu phẩy hai mươi lăm: đọc phần nguyên, đọc chữ phẩy, rồi đọc phần thập phân. | faithful 5 / relevant 5 / correct 5 / child_friendly 5 · Câu nối đúng, nhắc lại ý học sinh và giải thích cách đọc số 6,25 chính xác, ngôn ngữ ấm áp, phù hợp với học sinh lớp 5. |
| B05 | Hùng chạy nhanh hơn vì 8,6 lớn hơn | bridge | bridge | LLM | – | Con nói Hùng chạy nhanh hơn, nhưng mình cùng xem lại nhé. Dũng chạy nhanh hơn, vì Dũng chạy hết 8,45 giây, ít thời gian hơn Hùng. | faithful 5 / relevant 5 / correct 2 / child_friendly 4 · BỊA · LỘ · Giáo viên lặp lại ý của học sinh (đúng nguồn), nhưng đưa ra thông tin mới về thời gian 8,45 giây không có trong đoạn nguồn hoặc lời học sinh, gây hallucination và trả lời câu hỏi đang chờ, nên bị leaky. Kiến thức chưa chắc đúng. |
| B06 | chữ số 6 chỉ 6 dm | bridge | bridge | LLM | UNSUPPORTED_CLAIM | Con nghĩ 6 chỉ 6 dm, mình cùng xem lại nhé. Chữ số 6 ở hàng phần trăm nên chỉ 6 cm; chữ số 5 ở hàng phần mười chỉ 5 dm. | faithful 5 / relevant 5 / correct 5 / child_friendly 5 · BỊA · Giáo viên nhắc lại suy nghĩ của học sinh và giải thích đúng rằng chữ số 6 là 6 cm; tuy nhiên phần giải thích dùng cụm 'hàng phần trăm' không có trong nguồn, nên có hallucination. |

## Câu Qwen viết mà bộ kiểm chứng chặn (học sinh không nghe thấy)

- G04 (UNSUPPORTED_CLAIM): «Mẫu số 1000 có ba chữ số 0, nên sau dấu phẩy có ba chữ số.»
- G04 (UNSUPPORTED_CLAIM): «Mẫu số 1000 có ba chữ số 0, nên sau dấu phẩy có ba chữ số.»
- G09 (UNSUPPORTED_CLAIM): «Không, con ạ. Viết thêm số 0 vào tận cùng bên phải thì giá trị số không thay đổi.»
- B01 (UNSUPPORTED_CLAIM,UNATTRIBUTED): «Cô cùng An xem lại nhé, vì thêm số 0 vào cuối không làm đoạn dây dài hơn.»
- B02 (UNSUPPORTED_CLAIM,UNATTRIBUTED): «Con thử xem lại nhé, cô cùng con kiểm tra lại cách viết phân số đó.»
- B02 (UNSUPPORTED_CLAIM,UNATTRIBUTED): «An nghĩ là 4/10, cô cùng con xem lại nhé.»
- B06 (UNSUPPORTED_CLAIM): «Con nói 6 dm, mình cùng xem lại vị trí của chữ số 6 nhé.»
