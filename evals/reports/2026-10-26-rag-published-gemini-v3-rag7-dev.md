# Đánh giá Hybrid RAG trên hai chương đã phát hành (gemini), 2026-10-26

Kho đoạn: 221 đoạn (trong đó 83 đoạn tài liệu của giáo viên) của math-g5-area-triangle-trapezoid, math-g5-decimals, database `cavat_dev` (chỉ đọc). Lệnh: `make eval-rag-published LIVE=1`. Cấu hình chạy thật: `hybrid+rerank`.

## Bộ câu chính (dùng để chỉnh DI-50)

Embedder: `gemini-embedding-001`

| Cấu hình | n | Hit@1 | Hit@3 | Recall@3 | Recall@5 | MRR |
|---|---|---|---|---|---|---|
| keyword | 18 | 0.56 | 0.56 | 0.18 | 0.30 | 0.608 |
| semantic | 18 | 0.56 | 0.56 | 0.18 | 0.30 | 0.599 |
| hybrid | 18 | 0.56 | 0.56 | 0.18 | 0.31 | 0.609 |
| keyword+rerank | 18 | 0.72 | 0.83 | 0.24 | 0.38 | 0.804 |
| hybrid+rerank | 18 | 0.89 | 1.00 | 0.29 | 0.45 | 0.944 |

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

Ablation từng thành phần (RAG-5, embedder `gemini-embedding-001`): bỏ một thành phần khỏi cấu hình đủ, hoặc thêm một thành phần vào `hybrid`. Trước RAG-5, cờ `rerank` bật cả định tuyến và ưu tiên định nghĩa, nên dòng `+rerank` ở bảng trên là ba cơ chế cộng lại.

| Thành phần | Cấu hình | Hit@1 | Hit@3 | MRR | ΔMRR so với đủ | Hit@3 đổi (− mất, + được) |
|---|---|---|---|---|---|---|
| đủ mọi thành phần | `hybrid+rerank` | 0.89 | 1.00 | 0.944 | — | — |
| bỏ từ khóa (BM25) | `no-keyword` | 0.89 | 1.00 | 0.944 | +0.000 | — |
| bỏ vector | `keyword+rerank` | 0.72 | 0.83 | 0.804 | -0.140 | −D09, −D10, −D18 |
| bỏ xếp lại sư phạm | `no-rerank` | 0.89 | 1.00 | 0.944 | +0.000 | — |
| bỏ định tuyến DI-57 | `no-route` | 0.72 | 0.83 | 0.804 | -0.140 | −D09, −D10, −D18 |
| bỏ ưu tiên định nghĩa DI-50 | `no-define` | 1.00 | 1.00 | 1.000 | +0.056 | — |
| *thêm từng thành phần vào hybrid* | | | | | | |
| hybrid (RRF, phạm vi đồ thị) | `hybrid` | 0.56 | 0.56 | 0.609 | -0.335 | −D09, −D10, −D13, −D14, −D15, −D16, −D17, −D18 |
| hybrid + xếp lại sư phạm | `hybrid+rerank-only` | 0.56 | 0.56 | 0.620 | -0.325 | −D09, −D10, −D13, −D14, −D15, −D16, −D17, −D18 |
| hybrid + định tuyến DI-57 | `hybrid+route-only` | 1.00 | 1.00 | 1.000 | +0.056 | — |
| hybrid + ưu tiên định nghĩa DI-50 | `hybrid+define-only` | 0.72 | 0.83 | 0.798 | -0.146 | −D09, −D10, −D18 |

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
| keyword+rerank | 30 | 0.63 | 0.67 | 0.23 | 0.36 | 0.679 |
| hybrid+rerank | 30 | 0.83 | 0.87 | 0.29 | 0.47 | 0.860 |

Hit@3 theo nhóm câu hỏi:

| Cấu hình | bai-truoc | cung-bai |
|---|---|---|
| keyword | 0.00 | 1.00 |
| semantic | 0.00 | 1.00 |
| hybrid | 0.00 | 1.00 |
| keyword+rerank | 0.44 | 1.00 |
| hybrid+rerank | 0.78 | 1.00 |

Có căn cứ (hybrid+rerank): 100% của 30 câu trong chương được coi là có căn cứ; 85% của 13 câu lạc đề bị từ chối.

Câu chưa đạt (hybrid+rerank):

- W13 «phan nguyen voi phan thap phan cach nhau bang j»: đoạn đúng đầu tiên ở hạng 23; top 3: ['STP-T01:theory:T2', 'STP-T01:method', 'STP-T04:method']
- W23 «dien tich hinh thang tinh sao»: đoạn đúng đầu tiên ở hạng 10; top 3: ['doc:01a12e6d-d499-73d5-9b21-f2237486adfa:8', 'doc:01a12e6d-d53e-77e4-8ce0-6e3484aa44b0:11', 'DTTGHT-T08:theory:T1']
- W24 «muon tinh dien tich tam giac can biet nhung gi»: đoạn đúng đầu tiên ở hạng 14; top 3: ['DTTGHT-T04:example:WE1', 'doc:01a12e63-e4cc-731c-b992-cbf772fdb681:9', 'DTTGHT-T04:misconception:DTTGHT-L1']
- W30 «phần thập phân của số thập phân là gì»: đoạn đúng đầu tiên ở hạng 11; top 3: ['STP-T01:theory:T2', 'STP-T01:method', 'STP-T01:theory:T1']
- W32 «dien tich hinh thang tinh ntn»: câu lạc đề mà vẫn coi là có căn cứ; top 1: ['doc:01a12e6d-d53e-77e4-8ce0-6e3484aa44b0:1']
- W34 «dien tich tam giac day 8 cao 5 la bao nhieu»: câu lạc đề mà vẫn coi là có căn cứ; top 1: ['doc:01a12e6d-d53e-77e4-8ce0-6e3484aa44b0:1']

