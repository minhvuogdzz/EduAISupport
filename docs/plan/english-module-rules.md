# Luật bắt buộc của module Tiếng Anh (ENG)

Ngày: 12/11/2026 · Quyết định D-T13 · Trạng thái: **chủ dự án duyệt mặc định ngày 12/11/2026**

File này là **luật**; hướng đi, quyết định và các mốc nằm ở `docs/plan/plan-english-g5-my-family.md`, khung đánh giá ở `docs/adr/ADR-060-english-assessment-framework.md`. Mọi phiên làm task ENG phải tuân theo file này. Khi plan, ADR-060 hay blueprint khác với file này về một luật, file này thắng.

**Mục tiêu duy nhất của các luật dưới đây:** thêm môn Tiếng Anh mà **không làm thay đổi hành vi, công thức, ngưỡng, prompt hay kết quả eval của Toán**, và không để nội dung hai môn lẫn vào nhau.

Mỗi tầng có: **Luật** (bắt buộc) và **Cách kiểm** (test hoặc eval chứng minh luật đó). Một luật chưa có cách kiểm tự động thì PR chạm tầng đó phải thêm test kiểm nó.

Từ ngữ: "phần dùng chung" là code mà cả hai môn chạy qua (projector, `node_policy`, vòng dạy, `ai_gateway`, `session`, `rag`, `teacher_view`, `progress`, component web dùng chung). "Hành vi Toán" là mọi output quan sát được của một buổi Toán: lượt cô, sự kiện, phép chiếu mastery, kết quả RAG, prompt gửi model, giao diện.

---

## 1. Nội dung và ingest

**Luật**
- N1. Mọi tài liệu giáo viên (`TeacherDocument`), mọi item trong item bank, mọi `ChapterPackage` và `LessonPackage` mang trường `subject` (`"math"` | `"english"`). Thiếu `subject` là lỗi validate; không có giá trị mặc định ngầm. Dữ liệu Toán cũ được gán `"math"` một lần bằng migration tường minh hoặc lúc nạp, có test.
- N2. Bộ đọc Tiếng Anh là **module riêng** (ví dụ `ingest/english/…`). Không sửa nhánh xử lý, regex, ngưỡng hay output của bộ đọc Toán (`ingest/parse.py`, `plan.py`, `verify.py`, `build.py`, `theory.py`, `teaching.py`). Điểm vào chọn bộ đọc theo `subject` của tài liệu.
- N3. Item và đáp án chỉ lấy từ tài liệu chủ dự án cung cấp, kèm trang nguồn. Câu thiếu đáp án hoặc đáp án mâu thuẫn với đề thì không dạy và được liệt kê trong báo cáo ingest. Không model nào được tạo đáp án cho item assessment.
- N4. Biến thể đáp án ngoài bảng chuẩn hóa DI-110 chỉ thêm khi chủ dự án duyệt.

**Cách kiểm**
- Test validate: gói/tài liệu/item thiếu `subject` bị từ chối.
- Test golden ingest Toán: chạy bộ đọc Toán trên các tài liệu mẫu đã ghi sẵn, output giống hệt trước PR (`make item-bank`, `make teaching-plan` trên fixture; `make eval-items` không đổi).
- Test bộ đọc Tiếng Anh trên fixture giáo án Tiếng Anh thật: mọi đáp án truy về trang nguồn; câu thiếu đáp án nằm trong báo cáo, không nằm trong gói.

## 2. RAG

**Luật**
- G1. **Chỉ mục tách theo môn, lọc khi dựng**: mỗi môn một `RagIndex` (BM25, vector, đồ thị). Không dựng một chỉ mục chung rồi chỉ lọc lúc truy xuất.
- G2. `subject` bắt buộc ở mọi `Chunk` và mọi đoạn tra cứu. Chunk thiếu `subject` làm việc dựng chỉ mục báo lỗi, không được bỏ qua im lặng.
- G3. Truy xuất nhận `subject` từ ngữ cảnh buổi học và chỉ đọc chỉ mục của môn đó. Chunk có `chapter_id` rỗng hoặc chưa gắn node (`UNASSIGNED_DISTANCE`) **chỉ được xét trong môn của nó**.
- G4. Tokenizer theo môn: Toán giữ `core/vi_text`; Tiếng Anh dùng tokenizer riêng. Không sửa `vi_text` vì Tiếng Anh.
- G5. Cache embedding dùng chung được (khóa theo nội dung), vì vector không mang môn; nhưng kết quả truy xuất không được cache chung giữa hai môn.
- G6. Không tự nạp trang web vào RAG của môn nào (BRAIN-7).

