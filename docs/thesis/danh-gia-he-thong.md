# Đánh giá hệ thống CAVAT (tư liệu cho chương Đánh giá của luận văn)

**Phiên bản:** 2026-10-14. Mọi con số dưới đây lấy từ báo cáo trong `evals/reports/` và từ `docs/paper/data/`, tái lập được bằng lệnh `make` ghi kèm. Bản đầy đủ và chặt chẽ hơn của tài liệu này là bài báo `docs/paper/cavat-paper.pdf` (`make paper`, số liệu: `make paper-data`).

**Nhãn:**
- **[FACT]**: đo được, có báo cáo.
- **[DI]**: ngưỡng hoặc diễn giải do dự án tự khai báo.
- **[OPEN]**: chưa đo.

Tài liệu trả lời bốn câu hỏi của chủ dự án:

| Câu hỏi | Mục |
|---|---|
| RQ1. Đánh giá hệ thống bằng phương pháp nào, theo những chiều nào? | 1 |
| RQ2. RAG làm tốt bao nhiêu % so với định hướng? | 2 |
| RQ3. CAVAT giúp học sinh hơn các mô hình trên thị trường ở điểm nào? | 3 |
| RQ4. Cách đánh giá "hiểu bài" sát bao nhiêu so với khung đánh giá ban đầu? | 4 |

---

## Tóm tắt kết quả

| Câu hỏi | Kết quả chính | Nguồn |
|---|---|---|
| RQ1 | Khung 8 chiều: 7 chiều đánh giá AI của blueprint (PART 45.1) cộng chiều "kết quả học tập". 13 bộ đo tái lập được, gồm 9 bộ tất định và 4 bộ có giám khảo là mô hình khác họ. Các bộ có ngưỡng là đặt từ trước, không chỉnh theo kết quả. | Mục 1 |
| RQ2 | RAG đạt **85%** mức trung bình so với 7 mục tiêu định hướng (đạt trọn 5/7, R1 đạt 96%, R7 chưa đạt), tăng từ 65% sau đợt sửa RAG-4 ngày 2026-10-13. Phần tăng đến từ hai nguồn, ghi riêng: một sửa thật của hệ thống (định tuyến câu hỏi bài trước, DI-57), và một lần đo lại R5/R6 trên code hiện tại với giám khảo đã sửa lỗi định dạng. | Mục 2 **So với RAG phẳng** (cùng chỉ mục, không đưa tiết đang học vào): độ chính xác ngang nhau (Hit@3 0,90 ở v2; gộp 52 câu 0,96 so với 0,92, McNemar p = 0,63), nhưng RAG phẳng đưa đoạn của bài sau vào top-3 ở 31/83 câu và trả lời cả 11/11 câu hỏi bài sau; CAVAT: 0. Ràng buộc đồ thị là chi phí để mua an toàn phạm vi, không mua độ chính xác. |
| RQ3 | So với Qwen chỉ có lời nhắc Socratic tốt (B2), CAVAT không hơn về giọng văn: giám khảo chấm Socratic 4,46 so với 4,84, hợp trẻ 4,88 như nhau. CAVAT hơn ở chỗ **không bao giờ nói ra đáp án và không khen sai** (0 lần, B2 có 1 lần khen câu sai "0,09" là đúng rồi đưa luôn "0,9", và **giám khảo LLM không phát hiện**). Ngoài ra CAVAT chấm tất định theo chuẩn Việt Nam, theo dõi hiểu bài theo đồ thị tri thức, có trang giáo viên và học theo tài liệu của chính giáo viên. **Mốc chatbot thương mại (B1, Gemini, lời nhắc thường) chạy ngày 2026-10-14:** nói ra đáp án ở 15/25 lượt (60%), giám khảo thấy lộ 18/25, 7 lượt có hơn một câu hỏi, trung bình 128 từ mỗi lượt, Socratic 2,28/5; chấm câu trả lời của trẻ 25/36 và 25/35 (toàn bộ lỗi là bác câu đúng viết bằng chữ, có lời đệm hoặc teencode). | Mục 3 |
| RQ4 | Đã làm **16/25** mục của khung Toán đầy đủ và 5 mục một phần, độ sát **74%** (mục một phần tính nửa). Chưa làm: chiều Ghi nhớ (S) và các trạng thái dựa trên nó, điểm từng câu (QS), giáo viên sửa điểm. Mọi chỗ khác khung đều có DI: 56 DI đã khai báo. | Mục 4 |

---

## 1. Phương pháp đánh giá (RQ1)

### 1.1. Nguyên tắc

