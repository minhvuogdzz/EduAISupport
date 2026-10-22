# Kế hoạch v1: gia sư dạy học theo đồ thị tri thức

**Trạng thái:** chủ dự án (giáo viên kiểm soát) duyệt ngày 2026-10-06. Ghi đè thứ tự task cũ trong `docs/tasks/BACKLOG.md`. Quyết định liên quan: D-T9, D-T10 (mục Revision của `docs/blueprint/00-START-HERE.md`), ADR-018.

## 1. Mục tiêu

Chứng minh gia sư AI **dạy được** học sinh lớp 5, cả **lý thuyết** lẫn **phương pháp**, và **đo được** học sinh đã hiểu thật hay chưa bằng bằng chứng, không dựa vào việc học sinh tự nói "con hiểu rồi".

Gia sư không chỉ kèm làm bài tập. Bài tập chỉ là một bước trong vòng dạy (mục 5.2).

## 2. Phạm vi (D-T9)

- **Hai chương Toán lớp 5:**
  - Số: **Số thập phân**.
  - Hình học: **Diện tích hình tam giác và hình thang**. Đề có số đo thập phân, nên chương hình học nối được với chương số.
- **Ra khỏi demo:** English (Reading, Speaking), giọng nói (T15 cũ).
- Chương được coi như giáo viên đã tải lên sẵn. Đường nhập tài liệu (OCR, sửa lỗi) vẫn được xây ở Mốc 2 và dùng để dựng phần còn lại của chương.
- Hai chương rất khác nhau là bằng chứng chính cho việc khuôn mẫu dùng lại được. Bằng chứng bổ sung: thêm một bài của chương thứ ba chỉ bằng nội dung, không sửa code (mục 8).

## 3. Nguyên tắc tự xây (D-T11)

Chủ dự án quán triệt ngày 2026-10-06: **hạn chế dùng kiến trúc của bên thứ ba**, vì hội đồng đánh giá phần dự án tự thiết kế và tự xây.

| Tự xây (phần đóng góp của đồ án) | Dùng của bên ngoài (không phải kiến trúc) |
|---|---|
| Hybrid RAG: chia đoạn, chỉ mục từ khóa BM25, chỉ mục vector, hợp nhất kết quả, xếp hạng lại theo sư phạm | API model: Qwen trên Groq (sinh lời), Gemini (đọc ảnh, tạo vector embedding), luôn gọi qua `ai_gateway` của dự án |
| Đồ thị tri thức, dựng đồ thị từ tài liệu, kiểm tra không vòng lặp | Thư viện cấp thấp: đọc chữ có sẵn trong PDF, toán ma trận (numpy) |
| Chấm điểm từng node, chính sách dạy, vòng dạy, policy gợi ý, bộ kiểm tra câu nói | Hạ tầng: FastAPI, React, MongoDB Atlas |
| Đường đọc tài liệu: tách trang, tầng sửa lỗi OCR, dựng cấu trúc | |

**Không dùng:** framework RAG hay agent (LangChain, LlamaIndex...), dịch vụ vector database, dịch vụ đọc tài liệu (**LlamaParse bị bỏ**, thay vai trò ghi trong ADR-017), thư viện knowledge tracing có sẵn.

## 4. Nguồn tham khảo

### 4.1. Bài báo 2T-KT

Li, Wang, Jose, Ge. *LLM supporting knowledge tracing leveraging global subject and student specific knowledge graphs.* Information Fusion 126 (2026) 103577. doi:10.1016/j.inffus.2025.103577.

**[FACT]** Đây là bài về **dự đoán** (knowledge tracing): đoán học sinh làm đúng câu tiếp theo, nhất là câu có khái niệm mới. Bài không có chính sách dạy, RAG hay ngưỡng qua node. Vòng dạy của dự án (mục 5.2, 5.4) là thiết kế của dự án, dựa trên blueprint và hai khung đánh giá.

| Lấy từ bài báo | Cách dùng trong dự án |
|---|---|
| Đồ thị môn học hai tầng: khái niệm **cơ bản** (Basic) và khái niệm **vận dụng** (Implement); quan hệ trong tầng (lớp con, tiên quyết, tương tự) và giữa hai tầng (vận dụng, chỉ đi từ cơ bản sang vận dụng); mỗi node có mô tả (Hình 2–3, Bảng 1) | Khuôn đồ thị của gói chương (mục 5.1) |
| Prompt dựng đồ thị theo các bước (Hình 4) | Prompt dựng đồ thị từ tài liệu (Mốc 2) |
| Thêm khái niệm mới: LLM chấm điểm quan hệ đề xuất, chỉ giữ quan hệ có điểm trên ngưỡng θ = 0,75, rồi kiểm chứng | Lọc quan hệ khi dựng đồ thị; một lượt LLM kiểm chứng lại từng quan hệ, cộng giáo viên duyệt |
| Bài toán "khái niệm mới chưa có dữ liệu" (cold start) | Điểm khởi đầu của node mới lấy từ điểm các node tiên quyết (mục 5.3) |
| 4 giai đoạn học: Exposure, Comprehension, Practice, Transfer (mục 4.2.1 của bài) | 4 **mức** của mỗi node: Tiếp xúc, Hiểu, Luyện tập, Vận dụng (mục 5.2) |
| "Tư duy giáo viên": quan sát, hướng dẫn, diễn giải, nhận định; phần diễn giải quan trọng nhất theo thí nghiệm bỏ từng phần (Bảng 5) | Nhận xét cho giáo viên: mức nắm từng node (tốt, trung bình, yếu), dấu hiệu cẩu thả, quên, đoán mò (Mốc 2) |

| Không lấy | Lý do |
|---|---|
| GCN, IRT có giải thích, SHAP | Cần huấn luyện trên hàng trăm nghìn lượt làm bài; dự án không có dữ liệu đó |
| LLM đoán điểm ở mọi bước | Tốn token (khoảng 4 triệu token cho 536 học sinh trên FrcSub) so với hạn mức Groq miễn phí 200 nghìn token/ngày; trái quy tắc 3 (điểm là projection tất định) |
| Kiểm chứng quan hệ bằng Wikipedia và mạng nơ-ron đồ thị | Thay bằng một lượt LLM kiểm chứng và giáo viên duyệt |

**[FACT]** Bộ dữ liệu nhỏ nhất của bài (FrcSub, trừ phân số) có 8 khái niệm và 20 câu hỏi, cùng cỡ với một chương của dự án.

### 4.2. Hai khung đánh giá (blueprint PART 25–26)

Chuẩn "đã hiểu" của dự án lấy từ khung Toán đã trích xuất trong `docs/blueprint/09-student-model-assessment-analytics.md`: 7 chiều điểm, công thức composite, các cổng UNDERSTOOD và MASTERED, và bảng DI-8 nối dải điểm với hành động của gia sư. Kế hoạch này **code** phần đó, không đặt ra chuẩn mới.

## 5. Kiến trúc: năm khối

```text
Tài liệu giáo viên ──► [1] Gói chương: đồ thị tri thức + nội dung dạy của từng node (giáo viên duyệt)
                                │
Học sinh ◄──► [2] Vòng dạy ◄── [4] Chính sách dạy: chọn bước tiếp theo, đi tiếp hay quay lại
                    │                      ▲
                    └──► [3] Điểm từng node: hiểu chưa, còn thiếu bằng chứng gì
                                │
Giáo viên ◄── [5] Báo cáo: cây tri thức tô màu theo điểm, lỗi sai, nhận xét
```

Vai trò: **vòng dạy** quyết định dạy thế nào; **đồ thị** quyết định dạy ở đâu; **điểm** quyết định con đã hiểu chưa và còn thiếu gì; **RAG** quyết định nói nội dung gì; **Qwen** chỉ diễn đạt lại.

### 5.1. Gói chương

Một file cho mỗi chương (ví dụ `docs/pedagogy/math-g5/so-thap-phan/chapter.yaml`), dùng lại câu hỏi của các `lesson.yaml` trong chương.

- **Node** (một kiến thức, cũng là KC): `id`, tên, mô tả, **tầng** (`BASIC` hoặc `IMPLEMENT`), các bài (lesson) chứa nó.
- **Quan hệ:** `PREREQUISITE` (tiên quyết; đồ thị con của loại này phải không có vòng lặp), `SUBCLASS`, `SIMILAR`, `APPLICATION` (chỉ từ BASIC sang IMPLEMENT), kèm `confidence`.
- **Nội dung dạy của mỗi node,** gắn theo mức:

| Mức | Nội dung |
|---|---|
| Tiếp xúc | Lý thuyết: ít nhất **2 cách giảng** khác nhau (mỗi cách một hình ảnh: bảng hàng, trục số, tiền, đo độ dài...), mỗi cách kết thúc bằng một câu hỏi gợi suy nghĩ; quy tắc và phương pháp theo từng bước |
| Hiểu | Câu hỏi kiểm tra hiểu (chấm tất định); lời mời giải thích lại bằng lời của học sinh, kèm các ý bắt buộc phải có để chấm; câu "tìm chỗ sai của bạn" |
| Luyện tập | Ví dụ mẫu giải thích từng bước ("cô làm"); bài làm dở để học sinh làm nốt ("cô với con cùng làm"); bài luyện tập có gợi ý 5 mức ("con tự làm") |
| Vận dụng | Bài dạng mới, bài có lời văn, có hỏi "vì sao" |

- Lỗi sai hay gặp, phản ví dụ, gợi ý chung: như `lesson.yaml` hiện nay.
- Trạng thái DRAFT hoặc APPROVED; chỉ nội dung đã duyệt mới tới học sinh.

### 5.2. Vòng dạy 7 bước (trung tâm)

| Bước | Gia sư làm gì | Mức (2T-KT) | Bằng chứng thu được (chiều PART 26.1) |
|---|---|---|---|
| 1. Ôn kiến thức nền | Hỏi nhanh node tiên quyết. Sai thì **quay về dạy node tiên quyết**, xong mới quay lại | (của node tiên quyết) | C của node tiên quyết |
| 2. Giảng lý thuyết | Giảng ngắn (3–4 câu) kèm hình ảnh, kết thúc bằng câu hỏi gợi suy nghĩ. **Dạy ngắn, hỏi nhiều** | Tiếp xúc | — |
| 3. Kiểm tra hiểu | Câu hỏi khái niệm và yêu cầu nói lại quy tắc bằng lời của con. Chưa đạt thì **giảng lại theo cách khác**, không lặp câu cũ | Hiểu | C, R, D |
| 4. Dạy phương pháp | Cô làm mẫu từng bước và nói vì sao; cô làm nửa, con làm nửa; rồi con tự làm | Luyện tập | C (có hỗ trợ) |
| 5. Luyện tập | Vòng kèm từng câu hiện có: gợi ý 5 mức, hỏi "con làm thế nào", phản ví dụ cho lỗi sai | Luyện tập | C, I |
| 6. Vận dụng | Bài dạng mới hoặc có lời văn, hỏi "vì sao" | Vận dụng | A, T, R |
| 7. Quyết định | Đủ bằng chứng thì qua node; thiếu loại nào quay lại đúng bước đó; ôn xen kẽ node cũ | — | S (ôn lại sau, Mốc 2) |

### 5.3. Điểm từng node (theo PART 25.2 và 26.1)

- **Cộng trừ điểm:** mỗi chiều của mỗi node là một phân phối Beta(α, β), khởi đầu Beta(1, 1). Mỗi bằng chứng có điểm `s ∈ [0, 1]` và trọng số `w`: đúng làm tăng α (cộng điểm), sai làm tăng β (trừ điểm).
  - Trọng số theo mức gợi ý (§11 + DI-2): H0 1,00 · H1 0,85 · H2 0,70 · H3 0,60 · H4 0,50 · H5 0,35 · H6 0,20 · H7 0.
  - Trọng số theo độ khó (§31 + DI-4): đúng `0,5 + difficulty`; sai `1,5 − difficulty`.
  - Điểm theo loại lỗi (§34 + DI-3): tính nhầm khi phương pháp đúng chỉ trừ nhẹ; lỗi khái niệm trừ mạnh và ghi lỗi sai.
- **Điểm tổng (§20 + DI-1):** `M = 0,20·C + 0,20·R + 0,15·A + 0,15·T + 0,10·I + 0,10·S + 0,10·D`; chiều chưa có bằng chứng bị bỏ và chuẩn hóa lại trọng số.
- **6 mức hiểu (§4–§8):** 0 chưa học · 1 nhận biết · 2 làm theo thủ tục · 3 hiểu khái niệm · 4 vận dụng · 5 thành thạo.
- **Qua node** (DI-15, chờ duyệt): đạt mức 4 (M ≥ 75) **và** cổng UNDERSTOOD (§52: ≥ 3 bằng chứng đúng trên ≥ 2 mức nhận thức và ≥ 2 dạng câu) **và** DI-6 (có bằng chứng giải thích với μ_R ≥ 0,6, có bằng chứng vận dụng A). Không còn lỗi sai nghiêm trọng đang hoạt động.
  - **Chủ dự án quyết ngày 2026-10-12** cho phương án dựng từ tài liệu (INGEST-3a):
    - tiết khái niệm (BASIC) đạt bằng hiểu và luyện tập, không đòi bằng chứng vận dụng;
    - bằng chứng vận dụng được đòi ở tiết vận dụng (IMPLEMENT) và bài kiểm tra cuối chương;
    - node có `require_application: false` thì không cần câu vận dụng.