**Cách kiểm**
- Test dựng chỉ mục: chunk thiếu `subject` → lỗi; chỉ mục Toán không chứa chunk `english` và ngược lại.
- Test truy xuất: chunk Tiếng Anh `chapter_id = ""` không bao giờ xuất hiện khi truy xuất trong môn Toán, và ngược lại.
- Eval rò rỉ chéo hai chiều (mục 11): 0 chunk khác môn ở top-k.
- `make eval-rag` và `make eval-rag-published` của Toán: chỉ số giống hệt trước PR.

## 3. Session và policy

**Luật**
- S1. `subject` là một phần của ngữ cảnh buổi học (SessionContext, blueprint PART 24), do **backend đặt** từ gói chương/unit mà buổi học chạy, lưu trong document buổi học. Client không gửi, không chọn, không đổi `subject` (giống quy tắc 4 của `CLAUDE.md` về model). Request có `subject` từ client bị bỏ qua hoặc từ chối.
- S2. Vòng dạy 6 bước (ADR-059), `node_policy` và luật `N-*` **dùng chung**. Khác biệt giữa hai môn đến từ **dữ liệu** (gói unit, item, gợi ý, `pass_rule`) và **cấu hình theo môn** (policy, prompt, bộ chấm), không từ nhánh `if subject == "english"` rải trong policy.
- S3. Nếu cần một luật policy riêng cho Tiếng Anh, nó là luật mới có tên riêng, chỉ bật bằng cấu hình của môn Tiếng Anh, và không đổi thứ tự hay ngưỡng của luật Toán.
- S4. Buổi Toán đã lưu (không có `subject`) được hiểu là Toán khi đọc lại; không ghi lại document cũ.

**Cách kiểm**
- Test API: tạo buổi học với `subject` do client gửi không làm đổi môn; buổi học của unit Tiếng Anh có `subject = "english"` trong state.
- Test chống quên truyền `subject` (mục 11): mọi lời gọi RAG, prompt, bộ chấm, web lookup, Whisper, TTS trong một buổi đều nhận `subject` từ ngữ cảnh; thiếu thì lỗi chứ không rơi về Toán.
- Replay buổi Toán cũ: state và lượt cô giống hệt trước PR.

## 4. Prompt và validator

**Luật**
- P1. Prompt có bộ riêng cho từng môn (`constitution-en`, `listener-en`, `curriculum-check-en`...). Không thêm điều kiện "nếu là Tiếng Anh" vào prompt Toán. Prompt Toán giữ nguyên tên file và version.
- P2. Prompt Tiếng Anh không chứa luật hay thuật ngữ Toán (số thập phân, phân số, diện tích, phép tính...); prompt Toán không chứa luật hay câu đích Tiếng Anh.
- P3. Validator theo môn: lời cô trong buổi Tiếng Anh bị chặn nếu chứa thuật ngữ Toán của danh sách chặn, và ngược lại. Validator lộ đáp án của Tiếng Anh hiểu câu lẫn Việt–Anh (ADR-060, DI-108). Validator Toán không đổi.
- P4. Câu hỏi lệch môn (hỏi Toán trong buổi Tiếng Anh và ngược lại) được xử lý như `OFF_TOPIC`: không trả lời bằng nội dung môn kia, cô đưa con về bài. Không tính là lượt trả lời, không chấm, không đổi mastery.
- P5. Prompt gửi Groq ≤ 3.000 token và `reasoning_effort` đúng từng model, như Toán.

**Cách kiểm**
- Test: dựng prompt buổi Tiếng Anh, không có từ nào trong danh sách thuật ngữ Toán; dựng prompt buổi Toán, giống hệt trước PR (so chuỗi).
- Test validator: lời cô Tiếng Anh có "số thập phân" bị từ chối; lời cô Toán có "This is my mother" bị từ chối.
- Test học sinh mô phỏng: câu Toán trong buổi Tiếng Anh cho `OFF_TOPIC`, không có `ITEM_RESOLVED` hay evidence mới.
- Eval regression prompt Toán (quy tắc 7): `make eval-hard`, `make eval-grounded` không đổi.

## 5. Chấm và mastery

**Luật**
- M1. Bộ chấm Tiếng Anh (`assessment/english_checker.py`) **tách khỏi** `MathChecker`. Không sửa `math_checker.py`, `vi_numbers.py`, `vi_words.py`, `misconception_rules.py` vì Tiếng Anh.
- M2. Projector **dùng chung**; mọi khác biệt nằm trong một `MasteryPolicy` riêng của Tiếng Anh có version riêng (`node-mastery-en/…`) và trong nhãn (mã lỗi, mã hiểu lầm) theo môn. Projector chọn policy theo `subject` của gói chương.
- M3. **Không đổi** công thức, trọng số, ngưỡng hay `MASTERY_POLICY_VERSION` (`node-mastery/0.3.0`) của Toán. Thêm thành viên enum (ví dụ `ErrorClass.L1`) được, với điều kiện policy Toán không dùng nó.
- M4. Đọc `asr_confidence` (DI-109) chỉ khi policy Tiếng Anh bật luật đó; policy Toán bỏ qua.
- M5. LLM không chấm đúng/sai câu Tiếng Anh và không ghi mastery (quy tắc 1, 3 của `CLAUDE.md`).