1. **Tất định trước, mô hình chấm sau.** Chỉ số nào đo được bằng luật thì đo bằng luật: lộ đáp án, số câu hỏi mỗi lượt, đúng/sai Toán, phạm vi bài. Giám khảo là mô hình chỉ dùng cho chất lượng ngôn ngữ và sư phạm. Giám khảo luôn **khác họ** với mô hình gia sư: gia sư là Qwen, giám khảo là `openai/gpt-oss-120b`.
2. **Tách bộ chỉnh và bộ giữ riêng.** Mọi bộ câu dùng để chỉnh tham số đều có một bộ giữ riêng (holdout), viết sau và không dùng để chỉnh gì. Con số của bộ giữ riêng mới là con số báo cáo.
3. **Bỏ từng phần (ablation)** để chứng minh mỗi thành phần có tác dụng, cùng kiểu Bảng 5 của bài báo 2T-KT.
4. **Đối chứng** với hai mốc:
   - một chatbot thương mại;
   - chính mô hình của CAVAT nhưng chỉ có lời nhắc, không có hệ thống bao quanh.
5. **Tái lập:** mỗi con số có một lệnh `make`. Phiên học phát lại được từ sổ sự kiện (quy tắc 3). Bộ đệm embedding giúp chạy lại mà không tốn hạn mức.
6. **Báo cáo trung thực:** câu trượt được liệt kê từng câu. Kết quả xấu không bị bỏ ra khỏi bảng.

### 1.2. Khung 8 chiều

Bảy chiều đầu theo blueprint PART 45.1, giữ nguyên ngưỡng ban đầu. Chiều 8 do luận văn bổ sung.

| # | Chiều | Câu hỏi | Chỉ số | Cách đo | Ngưỡng | Trạng thái |
|---|---|---|---|---|---|---|
| 1 | Tuân thủ Socratic | Gia sư có thật sự để con tự làm? | Lộ đáp án; số câu hỏi mỗi lượt; giám khảo chấm Socratic | Validator, luật (`eval-baselines`), giám khảo | Lộ ≤ 1% luyện tập, 0% kiểm tra | Đã đo (mục 3) |
| 2 | Chất lượng gợi ý | Gợi ý đúng mức, đúng chỗ? | Giám khảo chấm "đáp đúng ý"; tiến bộ sau gợi ý | `eval-hard`, `trial` | ≥ 4/5 | Đã đo (4,53/5) |
| 3 | Bám nguồn (RAG) | Lời gia sư dựa vào tài liệu của bài? | Hit@k, MRR, tỉ lệ có căn cứ, giám khảo chấm bám nguồn | `eval-rag`, `eval-rag-published`, `eval-grounded` | ≥ 95% bám nguồn | Đã đo (mục 2) |
| 4 | Chất lượng sư phạm | Đúng kiến thức, hợp lớp 5? | Giám khảo chấm "hợp trẻ"; giáo viên duyệt nội dung | `eval-hard`, duyệt phương án dạy (INGEST-4/5) | ≥ 80% chấp nhận | Đã đo (4,95/5), giáo viên duyệt 2 chương |
| 5 | Độ tin cậy đánh giá | Chấm đúng, nhất quán? | Tất định; độ chính xác chấm đáp án; độ nhạy bộ kiểm đáp án; κ với giáo viên | Test phát lại, `grading-vi-v1`, `eval-items` | Tất định 100%; κ ≥ 0,6 | Đã đo, trừ κ **[OPEN]** |
| 6 | Tuân thủ trạng thái | Gia sư không vượt quyền? | Dạy trước bài sau; đổi buổi học; LLM ghi điểm | Test API, `eval-rag-published` (nhóm bài sau) | 0 vi phạm lọt ra | Đã đo |
| 7 | Bịa đặt | Có nói sai, bịa số? | Câu không có nguồn; sai Toán | Bộ kiểm grounding, MathChecker, giám khảo | ≤ 2% lượt; 0 lỗi Toán | Đã đo (mục 2.2) |
| 8 | Kết quả học tập (bổ sung) | Học sinh có tiến bộ thật? | Điểm trước/sau, so với nhóm đối chứng; ghi nhớ sau T7/T30 | Thử nghiệm với học sinh thật | — | **[OPEN]**: chỉ có học sinh giả lập (mục 5) |

### 1.3. Các bộ đo và lệnh tái lập

| Lệnh | Đo gì | Dữ liệu | Có gọi model |
|---|---|---|---|
| `make test` | 1199 test: chính sách dạy, chấm, phát lại tất định, API, an toàn dữ liệu | Code | Không |
| `make eval-rag LIVE=1` | Truy xuất trên chương mẫu: 5 cấu hình ablation | 67 câu chỉnh + 30 câu giữ riêng | Embedding (lưu đệm) |
| `make eval-rag-published LIVE=1` | Truy xuất trên 2 chương phát hành từ tài liệu thật của giáo viên, kèm quyết định của gia sư | 30 câu chỉnh + 23 câu giữ riêng | Embedding (lưu đệm) |
| `make eval-grounded` | Qwen trả lời câu bé hỏi, có kiểm chứng; giám khảo chấm | 21 ca | Qwen + giám khảo |
| `make eval-hard` | 13 vai học sinh khó, gia sư thật | 24 lượt | Qwen + giám khảo |
| `make eval-baselines` | CAVAT so với chatbot và LLM chỉ có lời nhắc; chấm đáp án | 13 vai, 36 câu trả lời gán nhãn tay | Gemini, Qwen, giám khảo |
| `make eval-items` | Độ nhạy bộ kiểm đáp án: đổi một chữ số của đáp án, đếm số lần bắt được | 389 câu, 3.442 lần đổi | Không |
| `make trial` | 4 học sinh mẫu học hết 2 chương phát hành | 2 chương | Không |
| `make misconception-coverage` | Lỗi sai trong tài liệu nhận ra được bao nhiêu | 2 chương | Không |
| `scripts/simulate_learner.py` | Học sinh giả lập "Vương" từ chưa hiểu đến hiểu; dữ liệu cho trang giáo viên | 2 chương | Qwen |