- **Thành thạo** (§53) cần thêm ghi nhớ S từ lần ôn sau một thời gian: Mốc 2.
- **Điểm khởi đầu của node mới** (DI-16, chờ duyệt; ý tưởng cold start của 2T-KT): prior của node lấy từ trung bình điểm các node tiên quyết, với khối lượng nhỏ để bằng chứng thật nhanh chóng lấn át.
- **Tất định:** điểm là hàm thuần của chuỗi sự kiện và version của quy tắc (quy tắc 3). AI không ghi điểm. Lời giải thích do AI chấm (Mốc 2) chỉ là một bằng chứng có độ tin cậy; quy tắc quyết định cộng bao nhiêu.
- **Cài đặt (M1-3):** `services/api/cavat/modules/assessment/projector.py`, policy `node-mastery/0.1.0`. Đọc ba loại sự kiện: `ITEM_RESOLVED` (kết quả từng câu), `EXPLANATION_SUBMITTED` (câu trả lời "vì sao") và `RETELL_JUDGED` (phần con nói lại, chấm bằng `assessment/retell.py`). Mỗi lần cộng trừ được ghi thành một bằng chứng kèm lý do, để giáo viên xem lại được.
- **[FACT] Đo trên nội dung hiện tại:** học sinh làm đúng hết node đầu (FRAC: 5 câu và một lần nói lại đủ ý) được M = 75,3, vừa đủ qua node. Chỉ cần một gợi ý, kể cả H1, là chưa qua (74,6), khi đó chính sách dạy phải thu thêm bằng chứng (giải thích, câu luyện). Node sau dễ hơn nếu node tiên quyết tốt: làm đúng hết CONCEPT được 86,9 nhờ điểm khởi đầu 0,75 (DI-16). Node đầu chương vì vậy khó qua nhất. M1-8 (học sinh ảo) sẽ đo lại; nếu cần, thêm câu luyện cho mỗi node hoặc chỉnh DI.

### 5.4. Chính sách dạy theo node

Luật tất định, mỗi luật một mã `N-*`, có version như policy gợi ý (quy tắc 7). Cùng đầu vào thì cùng quyết định.

| Luật | Khi nào | Làm gì |
|---|---|---|
| N-WARMUP | Vào node có tiên quyết chưa đủ bằng chứng trong buổi | Hỏi nhanh một câu của node tiên quyết |
| N-RECALL (DI-52) | Vào node không có câu ôn nền, hoặc kiểm tra hiểu sai lần đầu | Mời học sinh nhớ lại ý chính của một node liên quan đã học, chấm như phần nói lại, rồi nối sang node đang học |
| N-REMEDIATE | Câu ôn nền sai, hoặc kiểm tra hiểu sai hai lần mà node tiên quyết yếu | Đẩy node hiện tại vào ngăn chờ, chuyển sang dạy node tiên quyết |
| N-TEACH | Node chưa được giảng | Giảng cách 1 |
| N-CHECK | Vừa giảng xong | Câu kiểm tra hiểu, rồi mời giải thích lại |
| N-RETEACH | Kiểm tra hiểu chưa đạt | Giảng cách tiếp theo chưa dùng; hết cách thì sang ví dụ mẫu với hỗ trợ cao |
| N-METHOD | Kiểm tra hiểu đạt | Ví dụ mẫu, rồi bài làm dở |
| N-PRACTICE | Chưa đủ bằng chứng tự làm (C, I) | Bài luyện tập tiếp theo chưa dùng |
| N-TRANSFER | Đủ C, I nhưng thiếu A hoặc T | Bài vận dụng |
| N-PASS | Đạt điều kiện qua node (5.3) | Ghi qua node; quay về node đang chờ nếu có, không thì sang node tiếp theo đã mở khóa |
| N-REVIEW | Sau mỗi lần qua node | Một câu ôn xen kẽ của node đã qua trước đó |
| N-BUDGET | Hết số câu cho phép ở node mà chưa đạt | Dừng node, ghi "cần học lại" cho giáo viên; node phụ thuộc vẫn khóa |
| N-FINISH | Không còn node mở khóa chưa qua | Tổng kết buổi học |

Bảng DI-8 của blueprint (dải M → hành động) dùng để chọn mức hỗ trợ trong N-PRACTICE và N-TRANSFER.

- **Cài đặt (M1-4):** `services/api/cavat/modules/teaching/node_policy.py`, policy `node-policy/0.1.0`.
  - Thêm luật N-NEXT: chưa ở node nào thì quay về node đang chờ, không thì vào node đầu tiên đã mở khóa mà chưa qua.
  - Mỗi quyết định được ghi thành sự kiện `NODE_DECISION`, có mã luật và lý do.
  - Trạng thái dạy của buổi học (`teaching/state.py`) được tính lại từ các quyết định đó cùng kết quả từng câu và phần con nói lại, nên phát lại được.
- **[FACT] Đo bằng học sinh giả lập làm đúng hết:** cả 7 node qua theo đúng thứ tự học, mất 73 quyết định (khoảng 10 bước mỗi node, 2 câu ôn xen kẽ).
- **Vòng dạy (M1-6):** `services/api/cavat/modules/teaching/loop.py`.
  - Thực hiện từng quyết định của chính sách: giảng, câu hỏi (qua item loop với gợi ý 5 mức và "vì sao"), con nói lại (chấm bằng `assessment/retell.py`), cô làm mẫu, chuyển node.
  - Tự đi tiếp cho tới khi cần học sinh trả lời.
  - `TeachingLoop.resume` dựng lại vòng dạy từ sự kiện đã lưu: câu đang làm phát lại các lần trả lời bằng mẫu câu.
- **[FACT] Đo bằng học sinh giả lập:** cả chương mất 70 lượt trả lời (khoảng 10 mỗi node).
- **[OPEN] Câu hỏi cuối phần giảng chưa có đáp án mẫu:** cô chỉ đáp "Cô cảm ơn con." mà không nhận xét câu trả lời. Cách sửa: thêm đáp án mẫu cho câu hỏi của từng cách giảng (nội dung), hoặc để Qwen nhận xét có căn cứ ở M1-9.
- **[OPEN] Kho câu còn mỏng:** mỗi node mới có 2 câu luyện. Khi quay về node tiên quyết giữa buổi, gia sư giảng lại được (cách giảng và ví dụ mẫu chưa dùng), nhưng không còn câu luyện mới nên phải dừng node với lý do `NO_ITEMS_LEFT`. Đề xuất: thêm 2–3 câu luyện cho mỗi node (task M1-2c).

### 5.5. Hybrid RAG (tự xây)

RAG trả lời câu hỏi: **gia sư nên dựa vào đoạn nội dung đã duyệt nào** cho lượt này. Kết quả là một hoặc vài đoạn làm **neo** cho lời nói (mục 5.6). LLM không bao giờ trả lời mà không có neo.

"Hybrid" ở đây gồm ba tín hiệu bổ sung cho nhau:
- **Cấu trúc đồ thị:** lọc theo node và mức, mở rộng sang node lân cận khi cần.
- **Từ khóa (sparse, BM25):** bắt đúng thuật ngữ và con số ("hàng phần mười", "0,50").
- **Ngữ nghĩa (dense, vector embedding):** bắt câu hỏi diễn đạt khác tài liệu ("sao thêm số 0 mà không đổi?" và đoạn "viết thêm chữ số 0 ở tận cùng bên phải phần thập phân").

#### 5.5.1. Kho đoạn (corpus) và chia đoạn

- **Nguồn:** nội dung **đã duyệt** của gói chương (lý thuyết từng cách giảng, quy tắc, ví dụ mẫu, câu kiểm tra, ghi chú lỗi sai) và, từ Mốc 2, các đoạn tài liệu giáo viên sau khi đọc và sửa lỗi.
- **Mỗi đoạn có:** `chunk_id`, `node_id`, `stage` (Tiếp xúc, Hiểu, Luyện tập, Vận dụng), `kind` (theory, method, worked_example, check, misconception_note, source_passage), `text`, nguồn gốc (file, trang), version, trạng thái duyệt, vector embedding.
- **Chia theo đơn vị sư phạm:** một cách giảng là một đoạn, một ví dụ mẫu là một đoạn. Tài liệu dài chia theo đoạn văn, khoảng 150–300 token, chồng lấn một câu. Không cắt giữa một biểu thức hay một bảng.

#### 5.5.2. Lập chỉ mục (khi nội dung được duyệt, không phải lúc học)

1. **Chuẩn hóa tiếng Việt:** NFC, chữ thường. Lập chỉ mục hai bản: **còn dấu** (chính xác) và **bỏ dấu** (học sinh hay gõ không dấu: "tai sao phai them so 0"). Số được chuẩn về một dạng (`0,25` và `0.25` là một token).
2. **Chỉ mục từ khóa:** BM25 tự viết trên âm tiết và cặp âm tiết liền nhau (để giữ cụm như "phần mười"). Tham số k1 = 1,2, b = 0,75 (DI-17).
3. **Chỉ mục vector:** embedding của từng đoạn, tạo qua gateway (model class `EMBEDDING`). Lưu kèm đoạn; tìm bằng cosine tự viết với numpy. Không dùng vector database: Atlas M0 không có Vector Search (D-T7), và sau khi lọc theo node thì số đoạn rất nhỏ.
4. **Chỉ mục cấu trúc:** node, mức, loại, và quan hệ trong đồ thị (tiên quyết, tương tự).

#### 5.5.3. Truy xuất lúc học: 6 bước

| Bước | Làm gì |
|---|---|
| 1. Phạm vi | Lấy các đoạn của node đang học, đúng mức hiện tại. Đang dạy lại node tiên quyết thì phạm vi là node đó. Câu hỏi tự do của học sinh thì mở rộng sang node tiên quyết và node tương tự, kèm hệ số phạt theo khoảng cách trên đồ thị |
| 2. Từ khóa | BM25 trên cả hai bản (còn dấu, bỏ dấu), lấy bản điểm cao hơn cho mỗi đoạn → danh sách xếp hạng thứ nhất |
| 3. Ngữ nghĩa | Embedding câu truy vấn, cosine với các đoạn trong phạm vi → danh sách xếp hạng thứ hai |
| 4. Hợp nhất | Reciprocal Rank Fusion: `score(d) = Σ 1 / (60 + rank_i(d))`, trên hai danh sách và có trọng số theo khoảng cách đồ thị (DI-17) |
| 5. Xếp hạng lại theo sư phạm | Luật tất định: đúng mức trước; đoạn **chưa dùng** trong buổi trước đoạn đã dùng (giảng lại phải bằng cách khác); đoạn nói về lỗi sai vừa phát hiện được ưu tiên; chỉ đoạn đã duyệt |
| 6. Chọn và ghi vết | Lấy 1–3 đoạn trong giới hạn token của prompt (tổng ≤ 3.000). Ghi sự kiện `RAG_RETRIEVED` (đoạn nào, điểm từng tín hiệu) để kiểm tra và đánh giá |

**Câu truy vấn** ghép từ: câu học sinh vừa nói, tên và mô tả node, mã lỗi sai vừa phát hiện (nếu có).

**Hai chế độ:**
- **Theo chính sách:** bước dạy cần "cách giảng tiếp theo của node X". Bước 1 và 5 quyết định gần hết; bước 2–4 dùng để chọn cách giảng hợp với điều học sinh vừa nói.
- **Học sinh hỏi tự do** ("sao 0,5 lại bằng 0,50?"): chạy đủ 6 bước. Điểm hợp nhất cao nhất dưới ngưỡng (DI-17) thì gia sư không bịa: trả lời bằng nội dung chính của node và ghi câu hỏi cho giáo viên.

#### 5.5.4. Dự phòng và kiểm tra

- **Không gọi được embedding** (hết hạn mức, lỗi mạng): chạy với từ khóa và cấu trúc. Buổi học không dừng.
- **Không có kết quả:** dùng đoạn lý thuyết mặc định của node.
- **Test offline:** dùng một hàm embedding tất định thay cho model thật, để CI và phiên không có khóa vẫn chạy được.
- **Model embedding:** model đa ngôn ngữ của Gemini qua gateway, tên model nằm trong cấu hình. **[OPEN]** Hạn mức miễn phí của embedding phải đo lại như `docs/poc/free-tier-quota.md`. Nếu không đủ, dùng model đa ngôn ngữ chạy local ở Mốc 2.

#### 5.5.5. Đánh giá RAG (cho chương thực nghiệm)

- Bộ câu hỏi có nhãn: câu học sinh hỏi (gồm cả không dấu, viết sai) và đoạn đúng cần lấy.
- So sánh **chỉ từ khóa**, **chỉ ngữ nghĩa**, **hybrid** và **hybrid + xếp hạng lại** bằng Recall@k và MRR. Đây là thí nghiệm bỏ từng phần, cùng kiểu Bảng 5 của 2T-KT, để chứng minh vì sao chọn hybrid.

#### 5.5.6. Cài đặt (RAG-1) và kết quả đo

- **RAG lấy dữ liệu từ đâu:**
  - Nội dung chương trong `docs/pedagogy/` (47 đoạn: 15 cách giảng, 7 phương pháp, 16 ví dụ mẫu, 9 ghi chú lỗi sai). Đây là bản nháp do AI soạn, chờ giáo viên duyệt; được dùng nhưng xếp sau nội dung đã duyệt.
  - Các tài liệu giáo viên tải lên ở tab Tài liệu (DOC-1), sau khi đọc ra chữ.
  - Câu hỏi bài tập và đáp án **không** vào kho (quy tắc 2). "Câu kiểm tra" của 5.5.1 chính là câu hỏi của từng cách giảng, đã nằm trong đoạn lý thuyết.
- **Chỉ mục:**
  - Dựng lại trong tiến trình API khi một tài liệu hay version chương đổi.
  - Vector Gemini lưu đệm theo mã băm ở `var/storage/rag/`, nên mỗi đoạn chỉ tốn hạn mức một lần.
  - Không có khóa Gemini hoặc gọi lỗi: chạy bằng từ khóa và cấu trúc, sau 10 phút thử gọi lại.
  - Vector trigram tất định chỉ dùng cho test: nó so chữ, không hiểu nghĩa.
- **Đổi so với 5.5.3:**
  - Ngưỡng "có căn cứ" không đặt trên điểm hợp nhất. RRF chỉ xếp hạng: đoạn đứng đầu luôn được 1/61 mỗi danh sách, nên không biết được là không đoạn nào trả lời câu hỏi.
  - Thay vào đó dùng cosine của model ngữ nghĩa, hoặc độ phủ từ khóa khi không có model (DI-17). Có model thì từ khóa không được quyết thay: câu Toán của chương khác ("cộng hai phân số khác mẫu số") có tới năm từ chung với chương.
