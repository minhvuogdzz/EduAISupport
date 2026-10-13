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

## Bộ câu giữ riêng `rag-published-holdout-v2.yaml` (không dùng để chỉnh gì)

Embedder: `gemini-embedding-001`

| Cấu hình | n | Hit@1 | Hit@3 | Recall@3 | Recall@5 | MRR |
|---|---|---|---|---|---|---|
| keyword | 20 | 0.40 | 0.40 | 0.14 | 0.23 | 0.459 |
| semantic | 20 | 0.40 | 0.40 | 0.14 | 0.23 | 0.449 |
| hybrid | 20 | 0.40 | 0.40 | 0.14 | 0.23 | 0.460 |
| keyword+rerank | 20 | 0.70 | 0.70 | 0.21 | 0.34 | 0.728 |
| hybrid+rerank | 20 | 0.85 | 0.90 | 0.27 | 0.42 | 0.887 |

Hit@3 theo nhóm câu hỏi:

| Cấu hình | bai-truoc | cung-bai |
|---|---|---|
| keyword | 0.00 | 1.00 |
| semantic | 0.00 | 1.00 |
| hybrid | 0.00 | 1.00 |
| keyword+rerank | 0.50 | 1.00 |
| hybrid+rerank | 0.83 | 1.00 |

Có căn cứ (hybrid+rerank): 100% của 20 câu trong chương được coi là có căn cứ; 80% của 10 câu lạc đề bị từ chối.

Câu chưa đạt (hybrid+rerank):

- V09 «phần thập phân nằm ở bên nào dấu phẩy»: đoạn đúng đầu tiên ở hạng 14; top 3: ['STP-T01:theory:T2', 'STP-T01:method', 'STP-T01:example:WE1']
- V12 «làm tròn đến hàng phần mười là nhìn chữ số nào»: đoạn đúng đầu tiên ở hạng 6; top 3: ['STP-T10:method', 'STP-T10:theory:T1', 'STP-T10:example:WE1']
- V23 «hình thang có mấy đáy»: câu lạc đề mà vẫn coi là có căn cứ; top 1: ['doc:01a12e6d-d499-73d5-9b21-f2237486adfa:2']
- V24 «tính diện tích tam giác đáy 6 cao 4»: câu lạc đề mà vẫn coi là có căn cứ; top 1: ['doc:01a12e6d-d53e-77e4-8ce0-6e3484aa44b0:1']

| Nhóm | n | Hit@3 | Trả lời | Báo bài sau | Gác cho cô | Mong muốn |
|---|---|---|---|---|---|---|
| cung-bai | 8 | 1.00 | 0.88 | 0.12 | 0.00 | trả lời, đúng đoạn |
| bai-truoc | 12 | 0.83 | 1.00 | 0.00 | 0.00 | trả lời, đúng đoạn |
| bai-sau | 4 | — | 0.00 | 1.00 | 0.00 | báo bài sau hoặc gác |
| lac-de-toan | 3 | — | 0.00 | 0.00 | 1.00 | gác |
| lac-de | 3 | — | 0.00 | 0.00 | 1.00 | gác |

Câu cấu hình chạy thật làm sai:

- V01 (cung-bai, ở STP-T02): «số 7,25 đọc như thế nào ạ»: hạng đoạn đúng đầu tiên 1, gia sư: LATER, cosine tốt nhất 0.67; 3 đoạn đầu: STP-T02:misconception:STP-L1, doc:01a12e6f-2cea-7748-97e6-5bd2e53faec2:3, STP-T02:theory:T2
- V09 (bai-truoc, ở STP-T05): «phần thập phân nằm ở bên nào dấu phẩy»: hạng đoạn đúng đầu tiên 14, gia sư: ANSWER, cosine tốt nhất 0.77; 3 đoạn đầu: STP-T01:theory:T2, STP-T01:method, STP-T01:example:WE1
- V12 (bai-truoc, ở STP-T10): «làm tròn đến hàng phần mười là nhìn chữ số nào»: hạng đoạn đúng đầu tiên 6, gia sư: ANSWER, cosine tốt nhất 0.80; 3 đoạn đầu: STP-T10:method, STP-T10:theory:T1, STP-T10:example:WE1

Gọi model embedding: 0 request, 0 văn bản (lưu đệm).