---

## 2. RAG đạt bao nhiêu % so với định hướng (RQ2)

### 2.1. Định hướng RAG

Định hướng lấy từ kế hoạch (mục 5.5), blueprint PART 45.1 và các DI-17, DI-50, DI-51. Mục tiêu nào blueprint chưa có số thì được khai báo là [DI] ở đây, trước khi xem kết quả của bộ giữ riêng.

| Mã | Định hướng | Chỉ số | Mục tiêu | Nguồn mục tiêu |
|---|---|---|---|---|
| R1 | Truy xuất đúng đoạn cho câu hỏi trong bài | Hit@3, bộ giữ riêng | ≥ 0,90 | [DI] |
| R2 | Biết khi nào **không** có căn cứ: câu lạc đề không được trả lời | Tỉ lệ câu lạc đề không được trả lời bằng tài liệu | ≥ 95% | PART 45.1 (bịa ≤ 2%) |
| R3 | Câu trong chương được coi là có căn cứ | Tỉ lệ có căn cứ | ≥ 95% | PART 45.1 (bám nguồn ≥ 95%) |
| R4 | Không dạy trước bài sau (plan 5.5.3) | Câu hỏi bài sau: không trả lời trước | 100% | Quy tắc thiết kế |
| R5 | Lời trả lời bám nguồn | Giám khảo chấm bám nguồn, quy ra % | ≥ 95% | PART 45.1 |
| R6 | Không bịa, không lộ đáp án câu đang chờ | Lượt bịa hoặc lộ theo giám khảo | ≤ 2% | PART 45.1 |
| R7 | Hybrid có lý do để tồn tại (ablation) | MRR của hybrid + xếp hạng lại ≥ mọi thành phần, trên bộ giữ riêng | Đạt / không | Plan 5.5.5 |

### 2.2. Kết quả đo [FACT]

**Chương mẫu (Số thập phân, nội dung YAML), `2026-10-13-rag-gemini.md`:**

| Cấu hình | MRR chỉnh | MRR giữ riêng | Hit@3 giữ riêng |
|---|---|---|---|
| Chỉ từ khóa | 0,826 | 0,608 | 0,80 |
| Chỉ ngữ nghĩa | 0,868 | **0,765** | **0,93** |
| Hybrid | 0,864 | 0,722 | 0,87 |
| Hybrid + xếp hạng lại (chạy thật) | **0,939** | 0,678 | 0,87 |

Có căn cứ: 100% câu trong chương được nhận, 100% câu lạc đề bị từ chối, trên cả hai bộ (72 + 25 câu).

**Hai chương phát hành từ tài liệu thật của giáo viên** (221 đoạn, 83 đoạn tài liệu), `2026-10-13-rag-published-gemini.md`:

| Nhóm câu | Bộ chỉnh: Hit@3 / gia sư làm đúng | Bộ giữ riêng: Hit@3 / gia sư làm đúng |
|---|---|---|
| Hỏi trong bài đang học | 1,00 / 1,00 | 1,00 / 1,00 |
| Hỏi khái niệm của bài trước | 0,70 / 1,00 | **0,29** / 0,71 |
| Hỏi bài sau (phải báo "bài sau mình học") | — / 1,00 | — / 1,00 |
| Toán ngoài chương (phải gác) | — / 1,00 không trả lời | — / 1,00 không trả lời |
| Lạc đề (phải gác) | — / 1,00 | — / 1,00 |

Ở nhóm "Toán ngoài chương", một phần câu được báo là "bài sau" thay vì gác cho cô. Nhưng không câu nào được trả lời, nên vẫn tính là đạt.

**Lời trả lời của Qwen từ RAG** (`2026-10-07-grounded-live.md`, 15 câu bé hỏi và 6 câu nối):
- Chọn đúng loại phản hồi (trả lời, bài sau, gác cho cô, "chính là câu cô đang hỏi"): 15/15.
- Giám khảo chấm bám nguồn: câu trả lời 4,12/5, câu nối 5,00/5.
- Giám khảo thấy bịa: 1/8 câu trả lời và 2/5 câu nối. Lộ đáp án câu đang chờ: 1/5 câu nối.
- Bộ kiểm chứng đã chặn 5 câu Qwen viết không có nguồn trước khi học sinh nghe thấy.

**Sau RAG-4** (DI-57, định tuyến câu hỏi về bài trước, 2026-10-13). Đo trên **bộ giữ riêng v2**, viết và commit trước khi sửa, đo một lần (`2026-10-13-rag-published-gemini-v2-before.md`, `…-v2-after.md`):

