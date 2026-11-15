# ADR-070: Sửa lỗi dạy và chấm của buổi Tiếng Anh sau lượt học thật của học sinh Vuong (ENG-5g)

Ngày: 15/11/2026 · DI-156 … DI-163 · Task ENG-5g · Luật `docs/plan/english-module-rules.md` · Liên quan: ADR-060 (DI-107), ADR-063 (bộ chấm), ADR-065 (prompt/validator Tiếng Anh), ADR-066 (DI-140, DI-141), ADR-068 (ENG-5c)

## Bối cảnh

Ngày 15/11/2026 tài khoản Vuong học Unit 11 "Family time" trên server thật (session `01a1df0f-8f3a-7332-9d6e-8c43354b925a`, `cavat_dev`, 18 phút, khoảng 150 lượt). Buổi kết thúc COMPLETED, 5/6 nút qua, nhưng lời cô có nhiều lỗi dạy và chấm. Báo cáo đầy đủ nằm trong ghi chép của phiên chạy thật; tám lỗi ENG-5g sửa:

1. **Vòng lặp retell ở VOCAB:** rubric từ khóa cho 0,667 (thiếu ý 2 "việc làm/động từ"), cô nói "Con nói đúng ý rồi." rồi hỏi lại đúng câu cũ, ba lần liền. Con không biết mình thiếu ý nào.
2. **Câu của Toán trong buổi Tiếng Anh:** "Ừ, mình thử nhé. Kết quả bài trên thẻ là gì con?", "Con đã bắt đầu từ bước nào?" (câu hỏi đang chờ của item loop), "Cô muốn nghe rõ hơn bước con đã làm và những số con đã dùng" (lời dẫn VAGUE).
3. **Sau PROBE:** con nói đúng câu (U11-WD-CP-01) thì bộ nghe đọc thành REPAIR và cô dán lại lý thuyết thay vì chấm. (Trường hợp U11-DY-PR-04 "B" rồi "A": "A" thật ra được chấm CORRECT; chỉ nhãn `STUDENT_MESSAGE.kind` là EXPLANATION, không đổi chấm.)
4. **Chấm sai câu đúng:** "We took many photos." WRONG; "I bought a keychain and a hat in Da Lat." PARTIAL; "ate" (điền chỗ trống "Yesterday we … seafood") WRONG, gợi ý không nói phải nói cả câu.
5. **Lời giải thích tiếng Việt đúng bị coi là mơ hồ:** "Vì chuyến đi đã qua rồi nên dùng took, quá khứ của take." chấm 0,2 (rubric chỉ biết số và từ Toán); "…Ha Long Bay…" bị đọc thành "hả?" (CLARIFY) nên đóng câu bằng "Cô nói rõ hơn nhé. Mình sang câu tiếp theo nhé."
6. **Xin giảng lại:** "Cô chưa thể giải thích tiếp ở lượt này." hai lần liền (speaker của buổi Tiếng Anh không có model, DI-140); "souvenirs là gì" được dán lại cả đoạn bốn tranh.
7. **Gợi ý lạc nút:** ba gợi ý của câu hiểu nghĩa U11-VO-CC-01 dạy mẫu "Did you…?" (nút khác).
8. **Lạc đề:** câu hỏi Toán luôn được đáp cùng một câu và dán lại nguyên đoạn đọc dài; "hôm nay con buồn" được đáp "phần này hơi khó"; cô gọi "Vuông" và trích lời con mà con không nói.

**Ràng buộc trên hết:** luồng Toán không đổi; golden Toán trong `tests/golden/` không ghi lại; không chạm `ai_gateway/`, chỗ đếm cap lượt gọi (ENG-5f) và `reports/` (ENG-7c).

## Quyết định

Mọi thay đổi là một nhánh theo môn, đọc từ gói nội dung của buổi học (`package.subject` hay `chapter.package.subject`), không có tham số nào client chọn được.

