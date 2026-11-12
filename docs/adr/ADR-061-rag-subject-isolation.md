# ADR-061: Hybrid RAG cô lập theo môn (ENG-2)

Ngày: 12/11/2026 · DI-120, DI-121, DI-122, DI-123 · **Infrastructure/data-safety change** (quy tắc 25)

Ngày 12/11/2026 chủ dự án chốt làm module Tiếng Anh thật cho Unit 11 "Family time" (SGK Tiếng Anh 5 Global Success, tập hai; ADR-060, `docs/plan/english-module-rules.md` mục 2, luật G1–G4). Nỗi lo lớn nhất: Tiếng Anh không được lẫn vào Toán hay làm đổi hành vi của Toán. Trước thay đổi này Hybrid RAG gom **mọi** chương và **mọi** tài liệu giáo viên của trường vào **một** `RagIndex`; hai chương không lẫn nhau chỉ nhờ lọc `chapter_id` lúc truy xuất, mà điều kiện lọc còn cho qua chunk có `chapter_id` rỗng. Đoạn tài liệu chưa gắn nút được coi là cách một bước (`UNASSIGNED_DISTANCE`), `tag_passages` gắn đoạn vào nút bằng BM25 trên chunk của mọi chương, đồ thị là một `graph` chung, và BM25 đọc chữ theo kiểu tiếng Việt/Toán. Thêm tài liệu Tiếng Anh vào chỉ mục đó thì một đoạn Tiếng Anh không gắn chương có thể tới buổi Toán, và ngược lại.

## Khảo sát: mọi đường truy xuất và cách xác định chương/môn

| Đường | Nơi gọi | Chương/môn lấy từ đâu |
|---|---|---|
| Câu hỏi của bé, gợi ý bằng tài liệu (CTX-1), tra cứu kiến thức (BRAIN-2/4/7), `later_node` | `teaching/grounded.py` (`GroundedSpeaker`: `retrieve`, `question`, `index.chunks`, `ancestors`), `teaching/official_web.py` (`scoped_query`), `teaching/loop.py` (đi qua speaker) | `session/api.py::_chapter_speaker` dựng speaker bằng `_rag_service.current(database)`; chương là gói chương backend nạp theo `lesson_id`/`lesson_version` của buổi học |
| Trang RAG của giáo viên (`/status`, `/rebuild`, `/search`) | `rag/api.py` | không có; đọc chỉ mục chung |
| Đánh giá | `rag/evaluate.py`, `scripts/eval_rag.py`, `eval_rag_published.py`, `eval_grounded.py`, `paper_rag.py`, `eval_brain2.py` | các chương trong repo hoặc chương đã xuất bản (đều là Toán) |
| Đọc tài liệu cho item bank, giáo án, hình vẽ | `ingest/service.py`, `figures/service.py`, `library_import.py`, `scripts/eval_item_bank.py` (không qua RAG, nhưng cùng đọc `DocumentRepository.list_all`) | lọc `chapter_id` sau khi đọc mọi tài liệu |

Không có lớp `SessionContext` riêng trong code; ngữ cảnh buổi học là gói chương mà backend nạp cho buổi học (`content`), không do request gửi lên.

## Quyết định