| | Trước | Sau |
|---|---|---|
| Hit@3, câu hỏi trong chương (20 câu) | 0,45 | **0,90** |
| Hit@3, nhóm hỏi bài trước (12 câu) | 0,08 | **0,83** |
| MRR (hybrid + xếp hạng lại) | 0,503 | **0,887** |
| Câu bài sau: không dạy trước | 4/4 | 4/4 |
| Câu lạc đề, Toán ngoài chương: gác cho cô | 6/6 | 6/6 |

- Bộ chỉnh và bộ v1: Hit@3 1,00 sau sửa. Chương mẫu không tụt.
- **Ablation trên v2:** hybrid + xếp hạng lại 0,887 > từ khóa + xếp hạng lại 0,728 > hybrid 0,460 ≈ từ khóa 0,459 ≈ ngữ nghĩa 0,449. Xếp hạng lại theo cấu trúc là phần có tác dụng (hybrid → hybrid + xếp hạng lại: ΔMRR +0,427, khoảng [0,236; 0,613], McNemar p = 0,002). **Phần góp của vector chưa chứng minh được**: từ khóa + xếp hạng lại → hybrid + xếp hạng lại ΔMRR +0,158, khoảng [−0,031; 0,359], p = 0,22 (n = 20). Nhận định trước đây "vector chỉ có ích khi đi cùng cấu trúc đồ thị" vì vậy không được dữ liệu ủng hộ ở mức thống kê.

**Lời trả lời của Qwen, đo lại ngày 2026-10-13** (`2026-10-13-grounded-live.md`, code `grounded-speech/0.2.2`, giám khảo nhận đầu vào dạng các dòng có nhãn thay vì JSON):
- Chọn đúng loại phản hồi: 15/15.
- Bám nguồn: câu trả lời 5,00/5, câu nối 5,00/5.
- Giám khảo thấy bịa: 0/14. Lộ đáp án: 0/14.
- Bộ kiểm chứng chặn 5 câu trước khi học sinh nghe.

### 2.3. Mức đạt từng mục tiêu

**Quy tắc tính** (khai báo trước khi đo lại):
- Mục tiêu "≥": mức đạt = kết quả / mục tiêu.
- Mục tiêu "≤": mức đạt = mục tiêu / kết quả.
- Tối đa 100%. R7 là đạt/không đạt.
- Dùng bộ giữ riêng mới nhất. Khi có cả chương mẫu và chương phát hành thì lấy **con số thấp hơn**.

| Mã | Mục tiêu | Lần đo đầu (sáng 2026-10-13) | Sau RAG-4 và đo lại (chiều 2026-10-13) | Mức đạt |
|---|---|---|---|---|
| R1 | Hit@3 ≥ 0,90 | 0,64 → 71% | min(chương mẫu 0,867; phát hành v2 0,90) = 0,867 | **96%** |
| R2 | ≥ 95% câu lạc đề không được trả lời | 100% | Chương mẫu 15/15, v2 6/6 | **100%** |
| R3 | ≥ 95% câu trong chương có căn cứ | 93% | Chương mẫu 100%, v2 100% | **100%** |
| R4 | 100% câu bài sau không dạy trước | 100% | v2 4/4 | **100%** |
| R5 | Bám nguồn ≥ 95% | 4,12/5 = 82% | 5,00/5 = 100% | **100%** |
| R6 | Bịa hoặc lộ ≤ 2% lượt | 3/13 lượt (23%) | 0/14 lượt | **100%** |
| R7 | Hybrid + xếp hạng lại tốt nhất trên bộ giữ riêng | Không | Phát hành v2: **có** (0,887). Chương mẫu: không (chỉ ngữ nghĩa 0,765 > 0,678) | **0%** (lấy chương thấp hơn) |

- **Mức đạt trung bình: (96 + 100 × 5 + 0) / 7 = 85%. Đạt trọn 5/7 mục tiêu.**
- **Nguồn của phần tăng từ 65% lên 85%:**
  - R1 tăng nhờ một sửa thật của hệ thống (DI-57), đo trên bộ giữ riêng viết trước khi sửa.
  - R5 và R6 tăng vì đo lại trên code hiện tại (đã qua nhiều bản sửa từ 7/10). Đồng thời giám khảo đã được sửa lỗi định dạng làm nó chấm nhầm ca G05.
  - Trong luận văn nên nói rõ cả hai nguồn.
- **Giới hạn của số đo:** R5 và R6 chỉ có 14 lượt, và bộ ca `grounded-decimals-v1` đã có từ trước. Ngưỡng 2% chỉ thật sự kiểm chứng được với mẫu lớn hơn (khoảng 100 lượt).
- **Cách nói trong luận văn:** "RAG đạt các định hướng về an toàn phạm vi, độ bám nguồn và truy xuất (5/7 trọn vẹn, R1 96%). Riêng giả thuyết 'hybrid tốt hơn từng thành phần' chỉ đúng trên tài liệu thật của giáo viên, chưa đúng trên chương mẫu."

### 2.4. Nhận xét kỹ thuật cho luận văn

