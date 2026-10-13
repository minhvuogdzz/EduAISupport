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

## Bộ câu giữ riêng `rag-published-holdout-v2.yaml` (không dùng để chỉnh gì)

Embedder: `gemini-embedding-001`

| Cấu hình | n | Hit@1 | Hit@3 | Recall@3 | Recall@5 | MRR |
|---|---|---|---|---|---|---|
| keyword | 20 | 0.40 | 0.40 | 0.14 | 0.23 | 0.459 |
| semantic | 20 | 0.40 | 0.40 | 0.14 | 0.23 | 0.449 |
| hybrid | 20 | 0.40 | 0.40 | 0.14 | 0.23 | 0.460 |
| keyword+rerank | 20 | 0.45 | 0.45 | 0.15 | 0.25 | 0.502 |
| hybrid+rerank | 20 | 0.45 | 0.45 | 0.15 | 0.25 | 0.503 |

Hit@3 theo nhóm câu hỏi:

| Cấu hình | bai-truoc | cung-bai |
|---|---|---|
| keyword | 0.00 | 1.00 |
| semantic | 0.00 | 1.00 |
| hybrid | 0.00 | 1.00 |
| keyword+rerank | 0.08 | 1.00 |
| hybrid+rerank | 0.08 | 1.00 |

Có căn cứ (hybrid+rerank): 100% của 20 câu trong chương được coi là có căn cứ; 90% của 10 câu lạc đề bị từ chối.

Câu chưa đạt (hybrid+rerank):

- V09 «phần thập phân nằm ở bên nào dấu phẩy»: đoạn đúng đầu tiên ở hạng không có; top 3: ['STP-T05:method', 'doc:01a12e6f-2c29-746d-88ce-365908a5eba1:6', 'STP-T05:theory:T2']
- V10 «chữ số ở hàng phần mười chỉ mấy phần»: đoạn đúng đầu tiên ở hạng không có; top 3: ['STP-T07:method', 'STP-T07:theory:T2', 'STP-T07:theory:T1']
- V11 «viết thêm số 0 vào cuối số thập phân có sao không»: đoạn đúng đầu tiên ở hạng 7; top 3: ['STP-T04:theory:T2', 'STP-T04:example:WE1', 'STP-T04:method']
- V12 «làm tròn đến hàng phần mười là nhìn chữ số nào»: đoạn đúng đầu tiên ở hạng 6; top 3: ['STP-T10:method', 'STP-T10:theory:T1', 'STP-T10:example:WE1']
- V13 «1 m bằng bao nhiêu cm vậy cô»: đoạn đúng đầu tiên ở hạng 6; top 3: ['STP-T08:theory:T2', 'STP-T08:misconception:STP-T08-M1', 'STP-T08:misconception:STP-L5']
- V14 «so sánh số thập phân thì làm thế nào»: đoạn đúng đầu tiên ở hạng 9; top 3: ['STP-T11:method', 'doc:01a12e6f-2cea-7748-97e6-5bd2e53faec2:10', 'STP-T11:theory:T2']
- V15 «7/100 viết thành số thập phân thế nào»: đoạn đúng đầu tiên ở hạng không có; top 3: ['STP-T06:theory:T1', 'STP-T06:theory:T2', 'STP-T06:method']
- V17 «tính diện tích tam giác thì nhân gì với gì»: đoạn đúng đầu tiên ở hạng 6; top 3: ['doc:01a12e6d-d53e-77e4-8ce0-6e3484aa44b0:7', 'DTTGHT-T05:misconception:DTTGHT-L3', 'DTTGHT-T05:method']
- V18 «hai cạnh song song của hình thang gọi là gì»: đoạn đúng đầu tiên ở hạng 8; top 3: ['doc:01a12e6d-d499-73d5-9b21-f2237486adfa:6', 'DTTGHT-T07:theory:T2', 'DTTGHT-T07:theory:T1']
- V19 «muốn tính diện tích hình thang phải biết những gì»: đoạn đúng đầu tiên ở hạng 10; top 3: ['doc:01a12e6d-d499-73d5-9b21-f2237486adfa:8', 'DTTGHT-T08:theory:T1', 'DTTGHT-T08:example:WE2']
- V20 «đường cao có vuông góc với đáy không cô»: đoạn đúng đầu tiên ở hạng 13; top 3: ['doc:01a12e63-e4cc-731c-b992-cbf772fdb681:9', 'DTTGHT-T04:example:WE3', 'DTTGHT-T04:example:WE4']
- V24 «tính diện tích tam giác đáy 6 cao 4»: câu lạc đề mà vẫn coi là có căn cứ; top 1: ['doc:01a12e6d-d53e-77e4-8ce0-6e3484aa44b0:1']