- **Giáo viên xem:** tab RAG hiện nguồn của kho, số đoạn của từng tài liệu, model đang dùng. Ô tra cứu chạy đủ 6 bước và hiện điểm từng tín hiệu của từng đoạn.
- **Kết quả với Gemini** (`make eval-rag LIVE=1`, báo cáo `evals/reports/2026-10-07-rag-gemini.md`; MRR):

  | Cấu hình | Bộ câu chính: 57 câu, dùng để chỉnh tham số | Bộ câu riêng: 15 câu, không dùng để chỉnh |
  |---|---|---|
  | Chỉ từ khóa | 0,826 | 0,608 |
  | Chỉ ngữ nghĩa | 0,868 | 0,765 |
  | Hybrid | 0,864 | 0,722 |
  | Từ khóa + xếp hạng lại (khi không có vector) | 0,882 | 0,608 |
  | Hybrid + xếp hạng lại | **0,947** (Hit@3 = 1,00) | 0,722 (Hit@3 = 0,87) |

  - "Có căn cứ" ở ngưỡng 0,65: đúng 100% trên cả hai bộ (72 câu trong chương nhận, 25 câu lạc đề từ chối, trong đó 10 câu Toán ngoài chương).
- **Giới hạn đã thấy:**
  - Khoảng cách giữa câu Toán ngoài chương gần nhất (0,648) và câu trong chương xa nhất (0,668) chỉ khoảng 0,02. Khi thử trên web, "chu vi hình vuông tính sao cô" ra 0,64. Cần đo lại khi có tài liệu thật và câu hỏi thật của học sinh.
  - Trên bộ câu riêng (15 câu), chỉ ngữ nghĩa nhỉnh hơn hybrid một câu. Mẫu còn nhỏ nên giữ RRF theo plan và đo lại.
  - Xếp hạng lại chỉ có tác dụng với câu của chính sách dạy và câu "là gì". Bộ câu riêng không có loại câu đó.
  - Nhãn của hai bộ câu do AI soạn, chờ giáo viên duyệt.

### 5.6. Lời nói của gia sư

- Đoạn lấy từ Hybrid RAG là **neo**. Qwen diễn đạt lại cho hợp với câu học sinh vừa nói, phải giữ đủ ý của neo (bộ chặn `llm-renderer.v2`: bám câu mẫu, không thêm số, không lặp lại).
- Mọi câu qua bộ kiểm tra hiện có. Hết hạn mức, lỗi mạng hay câu bị loại thì dùng nguyên văn nội dung đã duyệt.

#### 5.6.1. Cài đặt (RAG-2, ADR-021) và kết quả đo

- **Trước RAG-2 [FACT]:** trong buổi học theo chương, lời giảng, lời đáp câu hỏi của cách giảng và mọi câu con tự hỏi đều là câu mẫu. Qwen chỉ diễn đạt nước đi trong bài tập.
- **Câu con tự hỏi** (khi gia sư đang chờ con trả lời câu hỏi của cách giảng hoặc nói lại bài):
  - Câu được tính là câu hỏi khi có dấu hỏi, mở đầu bằng từ hỏi, hoặc kết thúc bằng tiểu từ hỏi, và có ít nhất 2 từ có nghĩa (DI-39).
  - Gia sư truy xuất trong phạm vi bài đang học. Có căn cứ thì Qwen trả lời từ tối đa 3 đoạn, và câu trả lời qua bộ kiểm chứng (mục 5.6.2 và DI-40).
  - Gia sư không trả lời trong các trường hợp sau, mỗi trường hợp ghi `QUESTION_PARKED` cho giáo viên:
    - không có căn cứ;
    - Qwen thấy đoạn không trả lời được;
    - câu thuộc bài học sau: gia sư nói tên bài đó;
    - con hỏi lại đúng câu gia sư đang hỏi: gia sư mời con tự nghĩ;
    - quá 2 câu hỏi mỗi lượt chờ.
- **Câu nối:** con trả lời câu hỏi của cách giảng chưa đúng thì Qwen viết một câu nhắc lại ý của con, có gắn ý cho con ("con nghĩ…"). Sau đó gia sư nói nguyên văn lời giải thích đã duyệt.
- **Bộ kiểm chứng** (`teaching/grounded.py`, DI-40):
  - số và thuật ngữ Toán phải có trong nguồn;
  - ít nhất 60% từ có nghĩa có trong nguồn;
  - không có chữ ngoài tiếng Việt;
  - không câu hỏi, không quá dài;
  - không hỏi thông tin cá nhân, không khen trí thông minh;
  - câu nối phải gắn ý cho con, không chép lời giải thích, không khen "đúng rồi" khi con chưa đúng.

  Bị chặn thì thử lại một lần, rồi dùng câu dự phòng:
  - câu trả lời: nguyên văn câu của đoạn nguồn, nếu câu đó phủ được ít nhất một nửa câu hỏi;
  - câu nối: câu mẫu.
- **Kết quả với Qwen và Gemini thật:** `make eval-grounded`, báo cáo `evals/reports/2026-10-07-grounded-live.md`. Số liệu tóm tắt ở mục 5.6.2.

#### 5.6.2. Kết quả đo và những gì đã sửa nhờ đo (2026-10-07)

**Lượt chạy đủ 21 ca** (`grounded-speech/0.1.0`, `evals/reports/2026-10-07-grounded-live.md`, giám khảo `openai/gpt-oss-120b`):
- Quyết định đúng 15/15 câu con tự hỏi: trả lời, mời con tự nghĩ, bài sau, để lại cho giáo viên.
- Câu trả lời: 7 câu do Qwen viết, 1 câu trích nguyên văn đoạn nguồn. Giám khảo chấm bám nguồn 4,12, đúng trọng tâm 3,62, đúng kiến thức 4,12. Không câu nào lộ đáp án câu đang chờ.
- Giám khảo có hai lần chấm sai, nên làm điểm trung bình thấp đi:
  - G05: chấm 1/5 kèm nhận xét "không có câu trả lời để đánh giá", trong khi câu trả lời có và đúng.
  - G07: chấm 2/5 một câu trả lời đúng và bám nguồn.
- Câu nối: 5/6 do Qwen viết. Bám nguồn 5,00, đúng trọng tâm 5,00, đúng kiến thức 4,40. Hai cờ "bịa" (B05, B06) là giám khảo chấm vào lời giải thích đã duyệt nằm sau câu nối, không phải chấm câu nối.

**Những gì đã sửa nhờ đo:**
- **Câu nối nhắc lại ý sai của con mà không nói đó là ý của con.** Cả giám khảo lẫn trẻ có thể hiểu là cô xác nhận ý sai. Câu nối giờ phải gắn ý cho con ("con nghĩ…", "An nói…") và không được khen "đúng rồi" khi con chưa đúng.
- **Lượt đầu, phần trích dự phòng nói câu lạc đề** ("1 m bằng 10 dm…" cho câu hỏi về 0,5 và 0,50). Giờ:
  - câu trích phải phủ ít nhất một nửa câu hỏi;
  - câu thuộc bài học sau thì gia sư nói tên bài đó;
  - Qwen để trống câu trả lời thì gia sư không trả lời.
- **Bộ kiểm chứng đòi 80% mọi từ có trong nguồn (trọng số idf) nên chặn oan các câu đúng:**
  - "giá trị không thay đổi" (nguồn viết "không đổi");
  - "đọc như số tự nhiên bình thường";
  - "đếm xem mẫu số 1000 có ba chữ số 0".

  Từ của chương xuất hiện ở mọi đoạn nên gần như không có trọng lượng, và vài từ thường quyết định kết quả. Bản `0.2.0` đổi cách kiểm:
  - thuật ngữ Toán (`MATH_TERMS`) phải có trong nguồn;
  - con số phải có trong nguồn;
  - mọi từ có nghĩa đếm đều nhau, cần đạt 60%.

  Kiểm lại 4 ca (`…-grounded-live-partial.md`): G04, G05, B06 đều qua với câu trả lời đúng.
- **Ở lượt kiểm lại đó Qwen sinh câu hỏng lẫn chữ Trung và chữ Anh** ("số chữ số thập分 like nha"), và bộ kiểm chứng đã nới để lọt. Bản `0.2.1` thêm kiểm tra ngôn ngữ (`FOREIGN_TEXT`): chặn chữ Trung, Nhật, Hàn, Thái, Kirin, chữ cái f, j, w, z và từ tiếng Anh thông dụng. Kiểm tra này áp cho cả câu gợi ý trong bài tập. Câu hỏng đó nay là một test.
- **Nội dung chương:** câu hỏi "chữ số 6 chỉ mấy xăng-ti-mét?" chấp nhận số "6" trần, nên "6 dm" (sai đơn vị) bị chấm là đúng. Đã bỏ "6" trần (`chapter.yaml` 0.1.1, chờ duyệt).

**Còn phải làm:**
- Chạy lại đủ 21 ca với `grounded-speech/0.2.1` khi có hạn mức Qwen ngày mới. Hôm nay đã dùng phần lớn hạn mức cho 4 lượt chạy.
- Thêm một giám khảo thứ hai hoặc chấm hai lần, vì giám khảo đơn có sai sót.
- Ca G09: câu trả lời trúng ý nằm ở bài nền (cách 1 bước), nên đoạn về so sánh của bài đang học đứng đầu. Ghi vào RAG-3.

### 5.7. Báo cáo cho giáo viên

- Cây tri thức của từng học sinh tô màu theo điểm (dải màu §25), bằng chứng theo từng chiều, lỗi sai, node "cần học lại".
- Nhận xét kiểu "tư duy giáo viên" của 2T-KT do Qwen viết từ dữ liệu tất định, ghi rõ là nhận xét của AI.
- Transcript có nhãn hiện có (kết quả chấm, lỗi sai, mã luật, nguồn câu nói).
- **Cài đặt (M1-7):**
  - API: buổi học mặc định là buổi học theo chương (`session/chapter_service.py`). Mỗi lệnh dựng lại vòng dạy từ sự kiện của buổi học. `GET /v1/sessions/{id}/report` trả "bộ não gia sư" cho giáo viên.
  - Web, phía học sinh: bản đồ bài học (cây tri thức hai tầng, trạng thái từng bài, mức hiểu bằng chữ), thanh 7 bước, thẻ "Cô giảng bài", thẻ "Cô làm mẫu", ô "con nói lại".
  - Web, phía giáo viên: tab "Bộ não gia sư" gồm cây tri thức có điểm M từng bài, điểm M qua từng lượt so với ngưỡng, 7 chiều đánh giá, điều kiện qua bài, bảng bằng chứng cộng/trừ kèm lý do, dòng quyết định của cô kèm mã luật. Tab "Hội thoại" thêm nhãn bước dạy, mã luật và kết quả phần nói lại.
  - Lịch sử (M1-7b): `make demo` lưu vào `cavat_dev`; học sinh có "Lịch sử học"; buổi mới đọc sự kiện các buổi trước của cùng học sinh trên chương. Bài đã qua giữ nguyên, điểm cộng dồn, gia sư vào bài tiếp bằng câu ôn bài nền (N-WARMUP).
  - Chưa làm: tô màu theo dải §25 và nhận xét kiểu "tư duy giáo viên" (Mốc 2).

## 6. Giữ, thay, bỏ

- **Giữ:** bộ chấm Toán (T01), policy gợi ý và vòng kèm từng câu (T02, T04; thành bước 5), câu mẫu và bộ kiểm tra (T03), kết nối Groq/Gemini (T06a), Qwen bám câu mẫu (T06b), lưu trữ Atlas (T07), API buổi học (T08), web (T09, T13).
- **Thay:** danh sách 8 câu cố định của buổi học bằng chính sách dạy theo đồ thị.
- **Bỏ khỏi demo:** English, giọng nói (T15).
- **Bỏ hẳn:** LlamaParse (D-T11); khóa `LLAMA_CLOUD_API_KEY` không còn được dùng.

## 7. Lộ trình

### Mốc 1: vòng dạy chạy được ở phần đầu chương Số thập phân

7 node: Phân số thập phân → Khái niệm số thập phân → Giá trị theo hàng → Số thập phân bằng nhau → So sánh → Sắp xếp, Vận dụng so sánh. Năm node cuối đã có câu hỏi trong bài 1; AI soạn nháp phần còn thiếu, chủ dự án duyệt.

| Task | Nội dung |
|---|---|
| M1-1 | Ghi kế hoạch vào repo (tài liệu này, ADR-018, blueprint, CLAUDE.md, BACKLOG) |
| M1-2 | Khuôn gói chương, bộ đọc và bộ kiểm tra (không vòng lặp tiên quyết, tham chiếu hợp lệ, mỗi node đủ nội dung theo 4 mức); gói chương Số thập phân phần đầu (nháp) |
| M1-3 | Điểm từng node theo mục 5.3: projector tất định từ sự kiện, cổng qua node, điểm khởi đầu từ tiên quyết |
| M1-4 | Chính sách dạy theo node (mục 5.4) |
| M1-5 | Hybrid RAG (mục 5.5): chia đoạn, chỉ mục BM25 hai bản, chỉ mục vector, hợp nhất RRF, xếp hạng lại theo sư phạm, ghi vết; model class `EMBEDDING` trong gateway; bộ câu hỏi đánh giá đầu tiên |
| M1-6 | Bộ máy vòng dạy: chạy 7 bước trên đồ thị, gọi vòng kèm từng câu ở bước luyện tập; test hội thoại trọn 7 node, chạy offline |
| M1-7 | Nối vào API buổi học và web: bản đồ node (đã qua, đang học, chưa mở), lời giảng lý thuyết, ô giải thích |
| M1-8 | Học sinh ảo (thay T05): mỗi em mang một lỗi sai hoặc một chỗ hổng tiên quyết; đo số lần công nhận "đã hiểu" sai, số lần quay về đúng node tiên quyết |
| M1-9 | Qwen diễn đạt lời giảng neo vào đoạn của Hybrid RAG; chạy thử thật trên web |

**Xong Mốc 1 khi:**
- Một học sinh học trọn 7 node theo vòng 7 bước: cô ôn nền, giảng, hỏi lại, làm mẫu, cho làm cùng rồi tự làm.
- Cô quay về node tiên quyết khi con hổng, giảng lại cách khác khi con chưa hiểu, và chỉ cho qua node khi đủ bằng chứng (5.3).
- Học sinh ảo mang lỗi sai không lần nào được công nhận "đã hiểu" ở node chứa lỗi đó.
- `make test` và `make web-check` xanh.