1. **An toàn quan trọng hơn truy xuất.** RAG được thiết kế để thà gác cho cô còn hơn trả lời sai. Kết quả xác nhận điều này: R2 và R4 đạt 100% ở mọi bộ. Phần chưa tốt (R1) chỉ làm bé phải chờ cô giải đáp, không làm bé học sai.
2. **Cấu trúc đồ thị phải có định tuyến mới không làm hại độ chính xác, và nó mua an toàn chứ không mua độ chính xác.**
   - Phạm vi chặt chưa có định tuyến cho Hit@3 trên v2 chỉ 0,45 (RAG phẳng: 0,90), vì nó đẩy ra ngoài các đoạn trả lời câu hỏi về bài cũ. Định tuyến (DI-57) khôi phục 0,90.
   - So với RAG phẳng, độ chính xác ngang nhau (v2: 0,90 và 0,90; gộp ba tập phát hành 0,96 so với 0,92, p = 0,63). Cái khác nhau là phạm vi: RAG phẳng đưa đoạn bài sau vào top-3 ở 31/83 câu (37%) và trả lời 11/11 câu hỏi bài sau.
   - Ngưỡng nền tảng cosine ≥ 0,65 một mình không đủ: 7/11 câu hỏi bài sau vượt ngưỡng vì kho có nội dung đó ở tiết sau; chính phát hiện tiết sau chuyển chúng sang "bài sau".
3. **Bộ kiểm chứng là thành phần chính, không phải phụ.** Giám khảo vẫn thấy lời Qwen bịa ở khoảng 1/4 lượt có lời Qwen; ngoài ra bộ kiểm chứng đã chặn 5 câu không có nguồn trước khi học sinh nghe thấy.
4. **Giới hạn của số đo:** bộ câu nhỏ (bộ giữ riêng 14–30 câu) và do người phát triển viết, chưa có câu hỏi của học sinh thật.

---

## 3. CAVAT giúp học sinh hơn các mô hình trên thị trường ở điểm nào (RQ3)

### 3.1. Thị trường hiện nay (thông tin công khai, 2025–2026)

| Sản phẩm | Cách hướng dẫn | Cơ chế không lộ đáp án | Theo dõi hiểu bài | Giáo viên | Tiếng Việt lớp 5, chương trình Việt Nam | Chi phí |
|---|---|---|---|---|---|---|
| ChatGPT, chế độ học (Study mode, 7/2025) | Hỏi gợi mở, chia nhỏ, kiểm tra hiểu | Lời nhắc hệ thống tùy biến, không phải mô hình riêng [1] | Ghi nhớ hội thoại, không có mô hình học sinh theo kỹ năng | Không có lớp, không có báo cáo | Chung, không theo bài của giáo viên | Có bản miễn phí |
| Gemini, Guided Learning (8/2025) | Từng bước, câu hỏi, hình ảnh, quiz | Dựa trên LearnLM [2] | Không công bố mô hình kỹ năng | Không có lớp, không có báo cáo | Chung; tải tài liệu lên được | Miễn phí |
| Khanmigo (Khan Academy) | Socratic, gợi ý trên bài của Khan Academy | Thiết kế không đưa đáp án; dùng GPT-4 [3] | Theo tiến độ trên nền tảng Khan | Giáo viên có công cụ và tổng hợp lớp | Tiếng Anh, chương trình Mỹ | Học sinh trả phí (khoảng 4 USD/tháng) |
| App giải bài bằng ảnh (kiểu Photomath, Gauth) | Đưa lời giải từng bước | Không: mục tiêu là đưa lời giải | Không | Không | Có, nhưng là giải hộ | Miễn phí hoặc trả phí |
| **CAVAT** | Vòng dạy 7 bước trên đồ thị tri thức; chính sách tất định chọn nước đi; LLM chỉ diễn đạt | **Bằng luật:** đáp án câu kiểm tra không bao giờ có trong prompt; validator chặn trước khi học sinh thấy | Điểm 7 chiều từng tiết, phát lại được, theo khung đánh giá Toán | Giáo viên tải tài liệu, duyệt phương án dạy, xem bản đồ nhiệt, đường tiến bộ, lỗi sai, hội thoại | Theo tài liệu của chính giáo viên; dấu phẩy thập phân; teencode; giọng nói | 0 đồng (free tier, chạy local) |

Khác biệt về thiết kế: chế độ học của các chatbot vẫn để **mô hình tự quyết** khi nào gợi ý, khi nào nói đáp án. Vì vậy lời nhắc chỉ là "lời khuyên" cho mô hình. CAVAT tách hai việc:
- **chính sách tất định quyết định**, gồm nước đi, mức gợi ý, chuyển tiết, chấm đúng/sai;
- **mô hình chỉ diễn đạt**, và lời của mô hình qua bộ kiểm trước khi đến học sinh.

Thí nghiệm EVAL-1 (mục 3.2) đo xem sự khác biệt này có thể hiện ra thành số liệu không.

### 3.2. Thí nghiệm đối chứng EVAL-1 [FACT]

