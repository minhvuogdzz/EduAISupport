# Đánh giá Hybrid RAG trên hai chương đã phát hành (gemini), 2026-10-25

Kho đoạn: 221 đoạn (trong đó 83 đoạn tài liệu của giáo viên) của math-g5-area-triangle-trapezoid, math-g5-decimals, database `cavat_dev` (chỉ đọc). Lệnh: `make eval-rag-published LIVE=1`. Cấu hình chạy thật: `hybrid+rerank`.

## Bộ câu chính (dùng để chỉnh DI-50)

Embedder: `gemini-embedding-001`

| Cấu hình | n | Hit@1 | Hit@3 | Recall@3 | Recall@5 | MRR |
|---|---|---|---|---|---|---|
| keyword | 18 | 0.56 | 0.56 | 0.18 | 0.30 | 0.608 |
| semantic | 18 | 0.56 | 0.56 | 0.18 | 0.30 | 0.599 |
| hybrid | 18 | 0.56 | 0.56 | 0.18 | 0.31 | 0.609 |
| keyword+rerank | 18 | 0.72 | 0.83 | 0.25 | 0.39 | 0.804 |
| hybrid+rerank | 18 | 0.89 | 1.00 | 0.30 | 0.46 | 0.944 |

Hit@3 theo nhóm câu hỏi:

| Cấu hình | bai-truoc | cung-bai |
|---|---|---|
| keyword | 0.20 | 1.00 |
| semantic | 0.20 | 1.00 |
| hybrid | 0.20 | 1.00 |
| keyword+rerank | 0.70 | 1.00 |
| hybrid+rerank | 1.00 | 1.00 |

Có căn cứ (hybrid+rerank): 100% của 18 câu trong chương được coi là có căn cứ; 75% của 12 câu lạc đề bị từ chối.
Hiệu chỉnh ngưỡng cosine: câu lạc đề gần nhất 0.715, câu trong chương xa nhất 0.696, ngưỡng ở giữa 0.72.

Câu chưa đạt (hybrid+rerank):

- D19 «làm tròn số 3,46 thế nào»: câu lạc đề mà vẫn coi là có căn cứ; top 1: ['doc:01a12e6f-2c95-7254-ad28-4ddd8f25b30e:5']
- D20 «diện tích hình thang tính sao»: câu lạc đề mà vẫn coi là có căn cứ; top 1: ['doc:01a12e6d-d53e-77e4-8ce0-6e3484aa44b0:1']
- D22 «hình thang vuông có mấy góc vuông»: câu lạc đề mà vẫn coi là có căn cứ; top 1: ['doc:01a12e6d-d4f2-7250-8b38-728f38c7bf4e:5']

| Nhóm | n | Hit@3 | Trả lời | Báo bài sau | Gác cho cô | Mong muốn |
|---|---|---|---|---|---|---|
| cung-bai | 8 | 1.00 | 1.00 | 0.00 | 0.00 | trả lời, đúng đoạn |
| bai-truoc | 10 | 1.00 | 1.00 | 0.00 | 0.00 | trả lời, đúng đoạn |
| bai-sau | 4 | — | 0.00 | 1.00 | 0.00 | báo bài sau hoặc gác |
| lac-de-toan | 4 | — | 0.00 | 0.25 | 0.75 | gác |
| lac-de | 4 | — | 0.00 | 0.00 | 1.00 | gác |

Câu cấu hình chạy thật làm sai:

- (không có)

## Bộ câu giữ riêng `rag-published-holdout-v3.yaml` (không dùng để chỉnh gì)

Embedder: `gemini-embedding-001`

| Cấu hình | n | Hit@1 | Hit@3 | Recall@3 | Recall@5 | MRR |
|---|---|---|---|---|---|---|
| keyword | 30 | 0.40 | 0.40 | 0.15 | 0.25 | 0.465 |
| semantic | 30 | 0.40 | 0.40 | 0.15 | 0.25 | 0.458 |
| hybrid | 30 | 0.40 | 0.40 | 0.15 | 0.25 | 0.465 |
| keyword+rerank | 30 | 0.63 | 0.67 | 0.22 | 0.35 | 0.679 |
| hybrid+rerank | 30 | 0.80 | 0.80 | 0.28 | 0.44 | 0.822 |

Hit@3 theo nhóm câu hỏi:

| Cấu hình | bai-truoc | cung-bai |
|---|---|---|
| keyword | 0.00 | 1.00 |
| semantic | 0.00 | 1.00 |
| hybrid | 0.00 | 1.00 |
| keyword+rerank | 0.44 | 1.00 |
| hybrid+rerank | 0.67 | 1.00 |

Có căn cứ (hybrid+rerank): 100% của 30 câu trong chương được coi là có căn cứ; 77% của 13 câu lạc đề bị từ chối.

Câu chưa đạt (hybrid+rerank):