Ablation từng thành phần (RAG-5, embedder `gemini-embedding-001`): bỏ một thành phần khỏi cấu hình đủ, hoặc thêm một thành phần vào `hybrid`. Trước RAG-5, cờ `rerank` bật cả định tuyến và ưu tiên định nghĩa, nên dòng `+rerank` ở bảng trên là ba cơ chế cộng lại.

| Thành phần | Cấu hình | Hit@1 | Hit@3 | MRR | ΔMRR so với đủ | Hit@3 đổi (− mất, + được) |
|---|---|---|---|---|---|---|
| đủ mọi thành phần | `hybrid+rerank` | 0.83 | 0.87 | 0.860 | — | — |
| bỏ từ khóa (BM25) | `no-keyword` | 0.80 | 0.87 | 0.843 | -0.017 | — |
| bỏ vector | `keyword+rerank` | 0.63 | 0.67 | 0.679 | -0.181 | −W14, −W16, −W17, −W18, −W22, −W28 |
| bỏ xếp lại sư phạm | `no-rerank` | 0.83 | 0.87 | 0.860 | -0.001 | — |
| bỏ định tuyến DI-57 | `no-route` | 0.53 | 0.53 | 0.583 | -0.277 | −W14, −W15, −W16, −W17, −W18, −W19, −W20, −W21, −W22, −W28 |
| bỏ ưu tiên định nghĩa DI-50 | `no-define` | 0.83 | 0.87 | 0.860 | +0.000 | — |
| *thêm từng thành phần vào hybrid* | | | | | | |
| hybrid (RRF, phạm vi đồ thị) | `hybrid` | 0.40 | 0.40 | 0.465 | -0.395 | −W14, −W15, −W16, −W17, −W18, −W19, −W20, −W21, −W22, −W25, −W26, −W27, −W28, −W29 |
| hybrid + xếp lại sư phạm | `hybrid+rerank-only` | 0.40 | 0.40 | 0.470 | -0.390 | −W14, −W15, −W16, −W17, −W18, −W19, −W20, −W21, −W22, −W25, −W26, −W27, −W28, −W29 |
| hybrid + định tuyến DI-57 | `hybrid+route-only` | 0.83 | 0.87 | 0.860 | -0.001 | — |
| hybrid + ưu tiên định nghĩa DI-50 | `hybrid+define-only` | 0.53 | 0.53 | 0.581 | -0.279 | −W14, −W15, −W16, −W17, −W18, −W19, −W20, −W21, −W22, −W28 |

| Nhóm | n | Hit@3 | Trả lời | Báo bài sau | Gác cho cô | Mong muốn |
|---|---|---|---|---|---|---|
| cung-bai | 12 | 1.00 | 1.00 | 0.00 | 0.00 | trả lời, đúng đoạn |
| bai-truoc | 18 | 0.78 | 1.00 | 0.00 | 0.00 | trả lời, đúng đoạn |
| bai-sau | 5 | — | 0.00 | 1.00 | 0.00 | báo bài sau hoặc gác |
| lac-de-toan | 4 | — | 0.00 | 0.00 | 1.00 | gác |
| lac-de | 4 | — | 0.00 | 0.00 | 1.00 | gác |

Câu cấu hình chạy thật làm sai:

- W13 (bai-truoc, ở STP-T04): «phan nguyen voi phan thap phan cach nhau bang j»: hạng đoạn đúng đầu tiên 23, gia sư: ANSWER, cosine tốt nhất 0.74; 3 đoạn đầu: STP-T01:theory:T2, STP-T01:method, STP-T04:method
- W23 (bai-truoc, ở DTTGHT-T08): «dien tich hinh thang tinh sao»: hạng đoạn đúng đầu tiên 10, gia sư: ANSWER, cosine tốt nhất 0.72; 3 đoạn đầu: doc:01a12e6d-d499-73d5-9b21-f2237486adfa:8, doc:01a12e6d-d53e-77e4-8ce0-6e3484aa44b0:11, DTTGHT-T08:theory:T1
- W24 (bai-truoc, ở DTTGHT-T04): «muon tinh dien tich tam giac can biet nhung gi»: hạng đoạn đúng đầu tiên 14, gia sư: ANSWER, cosine tốt nhất 0.73; 3 đoạn đầu: DTTGHT-T04:example:WE1, doc:01a12e63-e4cc-731c-b992-cbf772fdb681:9, DTTGHT-T04:misconception:DTTGHT-L1
- W30 (bai-truoc, ở STP-T05): «phần thập phân của số thập phân là gì»: hạng đoạn đúng đầu tiên 11, gia sư: ANSWER, cosine tốt nhất 0.77; 3 đoạn đầu: STP-T01:theory:T2, STP-T01:method, STP-T01:theory:T1

Gọi model embedding: 0 request, 0 văn bản (lưu đệm).