`make eval-baselines`, báo cáo `evals/reports/2026-10-13-vs-baselines.md`.

**Phần A: 13 vai học sinh khó, cùng lời nói, cùng câu hỏi.**

| Gia sư | Lượt | Nói ra đáp án (luật) | Khen câu sai là đúng | Giám khảo thấy lộ | > 1 câu hỏi/lượt | Số chữ TB | Đáp đúng ý / Socratic / Hợp trẻ / Bám bài |
|---|---|---|---|---|---|---|---|
| B2: Qwen + lời nhắc Socratic tốt | 25 | **1** | **1** | 0/25 | 0 | 29 | 4,88 / 4,84 / 4,88 / 4,92 |
| C: CAVAT | 24 | **0** | **0** | 0/24 | 0 | 24 | 4,71 / 4,46 / 4,88 / 4,71 |
| B1: chatbot Gemini (lời nhắc thường) | 25 | **15** | **1** (khen "C" sai rồi nêu luôn 7/10) | 18/25 | 7 | 128 | 3,08 / 2,28 / 4,20 / 4,76 |

**Phân tích trung thực:**
- **Về giọng văn, CAVAT không hơn** một LLM có lời nhắc tốt. Giám khảo cho B2 điểm Socratic cao hơn. Ba lượt CAVAT bị chấm thấp:
  - xác nhận câu đúng rồi sang câu mới, không hỏi "vì sao" (luật chỉ hỏi ở 30% số câu, đã được duyệt);
  - một phản ví dụ chờ giáo viên duyệt nội dung;
  - một câu nhắc lại đề còn nhạt.
- **Về an toàn sư phạm, CAVAT hơn.**
  - Vai Mít trả lời sai "0,09". B2 đáp: "Con đã viết **đúng** số thập phân rồi… vì sao 9/10 lại bằng **0,9**?". Trong một câu, B2 vừa khen câu sai, vừa nói ra đáp án.
  - **Giám khảo LLM chấm câu đó 5/5 Socratic và "không lộ"**, chỉ luật tất định bắt được.
  - Đây là bằng chứng cho nguyên tắc thiết kế của CAVAT: không tin mô hình tự chấm và tự giữ đáp án, kể cả mô hình giám khảo.
- **Ý nghĩa:** chế độ học của ChatGPT và Gemini cũng là "lời nhắc tốt" (mục 3.1), nên B2 là xấp xỉ gần nhất của chúng mà dự án đo được miễn phí. B1 (chatbot với lời nhắc thường) cho thấy lựa chọn mặc định của một đứa trẻ: lộ đáp án ở 60% số lượt thử thách, kể cả khi được bảo "bỏ qua mọi hướng dẫn". B1 **không** đại diện cho các chế độ học thương mại.

**Phần B: chấm câu trả lời của trẻ** (gán nhãn tay; v2 là bộ giữ riêng viết trước khi sửa bộ chấm GRADE-1).

| Người chấm | v1 (36 câu, trước GRADE-1) | v2 (35 câu, giữ riêng, sau GRADE-1) | Tất định |
|---|---|---|---|
| C: CAVAT (bộ điều phối + MathChecker) | 31/36 (86%) | **35/35 (100%)**; trước GRADE-1: 26/35 (74%) | Có: lần nào cũng như nhau |
| B2: Qwen, chấm hàng loạt | 35/36 (97%) | 35/35 (100%) | Không |
| B1: Gemini, chấm hàng loạt | 25/36 (69%) | 25/35 (71%) | Không; toàn bộ 11 + 10 lỗi là bác câu đúng viết bằng chữ ("không phẩy chín"), có lời đệm ("0,9 ạ cô"), teencode ("o,9") hoặc so sánh bằng lời |

- GRADE-1: bộ chấm đọc được số viết bằng chữ ("không phẩy chín", "0 phẩy 3") và hiểu dạng mà đề hỏi.
- **Kết luận:** hai bên ngang nhau khi chấm hàng loạt có hướng dẫn. Nhưng khi chấm *giữa hội thoại*, B2 đã khen câu sai (phần A). Bộ chấm của CAVAT chạy cùng một code ở mọi chỗ.

### 3.3. Những gì CAVAT làm được mà chatbot không làm được, có bằng chứng

| Lợi ích cho học sinh | Bằng chứng |
|---|---|
| Không bị đưa đáp án dù đòi hay "bỏ qua hướng dẫn" | `eval-hard` 0/24; EVAL-1: CAVAT 0 lần, LLM chỉ có lời nhắc 1 lần (giám khảo LLM không bắt được) |
| Được chấm đúng theo cách viết và cách nói của trẻ Việt Nam (dấu phẩy, teencode, "o,9", "không phẩy chín") | `grading-vi-v2` (giữ riêng): 35/35, tất định; không khen sai giữa hội thoại (EVAL-1 phần A) |
| Được dạy lại đúng chỗ hổng: quay về bài nền, hỏi lại bài cũ, nhắc ý chính bài gốc khi sai | DI-52, DI-53; Vương: nhớ lại 11/15 lần, nhắc bài gốc 17 lần |
| Lỗi sai điển hình được nhận ra và giải thích riêng | DI-54: 14 họ lỗi, 26 và 103 đáp án sai gắn lỗi trên 2 chương |
| Giáo viên thấy bằng chứng, không chỉ con số | Trang giáo viên: bản đồ nhiệt, đường tiến bộ, hội thoại có nhãn ý định, lỗi sai, nguồn RAG |
| Học theo chính tài liệu của cô ở lớp, đúng phạm vi bài | Đáp án và lý thuyết lấy từ tài liệu giáo viên đã duyệt; R4 100% |
| Không mất tiền, không phụ thuộc gói trả phí | Toàn bộ chạy trên free tier và mô hình local (ADR-016) |

