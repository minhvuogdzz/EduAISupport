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

### 5.6. Lời nói của gia sư

- Đoạn lấy từ Hybrid RAG là **neo**. Qwen diễn đạt lại cho hợp với câu học sinh vừa nói, phải giữ đủ ý của neo (bộ chặn `llm-renderer.v2`: bám câu mẫu, không thêm số, không lặp lại).
- Mọi câu qua bộ kiểm tra hiện có. Hết hạn mức, lỗi mạng hay câu bị loại thì dùng nguyên văn nội dung đã duyệt.

### 5.7. Báo cáo cho giáo viên

- Cây tri thức của từng học sinh tô màu theo điểm (dải màu §25), bằng chứng theo từng chiều, lỗi sai, node "cần học lại".
- Nhận xét kiểu "tư duy giáo viên" của 2T-KT do Qwen viết từ dữ liệu tất định, ghi rõ là nhận xét của AI.
- Transcript có nhãn hiện có (kết quả chấm, lỗi sai, mã luật, nguồn câu nói).

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
- **DI-18 (tham số khác của `node-mastery/0.1.0`):**
  - bài cùng làm có trọng số × 0,5;
  - câu trả lời "vì sao" chưa được chấm tính R = 1 với trọng số 0,3, như nhãn chưa kiểm chứng (PART 26.5); được hỏi "vì sao" mà không giải thích, hoặc đoán, thì R = 0;
  - lỗi khái niệm chưa sửa được thì R cũng nhận điểm 0;
  - chiều của câu theo mức: A/B → C, C → R, D → A, E hoặc câu transfer → T, DIAG → D;
  - độc lập I chỉ tính từ câu giải được, theo gợi ý cao nhất;
  - mức 5 chỉ đạt khi qua cổng thành thạo tạm thời (M ≥ 85, độ tin cậy ≥ 75, μ_A ≥ 0,8), vì Mốc 1 chưa có chiều ghi nhớ S.
- **DI-17:** tham số Hybrid RAG: BM25 k1 = 1,2, b = 0,75; RRF k = 60; hệ số phạt theo khoảng cách đồ thị; ngưỡng "không đủ căn cứ để trả lời".
- Số câu tối đa mỗi node (N-BUDGET), số cách giảng tối thiểu, các ý bắt buộc khi chấm lời giải thích: đặt giá trị mặc định ở Mốc 1, duyệt sau.
- Nội dung gói chương do AI soạn nháp: chủ dự án duyệt từng node trước khi học sinh thật dùng.
- Tài liệu thật của hai chương: cần trước Mốc 2.

## 10. Rủi ro

- **Nội dung là phần tốn công nhất.** Mỗi node cần lý thuyết, ví dụ, câu kiểm tra, bài luyện và bài vận dụng. Giảm bằng cách để AI soạn nháp và đường nhập tài liệu ở Mốc 2.
- **Chấm lời giải thích** bằng các ý bắt buộc (Mốc 1) còn thô; bằng AI (Mốc 2) có thể sai, nên chỉ là bằng chứng có độ tin cậy, không quyết định một mình.
- **Hạn mức miễn phí:** Groq 8.000 token/phút, Gemini 20 lượt/ngày cho model sinh lời; hạn mức embedding chưa đo. Lời giảng luôn có nguyên văn đã duyệt làm dự phòng; RAG chạy được không cần embedding.