### Mốc 2: dữ liệu thật và màn hình giáo viên

- Đường dựng gói chương từ tài liệu, **tự xây** (không dùng LlamaParse): PDF có chữ đọc bằng thư viện đọc PDF cấp thấp rồi tự dựng bố cục; ảnh và bản scan qua Gemini; tầng sửa lỗi xem cả ảnh lẫn văn bản, đánh dấu chỗ lệch về chữ số và ký hiệu toán; LLM dựng node và quan hệ (prompt theo Hình 4 của 2T-KT, ngưỡng 0,75, một lượt kiểm chứng); kiểm tra tự động (khuôn, đáp án tự giải lại, các kiểm tra nội dung trong CI); màn hình duyệt.
- Việc thật đầu tiên: dựng phần còn lại của chương Số thập phân từ tài liệu của chủ dự án (làm tròn, viết số đo đại lượng, cộng trừ số thập phân, bài có lời văn).
- Chấm lời giải thích (AI đề xuất nhãn kèm độ tin cậy); đủ 7 chiều điểm; ôn lại sau một thời gian (S) và trạng thái thành thạo.
- Báo cáo giáo viên: cây tri thức, nhận xét kiểu "tư duy giáo viên".
- **Xong khi:** cả chương Số thập phân dựng từ tài liệu thật, chủ dự án duyệt, học sinh học trọn chương, giáo viên xem được cây tri thức.

### Mốc 3: chương Diện tích hình tam giác và hình thang

- Câu hỏi có hình vẽ, đáp án có đơn vị (cm², m², dm²), gợi ý chỉ vào hình.
- Node hình học trỏ về node phép tính số thập phân.
- **Xong khi:** chương thứ hai chạy chủ yếu nhờ thêm nội dung, sửa code ít.

## 8. Đo lường cho đồ án

Chạy song song từ Mốc 1:
- **Học sinh ảo:** độ chính xác chẩn đoán lỗi sai, số lần công nhận "đã hiểu" sai, số lượt và số gợi ý trung bình để qua node.
- **Học sinh thật:** bài kiểm tra trước và sau buổi học; chủ dự án chấm transcript.
- **Đồ thị máy dựng** so với đồ thị chủ dự án dựng tay: đúng bao nhiêu node, bao nhiêu quan hệ.
- **Độ chính xác đọc tài liệu** so với bản soạn tay (chữ số, câu hỏi).
- **Hybrid RAG:** Recall@k và MRR của từ khóa, ngữ nghĩa, hybrid, hybrid + xếp hạng lại (mục 5.5.5).
- **Tùy chọn:** so sánh điểm tính theo quy tắc với cách để LLM đoán theo 2T-KT trên dữ liệu học sinh ảo.
- **Khuôn mẫu dùng lại được:** thêm một bài của chương thứ ba chỉ bằng nội dung.

## 9. DI và việc chờ chủ dự án

- **DI-15:** điều kiện qua node (mục 5.3). Cách hiểu khi cài đặt:
  - câu "thành công" là câu giải đúng với gợi ý cao nhất ≤ H3, không đoán, không phải bài cùng làm;
  - "mức nhận thức" là A–E (câu DIAG không tính); "dạng câu" là loại đáp án (trắc nghiệm, điền số, điền dấu, sắp xếp, đúng/sai, tự luận);
  - "có bằng chứng giải thích": chiều R có ít nhất 1 đơn vị bằng chứng và μ_R ≥ 0,6;
  - "có bằng chứng vận dụng": một câu thành công ở mức D/E hoặc câu transfer (chiều A hoặc T);
  - lỗi sai CRITICAL được coi là đã sửa sau 2 câu thành công kể từ lần phát hiện cuối, ở kiến thức nơi lỗi đã xuất hiện.
- **DI-16:** điểm khởi đầu của node mới lấy từ node tiên quyết. Mỗi chiều bắt đầu từ Beta(2m, 2(1 − m)), với m là trung bình M (thang 0–1) của các node tiên quyết đã có điểm lúc node nhận bằng chứng đầu tiên; không có thì m = 0,5, tức Beta(1, 1) như DI-12. Điểm khởi đầu giữ nguyên từ đó.
- **DI-19 (tham số của `node-policy/0.1.0`):**
  - kiểm tra hiểu đạt khi câu kiểm tra thành công và con nói lại được ít nhất nửa số ý bắt buộc;
  - cần 2 câu luyện thành công trước bài vận dụng;
  - mời nói lại tối đa 3 lần mỗi lượt ở node;
  - mỗi cặp (node, node tiên quyết) chỉ quay về một lần mỗi buổi, không quay về node đã dừng;
  - chỉ lỗi sai CRITICAL của node tiên quyết (kể cả tiên quyết gián tiếp) mới kích hoạt N-REMEDIATE;
  - câu ôn xen kẽ lấy từ node đã qua có điểm thấp nhất;
  - ưu tiên câu chưa gặp ở buổi nào, câu dò được lỗi sai đang hoạt động được ưu tiên trước.
- **DI-18 (tham số khác của `node-mastery/0.1.0`):**
  - bài cùng làm có trọng số × 0,5;
  - câu trả lời "vì sao" chưa được chấm tính R = 1 với trọng số 0,3, như nhãn chưa kiểm chứng (PART 26.5); được hỏi "vì sao" mà không giải thích, hoặc đoán, thì R = 0;
  - lỗi khái niệm chưa sửa được thì R cũng nhận điểm 0;
  - chiều của câu theo mức: A/B → C, C → R, D → A, E hoặc câu transfer → T, DIAG → D;
  - độc lập I chỉ tính từ câu giải được, theo gợi ý cao nhất;
  - mức 5 chỉ đạt khi qua cổng thành thạo tạm thời (M ≥ 85, độ tin cậy ≥ 75, μ_A ≥ 0,8), vì Mốc 1 chưa có chiều ghi nhớ S.
- **DI-20 đến DI-31 (giao diện UI-1, UI-2; theo khung Toán §23–§28, §39, §43, §45, §46, §56, §57):**
  - **DI-20, học sinh cần chú ý.** Một em vào danh sách khi:
    - có lỗi sai đang mắc là CRITICAL, hoặc đã gặp từ 2 lần;
    - gia sư đã dừng một bài;
    - một bài chưa qua có M < 40 khi đã đủ dữ liệu (độ tin cậy ≥ 30, DI-7);
    - có buổi học dở dang mà 7 ngày chưa học.
  - **DI-21, điểm tổng và phủ kiến thức (§23).**
    - Điểm tổng là trung bình M của các bài đã có điểm.
    - Phủ kiến thức là tỉ lệ bài đã có điểm.
    - Độ tin cậy tổng là trung bình độ tin cậy của các bài đó.
  - **DI-22, mỗi chiều trên cả chương (radar §24).**
    - Giá trị là trung bình μ của chiều ở các bài mà chiều được tính vào M (DI-1), theo trọng số lượng bằng chứng hiệu dụng.
    - Trục Kiến thức của §24 lấy chiều C (blueprint C1). D hiện bên cạnh radar.
  - **DI-23, điểm mạnh và điểm yếu (§23).** Tối đa 2 chiều từ 75 trở lên (vùng xanh §25) là điểm mạnh; tối đa 2 chiều dưới 60 là điểm yếu.
  - **DI-24, xu hướng (§27).** So M hiện tại với M ở 3 lần thay đổi trước: chênh từ 3 điểm là tiến bộ hoặc suy giảm, còn lại là đứng yên.
  - **DI-25, tốc độ học (§39).** Điểm tổng hiện tại trừ điểm tổng cuối ngày học gần nhất trước tuần này (tuần tính từ thứ Hai).
  - **DI-26, dòng thời gian (§27).** Điểm tổng cuối mỗi ngày có bằng chứng mới, theo giờ Việt Nam.
  - **DI-27, nhóm kiến thức (§43).**
    - ✓ đã qua bài theo DI-15. Chưa gọi là "làm chủ" vì §53 cần chiều ghi nhớ.
    - ✕ còn yếu: M < 60 khi đủ dữ liệu.
    - ⚠ chưa ổn định: M ≥ 60 nhưng chưa qua.
    - Thêm hai nhóm: "chưa đủ dữ liệu" (DI-7) và "chưa học".
  - **DI-28, lỗi tái diễn (§28).**
    - Lỗi tái diễn nhiều nhất là lỗi gặp nhiều lần nhất trong 14 ngày.
    - "Cần can thiệp": lỗi CRITICAL, hoặc gặp từ 3 lần trong 14 ngày, mà còn em đang mắc.
    - "Đã sửa được": không còn em nào mắc.
    - Còn lại là "Theo dõi".
  - **DI-29, thời gian học.** Cộng khoảng cách giữa hai sự kiện liên tiếp trong buổi; mỗi khoảng tính tối đa 5 phút.
  - **DI-30, ngày học.** Ngày theo giờ Việt Nam có ít nhất một lượt học sinh.
  - **DI-31, hai nhãn thêm cho học sinh và phụ huynh (ngoài DI-14).** "Chưa học" cho bài chưa có bằng chứng; "Đang học" cho bài đang học mà chưa có bằng chứng.
- **DI-32 đến DI-38 (hiểu học sinh trước khi chấm, ADR-019):**
  - **DI-32, đọc ý định.**
    - Bảng chữ viết tắt kiểu teencode ("ko", "k", "bít", "j", "z", "dc"...) và các danh sách cụm từ trong `assessment/student_intent.py`.
    - Thứ tự ưu tiên: im lặng, đòi đáp án, có câu trả lời, cảm xúc tiêu cực, hỏi lại đề, không biết hoặc xin gợi ý, lạc đề.
    - Câu không đọc được, từ 4 từ trở lên, không có số và không có từ nào của bài, thì là lạc đề.
  - **DI-33, R-OFF-TOPIC.** Đáp ngắn rồi hỏi lại câu đang làm. Không tính lượt, không gợi ý.
  - **DI-34, R-CLARIFY và R-AFFECT.**
    - R-CLARIFY: lần đầu nói lại đề bằng gợi ý TASK H1, lần sau lên gợi ý tiếp theo.
    - R-AFFECT: lên 1 mức gợi ý, từ lần thứ hai lên 2 mức.
    - Ở câu kiểm tra cuối buổi, quá mức H1 thì chỉ nhắc lại câu hỏi, không đóng câu.
  - **DI-35, một lần hỏi "gợi ý hay tự thử".** Câu "gợi ý thêm hay tự thử lại?" hỏi một lần mỗi câu, chỉ sau "không biết". "Xin gợi ý" thì có gợi ý ngay.
  - **DI-36, đòi đáp án.** Từ chối có lý do rồi gợi ý mức tiếp theo.
  - **DI-37, thang gợi ý theo loại câu.**
    - Gợi ý chung của bài khai báo `answer_types`.
    - Thang gợi ý của một câu dừng ở gợi ý mạnh nhất dùng được cho câu đó; quá đó thì làm mẫu từng bước.
  - **DI-38, hỏi lại và lạc đề.**
    - Trả lời "vì sao" bằng "là sao", lạc đề hay than chán thì được hỏi lại một lần.
    - Ở lời giảng và phần nói lại, lạc đề được kéo về tối đa 2 lần rồi gia sư giải thích và đi tiếp.
    - Lời đáp câu hỏi lý thuyết (`reply`, `accept` trong `chapter.yaml`) là bản nháp chờ duyệt.
- **DI-39, câu con tự hỏi (RAG-2, chờ duyệt):**
  - Là câu hỏi khi có dấu hỏi, mở đầu bằng từ hỏi ("tại sao", "sao", "làm sao", "thế nào", "bao nhiêu"…), hoặc kết thúc bằng tiểu từ hỏi ("là gì", "không", "đúng không", "chưa"…), và có ít nhất 2 từ có nghĩa.
  - Từ hỏi nằm giữa câu kể ("bao nhiêu chữ số 0 thì…") không tính.
  - Mỗi lượt chờ trả lời tối đa 2 câu hỏi.
  - Coi là hỏi lại đúng câu gia sư đang hỏi khi ít nhất 80% từ có nghĩa của câu con hỏi nằm trong câu đó.
  - Đòi đáp án, than chán, lạc đề giữ đường riêng của ADR-019.
  - Các câu mẫu mới (`teaching-templates/0.3.0`: `question_back`, `question_parked`, `question_same`, `question_later`, `question_limit`) là bản nháp chờ duyệt.
- **DI-40, kiểm chứng lời Qwen (RAG-2, chờ duyệt; `grounded-speech/0.2.2`; 0.2.2 thêm chặn sai xưng hô):**
  - thuật ngữ Toán (`MATH_TERMS`) và con số phải có trong nguồn;
  - ít nhất 60% từ có nghĩa khác nhau có trong nguồn (bản 0.1.0 dùng 80% có trọng số idf và đã chặn oan câu đúng, mục 5.6.2);
  - không có chữ hay từ ngoài tiếng Việt;
  - câu trả lời tối đa 50 từ, câu nối tối đa 25 từ;
  - câu trích dự phòng phải phủ ít nhất 50% câu hỏi;
  - câu nối phải gắn ý cho con (cả khi gọi con bằng tên).
- **DI-66, gia sư của từng câu đọc Student Model (PRIOR-1, 2026-10-22):**
  - **Vấn đề:** blueprint 05 và 25.3 cho chính sách đọc snapshot của Student Model ("đóng băng đầu session, cập nhật cục bộ trong session") cho R-STRONG-PRIOR và R-WEAK-PRIOR. Nhưng buổi học chưa bao giờ truyền snapshot cho gia sư của từng câu, nên cả hai luật [FACT] này chưa từng chạy trong buổi học.
  - **Thay đổi:** khi mở một câu, buổi học dựng `StudentSnapshot` từ projection của các sự kiện tính tới quyết định mở câu, gồm cả các buổi trước:
    - mức nắm vững của mỗi tiết đã có số: M/100;
    - độ tin cậy: confidence/100;
    - mức phụ thuộc gợi ý `hint_dependency`: trung bình bậc gợi ý cao nhất của 10 câu gần nhất chia 7 (`RECENT_ITEMS`, DI).
    - Khi dựng lại buổi học, snapshot ra giống hệt lúc chạy.
  - **Đo** (học sinh mô phỏng "Vương", 2 buổi mỗi chương, câu mẫu, trong bộ nhớ):
    - 1 168/1 198 quyết định nay có mức nắm vững của câu;
    - không luật nào kích hoạt và không quyết định nào đổi. Học sinh này giỏi (M từ 0,5 tới 0,9), còn độ tin cậy chỉ từ 0,1 tới 0,4: chưa đủ ngưỡng 0,6 của R-STRONG-PRIOR, và M chưa xuống dưới 0,4 của R-WEAK-PRIOR;
    - hai luật sẽ chạy với học sinh yếu, hoặc sau nhiều buổi khi độ tin cậy đủ cao. Chưa đo trên học sinh thật.