1. **DI-156 (retell thiếu ý):** ở buổi Tiếng Anh, retell đủ để đi tiếp (≥ 0,5) nhưng chưa đủ mọi ý thì cô nói "Con nói đúng một phần rồi. Còn một ý con chưa nói: …" với câu của quy tắc nói đúng ý còn thiếu (`_rule_part`, như lời giữ lại của REFORM-6). Khi chính sách nút hỏi lại retell (`EXPLANATION_MISSING`), lời hỏi là "Lần này con nói thêm giúp cô ý còn thiếu nhé: … Con nói lại ý đó bằng lời của con, kèm một câu ví dụ tiếng Anh được không?"; nếu lần trước đã đủ ý thì hỏi lại bằng lời dẫn khác. Rubric, ngưỡng `retell_pass`, `max_retells`, cổng R của mastery và chính sách nút giữ nguyên.
2. **DI-157 (lời Tiếng Anh thay lời Toán):** bảng `PHRASES_EN`/`LEADS_EN` (`tutor/renderer.py`) và `PHRASES_EN` (`teaching/loop.py`) chỉ được đọc khi gói là Tiếng Anh: hỏi cách nghĩ (PROBE), "vì sao" (VERIFY), lời khen chuyển câu (bốn cách nói, đổi theo item và lần thử), lời dẫn VAGUE ("chữ nào trong câu cho con biết phải nói như vậy?"), lời dẫn cảm xúc ("Cô nghe con nói rồi… mình đi chậm thôi nhé", không nói "hơi khó"), ba cách nói khi con hỏi môn khác. Câu hỏi đang chờ của item Tiếng Anh (`_resume_question_en`) là câu hỏi cô vừa hỏi hoặc chính đề, không bao giờ "kết quả bài trên thẻ"/"từ bước nào". Từ lần thứ hai con hỏi môn khác, hoặc khi đề dài hơn 60 từ, cô chỉ hỏi lại câu hỏi của đề, không dán lại cả đoạn đọc. Sự kiện `TEACH_MESSAGE_SENT` của buổi Tiếng Anh ghi `teaching-templates-en/0.1.0`; buổi Toán vẫn ghi `teaching-templates/0.19.0`.
3. **DI-158 (câu đúng là câu trả lời):** ở item Tiếng Anh, một câu bộ chấm thấy CORRECT không đưa qua bộ nghe hội thoại, ở mọi pha (cả sau "con đã nghĩ thế nào?"), kể cả khi câu đó là câu hỏi ("What did your family do…?" là đáp án). Không tốn lệnh gọi model.
4. **DI-159 (từ đúng nói một mình):** bộ chấm Tiếng Anh nhận biết câu trả lời 1–2 từ nằm trong một câu đáp án, có một từ của nhóm `required` mà đề chưa cho (`PhraseSpec.given` = từ của đề): chấm `PARTIAL` với `detail.whole_sentence = true` thay cho WRONG. Lời cô thêm "Từ đó con chọn đúng rồi! Con nói cả câu giúp cô nhé." trước gợi ý; brain nhận cùng ý ở `[MÁY CHẤM]`. "seafood" (đề đã cho) vẫn WRONG.
5. **DI-160 (rubric "vì sao" Tiếng Anh, `reason-rubric-en/0.1.0`):** gói Tiếng Anh dùng rubric riêng: TERM là từ ngữ pháp tiếng Việt của bài ("quá khứ", "đã qua", "giữ nguyên", "trọng âm", "đoạn văn"…) hoặc tên KC; QUOTE là con trích một từ tiếng Anh của item (đáp án, lựa chọn, câu trong ngoặc, tên riêng); SOLUTION như Toán. Thang 0,2/0,6/1,0 của DI-55 giữ nguyên. Ý định của lời giải thích đọc trên câu đã bỏ các từ tiếng Anh con trích từ item (`english_intent`), nên "Ha Long Bay" không còn là "hả?". Rubric Toán (`reason-rubric/0.1.0`) và `classify_intent` không đổi.
6. **DI-161 (biến thể đáp án, chờ chủ dự án duyệt):** U11-VO-TR-04 thêm "we took many photos", "we took a lot of photos"; U11-VO-TR-03 cho nhóm 2 nhận "keychain", "key ring", "keyring", "hat" bên cạnh "souvenirs" (đề kể đúng hai món đó). Câu sai thì vẫn sai ("We take many photos.", "I buy a keychain."). Gói Unit 11 lên `0.3.1` (`chapter.yaml`, `lesson-1-did-you`).
7. **DI-162 (giảng lại ngắn đúng điều con hỏi):** ở lượt chờ lý thuyết hay retell của buổi Tiếng Anh, "con chưa hiểu, cô giảng lại" (nhãn REPAIR) và "X là gì" đi qua `_english_reteach`: (a) khi model được gọi, `EnglishRenderer.explain_again` gửi nhiệm vụ `RETEACH_TASK_EN` (1–2 câu, đúng điều con hỏi, kết bằng câu hỏi đang chờ) với căn cứ là đoạn của nút; kết quả qua validator Tiếng Anh (item kiểm tra của nút làm mốc kiểm lộ đáp án) và các kiểm của DI-163, sai thì thử lại một lần; (b) không có model hoặc model không qua kiểm: câu trong tư liệu của nút chung nhiều từ nhất với câu con hỏi (từ tiếng Anh tính gấp ba, câu "X là …" được cộng điểm), nếu không có thì câu đầu tiên con chưa nghe trong 10 lượt gần nhất (ưu tiên lời giải thích của câu lý thuyết đang hỏi, rồi quy tắc), không bao giờ là câu lộ đáp án của câu hỏi đang chờ; rồi hỏi lại câu đang chờ. Không còn "Cô chưa thể giải thích tiếp" trong buổi Tiếng Anh.
8. **DI-163 (kiểm thêm lời model Tiếng Anh, `tutor-prompt-en.v3`):** (a) gợi ý dựa vào gợi ý đã duyệt của chính item (đưa vào `[CĂN CỨ ĐÃ DUYỆT]`), nhiệm vụ HINT nói rõ "không dạy mẫu câu khác của bài"; `OFF_ITEM_ENGLISH`: gợi ý hay giảng có từ tiếng Anh ngoài tư liệu của nút và của item (hay có "did" khi nút không có) bị từ chối; (b) `INVENTED_QUOTE`: "Con nói: [câu tiếng Anh]" mà con không nói câu đó thì bị từ chối; (c) tên của con được viết đúng như tài khoản ("Vuông" → "Vuong"), sửa tất định trước khi kiểm; (d) CONFIRM_ADVANCE chỉ khen điều con vừa nói ở câu đang làm.