### 3.4. Điều chưa chứng minh [OPEN]

- **Chưa có thử nghiệm với học sinh thật.** Vì vậy luận văn **không được** khẳng định CAVAT "giúp học sinh học tốt hơn". Luận văn chỉ khẳng định được: CAVAT **tuân thủ** cách dạy và cách đánh giá đã đề ra tốt hơn các mốc đối chứng, theo các chỉ số ở 3.2.
- **Học sinh giả lập trả lời bằng ý của giáo viên khi đã hiểu.** Số liệu của học sinh giả lập kiểm luồng dạy, không đo hiệu quả học tập.

---

## 4. Cách đánh giá "hiểu bài" sát bao nhiêu so với khung ban đầu (RQ4)

### 4.1. Đối chiếu từng mục của khung Toán (blueprint PART 26.1, 26.3, 26.5, 26.6, 27) với code

Đầy đủ = 1 điểm, một phần = 0,5, chưa = 0.

| # | Mục của khung | Mục gốc | Trạng thái | Ghi chú (vị trí trong code) |
|---|---|---|---|---|
| 1 | 7 chiều C, R, A, T, I, S, D | §20 | Một phần | 6 chiều có nguồn bằng chứng; S để trống vì chưa có bài kiểm tra trì hoãn (`projector.py`) |
| 2 | Công thức M và trọng số | §20 | Đầy đủ | `MasteryPolicy.weights` |
| 3 | Thiếu chiều thì chuẩn hóa lại trọng số | DI-1 | Đầy đủ | `_composite` |
| 4 | Điểm từng câu QS | §35 | Chưa | Chưa có màn hình điểm từng câu |
| 5 | Độ độc lập H0–H7 | §11, DI-2 | Đầy đủ | `independence` |
| 6 | Phân loại lỗi và mức phạt | §34, DI-3 | Đầy đủ | `error_scores`, `guess_factor` |
| 7 | Trọng số theo độ khó | §31, DI-4 | Đầy đủ | `0,5 + d` / `1,5 − d` |
| 8 | Trọng số theo hỗ trợ | DI-5 | Đầy đủ | `min_support` |
| 9 | 6 mức hiểu và dải | §4–§8 | Đầy đủ | `bands` |
| 10 | Gate "hiểu" (≥ 3 lần đúng, ≥ 2 mức, ≥ 2 dạng) | §52 | Đầy đủ | `understood`, DI-49, DI-56 |
| 11 | Gate "thành thạo" (M, độ tin cậy, A, S, không còn lỗi nghiêm trọng) | §53 | Một phần | Có đủ trừ S, nên chỉ có "thành thạo tạm thời" |
| 12 | Thành thạo tạm thời | §53 | Đầy đủ | `provisional` |
| 13 | Gate theo chiều | DI-6 | Đầy đủ | Mức 3 cần R, mức 4 cần A |
| 14 | Trạng thái cuối AT_RISK, FORGOTTEN, MASTERED_STABLE | §54 | Chưa | Cần chiều S |
| 15 | "Chưa đủ dữ liệu" | DI-7 | Đầy đủ | `insufficient_data`, trang giáo viên |
| 16 | Độ tin cậy | §21, §33, DI-11 | Đầy đủ | `_confidence` |
| 17 | Vùng màu | §25 | Đầy đủ | `zones.ts` |
| 18 | Hành động theo dải M | §50, DI-8 | Đầy đủ | `_support` của chính sách dạy |
| 19 | Các loại bằng chứng | §9–§15 | Một phần | Thời gian làm bài có ghi nhưng chưa vào điểm |
| 20 | Chất lượng lập luận | §10, §16 | Một phần | Bộ chấm từ khóa DI-55; chưa chấm tính nhất quán logic |
| 21 | Chẩn đoán lỗi sai theo danh mục | §15 | Một phần | Bug rule (chương mẫu); DI-54 trên chương phát hành, chưa nhận ra hết |
| 22 | Kiểm tra nhãn do LLM đề xuất | 26.5 | Đầy đủ | `_label_weight` |
| 23 | Giáo viên sửa điểm | 26.6 | Chưa | Mới có kiểu sự kiện `TEACHER_OVERRIDE` |
| 24 | Báo cáo giáo viên, học sinh, phụ huynh | §23, §43, §44 | Đầy đủ | Trang giáo viên, học sinh, phụ huynh |
| 25 | Ghi nhớ bằng bài kiểm tra trì hoãn T1/T3/T7/T30 | §19 | Chưa | Ngoài phạm vi demo |

