# Đánh giá Hybrid RAG trên hai chương đã phát hành (gemini), 2026-10-13

Kho đoạn: 221 đoạn (trong đó 83 đoạn tài liệu của giáo viên) của math-g5-area-triangle-trapezoid, math-g5-decimals, database `cavat_dev` (chỉ đọc). Lệnh: `make eval-rag-published LIVE=1`. Cấu hình chạy thật: `hybrid+rerank`.

## Bộ câu chính (dùng để chỉnh DI-50)

Embedder: `gemini-embedding-001`

| Cấu hình | n | Hit@1 | Hit@3 | Recall@3 | Recall@5 | MRR |
|---|---|---|---|---|---|---|
| keyword | 18 | 0.56 | 0.56 | 0.18 | 0.30 | 0.608 |
| semantic | 18 | 0.56 | 0.56 | 0.18 | 0.30 | 0.599 |
| hybrid | 18 | 0.56 | 0.56 | 0.18 | 0.31 | 0.609 |
| keyword+rerank | 18 | 0.72 | 0.83 | 0.25 | 0.39 | 0.804 |
| hybrid+rerank | 18 | 0.72 | 0.83 | 0.25 | 0.39 | 0.804 |

Hit@3 theo nhóm câu hỏi:

| Cấu hình | bai-truoc | cung-bai |
|---|---|---|
| keyword | 0.20 | 1.00 |
| semantic | 0.20 | 1.00 |
| hybrid | 0.20 | 1.00 |
| keyword+rerank | 0.70 | 1.00 |
| hybrid+rerank | 0.70 | 1.00 |

Có căn cứ (hybrid+rerank): 100% của 18 câu trong chương được coi là có căn cứ; 83% của 12 câu lạc đề bị từ chối.
Hiệu chỉnh ngưỡng cosine: câu lạc đề gần nhất 0.715, câu trong chương xa nhất 0.657, ngưỡng ở giữa 0.72.

Câu chưa đạt (hybrid+rerank):

- D09 «phần thập phân là gì vậy cô»: đoạn đúng đầu tiên ở hạng 5; top 3: ['STP-T05:method', 'STP-T05:theory:T1', 'doc:01a12e6f-2c29-746d-88ce-365908a5eba1:6']
- D10 «hàng phần mười là hàng nào»: đoạn đúng đầu tiên ở hạng 14; top 3: ['STP-T04:method', 'STP-T04:theory:T2', 'STP-T04:theory:T1']
- D18 «phân số thập phân là gì»: đoạn đúng đầu tiên ở hạng 5; top 3: ['STP-T11:theory:T2', 'STP-T11:method', 'doc:01a12e6f-2cea-7748-97e6-5bd2e53faec2:10']
- D19 «làm tròn số 3,46 thế nào»: câu lạc đề mà vẫn coi là có căn cứ; top 1: ['doc:01a12e6f-2c95-7254-ad28-4ddd8f25b30e:5']
- D20 «diện tích hình thang tính sao»: câu lạc đề mà vẫn coi là có căn cứ; top 1: ['doc:01a12e6d-d53e-77e4-8ce0-6e3484aa44b0:1']

| Nhóm | n | Hit@3 | Trả lời | Báo bài sau | Gác cho cô | Mong muốn |
|---|---|---|---|---|---|---|
| cung-bai | 8 | 1.00 | 1.00 | 0.00 | 0.00 | trả lời, đúng đoạn |
| bai-truoc | 10 | 0.70 | 1.00 | 0.00 | 0.00 | trả lời, đúng đoạn |
| bai-sau | 4 | — | 0.00 | 1.00 | 0.00 | báo bài sau hoặc gác |
| lac-de-toan | 4 | — | 0.00 | 0.25 | 0.75 | gác |
| lac-de | 4 | — | 0.00 | 0.00 | 1.00 | gác |

Câu cấu hình chạy thật làm sai:

- D09 (bai-truoc, ở STP-T05): «phần thập phân là gì vậy cô»: hạng đoạn đúng đầu tiên 5, gia sư: ANSWER, cosine tốt nhất 0.70; 3 đoạn đầu: STP-T05:method, STP-T05:theory:T1, doc:01a12e6f-2c29-746d-88ce-365908a5eba1:6
- D10 (bai-truoc, ở STP-T04): «hàng phần mười là hàng nào»: hạng đoạn đúng đầu tiên 14, gia sư: ANSWER, cosine tốt nhất 0.71; 3 đoạn đầu: STP-T04:method, STP-T04:theory:T2, STP-T04:theory:T1
- D18 (bai-truoc, ở STP-T11): «phân số thập phân là gì»: hạng đoạn đúng đầu tiên 5, gia sư: ANSWER, cosine tốt nhất 0.66; 3 đoạn đầu: STP-T11:theory:T2, STP-T11:method, doc:01a12e6f-2cea-7748-97e6-5bd2e53faec2:10

## Bộ câu giữ riêng (không dùng để chỉnh gì)

Embedder: `gemini-embedding-001`