**Cách kiểm**
- Test golden: phép chiếu Toán trên mọi replay cố định giống byte-for-byte trước PR.
- Test golden Tiếng Anh: cùng event log → cùng `ChapterProjection`.
- Test từng dòng bảng lỗi DI-107 và chuẩn hóa DI-110.
- Test: không evidence nào của buổi Tiếng Anh rơi vào node Toán và ngược lại (0 mastery sai môn).

## 6. Event

**Luật**
- E1. Chỉ **thêm loại sự kiện mới** cho nhu cầu của Tiếng Anh (ví dụ `VOICE_TURN_RECORDED` mang `audio_ref`, `asr_confidence`, ngôn ngữ nhận dạng, gắn với lượt nói). Không xóa, không đổi tên, không đổi nghĩa trường của loại sự kiện đã có.
- E2. Trường đã có nhưng chưa dùng (`ItemResolved.modality`, `ItemResolved.asr_confidence`) được điền cho buổi mới; nghĩa không đổi.
- E3. Replay event log cũ của Toán cho cùng state và cùng phép chiếu. Event log append-only (quy tắc 3).

**Cách kiểm**
- Test replay các buổi Toán đã ghi sẵn trong test: state và projection không đổi.
- Test schema: loại sự kiện mới có test parse; event cũ vẫn parse như trước.

## 7. Giọng nói

**Luật**
- V1. Ngôn ngữ Whisper và giọng TTS được chọn theo **môn và bước** bởi backend. Buổi Toán giữ đúng mặc định hiện tại (`language="vi"`, giọng cô VieNeu hiện có).
- V2. Buổi Tiếng Anh: câu đích → `en`; hỏi đáp, "vì sao" → tự nhận dạng (plan, R-VOICE).
- V3. Audio vẫn ở `var/storage/` (gitignore); không vào database, không vào `db-dump`, không gửi ra ngoài trừ Whisper qua `ai_gateway`.
- V4. Không chấm phát âm theo âm vị; không thêm dịch vụ chấm phát âm.

**Cách kiểm**
- Test với gateway giả (`ai_gateway/fake.py`): buổi Toán gọi transcribe với `vi`; buổi Tiếng Anh ở bước câu đích gọi với `en`.
- Test `voice/api.py` của Toán: response và tệp lưu như trước PR.

## 8. API và frontend

**Luật**
- F1. Route và feature của Tiếng Anh tách riêng (API: tham số `chapter` trỏ tới unit hoặc tiền tố riêng; web: `features/english/` và route `/…/english`). Không đổi URL hay response của route Toán đang có, trừ thêm trường tùy chọn.
- F2. Trang giáo viên/phụ huynh **dùng chung component** (`StudentReportPage`, `ClassPage`, `ParentPages`, `analytics/*`), nhưng nhãn chiều, cây tri thức, tên hiểu lầm, chữ giải thích (`Method`) lấy theo môn từ dữ liệu/API. Không gắn cứng chữ "Toán", "khung Toán §…", tên chương Toán ở chỗ dùng chung; chỗ đang gắn cứng phải chuyển sang lấy theo môn khi PR chạm tới nó.
- F3. Client không chọn model, môn hay policy (quy tắc 4).
- F4. Phụ huynh không thấy điểm M, transcript hay audio (PART 27.4, ADR-060).
- F5. Endpoint nghe lại audio chỉ dành cho giáo viên và lọc `school_id`.

**Cách kiểm**
- `make web-check` xanh; test web Toán không đổi snapshot/nội dung.
- Test web: trang dùng chung với dữ liệu Tiếng Anh không hiện chữ "Toán"; với dữ liệu Toán hiện như trước.
- Test API: endpoint audio từ chối học sinh, phụ huynh và giáo viên trường khác.

## 9. Cấu hình

**Luật**
- C1. Biến môi trường mới cho Tiếng Anh có tiền tố hoặc phạm vi môn (ví dụ `ENGLISH_WEB_LOOKUP`, `ENGLISH_MAX_LLM_CALLS_PER_UNIT`). Biến đang có (`WEB_LOOKUP`, `MAX_LLM_CALLS_PER_SESSION`, `MAX_LLM_CALLS_PER_CHAPTER`, `TUTOR_MODELS`, `TUTOR_CHOOSER`...) giữ đúng nghĩa và mặc định cho Toán. Bật tra cứu web cho Tiếng Anh không làm đổi hành vi Toán.
- C2. Ngân sách model call và quota được đếm riêng theo môn trong một buổi; buổi Tiếng Anh không tiêu ngân sách của buổi Toán.
- C3. Biến mới được ghi vào `services/api/.env.example` kèm mặc định và chú thích.