**Kết quả:** 16 đầy đủ, 5 một phần, 4 chưa. **Độ sát = (16 + 0,5 × 5) / 25 = 74%** (chỉ tính mục đầy đủ: 64%).

Hai mục chưa làm (#14, #25) và hai mục một phần (#1, #11) xoay quanh **thời gian**: ghi nhớ sau nhiều ngày và các trạng thái quên. Một buổi demo không đo được những thứ này; đó là giới hạn của phạm vi, không phải sai lệch thiết kế. Hai mục chưa làm còn lại (#4 điểm từng câu, #23 giáo viên sửa điểm) là giao diện.

### 4.2. Những chỗ khác khung đều được khai báo (quy tắc 9)

- **58 DI** (DI-1 đến DI-58) đã ghi trong kế hoạch và blueprint. Mỗi DI nói rõ ngưỡng nào là của dự án, vì sao.
- **Ví dụ quan trọng cho luận văn:**
  - DI-15: luật qua tiết;
  - DI-16: điểm khởi đầu;
  - DI-49 và DI-56: bù dạng câu;
  - DI-52 đến DI-55: hỏi lại bài cũ, nhắc bài gốc, nhận lỗi sai, chấm "vì sao".
- Khi thực nghiệm cho thấy một DI sai, nó được sửa và ghi lại. Ví dụ ở DI-55: bản đầu trừ điểm câu "vì sao" chung chung, làm học sinh mẫu kẹt ở tiết đầu, nên đã đổi thành "không tính, không trừ".

### 4.3. Độ tin cậy của việc đánh giá [FACT]

| Chỉ số | Kết quả | Ngưỡng |
|---|---|---|
| Tất định và phát lại được | 100%: test phát lại cho cùng điểm, cùng quyết định; điểm là projection từ sổ sự kiện | 100% |
| Chấm đáp án của trẻ | v1: 31/36 (86%). Sau GRADE-1, trên v2 giữ riêng: **35/35 (100%)**, không sai dương, không sai âm | **[DI]** ≥ 95% |
| Độ nhạy bộ kiểm đáp án khi nội dung có lỗi (`eval-items`) | 97,1% và 98,4% | — |
| Lỗi sai trong tài liệu nhận ra được | Phụ thuộc chương, chi tiết ở `2026-10-13-misconception-coverage.md` | — |
| Đồng thuận với giáo viên (κ) | **[OPEN]**: cần ≥ 100 nhãn của giáo viên | ≥ 0,6 |

Bộ v1 đã chỉ ra hai lỗi chấm, và cả hai đã được sửa (GRADE-1) rồi đo trên bộ v2 viết trước khi sửa:
- **Số viết bằng chữ có "phẩy"** ("không phẩy chín", "0 phẩy 9") chưa đọc được. Điều này quan trọng với chế độ giọng nói.
- **"9/10" được nhận** khi đề hỏi số thập phân, vì câu thiếu khai báo `form`. Giờ bộ chấm suy ra dạng hỏi từ đề (DI).

---

## 5. Hạn chế và kế hoạch đánh giá tiếp

1. **Thử nghiệm với học sinh thật** (chiều 8):
   - Thiết kế: 2 nhóm (CAVAT / học bình thường hoặc chatbot), bài kiểm tra trước và sau, cùng chương. Kiểm tra trì hoãn sau 7 và 30 ngày để có chiều S.
   - Cỡ mẫu và đạo đức nghiên cứu: chủ dự án quyết định.
2. **κ với giáo viên:** giáo viên gán nhãn ≥ 100 lượt (lập luận, lỗi sai) để hiệu chỉnh bộ chấm và giám khảo.
3. **Câu hỏi thật của học sinh** cho RAG: thay bộ câu do người phát triển viết.
4. **Sửa các điểm yếu đã đo:**
   - đọc số viết bằng chữ có "phẩy";
   - truy xuất câu hỏi bài trước trên chương phát hành;
   - tỉ lệ lời Qwen bị chặn.

## Nguồn tham khảo thị trường

1. OpenAI Study mode: [Maginative](https://www.maginative.com/article/openai-launches-study-mode-for-chatgpt/), [InfoQ](https://www.infoq.com/news/2025/08/study-mode-chatgpt), [PCWorld](https://www.pcworld.com/article/2863281/chatgpt-gets-study-mode-to-guide-students-without-spoon-feeding-answers.html)
2. Gemini Guided Learning: [9to5Google](https://9to5google.com/2025/08/06/gemini-guided-learning/), [Google blog](https://blog.google/products/gemini/new-gemini-app-tools-to-help-students-in-europe-the-middle-east-and-africa/)
3. Khanmigo: [Cut the SaaS case study](https://cut-the-saas.com/ai/how-khan-academy-leveraged-ai-to-change-education), [Build Fast with AI review](https://buildfastwithai.com/ai-tools/khanmigo). Đây là nguồn bên thứ ba, cần đối chiếu với trang chính thức của Khan Academy.