- **DI-65, hỏi "vì sao" theo việc con đã vững kiến thức chưa (VERIFY-1, `hint-policy/0.10.0`, chủ dự án duyệt 2026-10-22):**
  - **Vấn đề:** R-VERIFY hỏi "vì sao" ở 30% số câu, lấy mẫu cố định theo mã câu. Vai "đúng mà lý do chưa chắc" (con trả lời "0,9" đúng ngay, thật ra là đoán) không được hỏi, Socratic 1/5.
  - **Cơ sở:**
    - hiệu ứng tự giải thích: nói ra lý do giúp nhiều nhất khi kiến thức còn mới hoặc chưa vững;
    - hiệu ứng đảo ngược chuyên môn: bắt người đã thành thạo giải thích lại điều đã vững không giúp thêm.
  - **Luật (`policy._correct`):** sau một câu đúng, nếu chưa hỏi "vì sao" ở câu đó và không phải bài kiểm tra, gia sư hỏi "vì sao" khi:
    1. chưa có câu nào của buổi được giải đúng trên một kiến thức của câu (`ItemFacts.first_on_kc`, mã `FIRST_ON_KC`). Câu giải được cần đến lời giải mẫu (`WORKED`) không tính là đã giải đúng;
    2. mức nắm vững của tiết chứa câu dưới 0,6 (`PolicyConfig.verify_mastery`, `ItemFacts.kc_mastery` = M/100 của projection, mã `WEAK_KC`);
    3. còn lại thì giữ mẫu 30% như cũ, gồm cả trường hợp chưa có mức nắm vững.
  - **Bộ chọn nước đi:** sau câu đúng mà con đã sai trước đó, bộ chọn nước đi (AUTO-5) vẫn được thêm "vì sao".
  - **Cách tính:** buổi học tính `first_on_kc` và `kc_mastery` từ các sự kiện tính tới quyết định mở câu. Khi chạy và khi dựng lại buổi học, đó đều là quyết định cuối cùng, nên phát lại ra đúng như lúc chạy.
  - **Ngưỡng 0,6** là DI. Nó nằm giữa R-WEAK-PRIOR (0,4) và R-STRONG-PRIOR (0,75).
  - **Đo:**
    - học sinh mô phỏng, hai chương, câu mẫu, trong bộ nhớ: tỉ lệ câu đúng được hỏi "vì sao" tăng từ 70/146 lên 91/158. Trong đó 31 lần là câu đúng đầu tiên trên kiến thức, 5 lần là kiến thức còn yếu;
    - bài đo vai khó ngày 22/10: vai "đúng mà lý do chưa chắc" được hỏi "vì sao". Khi con nói "vì con đoán ạ", gia sư hỏi con kể rõ hơn (5/5 ở cả hai lượt). Trong bài đo, mỗi vai được coi là câu đầu tiên của con trên kiến thức đó, như một buổi học mở đầu bằng câu ấy.
- **DI-64, phản ví dụ nói rõ vì sao nó đến, và lần sau là phản ví dụ khác (FIX-6, `template-renderer.v7`, 2026-10-22):**
  - **Vấn đề:** ở vai "sai mà chắc" (bài đo vai khó 21/10 và 22/10), con viết 0,09 cho 9/10. Gia sư đưa phản ví dụ của lỗi quan niệm (7 cm = 7/100 m so với 0,7 m). Giám khảo chấm Socratic 2/5, vì thấy phản ví dụ "không liên quan tới đề 9/10": nó nói về số khác mà không báo vì sao. Lần đo 19/10, phản ví dụ còn bị nói lại y nguyên ở lượt sau.
  - **Thay đổi:**
    - phản ví dụ mở đầu bằng câu "Cô lấy một ví dụ để con so sánh với bài này nhé." (`PHRASES["example_lead"]`). Câu do trợ lý soạn và duyệt theo ủy quyền; chủ dự án sửa được;
    - câu dẫn bị bỏ khi lượt đã có câu đáp lời con (ADR-019), hoặc khi thêm vào thì vượt trần số từ;
    - `ItemState.counter_examples_shown` đếm số phản ví dụ đã đưa ở câu. Lần sau gia sư dùng phản ví dụ dùng được kế tiếp của lỗi đó, hết thì quay lại phản ví dụ đầu. Chương trong repo hiện có một phản ví dụ dùng được cho mỗi lỗi, nên ở đó chỉ câu dẫn có tác dụng.
- **DI-63, gia sư không nhại lời con như lời của mình (FIX-5, 2026-10-22):**
  - **Vấn đề:** trong bài đo vai khó ngày 22/10, con nói "cô ơi con chơi game được không". Qwen trả lời "cô ơi con chơi game được không, nhưng bây giờ mình quay lại bài nhé…": cô nói lại câu của con như câu của cô. Giám khảo vẫn chấm 5/5, bộ kiểm chứng cũng cho qua.
  - **Luật (`validator.echoes_child`, mã `ECHOES_CHILD`):** bộ kiểm chứng bác lượt của gia sư khi:
    - lượt mở đầu bằng nguyên câu của con, và câu đó có từ 4 từ (`ECHO_OPENING_WORDS`);
    - hoặc lượt chép từ 6 từ liền nhau của con trở lên (`ECHO_RUN_WORDS`).
  - **Không bác:**
    - từ nằm trong ngoặc kép (cô trích lời con);
    - đoạn có trong đề, gợi ý, lời giải, bài học hoặc lời cô vừa nói (con đọc lại đề, hay nhắc lại lời cô);
    - câu ngắn ("C", "0,09", "con không biết").
  - **Cách so:** so theo từ, bỏ dấu, vì con hay gõ không dấu.
  - Lượt bị bác thì đi theo đường chung của bộ kiểm chứng: Qwen viết lại, hỏng nữa thì dùng câu mẫu.
  - **Ngưỡng 4 và 6 từ** là DI, chọn theo ca thật. Trên 74 lượt của bài đo vai khó ngày 22/10 (B1, B2, C), luật chỉ bắt đúng ca này. Bộ kiểm chứng không có số version riêng; thay đổi này không đổi prompt hay chính sách.