1. **`subject` là khái niệm chung** (`cavat/core/subjects.py`): `Subject = Literal["math", "english"]`. Bắt buộc, không mặc định, ở `ChapterPackage` (trước đó là `Literal["math"]`), `Chunk` (trường keyword-only, kiểm khi tạo), `TeacherDocument`, `RagIndex`, `RagService.current`, `DocumentRepository.list_all`, `analyzer_for`. Thiếu hoặc sai là lỗi (`TypeError`, `ValueError`, `ValidationError`), không bao giờ rơi về Toán.
2. **Một chỉ mục cho mỗi `(school_id, subject)`, lọc khi dựng.** `RagService` giữ một `SubjectIndex` cho mỗi môn (chỉ mục, chữ ký corpus, thời điểm dựng, tài liệu), dựng từ chương, tài liệu và đồ thị của riêng môn đó. `RagIndex` từ chối chunk khác môn (`ValueError`), nên không có đường nào chỉ lọc lúc truy xuất. Vòng lặp chọn phạm vi vẫn kiểm `c.subject` như một lớp phòng thủ thứ hai: chunk `chapter_id` rỗng và chunk chưa gắn nút chỉ được xét trong môn của nó. `tag_passages` chỉ so một đoạn với chunk cùng môn, bằng bộ đọc của môn đó.
3. **Môn của buổi học do backend đặt:** `_chapter_speaker` truyền `content.package.subject`, tức môn của gói chương mà backend nạp từ `lesson_id`/`lesson_version` đã lưu của buổi học. Không trường nào của request đổi được.
4. **Bộ đọc chữ theo môn** (`rag/analyzers.py`, DI-121). BM25 chỉ còn phần đếm; phần cắt chữ cắm vào theo môn.
5. **Luật chỉ dành cho Toán** (DI-122): nhận câu hỏi định nghĩa (DI-50) và thuật ngữ ngoài chương (DI-79, dựa trên `math_terms`) chỉ chạy trong chỉ mục Toán.
6. **Tài liệu giáo viên:** khi upload, môn lấy theo chương; nếu không chọn chương thì giáo viên phải nêu môn, nếu không có cả hai thì trả 422. Nếu môn gửi kèm khác môn của chương thì cũng 422. Bộ đọc item bank, giáo án và hình vẽ hiện có là bộ của Toán (luật N2) nên đọc tài liệu môn `math`.
7. **API và trace:** `/v1/teachers/rag/status|rebuild|search` nhận `subject` (DI-123) và trả `subject`; mỗi đoạn kết quả có `subject`. Trace `rag` ghi môn của chỉ mục và của từng chunk. Danh sách tài liệu có `subject`. Web chỉ thêm kiểu dữ liệu (`Subject`, các trường `subject?`). Upload chưa chọn chương thì gửi `subject=math`, vì thư viện của giáo viên hiện chỉ có Toán.

## Các DI

- **DI-120 (dữ liệu cũ là Toán):** document đã lưu trước ENG-2 không có khóa `subject`. Trước ngày này hệ thống chỉ có Toán (D-T9), nên khi đọc, `with_legacy_subject` hiểu document đó là `"math"`. Chỉ áp dụng lúc đọc, ở một chỗ duy nhất (`DocumentRepository`); không ghi lại, không migration vào `cavat_dev`/`cavat_prod`. Nếu khóa có mặt mà rỗng hoặc sai thì vẫn là lỗi. Lọc theo môn chạy sau quy tắc này (document cũ không có trường để Mongo khớp), trên thư viện của một trường (vài trăm document). Gói chương thì không cần quy tắc này, vì `subject` đã bắt buộc trong schema từ đầu.
- **DI-121 (bộ đọc chữ theo môn):** Toán giữ nguyên bộ đọc cũ (`vi-math/1`: `core/vi_text`, dấu chấm thập phân, từ đệm của câu hỏi), chuyển nguyên văn từ `bm25.py` sang `analyzers.py`, cho ra đúng từng token như trước. Tiếng Anh (`en-vi/1`): chữ thường, viết đầy đủ dạng rút gọn ("I'm" = "I am", "didn't" = "did not", "he's" = "he is", "father's" = "father"), bỏ dấu câu, rồi dùng cùng hai dạng (có dấu/bỏ dấu) và cặp từ, nên câu tiếng Việt chen từ tiếng Anh vẫn khớp. Động từ quá khứ gặp dạng gốc của nó: mỗi từ tiếng Anh có thêm một token gốc (`lemma`). Token này lấy từ quá khứ bất quy tắc thường gặp ở lớp 5 ("went" = "go", "did" = "do", "had" = "have") hoặc từ quá khứ có quy tắc ("collected" = "collect", "studied" = "study", "stopped" = "stop"), rồi bỏ "e" cuối để "baked" gặp "bake". Từ gốc ban đầu vẫn được giữ, nên đây chỉ là thêm một cách khớp. Danh sách bất quy tắc chưa đầy đủ. Từ đệm tiếng Việt vẫn bị bỏ, trừ "a", "the", "may" gõ không dấu (khi đó là từ tiếng Anh). `vi_text` không bị sửa (luật G4).
- **DI-122 (luật Toán chỉ chạy cho Toán):** DI-50 (câu hỏi định nghĩa, tăng điểm đoạn định nghĩa) và DI-79 (thuật ngữ Toán ngoài chương thì không có căn cứ) đọc cấu trúc câu tiếng Việt và danh sách thuật ngữ Toán lớp 5. Trong môn khác, câu hỏi giữ chế độ `question` và không có "thuật ngữ ngoài chương". Luật tương ứng cho Tiếng Anh sẽ do task Tiếng Anh khai báo riêng.
- **DI-123 (trang RAG của giáo viên mặc định là Toán):** trang có từ trước khi có môn thứ hai, nên khi không nêu `subject` thì nó đọc chỉ mục Toán. Đây chỉ là trang xem của giáo viên; buổi học không đi qua đường này, môn của buổi học luôn là môn của gói chương.