| Nhóm | n | Hit@3 | Trả lời | Báo bài sau | Gác cho cô | Mong muốn |
|---|---|---|---|---|---|---|
| cung-bai | 8 | 1.00 | 0.88 | 0.12 | 0.00 | trả lời, đúng đoạn |
| bai-truoc | 12 | 0.08 | 0.92 | 0.08 | 0.00 | trả lời, đúng đoạn |
| bai-sau | 4 | — | 0.00 | 1.00 | 0.00 | báo bài sau hoặc gác |
| lac-de-toan | 3 | — | 0.00 | 0.00 | 1.00 | gác |
| lac-de | 3 | — | 0.00 | 0.00 | 1.00 | gác |

Câu cấu hình chạy thật làm sai:

- V01 (cung-bai, ở STP-T02): «số 7,25 đọc như thế nào ạ»: hạng đoạn đúng đầu tiên 1, gia sư: LATER, cosine tốt nhất 0.67; 3 đoạn đầu: STP-T02:misconception:STP-L1, doc:01a12e6f-2cea-7748-97e6-5bd2e53faec2:3, STP-T02:theory:T2
- V09 (bai-truoc, ở STP-T05): «phần thập phân nằm ở bên nào dấu phẩy»: hạng đoạn đúng đầu tiên —, gia sư: ANSWER, cosine tốt nhất 0.69; 3 đoạn đầu: STP-T05:method, doc:01a12e6f-2c29-746d-88ce-365908a5eba1:6, STP-T05:theory:T2
- V10 (bai-truoc, ở STP-T07): «chữ số ở hàng phần mười chỉ mấy phần»: hạng đoạn đúng đầu tiên —, gia sư: LATER, cosine tốt nhất 0.69; 3 đoạn đầu: STP-T07:method, STP-T07:theory:T2, STP-T07:theory:T1
- V11 (bai-truoc, ở STP-T04): «viết thêm số 0 vào cuối số thập phân có sao không»: hạng đoạn đúng đầu tiên 7, gia sư: ANSWER, cosine tốt nhất 0.73; 3 đoạn đầu: STP-T04:theory:T2, STP-T04:example:WE1, STP-T04:method
- V12 (bai-truoc, ở STP-T10): «làm tròn đến hàng phần mười là nhìn chữ số nào»: hạng đoạn đúng đầu tiên 6, gia sư: ANSWER, cosine tốt nhất 0.80; 3 đoạn đầu: STP-T10:method, STP-T10:theory:T1, STP-T10:example:WE1
- V13 (bai-truoc, ở STP-T08): «1 m bằng bao nhiêu cm vậy cô»: hạng đoạn đúng đầu tiên 6, gia sư: ANSWER, cosine tốt nhất 0.69; 3 đoạn đầu: STP-T08:theory:T2, STP-T08:misconception:STP-T08-M1, STP-T08:misconception:STP-L5
- V14 (bai-truoc, ở STP-T11): «so sánh số thập phân thì làm thế nào»: hạng đoạn đúng đầu tiên 9, gia sư: ANSWER, cosine tốt nhất 0.76; 3 đoạn đầu: STP-T11:method, doc:01a12e6f-2cea-7748-97e6-5bd2e53faec2:10, STP-T11:theory:T2
- V15 (bai-truoc, ở STP-T06): «7/100 viết thành số thập phân thế nào»: hạng đoạn đúng đầu tiên —, gia sư: ANSWER, cosine tốt nhất 0.70; 3 đoạn đầu: STP-T06:theory:T1, STP-T06:theory:T2, STP-T06:method
- V17 (bai-truoc, ở DTTGHT-T05): «tính diện tích tam giác thì nhân gì với gì»: hạng đoạn đúng đầu tiên 6, gia sư: ANSWER, cosine tốt nhất 0.70; 3 đoạn đầu: doc:01a12e6d-d53e-77e4-8ce0-6e3484aa44b0:7, DTTGHT-T05:misconception:DTTGHT-L3, DTTGHT-T05:method
- V18 (bai-truoc, ở DTTGHT-T07): «hai cạnh song song của hình thang gọi là gì»: hạng đoạn đúng đầu tiên 8, gia sư: ANSWER, cosine tốt nhất 0.69; 3 đoạn đầu: doc:01a12e6d-d499-73d5-9b21-f2237486adfa:6, DTTGHT-T07:theory:T2, DTTGHT-T07:theory:T1
- V19 (bai-truoc, ở DTTGHT-T08): «muốn tính diện tích hình thang phải biết những gì»: hạng đoạn đúng đầu tiên 10, gia sư: ANSWER, cosine tốt nhất 0.72; 3 đoạn đầu: doc:01a12e6d-d499-73d5-9b21-f2237486adfa:8, DTTGHT-T08:theory:T1, DTTGHT-T08:example:WE2
- V20 (bai-truoc, ở DTTGHT-T04): «đường cao có vuông góc với đáy không cô»: hạng đoạn đúng đầu tiên 13, gia sư: ANSWER, cosine tốt nhất 0.66; 3 đoạn đầu: doc:01a12e63-e4cc-731c-b992-cbf772fdb681:9, DTTGHT-T04:example:WE3, DTTGHT-T04:example:WE4

Gọi model embedding: 1 request, 30 văn bản (lưu đệm).