- **DI-62, Qwen chọn nước đi trong giới hạn của chính sách (AUTO-1, ADR-031, `move-chooser/0.1.0`, 2026-10-19):**
  - **Yêu cầu của chủ dự án (2026-10-19):** làm bước "Qwen tự chủ có kiểm soát" của ADR-022.
  - **Tập nước đi được phép** (phương án `A` luôn là nước của chính sách, tối đa 3 phương án):
    - câu sai đầu tiên (R-FIRST-WRONG, PROBE): thêm gợi ý bậc 1 đúng loại lỗi;
    - gợi ý hoặc phản ví dụ sau câu sai: thêm PROBE (nếu câu này chưa hỏi "con làm thế nào"), gợi ý khái niệm thay cho phản ví dụ, hoặc gợi ý thấp hơn 1 bậc khi chính sách định lên 2 bậc;
    - hỏi con muốn gợi ý hay tự thử (OFFER_CHOICE), hoặc giải thích điều con hỏi (EXPLAIN): thêm gợi ý cùng bậc đưa ngay;
    - gợi ý sau câu nản (R-AFFECT), khi câu này chưa hỏi con chọn: thêm "con muốn gợi ý hay tự thử".
  - **Giới hạn:** không phương án nào giúp nhiều hơn nước của chính sách (cùng bậc hoặc thấp hơn, không H6/H7, không quá bậc cao nhất của câu). Không có lựa chọn ở bài kiểm tra cuối bài, ở nước đi kết thúc câu và ở các luật cố định (R-TIME, R-FRUSTRATION, R-FULL, R-PROBE-CAUSE, R-ASSESS-CAP, R-SLIP, R-STRONG-PRIOR, R-DEESCALATE, hết lượt). Con bấm "Xin gợi ý" thì được gợi ý luôn (DI-35).
  - **Hạn mức:** bộ chọn chỉ gọi Qwen trong nửa đầu trần của buổi (7 trên 15); nửa sau dành cho diễn đạt (DI-61).
  - **Ghi vết:** sự kiện `MOVE_CHOSEN`; nước Qwen chọn khác `A` mang luật `R-CHOICE`. Phát lại đọc bản ghi, không gọi model.
  - **Đo thật lần đầu (2026-10-19,** `simulate_learner.py --measure`, chương Số thập phân, 1 buổi, trong bộ nhớ, không ghi gì**):**
    - Buổi học 215 lượt, qua 11/11 tiết. Qwen được hỏi chọn nước ở 2 lượt và chọn trong tập cả 2 lần (0 lần bị từ chối):
      - giữ nước của chính sách (PROBE): "Con đang tự đặt câu hỏi về sự khác biệt giữa hai số, cô cần biết con đã suy luận thế nào để hỗ trợ đúng chỗ.";
      - đổi gợi ý thành "con muốn gợi ý hay tự thử" sau câu nản: "Con đang tỏ ra nản và từ chối làm, cần hỏi ý để con chủ động chọn cách tiếp cận thay vì ép gợi ý ngay."
    - Trong 233 lượt của gia sư, 206 là câu mẫu, 26 là câu dự phòng, 1 do Qwen viết. Lần đo này không tách được lượt gọi nào hết vì trần và lượt nào bị Groq từ chối (429), nên chưa nói được bộ chọn có làm bớt lời Qwen viết hay không.
  - **So với chính sách thuần (AUTO-2, 2026-10-19):**
    - **Cách đo:** `simulate_learner.py --measure` (trong bộ nhớ, không ghi gì), cả hai chương, tối đa 2 buổi mỗi chương, `TUTOR_RENDERER=llm`. Chạy một lần với `TUTOR_CHOOSER=llm`, ngay sau đó một lần với `TUTOR_CHOOSER=policy`. Học sinh mô phỏng `sim-auto2` chưa có buổi nào trước đó. `_measure` nay ghi thêm: số lượt gọi model của buổi (`state.activity.llm_calls`), kết quả từng lượt gọi qua router theo lớp model và lý do (`fallback_reason`), số yêu cầu Groq trả 429, lý do từng lượt của gia sư không do Qwen viết, số tiết bị dừng. `fallback_reason` không nằm trong sự kiện nào, nên script đếm nó ngay trong tiến trình.
    - **Kết quả** (cộng các buổi của mỗi chương; "câu" là câu hỏi đã kết thúc, sự kiện `ITEM_RESOLVED`):

      | | Số thập phân, `llm` | Số thập phân, `policy` | Hình học, `llm` | Hình học, `policy` |
      |---|---|---|---|---|
      | Số buổi, lượt của con | 1 buổi, 214 lượt | 2 buổi, 123 + 104 = 227 lượt | 1 buổi, 162 lượt | 1 buổi, 162 lượt |
      | Tiết qua | 11/11 | 5/11 rồi 11/11 | 8/8 | 8/8 |
      | Gợi ý (H1/H2/H3/H6) | 50 (29/12/2/7) | 43 (26/11/0/6) | 27 (18/5/0/4) | 28 (19/5/0/4) |
      | Bậc gợi ý cao nhất | H6 | H6 | H6 | H6 |
      | Câu tự giải / có gợi ý / giải mẫu / chưa giải | 38 / 21 / 4 / 3 (66 câu) | 50 / 23 / 5 / 1 (79 câu) | 42 / 12 / 3 / 1 (58 câu) | 41 / 13 / 3 / 1 (58 câu) |
      | Lượt gia sư trong câu: Qwen viết / tổng | 3 / 232 | 2 / 257 | 2 / 187 | 1 / 187 |
      | Lượt gọi model của buổi | 15 | 16 + 14 | 15 | 16 |
      | Yêu cầu Groq trả 429 | 2 | 4 + 5 | 5 | 7 |
      | Lượt Qwen không được viết vì: hết trần / hết hạn mức Groq / giữ lượt (DI-61) | 56 / 0 / 0 | 15 / 18 / 21 | 26 / 6 / 8 | 14 / 18 / 9 |
      | Số lần chọn (bị từ chối) | 2 (0) | — | 2 (0) | — |
      | Nước của chính sách → nước đã chơi | PROBE → PROBE, HINT → HINT | — | EXPLAIN → EXPLAIN, PROBE → PROBE | — |

    - **Đọc kết quả:**
      - Trong cả 4 lần chọn, Qwen đều giữ nước của chính sách (phương án `A`). Vì vậy ở lần chạy `llm`, mọi nước đã chơi đều trùng với nước chính sách thuần sẽ chơi. Bộ chọn chỉ ảnh hưởng gián tiếp: mỗi buổi nó tiêu 2 lượt gọi, nên còn ít lượt hơn cho phần diễn đạt.
      - Mỗi buổi chỉ có 2 lần chọn. Bộ chọn chỉ được gọi khi buổi còn chưa dùng 7 lượt gọi (DI-62), và mọi buổi đều dùng hết trần 15 lượt.
      - Chương hình học gần như trùng ở hai lần chạy: 162 lượt, 8/8 tiết, 58 câu, 27 và 28 gợi ý.
      - Chương Số thập phân khác nhau. Lần chạy `policy` cần 2 buổi, vì buổi 1 dừng ở 5/11 tiết: theo `node_policy.py`, buổi kết thúc khi không còn tiết nào mở được (N-FINISH, NO_NODE_LEFT), tức là có tiết bị dừng và chặn các tiết sau. Lần đo này chưa đếm số tiết bị dừng; script nay đếm thêm `nodes_stopped`. Vì nước đi đã chơi không khác chính sách, chênh lệch này (cùng với 50 so với 43 gợi ý, 66 so với 79 câu) không đến từ lựa chọn của Qwen. Nó đến từ chỗ khác: lời Qwen viết khác nhau, hạn mức Groq khác nhau, và con mô phỏng phản ứng theo lời gia sư nhận được. Lần `policy` chạy ngay sau lần `llm` nên gặp 429 nhiều hơn (16 so với 7 yêu cầu).
      - Hai lần chạy chỉ khác nhau 1–2 lượt Qwen viết (5 so với 3). Đây vẫn là phần rất nhỏ trong 400–450 lượt của gia sư, nên không đủ để nói bộ chọn có làm bớt lời Qwen viết hay không.
      - Gộp với lần đo đầu, Qwen đã chọn 6 lần, và chỉ 1 lần khác nước của chính sách (câu nản → "con muốn gợi ý hay tự thử").
    - **Kết luận:** chênh lệch giữa hai lần chạy **không đủ để kết luận** AUTO-1 làm thay đổi việc dạy hay việc học. Ở mức đo này, nó gần như không đổi gì: trong 4 lần chọn, Qwen giữ nước của chính sách cả 4. Muốn thấy khác biệt thì cần nhiều lần chọn hơn: nới phần trần dành cho bộ chọn, hoặc chạy nhiều buổi và nhiều hạt giống học sinh mô phỏng, rồi so trung bình.
    - **[OPEN]** Chưa đo trên học sinh thật, và chưa có đủ số lần chọn để so có ý nghĩa thống kê.
  - **Đo bộ chọn ngoài trần của buổi (AUTO-3, `make eval-chooser`, 2026-10-19):**
    - **Cách đo:** học sinh mô phỏng Vương học hai chương bằng câu mẫu, trong bộ nhớ (chỉ đọc kế hoạch từ database của `.env`, không ghi gì). Một bộ chọn ghi lại mọi lượt có lựa chọn mà không chọn gì. Sau đó Qwen chọn trên từng lượt đã ghi, mỗi lượt 1 lần gọi, ngoài trần 15 của buổi. Báo cáo đầy đủ ở máy chạy đo: `evals/reports/2026-10-19-chooser.md` (thư mục này không vào git; số liệu nằm ở bảng dưới).
    - **Kết quả:** 3 buổi, 48 lượt có lựa chọn (46 khác nhau). Qwen trả lời đủ 46/46: giữ nước của chính sách 27, chọn nước khác 19.

      | Thực đơn (nước của chính sách → nước được phép) | Lượt | Qwen giữ | Qwen chọn khác |
      |---|---|---|---|
      | PROBE → HINT | 19 | 19 | 0 |
      | HINT → PROBE | 8 | 0 | 8 |
      | EXPLAIN → HINT | 6 | 6 | 0 |
      | HINT → OFFER_CHOICE | 5 | 0 | 5 |
      | HINT → PROBE / HINT thấp hơn | 4 | 0 | 4 (đều PROBE) |
      | COGNITIVE_CONFLICT → PROBE / HINT | 2 | 0 | 2 (đều PROBE) |
      | OFFER_CHOICE → HINT | 2 | 2 | 0 |

    - **Đọc kết quả:** ở cả 46/46 lượt, Qwen chọn nước **không phải gợi ý** (hỏi "con làm thế nào", hỏi con muốn gợi ý hay tự thử, hoặc giải thích), dù nước đó là `A` hay `B`. Nên đây không phải thiên vị vị trí. Qwen chưa bao giờ chọn đưa gợi ý khi còn nước khác. Lý do Qwen nêu nghe hợp lý, nhưng lặp theo khuôn ("con đã đưa ra đáp án cụ thể, cô cần hỏi lại cách làm…"). Ở mức đo này, bộ chọn chạy như một luật cố định "hỏi trước khi gợi ý", chưa thấy nó chọn theo ngữ cảnh của từng đứa trẻ. Một phần có thể do prompt (`CHOOSE_SYSTEM` có câu "ưu tiên nước giúp ít hơn khi con có vẻ gần đúng hoặc đang tự nghĩ").
    - **Giới hạn:** chỉ một học sinh mô phỏng, 46 lượt, một lần hỏi mỗi lượt (chưa đo độ ổn định khi hỏi lại).
    - **Đã sửa:** 2/46 lý do có chữ Trung Quốc lẫn vào ("trước khi介入"). Lý do nay bị cắt ở chỗ đó (`chooser.clean_reason`); nước đi được chọn không đổi.
    - **Chủ dự án chọn (2026-10-19):** sửa prompt cho Qwen cân nhắc khi nào nên đưa gợi ý (ví dụ con đã sai nhiều lần cùng một chỗ), rồi đo lại. Đó là AUTO-4 bên dưới.
  - **Prompt mới (AUTO-4, `move-chooser/0.2.0`, 2026-10-19):**
    - **Qwen thấy thêm tình hình của con ở câu đang làm** (`tinh_hinh`, `chooser.situation`): số lần trả lời, số gợi ý đã nhận, bậc gợi ý cao nhất, số lượt chưa tiến bộ, số lần xin gợi ý, dấu hiệu nản, cô đã hỏi cách làm chưa, lỗi lặp lại nhiều nhất. Chỉ có số đếm, không có đáp án.
    - **Mỗi nước đi kèm mức giúp** (`muc_giup`): 0 là hỏi lại, còn lại là bậc gợi ý.
    - **Tiêu chí trong prompt:**
      - giúp ít (hỏi cách làm, hỏi con muốn tự thử) khi: đây là lần trả lời đầu tiên của câu, con có vẻ gần đúng, hoặc con đang nói cách nghĩ của mình;
      - đưa gợi ý khi: con đã sai từ 2 lần ở câu này, con lặp lại cùng một lỗi, cô đã hỏi cách làm rồi mà con vẫn sai, con nói không biết hoặc xin giúp, hoặc con nản sau nhiều lần thử;
      - "không có nước nào luôn đúng". Bỏ câu cũ "ưu tiên nước giúp ít hơn".
    - **Đo lại** (`make eval-chooser`, cùng cách đo, 3 buổi, 48 lượt có lựa chọn, 46 khác nhau): Qwen trả lời 46/46, giữ nước của chính sách 30, chọn nước khác 16.

      | Lúc chọn | Lượt | `0.1` chọn gợi ý | `0.2` chọn gợi ý |
      |---|---|---|---|
      | Lần trả lời đầu của câu, chưa có gợi ý | 36 | 0 | 0 |
      | Lần trả lời đầu, đã có gợi ý (sau khi con hỏi lại đề hoặc xin giúp) | 6 | 0 | 0 |
      | Con đã sai từ 2 lần ở câu này | 4 | 0 | 3 |

    - **Đọc kết quả:**
      - 45/46 lượt khớp tiêu chí đã viết. Lượt còn lại (sai lần 2, 2 gợi ý, 2 lượt chưa tiến bộ) Qwen vẫn hỏi lại, trái tiêu chí.
      - Lý do nay nêu dấu hiệu trong tình hình, ví dụ "con đã trả lời sai 2 lần và có dấu hiệu bế tắc", "lặp lại cùng một lỗi".
      - Bản `0.1` không bao giờ chọn gợi ý khi còn nước khác. Bản `0.2` chọn gợi ý khi con đã sai nhiều lần. Nhưng ở mẫu này, cách chọn của `0.2` vẫn gần như một luật theo số lần trả lời ("hỏi ở lần đầu, gợi ý từ lần sai thứ hai"). Chưa thấy Qwen dùng lời của con để chọn khác luật đó.
    - **Giới hạn:** chỉ 4 lượt con sai từ 2 lần, một học sinh mô phỏng, một lần hỏi mỗi lượt. Chưa đo lại trong buổi học (AUTO-2) và chưa đo trên học sinh thật.
  - **"Vì sao" sau câu đúng (AUTO-5, `hint-policy/0.9.0`, `move-chooser/0.3.0`, 2026-10-22):**
    - **Vấn đề:** bài đo vai khó ngày 21/10 có vai "đúng mà lý do chưa chắc". Con trả lời đúng, gia sư sang câu sau mà không hỏi vì sao (Socratic 1/5). Lý do: R-VERIFY chỉ hỏi "vì sao" ở 30% số câu, lấy mẫu tất định theo mã câu (DI ở `policy._sampled`). Câu không được lấy mẫu thì không bao giờ được hỏi, dù con đúng sau nhiều lần sai.
    - **Thay đổi:** con trả lời đúng, câu không được lấy mẫu, chưa hỏi "vì sao", chưa xem lời giải mẫu, không phải bài kiểm tra. Khi đó thực đơn có thêm `B`: hỏi "vì sao" rồi mới sang câu.
      - Hỏi "vì sao" không giúp thêm gì (mức giúp 0).
      - Câu đóng sau lời giải thích của con với cùng mức hoàn thành.
      - Mastery không đổi theo lựa chọn này (quy tắc 3).
      - Tỉ lệ 30% và phép lấy mẫu giữ nguyên. Đây vẫn là DI chờ chủ dự án duyệt.
    - **Tiêu chí trong prompt:**
      - hỏi vì sao khi: con đã sai hoặc đã nhận gợi ý ở câu này, hoặc con chọn một phương án trắc nghiệm mà chưa nói cách nghĩ;
      - sang câu ngay khi: con đúng từ lần đầu, không cần gợi ý, "để con giữ nhịp".
    - **Đo** (`make eval-chooser`, `evals/reports/2026-10-22-chooser.md`, 3 buổi mô phỏng, 34 lượt con vừa trả lời đúng, Qwen trả lời cả 34):

      | Con vừa trả lời đúng | Lượt | Hỏi vì sao | Sang câu sau |
      |---|---|---|---|
      | Đúng ngay lần đầu, chưa có gợi ý | 25 | 3 | 22 |
      | Đúng sau khi đã sai hoặc đã có gợi ý | 9 | 6 | 3 |

    - **Đọc kết quả:**
      - Qwen hỏi vì sao ở 6/9 lượt con đúng sau khi đã sai hoặc nhận gợi ý, và 3/25 lượt con đúng ngay. Lựa chọn đi theo tiêu chí đã viết, nhưng chưa khớp hết: 3 lượt "đúng sau khi sai" vẫn sang câu.
      - Ở 3 lượt "đúng ngay" được hỏi vì sao, lý do Qwen dựa vào lời con, ví dụ "lặp từ 'nghĩ mãi' và không nêu cách xác định hàng".
    - **Giới hạn:**
      - vai "đúng mà lý do chưa chắc" (con trả lời "0,9" đúng ngay lần đầu) không có dấu hiệu nào để biết con đoán, nên theo tiêu chí, Qwen sang câu;
      - một học sinh mô phỏng, một lần hỏi mỗi lượt.
- **DI-61, dành lượt gọi Qwen cho nước đi quan trọng (LLM-2, `llm-renderer.v5`, 2026-10-16):**
  - **Vấn đề:** trần 15 lần gọi mỗi buổi hết rất sớm. Trong một buổi hình học, PROBE ("con làm thế nào") tiêu 4 trên khoảng 13 lần gọi, rồi 19 gợi ý, 8 lần kéo về bài và 3 lời giải thích chỉ còn dùng được câu mẫu.
  - **Quyết định của chủ dự án (2026-10-16):** giữ trần 15, nhưng dành lượt gọi cho giải thích, gợi ý sau câu sai và kéo về bài.
  - **Luật mới:**
    - EXPLAIN và REDIRECT được dùng hết trần.
    - HINT và COGNITIVE_CONFLICT chừa lại 1/5 cuối của trần (3 lần) cho hai nước đi trên.
    - PROBE và NUDGE chỉ gọi mô hình trong 1/3 đầu (5 lần); sau đó nói bằng câu mẫu đã duyệt.
    - Lượt bị giữ lại ghi lý do `call_budget`.
- **DI-60, Qwen viết được lời trong buổi học (LLM-1, `llm-renderer.v4`, 2026-10-16):**
  - **Vấn đề:** bài báo đọc 16 sự kiện `OUTPUT_REJECTED` của S1 là "16 bản nháp của Qwen bị chặn". Chạy lại có ghi từng bản nháp (2026-10-16) cho thấy khác:
    - Sự kiện đó là lần kiểm cuối của vòng một câu hỏi. Lần kiểm này chạy trên **mọi** lời sắp gửi (cả câu mẫu đã duyệt) với trần cứng 60 từ. Ở chương hình học, lời giải thích đã duyệt dài tới 158 từ (nhắc lại đề) bị chặn hai lần, và trẻ nhận một câu chung chung (nguồn `FALLBACK`) thay vì lời giải thích. Lần kiểm này cũng chặn cả lời của Qwen mà renderer đã nhận.
    - `FALLBACK` không có nghĩa "mô hình thử rồi dùng câu mẫu": đó là câu chung chung khi không có gợi ý đã duyệt hợp bậc, hoặc khi lần kiểm cuối chặn hai lần. Khi Qwen hỏng, renderer dùng câu mẫu, và nguồn ghi là `TEMPLATE`.
    - Thứ giới hạn Qwen nhiều nhất là trần 15 lần gọi mỗi buổi và hạn mức Groq. Ở một buổi hình học: 28 lần hết trần, 9 lần bị 429, 3 lần Qwen viết được, 2 lần hỏng vì kiểm.
  - **Luật mới:**
    - Trần từ của lời mô hình là `max(trần của lượt, số từ của câu mẫu + 15)`. Lần kiểm cuối dùng đúng trần đó cho lời của mô hình, và không chặn câu mẫu đã duyệt vì độ dài.
    - Hai lỗi hình thức được sửa tại chỗ: thiếu câu hỏi thì nối câu hỏi cuối của chính câu mẫu (văn bản đã duyệt), gọi "em" thì đổi thành cách gọi của bài. Chỉ sửa khi đó là lỗi duy nhất, bản nháp kết thúc trọn câu (không bị cắt), và lời đã sửa phải qua lại toàn bộ phép kiểm. Không sửa lỗi nào khác.