- W13 «phan nguyen voi phan thap phan cach nhau bang j»: đoạn đúng đầu tiên ở hạng 23; top 3: ['STP-T01:theory:T2', 'STP-T01:method', 'STP-T04:method']
- W16 «lam tron den hang phan muoi la sao co»: đoạn đúng đầu tiên ở hạng 5; top 3: ['STP-T10:method', 'STP-T10:theory:T1', 'STP-T10:theory:T2']
- W22 «hinh thang co may canh song song»: đoạn đúng đầu tiên ở hạng 7; top 3: ['doc:01a12e6d-d53e-77e4-8ce0-6e3484aa44b0:8', 'DTTGHT-T07:theory:T1', 'DTTGHT-T07:theory:T2']
- W23 «dien tich hinh thang tinh sao»: đoạn đúng đầu tiên ở hạng 10; top 3: ['doc:01a12e6d-d499-73d5-9b21-f2237486adfa:8', 'doc:01a12e6d-d53e-77e4-8ce0-6e3484aa44b0:11', 'DTTGHT-T08:theory:T1']
- W24 «muon tinh dien tich tam giac can biet nhung gi»: đoạn đúng đầu tiên ở hạng 14; top 3: ['DTTGHT-T04:example:WE1', 'doc:01a12e63-e4cc-731c-b992-cbf772fdb681:9', 'DTTGHT-T04:misconception:DTTGHT-L1']
- W30 «phần thập phân của số thập phân là gì»: đoạn đúng đầu tiên ở hạng 11; top 3: ['STP-T01:theory:T2', 'STP-T01:method', 'STP-T01:theory:T1']
- W32 «dien tich hinh thang tinh ntn»: câu lạc đề mà vẫn coi là có căn cứ; top 1: ['doc:01a12e6d-d53e-77e4-8ce0-6e3484aa44b0:1']
- W34 «dien tich tam giac day 8 cao 5 la bao nhieu»: câu lạc đề mà vẫn coi là có căn cứ; top 1: ['doc:01a12e6d-d53e-77e4-8ce0-6e3484aa44b0:1']
- W39 «dien tich hinh tron tinh the nao»: câu lạc đề mà vẫn coi là có căn cứ; top 1: ['doc:01a12e6d-d499-73d5-9b21-f2237486adfa:4']

| Nhóm | n | Hit@3 | Trả lời | Báo bài sau | Gác cho cô | Mong muốn |
|---|---|---|---|---|---|---|
| cung-bai | 12 | 1.00 | 1.00 | 0.00 | 0.00 | trả lời, đúng đoạn |
| bai-truoc | 18 | 0.67 | 1.00 | 0.00 | 0.00 | trả lời, đúng đoạn |
| bai-sau | 5 | — | 0.00 | 1.00 | 0.00 | báo bài sau hoặc gác |
| lac-de-toan | 4 | — | 0.00 | 0.50 | 0.50 | gác |
| lac-de | 4 | — | 0.00 | 0.00 | 1.00 | gác |

Câu cấu hình chạy thật làm sai:

- W13 (bai-truoc, ở STP-T04): «phan nguyen voi phan thap phan cach nhau bang j»: hạng đoạn đúng đầu tiên 23, gia sư: ANSWER, cosine tốt nhất 0.74; 3 đoạn đầu: STP-T01:theory:T2, STP-T01:method, STP-T04:method
- W16 (bai-truoc, ở STP-T10): «lam tron den hang phan muoi la sao co»: hạng đoạn đúng đầu tiên 5, gia sư: ANSWER, cosine tốt nhất 0.76; 3 đoạn đầu: STP-T10:method, STP-T10:theory:T1, STP-T10:theory:T2
- W22 (bai-truoc, ở DTTGHT-T07): «hinh thang co may canh song song»: hạng đoạn đúng đầu tiên 7, gia sư: ANSWER, cosine tốt nhất 0.73; 3 đoạn đầu: doc:01a12e6d-d53e-77e4-8ce0-6e3484aa44b0:8, DTTGHT-T07:theory:T1, DTTGHT-T07:theory:T2
- W23 (bai-truoc, ở DTTGHT-T08): «dien tich hinh thang tinh sao»: hạng đoạn đúng đầu tiên 10, gia sư: ANSWER, cosine tốt nhất 0.72; 3 đoạn đầu: doc:01a12e6d-d499-73d5-9b21-f2237486adfa:8, doc:01a12e6d-d53e-77e4-8ce0-6e3484aa44b0:11, DTTGHT-T08:theory:T1
- W24 (bai-truoc, ở DTTGHT-T04): «muon tinh dien tich tam giac can biet nhung gi»: hạng đoạn đúng đầu tiên 14, gia sư: ANSWER, cosine tốt nhất 0.73; 3 đoạn đầu: DTTGHT-T04:example:WE1, doc:01a12e63-e4cc-731c-b992-cbf772fdb681:9, DTTGHT-T04:misconception:DTTGHT-L1
- W30 (bai-truoc, ở STP-T05): «phần thập phân của số thập phân là gì»: hạng đoạn đúng đầu tiên 11, gia sư: ANSWER, cosine tốt nhất 0.77; 3 đoạn đầu: STP-T01:theory:T2, STP-T01:method, STP-T01:theory:T1

Gọi model embedding: 1 request, 42 văn bản (lưu đệm).
