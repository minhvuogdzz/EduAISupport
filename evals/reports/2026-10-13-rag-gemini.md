# Đánh giá Hybrid RAG (gemini), 2026-10-13

Bộ câu hỏi: `evals/datasets/rag-decimals-v1.yaml`, 67 câu (57 câu trong chương, 10 câu lạc đề); kho đoạn: 47 đoạn của chương Số thập phân (chưa có tài liệu giáo viên). Lệnh: `make eval-rag LIVE=1`.

Hit@k: có ít nhất một đoạn đúng trong k đoạn đầu. Recall@k: tỉ lệ đoạn đúng nằm trong k đoạn đầu. MRR: trung bình 1/hạng của đoạn đúng đầu tiên. `keyword+rerank` là cấu hình chạy khi không có vector (không có khóa Gemini, hết hạn mức); `hybrid+rerank` là cấu hình chạy thật khi có vector.

## Bộ câu chính (dùng để chỉnh tham số DI-17)

Embedder: `gemini-embedding-001`

| Cấu hình | n | Hit@1 | Hit@3 | Recall@3 | Recall@5 | MRR |
|---|---|---|---|---|---|---|
| keyword | 57 | 0.74 | 0.91 | 0.67 | 0.82 | 0.826 |
| semantic | 57 | 0.77 | 1.00 | 0.82 | 0.91 | 0.868 |
| hybrid | 57 | 0.75 | 0.98 | 0.78 | 0.90 | 0.864 |
| keyword+rerank | 57 | 0.79 | 0.95 | 0.73 | 0.86 | 0.870 |
| hybrid+rerank | 57 | 0.88 | 1.00 | 0.86 | 0.93 | 0.939 |

Hit@3 theo nhóm câu hỏi:

| Cấu hình | chinh-sach | co-dau | dien-dat-khac | dinh-nghia | khong-dau | sai-chinh-ta |
|---|---|---|---|---|---|---|
| keyword | 1.00 | 0.96 | 0.83 | 0.50 | 0.86 | 1.00 |
| semantic | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| hybrid | 1.00 | 0.96 | 1.00 | 1.00 | 1.00 | 1.00 |
| keyword+rerank | 1.00 | 1.00 | 0.67 | 0.75 | 1.00 | 1.00 |
| hybrid+rerank | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |

Có căn cứ (hybrid+rerank): 100% của 57 câu trong chương được coi là có căn cứ; 100% của 10 câu lạc đề bị từ chối.
Hiệu chỉnh ngưỡng cosine: câu lạc đề gần nhất 0.633, câu trong chương xa nhất 0.668, ngưỡng ở giữa 0.65.

## Bộ câu kiểm tra riêng (không dùng để chỉnh gì)

`evals/datasets/rag-decimals-holdout-v1.yaml`, 30 câu viết sau khi chỉnh tham số, một nửa câu lạc đề là Toán ngoài chương. Đây là con số gần với câu học sinh thật hơn.

Embedder: `gemini-embedding-001`

| Cấu hình | n | Hit@1 | Hit@3 | Recall@3 | Recall@5 | MRR |
|---|---|---|---|---|---|---|
| keyword | 15 | 0.40 | 0.80 | 0.46 | 0.64 | 0.608 |
| semantic | 15 | 0.60 | 0.93 | 0.61 | 0.74 | 0.765 |
| hybrid | 15 | 0.53 | 0.87 | 0.56 | 0.77 | 0.722 |
| keyword+rerank | 15 | 0.40 | 0.87 | 0.49 | 0.64 | 0.613 |
| hybrid+rerank | 15 | 0.47 | 0.87 | 0.52 | 0.77 | 0.678 |

Hit@3 theo nhóm câu hỏi:

| Cấu hình | trong-chuong |
|---|---|
| keyword | 0.80 |
| semantic | 0.93 |
| hybrid | 0.87 |
| keyword+rerank | 0.87 |
| hybrid+rerank | 0.87 |

Có căn cứ (hybrid+rerank): 100% của 15 câu trong chương được coi là có căn cứ; 100% của 15 câu lạc đề bị từ chối.

Câu chưa đạt (hybrid+rerank):

- HO01 «0,7 và 0,70 cái nào lớn hơn»: đoạn đúng đầu tiên ở hạng 4; top 3: ['KC-DEC-CMP:theory:T1', 'KC-DEC-FRAC:misconception:FRAC-M01', 'KC-DEC-CMP:theory:T3']
- HO02 «viết 3/10 thành số thập phân»: đoạn đúng đầu tiên ở hạng 4; top 3: ['KC-DEC-FRAC:example:W2', 'KC-DEC-FRAC:misconception:FRAC-M01', 'KC-DEC-FRAC:theory:T2']

Thời gian: 0.4 s cho 485 lần truy xuất.
Gọi model embedding trong lần chạy này: 0 request, 0 văn bản; mọi lần truy xuất đều có vector. Vector được lưu đệm ở `var/storage/rag/`, các lần chạy sau không gọi lại model.
