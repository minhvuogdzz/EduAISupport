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

## Bộ câu giữ riêng `rag-published-holdout-v4.yaml` (không dùng để chỉnh gì)

Embedder: `gemini-embedding-001`

| Cấu hình | n | Hit@1 | Hit@3 | Recall@3 | Recall@5 | MRR |
|---|---|---|---|---|---|---|
| keyword | 22 | 0.27 | 0.27 | 0.11 | 0.18 | 0.344 |
| semantic | 22 | 0.27 | 0.27 | 0.11 | 0.18 | 0.332 |
| hybrid | 22 | 0.27 | 0.27 | 0.11 | 0.18 | 0.343 |
| keyword+rerank | 22 | 0.64 | 0.68 | 0.24 | 0.39 | 0.693 |
| hybrid+rerank | 22 | 0.86 | 0.91 | 0.31 | 0.49 | 0.897 |

Hit@3 theo nhóm câu hỏi:

| Cấu hình | bai-truoc | cung-bai |
|---|---|---|
| keyword | 0.00 | 1.00 |
| semantic | 0.00 | 1.00 |
| hybrid | 0.00 | 1.00 |
| keyword+rerank | 0.56 | 1.00 |
| hybrid+rerank | 0.88 | 1.00 |

Có căn cứ (hybrid+rerank): 100% của 22 câu trong chương được coi là có căn cứ; 73% của 15 câu lạc đề bị từ chối.

Câu chưa đạt (hybrid+rerank):

- X05 «lam tron den hang don vi thi nhin chu so nao»: đoạn đúng đầu tiên ở hạng 6; top 3: ['STP-T10:method', 'STP-T10:theory:T1', 'STP-T10:example:WE1']
- X08 «phan nguyen nam ben trai hay ben phai dau phay»: đoạn đúng đầu tiên ở hạng 15; top 3: ['STP-T01:theory:T2', 'STP-T01:method', 'STP-T05:theory:T2']
- X23 «lam tron 3,456 den hang phan tram»: câu lạc đề mà vẫn coi là có căn cứ; top 1: ['doc:01a12e6f-2c95-7254-ad28-4ddd8f25b30e:5']
- X24 «hinh thang co may dinh»: câu lạc đề mà vẫn coi là có căn cứ; top 1: ['doc:01a12e6d-d53e-77e4-8ce0-6e3484aa44b0:12']
- X28 «chu vi hinh chu nhat tinh the nao»: câu lạc đề mà vẫn coi là có căn cứ; top 1: ['DTTGHT-T04:misconception:DTTGHT-L1']
- X29 «nhan 2 phan so the nao»: câu lạc đề mà vẫn coi là có căn cứ; top 1: ['STP-T03:theory:T2']

Ablation từng thành phần (RAG-5, embedder `gemini-embedding-001`): bỏ một thành phần khỏi cấu hình đủ, hoặc thêm một thành phần vào `hybrid`. Trước RAG-5, cờ `rerank` bật cả định tuyến và ưu tiên định nghĩa, nên dòng `+rerank` ở bảng trên là ba cơ chế cộng lại.

| Thành phần | Cấu hình | Hit@1 | Hit@3 | MRR | ΔMRR so với đủ | Hit@3 đổi (− mất, + được) |
|---|---|---|---|---|---|---|
| đủ mọi thành phần | `hybrid+rerank` | 0.86 | 0.91 | 0.897 | — | — |
| bỏ từ khóa (BM25) | `no-keyword` | 0.82 | 0.91 | 0.873 | -0.024 | — |
| bỏ vector | `keyword+rerank` | 0.64 | 0.68 | 0.693 | -0.204 | −X02, −X03, −X09, −X11, −X12, −X13, +X08 |
| bỏ xếp lại sư phạm | `no-rerank` | 0.86 | 0.91 | 0.897 | +0.000 | — |
| bỏ định tuyến DI-57 | `no-route` | 0.32 | 0.32 | 0.384 | -0.513 | −X01, −X02, −X03, −X04, −X06, −X07, −X09, −X10, −X11, −X12, −X13, −X14, −X15 |
| bỏ ưu tiên định nghĩa DI-50 | `no-define` | 0.86 | 0.91 | 0.897 | +0.000 | — |
| *thêm từng thành phần vào hybrid* | | | | | | |
| hybrid (RRF, phạm vi đồ thị) | `hybrid` | 0.27 | 0.27 | 0.343 | -0.554 | −X01, −X02, −X03, −X04, −X06, −X07, −X09, −X10, −X11, −X12, −X13, −X14, −X15, −X16 |
| hybrid + xếp lại sư phạm | `hybrid+rerank-only` | 0.27 | 0.27 | 0.345 | -0.551 | −X01, −X02, −X03, −X04, −X06, −X07, −X09, −X10, −X11, −X12, −X13, −X14, −X15, −X16 |
| hybrid + định tuyến DI-57 | `hybrid+route-only` | 0.86 | 0.91 | 0.897 | +0.000 | — |
| hybrid + ưu tiên định nghĩa DI-50 | `hybrid+define-only` | 0.32 | 0.32 | 0.383 | -0.514 | −X01, −X02, −X03, −X04, −X06, −X07, −X09, −X10, −X11, −X12, −X13, −X14, −X15 |

| Nhóm | n | Hit@3 | Trả lời | Báo bài sau | Gác cho cô | Mong muốn |
|---|---|---|---|---|---|---|
| bai-truoc | 16 | 0.88 | 1.00 | 0.00 | 0.00 | trả lời, đúng đoạn |
| cung-bai | 6 | 1.00 | 1.00 | 0.00 | 0.00 | trả lời, đúng đoạn |
| bai-sau | 4 | — | 0.00 | 0.75 | 0.25 | báo bài sau hoặc gác |
| lac-de-toan | 8 | — | 0.25 | 0.00 | 0.75 | gác |
| lac-de | 3 | — | 0.00 | 0.00 | 1.00 | gác |

Câu cấu hình chạy thật làm sai:

- X05 (bai-truoc, ở STP-T10): «lam tron den hang don vi thi nhin chu so nao»: hạng đoạn đúng đầu tiên 6, gia sư: ANSWER, cosine tốt nhất 0.78; 3 đoạn đầu: STP-T10:method, STP-T10:theory:T1, STP-T10:example:WE1
- X08 (bai-truoc, ở STP-T05): «phan nguyen nam ben trai hay ben phai dau phay»: hạng đoạn đúng đầu tiên 15, gia sư: ANSWER, cosine tốt nhất 0.69; 3 đoạn đầu: STP-T01:theory:T2, STP-T01:method, STP-T05:theory:T2
- X28 (lac-de-toan, ở DTTGHT-T04): «chu vi hinh chu nhat tinh the nao»: hạng đoạn đúng đầu tiên —, gia sư: ANSWER, cosine tốt nhất 0.65; 3 đoạn đầu: DTTGHT-T04:misconception:DTTGHT-L1, DTTGHT-T04:misconception:DTTGHT-T04-M1, doc:01a12e6d-d4f2-7250-8b38-728f38c7bf4e:1
- X29 (lac-de-toan, ở STP-T09): «nhan 2 phan so the nao»: hạng đoạn đúng đầu tiên —, gia sư: ANSWER, cosine tốt nhất 0.66; 3 đoạn đầu: STP-T03:theory:T2, doc:01a12e6f-2c29-746d-88ce-365908a5eba1:4, doc:01a12e6f-2cea-7748-97e6-5bd2e53faec2:4

Gọi model embedding: 1 request, 36 văn bản (lưu đệm).
