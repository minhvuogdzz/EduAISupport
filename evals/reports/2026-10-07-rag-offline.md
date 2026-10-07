# Đánh giá Hybrid RAG (offline), 2026-10-07

Bộ câu hỏi: `evals/datasets/rag-decimals-v1.yaml`, 67 câu (57 câu trong chương, 10 câu lạc đề); kho đoạn: 47 đoạn của chương Số thập phân (chưa có tài liệu giáo viên). Lệnh: `make eval-rag`.

Hit@k: có ít nhất một đoạn đúng trong k đoạn đầu. Recall@k: tỉ lệ đoạn đúng nằm trong k đoạn đầu. MRR: trung bình 1/hạng của đoạn đúng đầu tiên. `keyword+rerank` là cấu hình chạy khi không có vector (không có khóa Gemini, hết hạn mức); `hybrid+rerank` là cấu hình chạy thật khi có vector.

## Bộ câu chính (dùng để chỉnh tham số DI-17)

Embedder: `hash-trigram-512`

| Cấu hình | n | Hit@1 | Hit@3 | Recall@3 | Recall@5 | MRR |
|---|---|---|---|---|---|---|
| keyword | 57 | 0.74 | 0.91 | 0.67 | 0.82 | 0.826 |
| semantic | 57 | 0.65 | 0.81 | 0.56 | 0.68 | 0.751 |
| hybrid | 57 | 0.67 | 0.95 | 0.63 | 0.82 | 0.803 |
| keyword+rerank | 57 | 0.81 | 0.95 | 0.73 | 0.87 | 0.882 |
| hybrid+rerank | 57 | 0.81 | 1.00 | 0.77 | 0.88 | 0.895 |

Hit@3 theo nhóm câu hỏi:

| Cấu hình | chinh-sach | co-dau | dien-dat-khac | dinh-nghia | khong-dau | sai-chinh-ta |
|---|---|---|---|---|---|---|
| keyword | 1.00 | 0.96 | 0.83 | 0.50 | 0.86 | 1.00 |
| semantic | 0.70 | 0.88 | 0.83 | 0.75 | 0.86 | 0.60 |
| hybrid | 0.90 | 0.96 | 1.00 | 1.00 | 0.86 | 1.00 |
| keyword+rerank | 1.00 | 1.00 | 0.67 | 0.75 | 1.00 | 1.00 |
| hybrid+rerank | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |

Có căn cứ (keyword+rerank): 84% của 57 câu trong chương được coi là có căn cứ; 90% của 10 câu lạc đề bị từ chối.

Câu chưa đạt (keyword+rerank):

- Q39 «số đứng trước dấu phẩy gọi là gì»: đoạn đúng đầu tiên ở hạng 4; top 3: ['KC-DEC-PLACE:method', 'KC-DEC-EQ:method', 'KC-DEC-ORDER:method']
- Q43 «con số sau dấu phẩy dài hơn có to hơn không»: đoạn đúng đầu tiên ở hạng 9; top 3: ['KC-DEC-CONCEPT:misconception:CONCEPT-M01', 'KC-DEC-EQ:theory:T2', 'KC-DEC-FRAC:misconception:FRAC-M01']
- H04 «so sánh số thập phân là như thế nào»: đoạn đúng đầu tiên ở hạng 4; top 3: ['KC-DEC-APPLY:method', 'KC-DEC-APPLY:theory:T1', 'KC-DEC-APPLY:theory:T2']
- O06 «cộng hai phân số khác mẫu số»: câu lạc đề mà vẫn coi là có căn cứ; top 1: ['KC-DEC-FRAC:misconception:FRAC-M01']

## Bộ câu kiểm tra riêng (không dùng để chỉnh gì)

`evals/datasets/rag-decimals-holdout-v1.yaml`, 30 câu viết sau khi chỉnh tham số, một nửa câu lạc đề là Toán ngoài chương. Đây là con số gần với câu học sinh thật hơn.

Embedder: `hash-trigram-512`

| Cấu hình | n | Hit@1 | Hit@3 | Recall@3 | Recall@5 | MRR |
|---|---|---|---|---|---|---|
| keyword | 15 | 0.40 | 0.80 | 0.46 | 0.64 | 0.608 |
| semantic | 15 | 0.47 | 0.73 | 0.37 | 0.44 | 0.601 |
| hybrid | 15 | 0.40 | 0.80 | 0.43 | 0.60 | 0.600 |
| keyword+rerank | 15 | 0.40 | 0.80 | 0.46 | 0.64 | 0.608 |
| hybrid+rerank | 15 | 0.40 | 0.80 | 0.43 | 0.60 | 0.600 |

Hit@3 theo nhóm câu hỏi:

| Cấu hình | trong-chuong |
|---|---|
| keyword | 0.80 |
| semantic | 0.73 |
| hybrid | 0.80 |
| keyword+rerank | 0.80 |
| hybrid+rerank | 0.80 |

Có căn cứ (keyword+rerank): 87% của 15 câu trong chương được coi là có căn cứ; 93% của 15 câu lạc đề bị từ chối.

Câu chưa đạt (keyword+rerank):

- HO01 «0,7 và 0,70 cái nào lớn hơn»: đoạn đúng đầu tiên ở hạng 6; top 3: ['KC-DEC-CMP:theory:T3', 'KC-DEC-CMP:theory:T1', 'KC-DEC-CMP:misconception:DEC-M02']
- HO03 «số 12,5 phần nguyên là bao nhiêu»: đoạn đúng đầu tiên ở hạng 5; top 3: ['KC-DEC-FRAC:method', 'KC-DEC-APPLY:example:W1', 'KC-DEC-CMP:misconception:DEC-M04']
- HO15 «số thập phân gồm mấy phần»: đoạn đúng đầu tiên ở hạng 4; top 3: ['KC-DEC-CONCEPT:example:W2', 'KC-DEC-PLACE:example:W2', 'KC-DEC-FRAC:method']
- HX04 «phân số 2/3 và 4/6 có bằng nhau không»: câu lạc đề mà vẫn coi là có căn cứ; top 1: ['KC-DEC-FRAC:theory:T1']

Thời gian: 0.3 s cho 485 lần truy xuất.
