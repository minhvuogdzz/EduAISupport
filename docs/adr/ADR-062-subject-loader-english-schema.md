# ADR-062: Bộ nạp nội dung theo môn và schema Tiếng Anh (ENG-3b)

Ngày: 13/11/2026 · DI-124, DI-125, DI-126, DI-127 · **Infrastructure/data-safety change** (quy tắc 25: đổi cách chọn nội dung theo môn)

ENG-3 (PR #141) đưa Unit 11 "Family time" vào `docs/pedagogy/english-g5/` nhưng đặt tên `unit.yaml` / `lesson-N-….yaml` để bộ nạp bỏ qua, vì bộ nạp lúc chạy tự nạp mọi `chapter.yaml` / `lesson.yaml` dưới `docs/pedagogy` mà không theo môn (README của unit, khoảng trống G0). Câu trả lời tiếng Anh dùng tạm `open` + `facts.phrases`, nguồn và trạng thái đáp án nằm ngoài schema (`sources.yaml`), lỗi chưa có lớp DI-107. ADR này mở bộ nạp theo môn, thêm schema Tiếng Anh, và đưa Unit 11 về dạng chuẩn. Luật áp dụng: `docs/plan/english-module-rules.md` (N1, N3, S1, F1, M1, M3).

## Khảo sát: mọi chỗ nạp gói chương/bài

| Chỗ | Trước | Sau |
|---|---|---|
| `session/chapter_service.chapter_sources()` (glob `**/chapter.yaml`) | mọi file, mọi môn | `all_chapter_sources()` (mọi môn, trùng mã chương là lỗi) + `chapter_sources(subject="math")` |
| `chapter_service.chapters()` (file + kế hoạch giáo viên đã xuất bản) | mọi chương | `chapters(subject="math")`; kế hoạch đã xuất bản cũng lọc theo `package.subject`; `all_chapters()` cho RAG |
| `chapter_service.chapter_for(id, version)` (replay buổi học) | mọi chương | `chapter_for(id, version, subject="math")` |
| `session/service.lesson_packages()` (glob `**/lesson.yaml`, kế hoạch bài 1 cố định) | mọi file | `all_lesson_packages()` + `lesson_packages(subject="math")` |
| Người gọi: `session/api.py` (tạo buổi, xem buổi, tổng quan học sinh/phụ huynh, lớp, `taught-chapters`, `_summaries`), `RagService` | thấy mọi chương | không đổi dòng nào, nên nhận Toán. Riêng `RagService` nhận `all_chapters` và tự tách chỉ mục theo môn (ADR-061) |
| Trang duyệt phương án dạy của giáo viên: `library/api.py` `GET /v1/teachers/chapters`, `/chapters/{id}` | mọi chương | `?subject=` (mặc định `math`, sai môn 422); chi tiết tìm theo mã trong mọi môn (mã chương là duy nhất); thêm trường `subject`; câu Tiếng Anh có thêm nguồn, trạng thái đáp án, duyệt, ngôn ngữ, `kind`; lỗi có `error_class` |
| Upload tài liệu (`document_subject`) | mọi chương | mọi môn (để biết môn của chương được chọn, như ADR-061) |
| `ingest/teaching.py` (dựng kế hoạch từ tài liệu Toán) | luôn `subject="math"` | không đổi |
| Script đánh giá, test | nạp đường dẫn file Toán trực tiếp | không đổi |

Web chưa đổi: trang duyệt của giáo viên vẫn gọi `/v1/teachers/chapters` không tham số, nên vẫn chỉ thấy Toán. Chọn môn trên web là ENG-7.

## Quyết định

1. **Bộ nạp đọc `subject` của từng file và chỉ trả gói của môn được hỏi.** Mọi hàm nạp nhận `subject`; mặc định là Toán (DI-124), nên mọi đường gọi có từ trước (đều là Toán) nhận đúng các gói như trước. Hai file cùng mã chương hoặc cùng mã bài là lỗi lúc nạp, không để một file che file kia. Một chương không được trộn môn: lesson khác môn với chương làm `load_chapter` báo lỗi, `validate_chapter` cũng báo.
2. **`ChapterPackage.subject`** đã là `Literal["math","english"]` bắt buộc từ ENG-2. [FACT] Mọi gói Toán, cả file lẫn kế hoạch đã xuất bản (`ingest/teaching.py` luôn ghi `"math"`, schema chương bắt buộc trường này từ PR #25, schema bài từ PR #3), đều có `subject`. Vì vậy gói không cần luật "thiếu là Toán" như tài liệu giáo viên (DI-120): gói thiếu `subject`, cũ hay mới, đều bị từ chối (luật N1).
3. **Schema Tiếng Anh** (`content/lesson_package.py`), theo hợp đồng chung với ENG-4. Mọi trường mới là tùy chọn với Toán; với gói `subject: english`, `validate_package` bắt buộc:
   - `PhraseAnswer` (`type: phrase`): `accept: list[str]`, `required: list[list[str]]`, `normalize: "en-vi/1"`, `wrong_answers: dict[str, str]`, `allow_name: bool = False` (DI-125).
   - `WordOrderAnswer` (`type: word_order`): `tokens: list[str]`, `accept: list[list[str]]`.
   - `Item`: `source: {doc, page, ref}`, `answer_source: {doc, page, ref}` (thêm ngoài hợp đồng, xem DI-126), `origin: BOOK | AUTHORED`, `answer_status: VERIFIED_SGV | FROM_TEXT | AUTHORED | NO_ANSWER`, `review: {status: PENDING | APPROVED | REJECTED, reviewed_by, reviewed_on}`, `response_language: en | vi | either`, `kind: say_after_me`.
   - `Misconception.error_class`: một mã lỗi tiếng Anh của DI-107 (`EN_SHORT_ANSWER`, `EN_TENSE`, `EN_MEANING`, `EN_STRUCTURE`, `EN_VERB_FORM`, `EN_SLIP`, `EN_PRONUNCIATION`, `EN_L1`).
4. **Validator gói** (không chấm gì): `phrase` phải có ít nhất một `accept` hoặc một nhóm `required`, không chuỗi rỗng; `word_order` có ít nhất hai token, mỗi thứ tự chấp nhận là hoán vị đúng của `tokens`; `wrong_answers` của `phrase` trỏ tới hiểu lầm có trong bài; luật nguồn và duyệt của DI-126; luật `say_after_me` (DI-108: chỉ ở `completion` của nút, trả lời `en`).
5. **Không viết logic chấm và không sửa `assessment/`.** Chấm `phrase` và `word_order` chờ ENG-4. Hiện `MathChecker._check_spec` gặp kiểu lạ thì `TypeError` khi chấm; việc nạp và validate không chạm tới nó, và chưa có đường API nào mở buổi học Tiếng Anh (test kiểm), nên không có lần chấm nào xảy ra.
6. **Unit 11 về dạng chuẩn:** `chapter.yaml` trong thư mục unit, mỗi bài một thư mục con có `lesson.yaml` (giống Toán: chương trỏ tới bài bằng đường dẫn tương đối). 23 câu `open` có câu trả lời tiếng Anh thành `phrase`: `accept` là đúng câu mẫu đã duyệt, `required` là đúng các nhóm `facts.phrases` cũ, nên không thêm biến thể nào (luật N4). `wrong_answers` chỉ gồm câu sai mà mô tả hiểu lầm đã viết sẵn. 5 câu mức C trả lời bằng tiếng Việt giữ `open`. Mọi câu có nguồn, nguồn gốc, trạng thái đáp án, ngôn ngữ trả lời; 20 câu `AUTHORED` ghi duyệt của chủ dự án ngày 13/11/2026; 3 câu nói theo cô có `kind: say_after_me`. Version chương và bài lên 0.2.0. `sources.yaml` giữ danh sách bài của sách (kể cả bài không thành câu) và bảng tổng hợp câu; một test kiểm bảng này khớp với các file bài.

## Các DI

- **DI-124 (môn mặc định của đường gọi không nêu môn là Toán):** mọi buổi học, trang và danh sách có trước Tiếng Anh đều là Toán, nên hàm nạp không nhận môn thì trả Toán. Tiếng Anh chỉ tới được khi gọi rõ `subject="english"`. Tương tự DI-123 (trang RAG của giáo viên). Đây không phải "rơi về Toán" khi thiếu dữ liệu: môn lạ hoặc rỗng là lỗi (`check_subject`), và gói thiếu `subject` vẫn bị từ chối. Khi buổi học lưu `subject` (luật S1, task phiên Tiếng Anh), đường gọi của buổi học truyền môn đã lưu; buổi học cũ không có trường đó là Toán (luật S4).
- **DI-125 (nghĩa dữ liệu của `phrase` và `word_order`; dạng câu hỏi):** câu trả lời `phrase` là đúng khi, sau chuẩn hóa `en-vi/1` (DI-110), nó là một câu trong `accept`, hoặc khi `required` không rỗng và mỗi nhóm có ít nhất một cách nói xuất hiện trong câu trả lời. Khóa của `wrong_answers` là câu sai viết như học sinh sẽ nói; cách so (ranh giới từ, nguyên câu hay chứa trong câu) do bộ chấm ENG-4 khai báo trong DI-110. `allow_name`: tên riêng học sinh tự thêm (nơi chốn, người nhà) không làm câu sai. `word_order` đúng khi thứ tự học sinh đưa ra là một phần tử của `accept`. Ở gate UNDERSTOOD và pass rule, `phrase` và `word_order` là hai "dạng câu hỏi" riêng (DI-106 gọi là `phrase`, `order`), khác `open`.
- **DI-126 (nguồn, trạng thái đáp án và duyệt):** câu sách (`origin: BOOK`) ghi trang của câu (`source`) và có `answer_status` là `VERIFIED_SGV` hoặc `FROM_TEXT`; đáp án `VERIFIED_SGV` phải ghi trang SGV có đáp án (`answer_source`, thêm ngoài hợp đồng vì câu và đáp án thường ở hai sách khác nhau, để mọi đáp án truy về trang nguồn theo luật N3). Câu `origin: AUTHORED` có `answer_status: AUTHORED` và chỉ được dạy khi `review.status = APPROVED`, có người và ngày duyệt; chưa duyệt thì validator báo lỗi. `NO_ANSWER` có trong enum để ghi bài của sách, nhưng một câu `NO_ANSWER` trong gói là lỗi (luật N3: không dạy câu thiếu đáp án). `response_language`: `en` câu đích tiếng Anh, `vi` câu giải thích mức C, `either` câu chọn nghĩa mức A (ADR-060 mục 5: trả lời tiếng Việt là đúng thể thức) và câu tìm lỗi. Với gói Tiếng Anh, `origin`, `answer_status`, `response_language` là bắt buộc.
- **DI-127 (lớp lỗi của hiểu lầm Unit 11):** `error_class` lấy theo ví dụ của chính bảng DI-107: M03 ("Yes, I do") `EN_SHORT_ANSWER`; M04, M07, M11 (kể chuyện đã qua bằng nguyên mẫu) `EN_TENSE`; M05 ("taked", "eated") `EN_VERB_FORM`; M01, M02, M08 (thiếu did, did + quá khứ) `EN_STRUCTURE`; M06, M09, M12 (nhầm nghĩa, trả lời lệch câu hỏi) `EN_MEANING`. M10 (chọn nhấn vào từ chức năng) là `EN_STRUCTURE`: đó là chọn sai mẫu nhịp, mẫu đích của nút STRESS, chứ không phải lỗi phát âm (`EN_PRONUNCIATION` là "không phải lỗi" nên sẽ làm câu chọn sai thành không bị tính). Cột "mã gần nhất" cũ trong README (phần lớn `EN_STRUCTURE`) được thay. Ánh xạ mã sang `ErrorClass` chung của projector theo nút là việc của ENG-4.

Đánh số: ENG-1 dùng DI-106 đến DI-117, ENG-2 dùng DI-120 đến DI-123. Bốn phiên chạy song song chia dải: ENG-3b DI-124 đến DI-127, ENG-4 DI-128 đến DI-131, ENG-6 DI-132 đến DI-135, ENG-5a DI-136 đến DI-139.

## Cách kiểm

- `services/api/tests/test_subject_content.py` (offline, bộ nhớ):
  - đường gọi không nêu môn chỉ nhận chương `math-g5-decimals` và hai bài Toán; Tiếng Anh chỉ nhận Unit 11; `chapter_for` không trả chương khác môn; môn lạ là lỗi; kế hoạch đã xuất bản ở lại đúng môn; RAG thấy cả hai môn nhưng dựng mỗi chỉ mục từ môn của nó;
  - cây `docs/pedagogy` giả có một chương mỗi môn: lọc đúng theo `subject` ghi trong file; hai file trùng mã chương là lỗi;
  - gói mới thiếu `subject` bị từ chối; chương trộn môn bị từ chối;
  - API: `POST /v1/sessions` với mã unit hoặc mã bài Tiếng Anh trả 404; tổng quan học sinh với `?chapter=` unit Tiếng Anh trả 404; `taught-chapters` và danh sách chương của học sinh chỉ có Toán; trang duyệt của giáo viên liệt kê Unit 11 khi `?subject=english`, chi tiết có nguồn/duyệt/`error_class`, câu Toán không có trường mới;
  - validator: `phrase` rỗng, nhóm rỗng, hiểu lầm không có, `normalize` lạ; `word_order` sai token; câu `AUTHORED` chưa duyệt / duyệt thiếu người, ngày; câu sách thiếu trang, `VERIFIED_SGV` thiếu `answer_source`, `NO_ANSWER`; câu Tiếng Anh thiếu `origin`/`response_language`; hiểu lầm thiếu `error_class`; `say_after_me` ngoài `completion`;
  - Unit 11: sạch lỗi, thứ tự học, 47 câu đều được nút dùng, 23 `phrase`, 20 câu duyệt 13/11/2026, `sources.yaml` khớp.
- **Toán không đổi:** dump (`model_dump`, bỏ các trường mới có giá trị `None`) của chương Toán, các bài của chương, `lesson_packages()`, thứ tự học và trang duyệt của giáo viên (bỏ trường `subject` mới) giống hệt `main` (so sha256 từng phần). Toàn bộ test cũ xanh, gồm golden RAG Toán của ENG-2. `make eval-rag` (offline) cho báo cáo giống `main`, chỉ khác dòng thời gian chạy. `make teach` với cùng 73 câu trả lời gõ sẵn (79 lượt cô) cho bản ghi giống hệt `main` từng byte. `make smoke` xanh.

## Giữ nguyên

Prompt, chính sách dạy, công thức và ngưỡng mastery (`node-mastery/0.3.0`), `MathChecker` và mọi file `assessment/`, RAG và bộ đọc chữ, event, giọng nói, web. Nội dung Toán không đổi một byte.

## Còn mở

- Chấm `phrase`/`word_order`, ánh xạ `error_class` sang `ErrorClass`, `MasteryPolicy` tiếng Anh: ENG-4.
- Lưu `subject` trong document buổi học và mở buổi học Tiếng Anh qua API (luật S1): task phiên Tiếng Anh (ENG-5). Khi đó đường tạo/xem buổi học truyền môn vào `chapters`/`chapter_for`.
- `response_language` trên `TheoryVariant.ask` (để chọn ngôn ngữ Whisper ở bước giảng): ENG-5/ENG-6 thêm khi cần.
- Khoảng trống G6 (tranh/âm thanh), G7 (đoạn ngữ liệu dùng chung), G9 (đánh dấu đoạn tiếng Anh cho TTS): để sau, đề xuất ở README của `english-g5` mục 6.
- Trang duyệt trên web chọn môn: ENG-7 (API đã nhận `?subject=`).
