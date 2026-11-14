# ADR-063: Bộ chấm Tiếng Anh tất định và mastery policy `node-mastery-en/0.1.0` (ENG-4)

Ngày: 14/11/2026 · Task ENG-4 · DI-128 đến DI-131 · Trạng thái: **chủ dự án duyệt mặc định** (như ADR-060; sửa đổi đi qua ADR mới hoặc mục Revision của file này).

- Dựa trên: ADR-060 (khung đánh giá Tiếng Anh, DI-106–116), `docs/plan/english-module-rules.md` (luật M1–M5, E1–E3, S1), ADR-061 (bộ đọc `en-vi/1` của RAG).
- Không thay: `node-mastery/0.3.0` của Toán, `math_checker.py`, `vi_numbers.py`, `vi_words.py`, `misconception_rules.py`.

## 1. Bối cảnh

**[FACT]** ADR-060 định nghĩa bảng lỗi (DI-107), chuẩn hóa (DI-110), đúng sau mẫu (DI-108), độ tin cậy ASR (DI-109), gate và luật qua nút (DI-111) cho Unit 11 "Family time", nhưng chưa có code: chưa có bộ chấm câu tiếng Anh, projector chưa đọc `asr_confidence`, `ErrorClass` chưa có `L1`, và mọi phép chiếu đều dùng `node-mastery/0.3.0`.

