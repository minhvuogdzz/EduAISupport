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

## Bộ câu giữ riêng `rag-published-holdout-v1.yaml` (không dùng để chỉnh gì)

Embedder: `gemini-embedding-001`

| Cấu hình | n | Hit@1 | Hit@3 | Recall@3 | Recall@5 | MRR |
|---|---|---|---|---|---|---|
| keyword | 14 | 0.64 | 0.64 | 0.22 | 0.37 | 0.669 |
| semantic | 14 | 0.64 | 0.64 | 0.22 | 0.37 | 0.668 |
| hybrid | 14 | 0.64 | 0.64 | 0.22 | 0.37 | 0.673 |
| keyword+rerank | 14 | 0.79 | 0.79 | 0.26 | 0.44 | 0.809 |
| hybrid+rerank | 14 | 0.93 | 1.00 | 0.30 | 0.48 | 0.952 |

Hit@3 theo nhóm câu hỏi:

| Cấu hình | bai-truoc | cung-bai |
|---|---|---|
| keyword | 0.29 | 1.00 |
| semantic | 0.29 | 1.00 |
| hybrid | 0.29 | 1.00 |
| keyword+rerank | 0.57 | 1.00 |
| hybrid+rerank | 1.00 | 1.00 |

Có căn cứ (hybrid+rerank): 100% của 14 câu trong chương được coi là có căn cứ; 78% của 9 câu lạc đề bị từ chối.

Câu chưa đạt (hybrid+rerank):

- H15 «so sánh 2,5 và 2,49»: câu lạc đề mà vẫn coi là có căn cứ; top 1: ['doc:01a12e6f-2c29-746d-88ce-365908a5eba1:2']
- H16 «diện tích hình thang bằng gì»: câu lạc đề mà vẫn coi là có căn cứ; top 1: ['doc:01a12e6d-d53e-77e4-8ce0-6e3484aa44b0:1']

| Nhóm | n | Hit@3 | Trả lời | Báo bài sau | Gác cho cô | Mong muốn |
|---|---|---|---|---|---|---|
| cung-bai | 7 | 1.00 | 1.00 | 0.00 | 0.00 | trả lời, đúng đoạn |
| bai-truoc | 7 | 1.00 | 1.00 | 0.00 | 0.00 | trả lời, đúng đoạn |
| bai-sau | 3 | — | 0.00 | 1.00 | 0.00 | báo bài sau hoặc gác |
| lac-de-toan | 3 | — | 0.00 | 0.33 | 0.67 | gác |
| lac-de | 3 | — | 0.00 | 0.00 | 1.00 | gác |

Câu cấu hình chạy thật làm sai:

- (không có)

Gọi model embedding: 0 request, 0 văn bản (lưu đệm).
