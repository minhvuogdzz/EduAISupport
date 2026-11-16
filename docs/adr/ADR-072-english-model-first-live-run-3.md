# ADR-072: Lời cô Tiếng Anh do model nói trước, template là dự phòng; sửa lỗi chấm và báo cáo sau lần chạy thật thứ ba (ENG-5i)

Ngày: 16/11/2026 · DI-177 … DI-187 · Task ENG-5i · Luật `docs/plan/english-module-rules.md` · Liên quan: ADR-040 (BRAIN-4), ADR-042 (BRAIN-6), ADR-069, ADR-070 (DI-164), ADR-071

## Bối cảnh

Lần chạy thật thứ ba (main `79404e4`, sau #157 ENG-5h; session `01a1e237-f98e…`, database trong bộ nhớ, khoảng 157 lượt, 97 lời cô) cho thấy **[FACT]**:

- Tỉ lệ lời cô do model nói ở lượt hội thoại tụt từ 77% (lần 2) xuống 40%: 36/62 lượt là template (FEEDBACK 15, HINT 6, VERIFY 4, REDIRECT 3, PROBE 2, CONFIRM_ADVANCE 2). Chủ dự án muốn gia sư là AI thật nói theo ngữ cảnh như Toán; template chỉ là dự phòng cuối.
- Đọc code: lượt của **item loop** đã đi model trước (`EnglishRenderer`, ba lần thử), nhưng mọi lời của **vòng dạy** (FEEDBACK sau câu hỏi lý thuyết, sau retell, nhắc bài cũ, hỏi môn khác, nói chuyện ngoài bài, câu hỏi của con trong lúc chờ) là template, vì `GroundedSpeaker` của buổi Tiếng Anh không có model (DI-140). Đây là nhóm template lớn nhất.
- Đo lại bằng eval live (model thật, `scripts/eval_english_students.py --live`) trên main: phần còn lại là lượt rơi template vì hết quota phút của Groq (`QUOTA`), không phải vì validator.
- Lỗi chấm: "We around the bay took a boat trip." CORRECT; "We took a bot trip around the bay." PARTIAL, không chỉ "bot"; "We ate seafod." được dẫn "eat đổi thành ate" (WORKED_GUIDANCE) dù con đã nói "ate".
- Lời model: khen "bought và souvenirs" khi con nói "keychain and a hat"; xưng "Bạn đã…", "Bạn nghĩ sao".
- Hint GENERIC "Did you swim? – Yes, I did…" ở bài "took a boat trip"; "Gợi ý từ bài cũ: …" dán cả danh sách tám cụm.
- Hỏi Toán ngay sau lời đồng cảm: "Mình quay lại câu này nhé: <chính lời đồng cảm>".
- "Con hỏi Did you swim? thì bạn trả lời…" (retell có trích dẫn) bị coi là câu hỏi → "Cô chưa tìm được câu trả lời chắc chắn…".
- Phụ huynh: nút đã qua có lỗi không nằm ở phần "cần luyện"; ví dụ "eat → ate" đọc như quy tắc chứ không như câu con nói.
- Buổi mở khi mọi nút đã qua tạo bản ghi 0 phút; `/health` báo `35d15a6` trong khi code chạy là `79404e4`.

## Quyết định

Mọi thay đổi dạy/chấm là nhánh theo môn (`package.subject`, `TeachingLoop._english`); Toán đi đúng đường cũ.

1. **DI-180 (model trước ở vòng dạy, như `bridge` của Toán):** `EnglishRenderer.lead_en(key, …)` nói **câu dẫn** (1–2 câu kể, theo lời con, không câu hỏi) cho mọi lời của vòng dạy Tiếng Anh; phần đã duyệt (lời giải thích của câu lý thuyết, ý còn thiếu, câu hỏi đang chờ) đi **nguyên văn** sau câu dẫn, đúng cách `GroundedSpeaker.bridge` của Toán (BRAIN-1, DI-81). Áp cho: phản hồi câu lý thuyết (đúng, chưa đúng, chưa biết, cảm xúc), retell (đủ ý, một phần, chưa có ý, giảng lại khi thiếu ý), nhắc bài cũ, nói chuyện ngoài bài, câu hỏi môn Toán (`off_subject`, câu hỏi Toán không bao giờ tới model, DI-139). Câu hỏi của con trong lúc chờ lý thuyết/retell được trả lời bằng `_english_reteach` (model có kiểm, DI-162) thay cho kho đoạn văn. Mỗi câu dẫn qua validator Tiếng Anh (item kiểm tra của nút làm mốc lộ đáp án), `_own_checks`, và `ASKS_IN_LEAD` (câu dẫn có dấu "?"); thử tối đa `MAX_ATTEMPTS_EN` = 3 lần kèm mã từ chối, rồi mới nói lời đã duyệt. Nhiệm vụ của từng câu dẫn: `LEAD_TASKS_EN` (`tutor-prompt-en.v5`). Không đổi chấm, gợi ý, mastery hay giáo án; lời an toàn (DI-41) và lời chào giữ nguyên.
2. **DI-177 (trật tự từ):** câu có đủ mọi từ của một câu đáp án nhưng sai thứ tự (độ dài dãy con chung dài nhất ngắn hơn câu) là WRONG `EN_STRUCTURE`, `detail.scrambled`. Ngoại lệ: một cụm của cuối câu nói lên đầu ("Around the bay, we took a boat trip.") vẫn là tiếng Anh đúng. Lời cô (model hay `SCRAMBLED_EN`) phải nói lỗi trật tự, không khen câu; model không nói thì `MISSES_WORD_ORDER`.
3. **DI-178 (chính tả từ bốn chữ cái):** một từ bốn chữ cái của câu đáp án viết thiếu hay thừa **một nguyên âm** ("bot" cho "boat") là lỗi chính tả `EN_SLIP` với đúng từ sai; đổi một phụ âm ("look" cho "took") vẫn là từ khác. Từ có thật thường gặp ("bat", "hat", "sea"…) không bao giờ bị sửa.
4. **DI-179 (lỗi chính tả trong WORKED_GUIDANCE):** WORKED_GUIDANCE của câu `EN_SLIP` nói chữ viết sai (template `SLIP_EN`); lời model dạy lại dạng quá khứ ("đổi thành", "dạng quá khứ") trên câu chỉ sai chính tả bị loại `MISSES_SLIP`. Chữ sai của con không bị `OUT_OF_UNIT_ENGLISH` khi cô nhắc nó.
5. **DI-181 (không bịa từ của con):** câu nói điều con đã nói/nhớ/dùng ("khi con nhớ …", "con đã nói …", "con dùng đúng …") chỉ được trích từ tiếng Anh có trong lời con; không thì `INVENTED_WORD`. "Con nhớ câu: …" (lời dặn) không phải lời khẳng định.
6. **DI-182 (xưng "con"):** lời model gọi con là "bạn" bị loại `ADDRESSES_BAN`; "bạn Nam", "hai bạn", "giúp bạn" (nhân vật của đề) không bị bắt.
7. **DI-183 (đúng câu đang chờ, không dán danh sách, trích dẫn không phải câu hỏi):** (a) hỏi Toán khi lời cô vừa rồi đáp lại cảm xúc thì cô hỏi lại câu item đang chờ (`_resume_question`), không phải câu cuối của lời đồng cảm; (b) "Gợi ý từ bài cũ", nhắc ý khi retell/recall chỉ nêu ý chính kèm **một** cụm liên quan nhất tới câu đang hỏi (đếm từ chung, dạng quá khứ đọc về nguyên mẫu); gợi ý bài cũ không có cụm nào liên quan thì không nói; (c) cụm tiếng Anh của bài con trích kèm "?" được bỏ ra trước khi xét câu hỏi.
8. **DI-187 (gợi ý chung đúng câu):** ở bài Tiếng Anh, gợi ý chung (`generic_hints`) có từ tiếng Anh của đáp án câu khác mà câu đang làm không có thì không dùng cho câu đó. Toán không đổi (test so danh sách).
9. **DI-186 (báo cáo phụ huynh):** nút đã qua có lỗi điển hình được thêm vào `to_practise` sau các nút đang học, với lý do "Có lúc nhầm/Còn hay nhầm: …"; ví dụ ghi "con nói “eat”, đúng là “ate”" (lời con trước, từ đúng sau). `/v1/parents/me/child` không `?chapter=` vẫn trả Toán (rule F1: không đổi response route Toán); web phụ huynh đã tự mở môn học gần nhất qua `/v1/parents/me/child/subjects` (#155, test `opens on English when English is what the child studied last`).
10. **DI-185 (không mở buổi 0 phút):** mở buổi Tiếng Anh khi mọi nút của unit đã qua trả 409 `INVALID_STATE` (`details.reason = UNIT_COMPLETED`) với lời báo "Con đã học xong cả … rồi", không lưu bản ghi nào; web hiện lời đó dưới nút "Bắt đầu buổi mới". Toán không gọi kiểm này.
11. **DI-184 (`/health` revision):** revision là `git rev-parse HEAD` của mã đang chạy khi chạy từ checkout git (đọc một lần lúc dựng app); không có git (image Docker) mới dùng `CAVAT_REVISION`. Giá trị cũ còn sót trong `.env` không còn thắng.

## Version

- `tutor-prompt-en.v5`, `english-session/1.4.0`. Gói Unit 11 không đổi (`0.3.1`).
- **Giữ nguyên số Toán:** `template-renderer.v14`, `teaching-templates/0.19.0`, `node-mastery/0.3.0`, `node-policy/0.5.0`, prompt Toán. Golden `tests/golden/` không ghi lại.

## Đo

Số liệu: `docs/thesis/data/english-model-share-eng5i.json`. Học sinh mô phỏng (`scripts/eval_english_students.py`), không phải trẻ thật.

| Phép đo | main `79404e4` | ENG-5i |
|---|---|---|
| Live, model thật, `--pace 8`, 3 profile × 40 lượt: tỉ lệ lời model ở lượt hội thoại | 31,7% (yeu 50%, tieng_viet 44%, hoi_toan 0% vì hết quota) | không đo được: Groq hết quota trong ngày ngay khi chạy (QUOTA ở hầu hết lượt) |
| Độ phủ đường model: model giả luôn trả lời hợp lệ, 5 profile × 60 lượt | 71,4% (225/315); 90 template, gần hết là FEEDBACK của vòng dạy | **96,4%** (296/307); 11 template (lời an toàn, lời chào, một CLOSE_ITEM) |
| Lệnh gọi model một buổi đủ 6 nút (model giả, không bị từ chối) | – | giỏi 89, trung bình 126, yếu 189 (cap 240) |

Độ phủ đo được đường đi (lượt nào được giao cho model), không đo chất lượng lời; tỉ lệ thật còn phụ thuộc quota free tier và số lời bị validator loại.

## Hệ quả

- Mỗi lời của vòng dạy Tiếng Anh tốn thêm 1–3 lệnh gọi model. Cap 240 một buổi (ADR-069) đủ cho một buổi sáu nút của học sinh giỏi và trung bình (89, 126 lệnh gọi); học sinh yếu (189) còn khoảng 50 lệnh gọi cho các lần thử lại. Khi chạm cap, lời cô rơi về lời đã duyệt như trước.
- Hết quota phút của Groq vẫn là nguyên nhân lớn nhất của template ở lượt item (đo ở eval live): không sửa bằng code dạy, là giới hạn free tier (ADR-016, ADR-069).
- **[OPEN]** Ngưỡng "một nguyên âm" của DI-178, danh sách từ có thật `_SHORT_WORDS`, quy tắc "cụm cuối nói lên đầu" của DI-177, và cách ghi ví dụ DI-186 là khai báo, chờ chủ dự án duyệt.
- **[OPEN]** Chất lượng câu dẫn của model chỉ đo được ở lần chạy thật tiếp theo (eval offline dùng template).