Đánh số: phiên ENG-1 (ADR-060, khung đánh giá) dùng DI-106 đến DI-117. Phiên này bắt đầu từ DI-120 để không trùng; DI-118 và DI-119 để trống.

## Cách kiểm

- `tests/test_rag_subjects.py` (offline, không cần Atlas hay Gemini; unit Tiếng Anh là bản giả nhỏ viết theo kiểu Unit 11 "Family time", không phải nội dung dạy thật):
  - **rò rỉ chéo hai chiều:** chỉ mục dựng từ cả hai môn và tài liệu của cả hai, có và không có chương (`None`, `""`). Câu Toán trong chỉ mục Tiếng Anh và câu Tiếng Anh trong chỉ mục Toán, ở mọi nút và ba chế độ, ra 0 chunk khác môn, kể cả đường `question`/`later_node`;
  - `RagIndex` từ chối chunk khác môn; `tag_passages` không gắn đoạn sang nút khác môn;
  - dữ liệu mới thiếu `subject` thì lỗi; document cũ không có `subject` được đọc là Toán và không bị ghi lại;
  - bộ đọc Tiếng Anh; DI-122; API (`subject` mặc định, chỉ mục Tiếng Anh, 422 khi sai môn); trace.
- **Regression Toán:** `test_mathematics_retrieves_exactly_as_before_subjects` so digest của mọi lần truy xuất trên 7 bộ câu hỏi `evals/datasets/rag-*.yaml` (260 câu × 12 cấu hình, thêm đường câu hỏi của bé và thuật ngữ ngoài chương), kèm danh sách chunk và kết quả `tag_passages` trên tài liệu lưu kiểu cũ, với `tests/golden/rag-math-before-eng2.json`. File golden được tạo từ code ở commit 565b6a0, trước thay đổi này. Kiểm thêm trên máy: snapshot đầy đủ 7 282 mục (thứ hạng, BM25, cosine của vector trigram offline, RRF, điểm cuối, độ phủ, lý do, grounded) trước và sau giống hệt từng byte; báo cáo `make eval-rag` (offline) giống hệt.
- Chưa chạy được trong phiên này (cần khóa model hoặc database thật): `make eval-rag LIVE=1`, `make eval-rag-published`, `make eval-grounded`, `make eval-hard`. Chạy ở máy local nếu muốn đối chiếu; code Toán của các đường đó chỉ đổi chữ ký (truyền `"math"`).

## Giữ nguyên

Công thức, ngưỡng và hằng số của truy xuất (DI-17, DI-50, DI-57, DI-79), prompt, chính sách dạy, chấm và mastery của Toán. Không đổi `vi_text`. Không ghi vào database nào. Cache embedding vẫn khóa theo (model, văn bản) và dùng chung giữa các môn; dùng chung như vậy không làm lẫn, vì một vector chỉ phụ thuộc vào văn bản.

## Còn mở

- Luật S1 yêu cầu lưu `subject` trong document buổi học. Thay đổi này chưa ghi trường đó vào state buổi học: môn được suy ra tất định từ gói chương đã lưu (`lesson_id`, `lesson_version`). Lưu `subject` vào state và test "client gửi `subject` không đổi được môn" thuộc task phiên Tiếng Anh.
- `DocumentRepository.list_recent` (danh sách thư viện của giáo viên) vẫn trả tài liệu mọi môn, kèm `subject`. Luật D1 muốn mọi truy vấn có `subject`; khi web có chọn môn thì thêm bộ lọc này.
- Trong bộ câu hỏi đánh giá Toán, `UNASSIGNED_DISTANCE` không được dùng tới: đoạn không gắn nút và không có ứng viên đều có điểm BM25 bằng 0. Test golden vì vậy không bắt được thay đổi của riêng hằng số này. Các hằng số còn lại có bị bắt (đã thử đổi RRF_K, DRAFT_FACTOR, GROUNDED_COVERAGE).