**Cách kiểm**
- Test cấu hình: đặt `ENGLISH_WEB_LOOKUP=off` không làm đổi tra cứu của buổi Toán, và ngược lại `WEB_LOOKUP` không đổi buổi Tiếng Anh nếu biến Tiếng Anh đã đặt.
- Test ngân sách: hết ngân sách ở buổi Tiếng Anh không ảnh hưởng buổi Toán.

## 10. Dữ liệu

**Luật**
- D1. Mọi document dữ liệu người học và nội dung có `school_id` (quy tắc 5) **và** `subject`. Repository lọc cả hai; truy vấn thiếu một trong hai là lỗi.
- D2. Document cũ không có `subject` được đọc là `"math"`; không ghi đè hàng loạt nếu không có migration tường minh được chủ dự án đồng ý.
- D3. Mọi quy tắc database 11–25 của `CLAUDE.md` giữ nguyên (tách `cavat_test`, không seed tự động, `is_demo`).

**Cách kiểm**
- Test repository in-memory: truy vấn buổi học/tài liệu của môn này không trả về document của môn kia; truy vấn thiếu `subject` báo lỗi.
- Test Atlas (nếu có) theo quy tắc 12–14.

## 11. Kiểm thử bắt buộc mỗi PR Tiếng Anh

1. `make lint`, `make test` xanh (offline).
2. **Regression Toán giữ nguyên kết quả**: `make eval-hard`, `make eval-rag`, `make eval-rag-published`, `make eval-grounded` (những eval chạy được offline trong phiên), cùng test golden replay/projection của Toán. Ghi số trước/sau vào mô tả PR. Eval cần khóa model mà phiên không có thì ghi rõ "chưa chạy, cần chạy ở máy local".
3. **Eval rò rỉ chéo hai chiều**: câu Toán trong phiên Tiếng Anh và câu Tiếng Anh trong phiên Toán → 0 chunk khác môn ở top-k, 0 prompt chứa nội dung môn kia, 0 evidence/mastery ghi sang môn kia (DI-116).
4. **Test chống quên truyền `subject`**: mọi đường RAG, prompt, chấm, web lookup, giọng nói lấy `subject` từ ngữ cảnh buổi học; thiếu thì lỗi.
5. `make web-check` nếu PR chạm `apps/web`.

## 12. Quy trình

- Mỗi task một nhánh `task/ENG-<n>-<tên-ngắn>` và một PR vào `main`; CI xanh trước khi gộp.
- PR chạm **phần dùng chung** với Toán phải có mục "Ảnh hưởng tới Toán" trong mô tả: liệt kê file dùng chung đã sửa, vì sao, và kết quả regression Toán.
- Đổi prompt, policy hay mastery policy của Tiếng Anh phải tăng version và chạy eval (quy tắc 7).
- DI mới đánh số tiếp từ DI-117; quyết định kiến trúc mới thành ADR.
- Mỗi PR có mục "Ghi chép luận văn" (quy tắc trong `CLAUDE.md`).

## 13. Definition of done (copy vào mô tả PR)

```markdown
### Checklist english-module-rules.md
- [ ] Nhánh `task/ENG-…`, một task, một PR
- [ ] Mọi tài liệu/item/gói/chunk/document mới có `subject` (và `school_id` với dữ liệu người học); thiếu là lỗi
- [ ] `subject` do backend đặt trong ngữ cảnh buổi học; client không chọn được
- [ ] RAG: chỉ mục theo môn, lọc khi dựng; chunk chưa gắn node chỉ xét trong môn của nó
- [ ] Prompt/validator theo môn; prompt Toán không đổi (so chuỗi); câu lệch môn là OFF_TOPIC
- [ ] Bộ chấm Tiếng Anh tách khỏi MathChecker; mastery policy Toán `node-mastery/0.3.0` không đổi
- [ ] Event: chỉ thêm loại mới; replay Toán cũ không đổi
- [ ] Giọng nói: mặc định của Toán không đổi
- [ ] Web: component dùng chung không gắn cứng chữ Toán; phụ huynh không thấy M/transcript/audio
- [ ] Cấu hình mới có tiền tố môn; ngân sách model call tính riêng
- [ ] `make lint`, `make test` xanh
- [ ] Regression Toán: số trước/sau giống nhau (ghi lệnh và kết quả)
- [ ] Eval rò rỉ chéo hai chiều = 0 (chunk, prompt, mastery)
- [ ] Test chống quên truyền `subject`
- [ ] Mục "Ảnh hưởng tới Toán" (nếu chạm phần dùng chung)
- [ ] Mục "Ghi chép luận văn"
```