| Cấu hình | n | Hit@1 | Hit@3 | Recall@3 | Recall@5 | MRR |
|---|---|---|---|---|---|---|
| keyword | 14 | 0.64 | 0.64 | 0.22 | 0.37 | 0.669 |
| semantic | 14 | 0.64 | 0.64 | 0.22 | 0.37 | 0.668 |
| hybrid | 14 | 0.64 | 0.64 | 0.22 | 0.37 | 0.673 |
| keyword+rerank | 14 | 0.64 | 0.64 | 0.22 | 0.37 | 0.670 |
| hybrid+rerank | 14 | 0.64 | 0.64 | 0.22 | 0.38 | 0.674 |

Hit@3 theo nhóm câu hỏi:

| Cấu hình | bai-truoc | cung-bai |
|---|---|---|
| keyword | 0.29 | 1.00 |
| semantic | 0.29 | 1.00 |
| hybrid | 0.29 | 1.00 |
| keyword+rerank | 0.29 | 1.00 |
| hybrid+rerank | 0.29 | 1.00 |

Có căn cứ (hybrid+rerank): 93% của 14 câu trong chương được coi là có căn cứ; 78% của 9 câu lạc đề bị từ chối.

Câu chưa đạt (hybrid+rerank):

- H07 «phần nguyên là phần nào»: đoạn đúng đầu tiên ở hạng 5; top 3: ['STP-T06:method', 'STP-T06:theory:T2', 'STP-T06:theory:T1']
- H08 «hàng phần trăm là chữ số thứ mấy sau dấu phẩy»: đoạn đúng đầu tiên ở hạng không có; top 3: ['STP-T09:method', 'STP-T09:theory:T1', 'STP-T09:theory:T2']
- H09 «tại sao 0,05 bé hơn 0,5»: đoạn đúng đầu tiên ở hạng 9; top 3: ['STP-T05:theory:T2', 'STP-T05:example:WE2', 'STP-T05:method']
- H10 «chiều cao của hình thang là gì»: đoạn đúng đầu tiên ở hạng 8; top 3: ['DTTGHT-T01:theory:T2', 'doc:01a12e6d-d53e-77e4-8ce0-6e3484aa44b0:1', 'DTTGHT-T06:theory:T2']
- H13 «chữ số 0 ở cuối phần thập phân có bỏ được không»: đoạn đúng đầu tiên ở hạng không có; top 3: ['STP-T10:misconception:STP-T10-M2', 'STP-T10:method', 'STP-T10:theory:T1']
- H15 «so sánh 2,5 và 2,49»: câu lạc đề mà vẫn coi là có căn cứ; top 1: ['doc:01a12e6f-2c29-746d-88ce-365908a5eba1:2']
- H16 «diện tích hình thang bằng gì»: câu lạc đề mà vẫn coi là có căn cứ; top 1: ['DTTGHT-T02:theory:T1']

| Nhóm | n | Hit@3 | Trả lời | Báo bài sau | Gác cho cô | Mong muốn |
|---|---|---|---|---|---|---|
| cung-bai | 7 | 1.00 | 1.00 | 0.00 | 0.00 | trả lời, đúng đoạn |
| bai-truoc | 7 | 0.29 | 0.71 | 0.14 | 0.14 | trả lời, đúng đoạn |
| bai-sau | 3 | — | 0.00 | 1.00 | 0.00 | báo bài sau hoặc gác |
| lac-de-toan | 3 | — | 0.00 | 0.33 | 0.67 | gác |
| lac-de | 3 | — | 0.00 | 0.00 | 1.00 | gác |

Câu cấu hình chạy thật làm sai:

- H07 (bai-truoc, ở STP-T06): «phần nguyên là phần nào»: hạng đoạn đúng đầu tiên 5, gia sư: PARKED, cosine tốt nhất 0.62; 3 đoạn đầu: STP-T06:method, STP-T06:theory:T2, STP-T06:theory:T1
- H08 (bai-truoc, ở STP-T09): «hàng phần trăm là chữ số thứ mấy sau dấu phẩy»: hạng đoạn đúng đầu tiên —, gia sư: ANSWER, cosine tốt nhất 0.73; 3 đoạn đầu: STP-T09:method, STP-T09:theory:T1, STP-T09:theory:T2
- H09 (bai-truoc, ở STP-T05): «tại sao 0,05 bé hơn 0,5»: hạng đoạn đúng đầu tiên 9, gia sư: ANSWER, cosine tốt nhất 0.71; 3 đoạn đầu: STP-T05:theory:T2, STP-T05:example:WE2, STP-T05:method
- H10 (bai-truoc, ở DTTGHT-T06): «chiều cao của hình thang là gì»: hạng đoạn đúng đầu tiên 8, gia sư: LATER, cosine tốt nhất 0.68; 3 đoạn đầu: DTTGHT-T01:theory:T2, doc:01a12e6d-d53e-77e4-8ce0-6e3484aa44b0:1, DTTGHT-T06:theory:T2
- H13 (bai-truoc, ở STP-T10): «chữ số 0 ở cuối phần thập phân có bỏ được không»: hạng đoạn đúng đầu tiên —, gia sư: ANSWER, cosine tốt nhất 0.74; 3 đoạn đầu: STP-T10:misconception:STP-T10-M2, STP-T10:method, STP-T10:theory:T1

Gọi model embedding: 0 request, 0 văn bản (lưu đệm).