- **DI-59, thành thạo tạm thời từ M ≥ 85 (FIX-1, `node-mastery/0.3.0`, 2026-10-16):**
  - **Vấn đề:** khung §53 cho "thành thạo tạm thời" khi M ≥ 85, tin cậy ≥ 75, chiều A ≥ 0,8 và không còn lỗi nghiêm trọng. Mã cũ chỉ xét các điều kiện này khi M đã qua dải 90 của §4–§8, nên ngưỡng 85 không bao giờ có tác dụng. Khi rà bài báo, Bảng 38 có hai trạng thái đạt §53 (M 88,9 và 88,7) mà vẫn ở mức 4.
  - **Luật mới:** chủ dự án chọn theo khung (2026-10-16): mức 5 do điều kiện §53 quyết định từ M ≥ 85. Dải 90 chỉ còn là vùng màu trên trang giáo viên, không còn là cổng.
  - **Test:** `test_provisional_mastery_starts_at_85_as_in_the_framework_not_at_the_90_band`.
- **DI-58, chấm câu trả lời viết hoặc nói bằng chữ (GRADE-1, 2026-10-13):**
  - **Đọc số nói (`vi_words.spoken_to_digits`):**
    - đổi "0 phẩy 9" và "không phẩy chín" thành 0,9;
    - một số bằng chữ không có "phẩy" ("mười hai", "sáu ạ") chỉ được đọc khi đó là tất cả những gì bé nói, nên "con không biết" không bao giờ thành 0.
  - **Dạng đề hỏi:** câu số không khai báo `form` mà đề viết "(dưới dạng / thành) số thập phân" thì không nhận phân số (từng thấy: "9/10" được chấm đúng).
  - **Đo:** bộ chấm `grading-vi-v2` (giữ riêng, commit trước khi sửa) tăng từ 26/35 lên 35/35. Bộ v1, đã xem trước khi sửa: 36/36.
- **DI-57, định tuyến câu hỏi về bài trước (RAG-4, 2026-10-13):**
  - **Vấn đề:** đánh giá cho luận văn cho thấy câu hỏi về khái niệm của bài trước, không có dạng "là gì" ("1 m bằng bao nhiêu cm" khi đang học diện tích), không với tới tiết đã dạy nó. Lý do: mỗi bước trên đồ thị nhân điểm với 1/(1 + khoảng cách). Tệ hơn, gia sư vẫn trả lời bằng đoạn của tiết đang học, vì đoạn đó cùng chương nên vẫn "có căn cứ".
  - **Luật mới:** trước khi xếp hạng, mỗi tiết trong phạm vi (tiết đang học và mọi tiết trước) được chấm bằng đoạn khớp nhất của nó (cosine; độ phủ từ khóa khi không có vector). Một tiết trước khớp hơn tiết đang học từ 0,02 cosine (0,15 độ phủ) trở lên thì được coi là chủ đề câu hỏi: đoạn của nó không bị trừ điểm khoảng cách.
  - Không bao giờ định tuyến sang tiết sau. Thuộc bước "cấu trúc" của thí nghiệm bỏ từng phần (`rerank`).
  - **Đo theo đúng quy trình:**
    - Bộ giữ riêng v2 (`rag-published-holdout-v2.yaml`) được viết và commit **trước** khi sửa, đo đúng một lần sau khi sửa: Hit@3 0,45 → 0,90 (nhóm bài trước 0,08 → 0,83), MRR 0,503 → 0,887.
    - Bộ chỉnh và v1: Hit@3 1,00.
    - Chương mẫu không tụt.
    - Hai giá trị biên độ là giá trị đặt lần đầu, chưa chỉnh lần nào.
- **DI-56, làm lại câu bù dạng (`node-policy/0.3.1`, 2026-10-13):** chạy Vương với lỗi sai điển hình thì lộ ra hai chỗ chặn qua tiết.
  - **Chỗ 1:** khi gia sư đang theo dõi một lỗi sai, các câu bắt lại lỗi đó được đưa lên trước, và luật DI-49 (đưa câu bù dạng lên trước) bị tắt. Các câu bắt lỗi đều là câu điền số, nên tiết hết 12 câu mà vẫn thiếu dạng. Sửa: DI-49 vẫn chạy khi đang theo dõi lỗi sai.
  - **Chỗ 2:** tiết DTTGHT-T02 chỉ có một câu trả lời tự do (BT-02) giữa các câu điền số. Bé sai câu đó lúc mới vào bài thì tiết không bao giờ đủ hai dạng câu.
  - **Luật mới:** khi không còn câu mới nào bù được dạng câu hoặc mức nhận thức còn thiếu, câu bù dạng mà bé từng làm chưa được sẽ được hỏi lại **một lần** (`reason_codes` có `RETRY_FORM`). Lúc đó bé đã học thêm, nên làm lại có ý nghĩa.
- **DI-55, chấm bước "vì sao" (WHY-1, `reason-rubric/0.1.0`, `hint-policy/0.7.0`, `template-renderer.v5`, `node-mastery/0.2.0`, 2026-10-13):** trước đây mọi câu trả lời "vì sao" không phải "không biết" đều được nhận.
  - **Ba dấu hiệu:** câu trả lời nói về câu đang làm khi có
    - **SỐ**: một số của câu (trong đề, đáp án, lời giải);
    - **THUẬT NGỮ**: thuật ngữ Toán lớp 5 hoặc tên KC của bài. Cụm nhiều chữ được so cả khi bỏ dấu; từ một chữ phải đúng dấu ("nhân" khác "nhận");
    - **LỜI GIẢI**: trùng ít nhất 2 từ nội dung với lời giải của câu.
  - **Điểm:** không có dấu hiệu nào là câu chung chung, 0,2; một dấu hiệu 0,6; từ hai dấu hiệu 1,0. Ghi vào `EXPLANATION_SUBMITTED` với `label_source: RUBRIC_RULE`.
  - **Gia sư:** gặp câu chung chung thì hỏi lại một lần, với lời dẫn "Cô muốn nghe rõ hơn bước con đã làm và những số con đã dùng." Lần thứ hai vẫn chung chung thì cho qua câu.
  - **Mastery:**
    - câu chung chung không được tính là bằng chứng, cũng không bị trừ, vì bé có thể hiểu mà chưa nói ra được;
    - câu có dấu hiệu là bằng chứng R với trọng số 0,5 (luật từ khóa, không phải người chấm). Trước đây câu chưa chấm có trọng số 0,3 với điểm 1,0.
  - **`make trial`:**
    - Bản đầu trừ điểm câu chung chung. Học sinh mẫu nói "Vì con làm theo quy tắc cô dạy" (câu của chương phát hành ít có lời giải mẫu) thì không qua nổi tiết đầu, nên em bỏ phần trừ điểm.
    - Bản hiện tại: mọi học sinh mẫu qua hết hai chương, số lượt tăng khoảng 15–20% vì gia sư hỏi lại.
- **DI-54, nhận ra lỗi sai của chương phát hành (MISC-1, `misconception-rules/0.1.0`, 2026-10-13):** phương án dựng từ tài liệu đã nêu các lỗi sai điển hình của từng tiết, nhưng chưa có đáp án sai nào trỏ tới chúng, nên gia sư không nhận ra lỗi nào.
  - **Họ lỗi:** mỗi lỗi sai được xếp vào một họ, đọc từ từ khóa và ví dụ trong lời của giáo viên (`families`). Có 14 họ:
    - số thập phân: mất số 0 giữ chỗ, quên dấu phẩy, đổi đơn vị sai bước, đổi đơn vị diện tích như độ dài, làm tròn dây chuyền, làm tròn quên nhớ, nhìn sai chữ số khi làm tròn;
    - so sánh: dài hơn thì lớn hơn, so sánh sai phần nguyên;
    - hình học: quên chia 2, quên nhân 2, nhân hai đáy, thiếu ngoặc, cạnh nghiêng làm đường cao.
  - **Đáp án sai:** tính từ đáp án đúng và các số trong đề của chính câu đó. Ví dụ: a × h khi đáp án là a × h : 2; 3,5 khi đáp án là 3,05.
    - Bỏ đáp án sai trùng đáp án đúng, và đáp án sai mà hai họ cùng tạo ra (không phân biệt được).
    - Luật hình tam giác hoặc hình thang chỉ áp khi đề hoặc tên tiết nói tới hình đó.
    - Nhân, chia 10 khi đổi đơn vị chỉ áp cho đề có một số đo.
  - **Mã lỗi:** chọn lỗi cùng họ của chính tiết đó, nếu không có thì của tiết trước gần nhất; trong mỗi nhóm, lỗi CRITICAL được chọn trước. Không gán lỗi của tiết sau.
  - **Câu so sánh:** được gắn luật lỗi có sẵn (`longer_is_larger`, `ignore_integer_part`).
  - **Phạm vi:** chỉ bổ sung cho câu chưa có đáp án sai do giáo viên viết, và làm lúc nạp chương, không ghi gì vào database.
  - **Độ phủ:** báo cáo `make misconception-coverage`.
  - **Giới hạn:** chưa nhận ra được các lỗi về đơn vị ghi ở đáp số, lỗi vẽ hình, và lỗi cạnh nghiêng (vì đề hiếm khi cho sẵn độ dài cạnh nghiêng).
- **DI-53, nhắc bài gốc khi làm bài sai (TEACH-2, `teaching-templates/0.5.0`, 2026-10-13):** phần [OPEN] của DI-52.
  - **Khi nào:** lần đầu bé trả lời sai (WRONG) một câu của tiết đang học.
  - **Nhắc tiết nào:** tiết gốc của lỗi sai nếu lỗi đó thuộc một tiết trước; không thì tiết tiên quyết gần nhất. Tiết không có tiết tiên quyết thì không nhắc.
  - **Gia sư nói gì:** sau lời nhận xét của câu, nói thêm "Gợi ý từ bài cũ: ở bài X, mình đã học: …" (ý chính của tiết X).
  - **Giới hạn:** mỗi câu chỉ nhắc một lần; không nhắc ở câu ôn nền hay câu ôn xen kẽ.
  - **Không đổi:** bậc gợi ý và nước đi vẫn do Hint Engine quyết định; không đổi điểm. Lời nhắc được ghi là `TEACH_MESSAGE_SENT` (`ref: RECALL_HINT`).
- **DI-52, hỏi lại bài đã học (N-RECALL, `node-policy/0.3.0`, `teaching-templates/0.4.0`, 2026-10-13):** chủ dự án định hướng: gia sư hỏi lại kiến thức của bài có liên quan tới bài đang học.
  - **Khi nào:**
    - vào một tiết mà không có câu ôn nền (N-WARMUP chỉ chạy khi tiết tiên quyết chưa có bằng chứng trong buổi);
    - hoặc khi kiểm tra hiểu sai lần đầu, trước khi giảng lại.
  - **Hỏi tiết nào:** một tiết đã qua hoặc đã gặp trong buổi. Ưu tiên tiết tiên quyết gần nhất (tiết mà tiết đang học dựa trực tiếp vào), sau đó tới tiết tương tự (SIMILAR, SUBCLASS).
    - Mỗi cặp (tiết đang học, tiết được hỏi lại) chỉ hỏi một lần trong buổi.
    - Không hỏi lại tiết vừa được dạy lại (N-REMEDIATE).
  - **Câu hỏi:** câu "nói lại" của tiết cũ, bỏ phần "Con nói lại giúp cô:".
    - Câu chỉ ghép tên tiết với "thế nào?" (thường gặp ở chương phát hành từ tài liệu) chỉ rõ nghĩa ngay sau khi vừa giảng. Với các câu đó, gia sư hỏi chung: "bài X cho con biết những điều gì?".
  - **Chấm:** theo các ý chính của tiết cũ, như phần nói lại (`RETELL_JUDGED`, `purpose: RECALL`).
    - Đây là bằng chứng R của tiết cũ: nhớ được thì điểm tăng, không nhớ thì điểm giảm.
    - Tiết đã qua không bị lấy lại dấu qua. Điểm thấp làm tiết đó dễ được ôn xen kẽ và dễ được quay về dạy lại (N-REMEDIATE) khi kiểm tra hiểu sai hai lần.
    - Không đổi công thức mastery (`node-mastery/0.1.0`).
  - **Lời đáp:**
    - nhớ đủ: khen rồi nối sang tiết mới ("Mình dùng điều đó cho bài …");
    - nhớ một phần hoặc không nhớ: gia sư nhắc lại ý chính của tiết cũ, rồi nối sang tiết mới.
  - **Tắt được:** `NodePolicyConfig.recall_prior`.
  - **[OPEN]** Chưa có câu hỏi lại bài liên quan trong lúc làm bài tập (bậc gợi ý của item). Bậc gợi ý vẫn theo Hint Engine hiện tại.
- **DI-51, tra nguồn chính thống khi tài liệu không trả lời (WEB-1, ADR-029, 2026-10-13):**
  - **Nguồn:** chỉ Wikipedia tiếng Việt, qua API chính thức.
  - **Phạm vi câu hỏi:** chỉ câu "X là gì / nghĩa là gì / là con gì", mở bài có tiêu đề X (hoặc chuyển hướng chính thức). Không tra câu về người, câu thuộc bài sau, câu không an toàn (`UNSAFE`), câu có thông tin liên lạc.
  - **Kiểm chứng:** lời trả lời qua cùng bộ kiểm như với tài liệu. Không qua thì trích nguyên văn hoặc gác cho cô.
  - **Ghi lại:** mỗi lần tra được ghi thành `WEB_LOOKED`.