**[FACT]** ENG-3b (PR #142, ADR-062) thêm vào schema `PhraseAnswer` (`phrase`), `WordOrderAnswer` (`word_order`) và `Misconception.error_class` (mã DI-107, DI-127); Unit 11 có 23 câu `phrase`, 12 hiểu lầm có `error_class`. Tên trường khớp đúng hợp đồng mà bộ chấm này viết theo.

## 2. Quyết định

### 2.1. Bộ chấm (`assessment/english_checker.py`)

- Tách khỏi `MathChecker` (luật M1), trả cùng `CheckResult` mà tutor policy đọc. Mã lỗi tiếng Anh nằm ở `detail["en_code"]` (và `en_codes`: mọi mã thấy trong câu); lớp chung ở `error_class`.
- Đầu vào là spec của chính module (`PhraseSpec`, `WordOrderSpec`); `english_spec()` đọc theo **tên trường** từ model schema, dict hay spec, nên nối với schema của ENG-3b (PR #142) không phải sửa bộ chấm; test chấm thẳng các câu Unit 11 đã nạp, qua `answer_check.check_answer`.
- `phrase`: thứ tự quyết định là (1) khớp nguyên một câu `accept` → CORRECT; (2) khớp mẫu trong `wrong_answers` → WRONG kèm mã hiểu lầm (độ tin 0,9); (3) mẫu lỗi chung (bảng mục 2.2) → WRONG với lỗi nặng nhất; (4) đủ mọi nhóm `required` (hoặc chứa nguyên một câu `accept`, DI-128) → CORRECT; (5) sửa một ký tự ở từ ≥ 5 chữ cái thì đúng → `EN_SLIP`; (6) đủ một phần các nhóm → PARTIAL; (7) câu tiếng Việt → `EN_L1`; (8) còn lại WRONG không mã.
- `word_order`: đúng một thứ tự `accept` → CORRECT; đủ đúng các từ nhưng sai thứ tự → `EN_STRUCTURE`; còn lại như `phrase` (mẫu lỗi, slip, L1).
- Mọi so khớp trên chuỗi đã chuẩn hóa và **theo ranh giới từ** ("ate seafood" không khớp "late seafood" hay "ate seafoods").
- Trước khi chấm, lời không phải câu trả lời ("con không biết", "cô nói lại", im lặng) được đọc bằng `student_intent.read_intent` như Toán.
- Gói phải có `subject = "english"`; đáp án tiếng Anh trong gói Toán là lỗi, không rơi về Toán (luật S1).

### 2.2. Mẫu lỗi chung (DI-107, DI-129)

| Mã | Mẫu bộ chấm nhận ra | Lớp |
|---|---|---|
| `EN_SHORT_ANSWER` | Item đợi "Yes, I did/No, I didn't" mà con nói "Yes, I do / will / am…", "No, I don't" | CONCEPTUAL |
| `EN_TENSE` | Câu kể việc đã qua (đáp án có động từ quá khứ) mà con dùng chủ ngữ + động từ hiện tại ("We eat seafood", "My family eat…") | CONCEPTUAL |
| `EN_MEANING` | Chỉ qua `wrong_answers` (cặp cụm dễ nhầm do giáo viên liệt kê) | CONCEPTUAL |
| `EN_STRUCTURE` | Câu hỏi có "did" mà động từ ở quá khứ ("Did you bought…?"); quên "did" hoặc dùng "do" ("What your family do…?", "You buy souvenirs?", "Do you swim yesterday?"); sai trật tự ở `word_order` | PROCEDURAL ở nút dạy mẫu đó, FORMAT ở nút khác |
| `EN_VERB_FORM` | Thêm -ed cho động từ có dạng quá khứ riêng ("buyed", "eated", "tooked") | PROCEDURAL / FORMAT như trên |
| `EN_SLIP` | Sai một ký tự ở từ ≥ 5 chữ cái mà sửa lại thì đúng ("grandmoter") | FORMAT |
| `EN_L1` | Câu trả lời bằng tiếng Việt | L1 |

`EN_PRONUNCIATION` không phải lỗi: bộ chấm chấm bản chép lời đã xác nhận. Bảng động từ bất quy tắc dùng chung với RAG, chuyển nguyên văn từ `rag/analyzers.py` sang `core/en_text.py`.

### 2.3. Projector: một projector, hai policy

- `ErrorClass.L1` thêm vào `core/pedagogy.py`; Toán không ghi nó.
- `MasteryPolicy` thêm các trường mặc định "tắt" (`subject="math"`, `completion_max_independence=None`, `asr_threshold=None`, `voice_low_forms=∅`). Với Toán mọi nhánh mới không chạy, phép tính giữ nguyên thứ tự (golden byte-for-byte, mục 4).
- `ENGLISH_POLICY` (`node-mastery-en/0.1.0`): giữ mọi số của Toán; `error_scores = {FORMAT: 0,7, L1: 0,3}`; cùng làm tối đa độc lập H6 (0,20, DI-108); ngưỡng ASR 0,6 và hệ số 0,3 (DI-109); `voice_low_forms = {phrase, word_order}` (DI-109 điểm 7).
- `project_chapter(events, chapter)` không truyền policy thì chọn theo `chapter.package.subject` (`policy_for`); truyền policy khác môn thì báo lỗi. `TeachingLoop` mặc định cũng chọn theo môn.
- DI-111 không cần số mới: thành công đã loại item cùng làm, đúng sau H4 trở lên; thêm loại câu nói nghe chưa rõ. "Dạng câu hỏi" là `answer.type` (đã đúng từ trước, DI-106).

## 3. DI mới

**DI-128 (chi tiết chuẩn hóa `en-vi/1` của bộ chấm, bổ sung DI-110):**
1. Chỉ 8 dạng rút gọn của DI-110 được viết đầy đủ; dấu nháy khác bị bỏ trong từ ("don't" → "dont"), nên không có biến thể ngoài bảng được nhận nhầm (luật N4). Dấu nháy cong được coi như nháy thẳng.
2. "yes"/"no" đầu câu bị bỏ khi item không hỏi có/không, **có hay không có dấu phẩy** (bản chép lời giọng nói thường thiếu dấu). Item hỏi có/không khi một đáp án chấp nhận bắt đầu bằng "yes"/"no".
3. Lời lễ phép tiếng Việt ở đầu ("dạ", "thưa cô", "cô ơi") và cuối ("ạ", "cô ơi") không thuộc câu trả lời.
4. Câu chứa nguyên một đáp án chấp nhận (theo ranh giới từ) kèm từ khác ("We ate seafood in Nha Trang") là đúng khi item không có `required`; khi có `required` thì đủ mọi nhóm là đúng. Lỗi chung trong câu vẫn được xét trước.
5. `allow_name`: một dãy từ viết hoa nằm giữa câu của đáp án (không phải từ đầu câu, không phải "I") là chỗ trống tên, nhận 1–3 từ không thuộc danh sách từ ngữ pháp/thời gian ("in the summer" không là tên).
6. Tên bộ chuẩn hóa trong spec (`normalize`) phải là `en-vi/1`; tên khác báo lỗi. Bộ đọc RAG cùng họ `en-vi/1` mở rộng nhiều dạng hơn vì truy xuất cần độ phủ; chấm thì không.
7. **Đáp án trích lỗi nó sửa** (câu DIAG: "Eated sai, phải là ate: …"): một mẫu `wrong_answers` hay một mẫu lỗi chung mà chính đáp án chấp nhận cũng chứa là trích dẫn, không phải lỗi, khi câu trả lời đã đủ ý đúng. "eated" một mình vẫn là lỗi M05.

**DI-129 (mẫu lỗi chung và lớp lỗi theo nút):**
1. Các mẫu ở bảng 2.2 áp cho mọi item; mẫu do giáo viên ghi trong `wrong_answers` thắng mẫu chung và mang mã hiểu lầm của nó.
2. `EN_STRUCTURE`/`EN_VERB_FORM` là PROCEDURAL khi nút của item có hiểu lầm mang `error_class` đó (nút "dạy" mẫu này), FORMAT khi không. Khi gói chưa có `error_class` cho hiểu lầm nào (nội dung hiện tại), coi là PROCEDURAL (chặt hơn).
3. Mã hiểu lầm cho lỗi chung lấy từ hiểu lầm cùng `error_class` của nút item, độ tin 0,7 (CONCEPTUAL) hoặc 0,5 (PROCEDURAL). Luật "ghi hiểu lầm khi lặp ≥ 2 lần" của DI-107 (M04, M05 theo ADR-060) là việc của vòng dạy (ENG-5), không phải bộ chấm.
4. Câu tiếng Việt: có chữ cái tiếng Việt có dấu, hoặc ≥ 2 âm tiết tiếng Việt không dấu thường gặp và chiếm ≥ nửa câu. Lần đầu trả `UNPARSEABLE` + lớp `L1` (không chấm, cô mời nói tiếng Anh); điểm 0,3 chỉ áp khi item đóng với `final_error_class = L1`.

**DI-130 (ASR trong `node-mastery-en/0.1.0`, cài đặt DI-109):**
1. Chỉ đọc khi policy có `asr_threshold` (Tiếng Anh). Câu trả lời `VOICE` là "nghe chưa chắc" khi `asr_confidence < 0,6`, khi **không có** `asr_confidence` (trước ENG-6, hoặc adapter không trả), hoặc khi kiểu đáp án nằm trong `voice_low_forms` (DI-109 điểm 7).
2. Nghe chưa chắc và đúng: evidence ANSWER và INDEPENDENCE nhân 0,3, không là thành công.
3. Nghe chưa chắc và sai/không chấm: không evidence, không hiểu lầm, không tăng số item; chỉ một dòng evidence trọng số 0, lý do `ASR_UNCERTAIN`, không làm đổi điểm, confidence hay trace.

**DI-131 (cùng làm và chọn policy):**
1. Mọi item `completion` của nút tiếng Anh (gồm "nói theo cô") có độc lập tối đa 0,20 (H6), trọng số theo DI-5 với sàn 0,3, rồi × 0,5. Item cùng làm của Toán giữ độc lập theo bậc gợi ý.
2. Policy chọn theo `subject` của gói chương; dùng policy khác môn là lỗi.

## 4. Kiểm chứng

- Golden Toán `tests/golden/math-projection-before-eng4.json` ghi trên `6ac53b9` (commit đầu của nhánh, trước khi sửa code): 7 học sinh mô phỏng qua vòng dạy chương Số thập phân + 5 log tổng hợp phủ mọi nhánh projector (mọi `ErrorClass`, hiểu lầm, đoán, nhãn LLM dưới/trên 0,6, câu nói có `asr_confidence` thấp). 12/12 log chiếu lại cho SHA-256 JSON giống hệt.
- `tests/test_english_checker.py`: từng dòng DI-107, bảng DI-110, ranh giới từ, câu thật Unit 11, dispatch, Toán qua dispatch cho kết quả y hệt `math_checker.check_answer`.
- `tests/test_english_projector.py`: chọn policy theo môn, L1, DI-108 (nói theo cô, H7), DI-109/DI-130 (q cao, q thấp đúng/sai, không q, gõ phím), học sinh chỉ nói theo cô không qua nút nào, golden tiếng Anh, 0 evidence sai môn.

## 5. Hệ quả và việc còn mở

- **Schema ENG-3b đã nối** (PR #142 merge trước PR này): dispatch đọc `answer.type` của `PhraseAnswer`/`WordOrderAnswer`; `Misconception.error_class` bật DI-129 điểm 2–3; 23 câu `phrase` của Unit 11 làm DI-109 điểm 7 có hiệu lực (câu nói luôn tính là nghe chưa chắc). Chưa có câu `word_order` trong Unit 11; bộ chấm được test trên spec tự dựng.
- **Vòng dạy (ENG-5):** `item_loop` đã gọi `answer_check.check_answer`, nhưng phần quanh nó (`no_is_an_answer`, `classify_intent` lúc xác nhận, bảng `_TARGET_FOR_ERROR` của `tutor/policy.py` chưa có `L1`) vẫn của Toán; đặt `final_error_class = L1` khi item đóng bằng tiếng Việt; đếm lặp ≥ 2 lần cho M04/M05.
- **Giọng nói (ENG-6):** điền `ItemResolved.asr_confidence`; trước đó mọi câu nói tiếng Anh tính là nghe chưa chắc (DI-130 điểm 1).
- **Web:** `apps/web/src/api/contract.ts` đã thêm `L1` vào danh sách gương `ERROR_CLASSES` (ENG-4); hiển thị nhãn lỗi tiếng Anh là việc của ENG-7.
- Ngưỡng 0,6, hệ số 0,3, danh sách âm tiết tiếng Việt và các mẫu lỗi chờ tập vàng ENG-9 (DI-115, DI-116).