## Version

- `english-session/1.2.0`, `tutor-prompt-en.v3`, `template-renderer-en.v1`, `teaching-templates-en/0.1.0`, `reason-rubric-en/0.1.0`, gói Unit 11 `0.3.1`.
- **Giữ nguyên số:** `template-renderer.v14`, `teaching-templates/0.19.0`, `reason-rubric/0.1.0`, `hint-policy`, `node-policy/0.5.0`, `node-mastery-en/0.1.0`, `node-mastery/0.3.0`. Các artifact dùng chung này có version trong sự kiện Toán; phần thêm chỉ chạy khi gói là Tiếng Anh, nên hành vi Toán đúng như version cũ và golden Toán không đổi.

## Hệ quả

- Lời cô trong buổi Tiếng Anh không còn câu của Toán (test quét mọi item × năm nước đi × năm lý do).
- Con biết mình thiếu ý nào ở retell; không còn lặp nguyên câu hỏi.
- Giải thích tiếng Việt đúng được ghi R với chất lượng 0,6–1,0 thay vì 0,2: node có thể qua sớm hơn ở cổng R (DI-6). Đây là thay đổi bằng chứng của Tiếng Anh, không đổi công thức mastery.
- **[OPEN]** Model cho `GroundedSpeaker` Tiếng Anh (DI-140) vẫn chưa có; DI-162 chỉ phủ giảng lại ở lượt chờ lý thuyết/retell. Các nhãn khác của bộ nghe (REACTION, DECLINE) vẫn là lời đã duyệt.
- **[OPEN]** Danh sách TERM của DI-160 và ngưỡng OFF_ITEM_ENGLISH (một từ ngoài tư liệu) là khai báo; cần chủ dự án xem lại sau lượt chạy thật kế tiếp.
- Cap lượt gọi model (L-1 của báo cáo) và lỗi cấu hình Gemini (L-10) thuộc ENG-5f, không sửa ở đây.