- **DI-50, phạm vi RAG trên chương đã phát hành (RAG-3, 2026-10-13; đánh giá `make eval-rag-published LIVE=1`):**
  - Câu hỏi định nghĩa ("X là gì", "là hàng nào", "là cạnh nào", "gồm mấy phần"…) tìm ở mọi bài tiên quyết, không giới hạn 2 bước. Bài sau vẫn ngoài phạm vi.
  - Đoạn có câu định nghĩa đúng thuật ngữ được hỏi ("X … là", "gọi là X") được nhân ×1,6 và không bị giảm điểm theo khoảng cách. Câu hỏi ("X là những cạnh nào") và giá trị ("phần nguyên là 0", "đều là 5") không phải định nghĩa.
  - Đoạn tài liệu gần ngang điểm với từ 3 bài trở lên (≥ 50% điểm cao nhất) không gắn vào bài nào. Đoạn chưa gắn bài chỉ được làm căn cứ khi mọi bài nó có thể thuộc về đều đã nằm trong phạm vi. Nhờ đó trang tổng quan của chương không làm lộ kiến thức bài sau.
  - Gia sư chỉ báo "bài sau mình học" khi đoạn của bài sau gần câu hỏi hơn đoạn tốt nhất trong phạm vi ít nhất 0,03 cosine.
  - Đoạn dài hơn cả ngân sách ký tự bị bỏ qua, trừ khi chỉ còn nó.
  - Kết quả và giới hạn: `evals/reports/2026-10-13-rag-published-gemini.md`.
    - Tập chỉnh, Hit@3 nhóm hỏi bài trước: 0,20 → 0,70.
    - Tập giữ riêng: 0,29 → 0,29, chưa cải thiện. Các câu hỏi khái niệm không theo dạng "là gì" về bài ở xa vẫn ngoài phạm vi.
    - Chương YAML cũ không tụt (Hit@3: 1,00 / 0,87).
- **DI-49, chọn câu bù dạng còn thiếu (`node-policy/0.2.0`, 2026-10-12):** khi tiết còn thiếu dạng câu hoặc mức nhận thức để "hiểu" (DI-6), danh sách câu luyện dài hơn ngân sách còn lại, và câu đầu tiên bù được chỗ thiếu nằm từ vị trí (ngân sách còn lại − 2) trở đi, thì câu đó được đưa lên trước. Các trường hợp khác giữ thứ tự cũ. Phiên học thử phát hiện STP-T06: học sinh làm đúng 11/12 câu vẫn bị dừng tiết vì 12 câu đầu cùng một dạng.
- **DI-48, chấm tất định câu đáp án mở (`KeyFacts`, 2026-10-12):**
  - Câu đáp án mở mang các ý bắt buộc, rút từ đáp án của giáo viên hoặc do giáo viên ghi (`item:<id>/facts`). `MathChecker` đúng khi mọi ý đều có:
    - số (mỗi nhóm một trong các cách viết tương đương, viết bằng số hoặc bằng chữ);
    - cụm từ;
    - dấu so sánh theo đúng thứ tự;
    - tên theo đúng thứ tự;
    - cặp (từ, tên) trong cùng một vế câu;
    - đọc số bằng chữ (không được viết lại chữ số);
    - `only_numbers`: không có giá trị thừa.
  - Thiếu ý thì chấm sai. Không đọc được ý nào thì hỏi lại.
  - Câu không rút được ý chắc chắn và giáo viên chưa ghi thì không có `facts`, và không được dạy (lần duyệt 2026-10-12 loại STP-BT-14, STP-BT-28).
- **DI-47, duyệt thay chủ dự án và đọc đáp án (2026-10-12, Claude duyệt theo ủy quyền; nhật ký: `evals/reports/2026-10-12-review-log.md`):**
  - Một tiết mà mọi câu trong tài liệu chỉ có một dạng (viết số đo, làm tròn, viết số thập phân) được hạ `min_forms` xuống 1 (STP-T01, T07, T08, T09). Không tự đặt câu ngoài tài liệu để đủ hai dạng.
  - `NumericAnswer.form`: "0,475 = ……" trong phần viết phân số thập phân đòi đúng phân số có mẫu của đáp án (475/1000); "49/100 = ……" đòi số thập phân. Cùng giá trị nhưng sai dạng thì chấm sai.
  - Câu hỏi nhiều ý (nhiều câu hỏi, "các", "nào… và…"), dòng có nhiều cặp so sánh, và câu có số đo nhiều đơn vị mà đề không nói đơn vị kết quả thì chấm theo rubric (đáp án mở), không ép thành một số.
  - Câu dựa vào hình mà đề không mô tả đủ để bé làm trong khung chat thì loại (STP-BT-06, STP-BT-30).
- **DI-46, phần do Qwen soạn (INGEST-3b, ADR-026, chờ duyệt):**
  - Gợi ý: H1 TASK, H2 CONCEPT, H3 STRATEGY; tối đa 40 từ; kết thúc bằng một câu hỏi.
  - Gợi ý qua `validate_message`. Thuật ngữ Toán phải có trong đề hoặc quy tắc của tiết.
  - Câu trả lời mẫu tối đa 35 từ, cách nói được chấp nhận tối đa 6 từ. Số và thuật ngữ phải có trong chữ của tiết.
  - Ý chính tối đa 8 từ, ít nhất 80% số từ có nghĩa có trong chữ của tiết.
  - Mỗi lần gọi gồm 6 câu, các lần gọi cách nhau 8 giây.
- **DI-45, dựng phương án dạy nháp từ tài liệu (INGEST-3a, ADR-025, chờ duyệt):**
  - Mỗi tiết có bài trong giáo án là một node. Tiết ôn tập là bài kiểm tra cuối chương.
  - Node vận dụng (IMPLEMENT) là tiết có tên chứa "luyện tập, ứng dụng, thực tế, vận dụng, hình ghép, công thức ngược".
  - Ghép mục lý thuyết vào tiết cùng bài SGK theo từ chung có trọng số. Trọng số là log(số tiết / số tiết có từ đó), tên tính gấp ba. Từng khung VÍ DỤ được ghép riêng.
  - Tiết không có câu "Kiểm tra hiểu" thì câu đầu của phiếu tiết đó là câu kiểm tra (mức A).
  - Mức nhận thức và độ khó theo mục của tài liệu:

    | Mục | Mức | Độ khó |
    |---|---|---|
    | Kiểm tra hiểu | A | 0,2 |
    | Cùng làm | B | 0,35 |
    | Luyện tập | B | 0,5 |
    | Phiếu | B | 0,45 |
    | Vận dụng | D | 0,7, có chuyển giao gần |

- **DI-44, kiểm đáp án của ngân hàng câu nháp (INGEST-2, ADR-024, chờ duyệt):**
  - Làm tròn "nửa lên" (chữ số bên phải từ 5 trở lên thì tăng 1), làm một lần, theo hàng đề nêu. Số đo được làm tròn theo đơn vị nó được viết.
  - Một số trong đáp án "có căn cứ" khi:
    - có trong đề hoặc trong cả câu (mọi câu nhỏ), so theo giá trị và mọi đơn vị cùng loại;
    - hoặc là kết quả một bước kiểm tự tính;
    - hoặc là một vế của phép "=" đúng.
    Phép so sánh không tạo ra số mới.
  - Số có 1 chữ số không xét "có căn cứ", vì lời giải hay dùng chữ số đơn lẻ.
  - Câu trắc nghiệm: giá trị điền vào chỗ trống là giá trị của phương án được chọn.
  - Thứ tự ưu tiên trạng thái: số đọc chưa chắc (DISPUTED) > mâu thuẫn (CONFLICT) > cần xem lời giải (REVIEW, khi chỉ phần "có căn cứ" không đạt) > đã kiểm (VERIFIED) > chưa kiểm được (UNCHECKED).
  - Đo độ nhạy: đổi từng chữ số của dòng đáp án (+1 và +5). Trên tài liệu thật bắt được 97,1% và 98,4%.
- **DI-43, đọc tài liệu từng trang có kiểm chứng (INGEST-1, ADR-023, chờ duyệt):**
  - Một trang PDF được Gemini đọc lại khi lớp chữ của nó không giữ được hết nội dung. Có 4 dấu hiệu:
    - dưới 40 ký tự (bản scan);
    - có ảnh nhúng (phân số dạng ảnh);
    - có từ 3 chữ in hoa đứng riêng liền nhau ("H A B C", nhãn điểm của hình vẽ), hoặc từ 2 dòng liền nhau chỉ có số đo ("5 m", "3 m");
    - có các dòng chỉ có số rồi một dòng chỉ có một chữ in hoa (trục số "3", "4", "3,5", "M").
  - Bản Gemini đọc chỉ được thay lớp chữ khi **mọi số có từ 2 ký tự trở lên của lớp chữ đều có trong bản đọc**, viết giống hệt hoặc cùng giá trị. Chữ số đứng riêng không tính, vì lớp chữ cắt bảng thành từng chữ số.
  - Thiếu số, Gemini lỗi hoặc không có khóa Gemini: giữ lớp chữ, trang được đánh dấu "cần xem lại" cho giáo viên.
  - Số chỉ có trong bản Gemini (phân số trong ảnh) phải được một model khác đọc lại ra đúng như vậy. Lệch thì trang được đánh dấu "cần xem lại", kèm các số lệch. Trên tài liệu thật, bước này đã bắt được câu 2 của đáp án bài tập: ảnh gốc là 9/10, một model đọc thành 7/10.
  - Đáp án và đề kiểm tra không bao giờ vào RAG (quy tắc 2 của CLAUDE.md).
  - Trên 18 file của chủ dự án: 31/77 trang được đọc lại (12 trang có ảnh, 19 trang có hình). 8 trang có phân số trong ảnh: 6 trang hai lần đọc khớp nhau, 2 trang chờ giáo viên xem.
- **DI-42, gia sư theo ngữ cảnh (CTX-1, ADR-022, chờ duyệt):**
  - Con hỏi về gợi ý hay nghĩa một từ: nước đi EXPLAIN, tính là bậc gợi ý tiếp theo; tối đa 2 lần mỗi câu, quá thì gợi ý tiếp; bài kiểm tra cuối bài chỉ nhắc lại đề.
  - Lời Qwen trong bài tập phải giữ ít nhất 60% thuật ngữ Toán của câu mẫu (đủ cả khi câu mẫu có 1–2 thuật ngữ); câu mẫu không có thuật ngữ thì giữ ít nhất 30% số từ.
  - "ko" trả lời câu lý thuyết không phải dạng có/không là "con không biết".
- **DI-41, câu đáng lo (RAG-2, chờ duyệt):**
  - Danh sách cụm từ ở `student_intent.signals_distress`: bị đánh, bị bắt nạt, bị chửi, bị dọa, bị nhốt, muốn chết, tự làm đau, sợ về nhà…, gồm cả dạng "bị bạn đánh".
  - Khi gặp các cụm này, gia sư không trả lời câu hỏi và không kéo về bài. Gia sư nói câu ân cần (câu mẫu `distress`, chờ duyệt) và ghi `SAFETY_FLAGGED` (`source: RULE`) cho giáo viên.
  - Áp cho cả lúc làm bài tập (SAFE-1): câu đáng lo không bị tính là một lần trả lời, câu hỏi bài tập vẫn để nguyên.
  - Giáo viên thấy cờ ở hai nơi:
    - trang Lớp học: lý do "Con nói điều đáng lo… cô xem ngay hội thoại" luôn đứng đầu, bấm vào mở buổi học;
    - tab Hội thoại: chip đỏ trên câu của con.
  - Cờ của Qwen (luật 8 của constitution) cũng hiện như vậy.
  - **[OPEN]** Chưa có bước "giáo viên đã xem", nên cờ còn hiện mãi.
- **DI-17, tham số Hybrid RAG** (chờ duyệt; code ở `services/api/cavat/modules/rag/`, đo bằng `make eval-rag`):
  - **Chia đoạn:** nội dung chương mỗi đơn vị dạy một đoạn. Tài liệu giáo viên 150–300 âm tiết một đoạn, cắt ở cuối dòng, dòng dài thì cắt ở cuối câu, chồng lấn một câu.
  - **Từ khóa:** BM25 k1 = 1,2, b = 0,75. Bỏ các từ đệm như "cô, ơi, ạ, là, gì, sao, thế, nào, nghĩa…", cả khi đứng một mình lẫn khi ghép cặp.
  - **Hợp nhất:** RRF k = 60, nhân 1/(1 + khoảng cách trên đồ thị). Có chọn bài thì phạm vi gồm bài đó, các bài nó dựa vào (tiên quyết, bài cơ bản mà nó vận dụng) và bài tương tự, tối đa 2 bước. Không gồm bài học sau nó, để gia sư không dạy trước. Đoạn tài liệu chưa gắn bài tính là 1 bước.
  - **Gắn đoạn tài liệu vào bài:** bài của đoạn nội dung chương giống nhất (BM25), khi điểm gấp 1,5 lần bài thứ hai.
  - **Xếp hạng lại:**
    - giảng bài: lý thuyết ×1,5, tài liệu ×1,2, làm mẫu ×1,1, lỗi sai ×0,7;
    - gợi ý: phương pháp ×1,4, làm mẫu ×1,3, lỗi sai ×1,2;
    - học sinh hỏi: không ưu tiên loại nào;
    - câu hỏi "… là gì": lý thuyết và phương pháp ×1,3, lỗi sai ×0,8;
    - đã dùng trong buổi ×0,5; đúng lỗi sai vừa gặp ×1,5; bản nháp ×0,9.
  - **Có căn cứ:**
    - Có model ngữ nghĩa: cosine ≥ 0,65 với `gemini-embedding-001`, hiệu chỉnh trên bộ câu chính và kiểm lại trên bộ câu riêng.
    - Không có model ngữ nghĩa: ít nhất 50% từ có nghĩa của câu hỏi (trọng số idf) nằm trong một đoạn được chọn.
- Số câu tối đa mỗi node (N-BUDGET), số cách giảng tối thiểu, các ý bắt buộc khi chấm lời giải thích: đặt giá trị mặc định ở Mốc 1, duyệt sau.
- Nội dung gói chương do AI soạn nháp: chủ dự án duyệt từng node trước khi học sinh thật dùng.
- Tài liệu thật của hai chương: cần trước Mốc 2.

## 10. Rủi ro

- **Nội dung là phần tốn công nhất.** Mỗi node cần lý thuyết, ví dụ, câu kiểm tra, bài luyện và bài vận dụng. Giảm bằng cách để AI soạn nháp và đường nhập tài liệu ở Mốc 2.
- **Chấm lời giải thích** bằng các ý bắt buộc (Mốc 1) còn thô; bằng AI (Mốc 2) có thể sai, nên chỉ là bằng chứng có độ tin cậy, không quyết định một mình.
- **Hạn mức miễn phí:** Groq 8.000 token/phút, Gemini 20 lượt/ngày cho model sinh lời; hạn mức embedding chưa đo. Lời giảng luôn có nguyên văn đã duyệt làm dự phòng; RAG chạy được không cần embedding.
