# ADR-068: Sửa buổi học Tiếng Anh sau lượt học sinh mô phỏng (ENG-5c)

Ngày: 15/11/2026 · DI-148, DI-149, DI-150, DI-151 · Task ENG-5c · Luật `docs/plan/english-module-rules.md` · Liên quan: ADR-060 (DI-107), ADR-063 (bộ chấm, `EN_L1`), ADR-064 (giọng nói), ADR-066 (DI-140, DI-141), báo cáo học sinh mô phỏng ENG-9a (`docs/poc/english-simulated-students.md`, PR #149)

## Bối cảnh

Học sinh mô phỏng của ENG-9a học Unit 11 qua session API thật và tìm ra các lỗi sau (mã lỗi theo báo cáo):

- **L-0 (nghiêm trọng):** với router thật (`build_router`, luôn `model_only_speech=True`, cũng là đường của `AUTH_MODE=accounts` khi triển khai), buổi Tiếng Anh dừng ngay ở lời giảng đầu: mỗi lượt chỉ trả "Con chờ cô một chút nhé…" (`MODEL_WAIT`, `rejected: MODEL_ONLY_SPEECH`), 0 lần gọi model. Test ENG-5b dùng router giả không bật `model_only_speech` nên không bắt được.
- **L-2:** câu trả lời tiếng Việt cho câu hỏi tiếng Anh bị đọc thành `REDIRECT UNREADABLE` ("Mình quay lại câu đang làm nhé…"), không có `ANSWER_SUBMITTED`, không có lớp `L1`, item không bao giờ đóng với `final_error_class = L1`.
- **L-3:** `ANSWER_SUBMITTED.modality` của câu nói ghi `TEXT` (chỉ `STUDENT_MESSAGE`, `ITEM_RESOLVED` mang `VOICE`).
- **L-4:** học sinh chỉ nhắc lại lời cô làm buổi chạy tới trần 320 lượt mà không kết thúc.
- **L-6 (thấp):** khi đưa câu hỏi Toán về bài ở item nhiều câu, cô chỉ hỏi lại câu cuối của đề.

**Ràng buộc trên hết:** luồng Toán không được đổi; mọi thay đổi chỉ chạy khi buổi học là Tiếng Anh.

## Nguyên nhân L-0

`session/api.py::_hold_for_unavailable_models` chạy sau mỗi lệnh có router. Khi router bật `model_only_speech`, hàm coi mọi lời không do model nói (trừ lời chào và `PRESENT`) là bị cấm, thay cả lượt bằng `MODEL_WAIT` và giữ lệnh để thử lại. Đó là luật của Toán (lời Toán không qua model thì không được nói). Nhưng DI-140 cho `GroundedSpeaker` của buổi Tiếng Anh chạy không router, nên lời giảng lý thuyết luôn là đoạn đã duyệt (`source = TEMPLATE`): cổng chặn đúng lời đầu tiên, trước khi item nào mở, nên bộ não Tiếng Anh không bao giờ được gọi.

## Quyết định

1. **L-0 (DI-148):** `_hold_for_unavailable_models` trả nguyên lượt khi buổi học là Tiếng Anh (`_is_english(session)`). Buổi Tiếng Anh nói bằng model khi model trả lời (`EnglishRenderer`), và bằng lời đã duyệt của unit khi model bận, hết quota hay bị validator loại (DI-140, DI-141). Router, `model_only_speech` và mọi nhánh của Toán giữ nguyên.
2. **L-2 (DI-149):** bộ chấm Tiếng Anh đã trả `UNPARSEABLE` + lớp `L1` cho câu tiếng Việt (ADR-063 §4). Item loop không còn đưa câu đó qua bộ đọc "không rõ":
   - lần đầu ở một item: không chấm, chính sách trả `REDIRECT` với lý do `L1_ASK_ENGLISH` (luật `R-L1`), lời cô mời nói bằng tiếng Anh rồi hỏi lại đúng câu đang chờ;
   - từ lần thứ hai: chấm `WRONG` với lớp `L1` (`ANSWER_SUBMITTED.error_class = L1`), chính sách đưa gợi ý kế tiếp của item (`HINT`, đích `FORMAT`, `R-L1`), không hỏi "con đã làm thế nào" (không có cách làm để kể). Item đóng mà câu cuối vẫn là tiếng Việt thì `final_error_class = L1`, `node-mastery-en` tính s = 0,3 (DI-107).
   - Chỉ bộ chấm Tiếng Anh ghi `L1`, nên Toán không bao giờ đi các nhánh này.
3. **L-3 (DI-150):** `session/voice_turns.with_voice_turn` (chỉ chạy ở môn ghi lượt nói, tức Tiếng Anh) ghi `modality = VOICE` cho `ANSWER_SUBMITTED` và `EXPLANATION_SUBMITTED` của lệnh gửi bằng giọng, khớp `STUDENT_MESSAGE` của chính lệnh đó. Chấm và mastery không đọc trường này.
4. **L-4 (DI-151):** `TeachingLoop` thêm tham số `echo_stop` (mặc định `None`); `english_session.loop_options` đặt `ECHO_STOP_EN = 4`. Khi 4 tin nhắn liên tiếp của con chỉ là lời cô vừa nói (cả tin nhắn, từ 3 từ trở lên, nằm nguyên trong lời cô ngay trước nó), vòng dạy dừng giai đoạn đang học: `NODE_DECISION STOP_NODE` với luật `N-ECHO`, lý do `ECHO_ONLY`, lời cô "Con đang nhắc lại lời của cô rồi. Mình tạm dừng phần này ở đây, cô sẽ cùng con học lại sau nhé." rồi lời dừng nút như mọi nút dừng; chính sách nút đi tiếp như sau mọi nút dừng (kể cả lượt học lại cuối buổi của DI-80). Câu trả lời được chấm đúng hoặc đúng một phần làm chuỗi về 0, nên con nói theo câu mẫu ở item "nói theo cô" không bị tính. Tin nhắn kích hoạt ghi `item_id` đuôi `:ECHO` (ngoài replay của item); item đang mở để chưa xong, không chấm gì. Luật chỉ đọc sự kiện đã lưu nên replay cho đúng trạng thái.
5. **L-6:** `TeachingLoop._off_subject` (chỉ chạy khi có `off_topic`, tức Tiếng Anh) hỏi lại cả đề khi câu đang chờ là một phần của đề.
6. Version: `tutor-prompt-en.v2` (nhiệm vụ `L1_ASK_ENGLISH`), `english-session/1.1.0`. `hint-policy/0.15.0`, `node-policy/0.5.0` và `teaching-templates/0.19.0` **giữ nguyên số**: ba artifact này dùng chung với Toán và version của chúng nằm trong sự kiện Toán; phần thêm (`R-L1`, `N-ECHO`, lời `L1_ASK_ENGLISH`, `echo_stop`) chỉ chạy được khi có lớp `L1` hoặc tham số `echo_stop`, cả hai Toán không có, nên hành vi Toán đúng như version cũ. Đổi số sẽ làm golden Toán khác chỉ vì nhãn.

## Các DI

- **DI-148 (cổng model-only theo môn):** cổng `model_only_speech` là luật của Toán. Buổi Tiếng Anh dùng lời đã duyệt của unit (dữ liệu chủ dự án duyệt, đã qua validator phiên DI-141) khi model không nói được; không có `MODEL_WAIT` trong buổi Tiếng Anh. Viết đường model cho `GroundedSpeaker` Tiếng Anh vẫn là việc **[OPEN]** của DI-140.
- **DI-149 (câu trả lời tiếng Việt):** lần đầu không chấm, mời nói tiếng Anh; các lần sau chấm `WRONG`/`L1` và gợi ý tiếp; không hỏi cách làm. Lời cô (soạn chờ chủ dự án duyệt): "Cô nghe con nói bằng tiếng Việt rồi. Câu này con nói bằng tiếng Anh giúp cô nhé." / "Mình đang luyện nói tiếng Anh, con trả lời bằng tiếng Anh nhé." Lời không khen nội dung vì chưa ai kiểm nghĩa câu tiếng Việt.
- **DI-150 (modality của lần thử nói):** `ANSWER_SUBMITTED`/`EXPLANATION_SUBMITTED` mang modality của lệnh gửi nó, như `STUDENT_MESSAGE`.
- **DI-151 (học sinh chỉ nhắc lại lời cô):** ngưỡng 4 tin nhắn liên tiếp, tối thiểu 3 từ, so sau khi bỏ dấu câu và chữ hoa; câu đúng/đúng một phần hoặc một nút dừng đặt lại chuỗi. Con số 4 là khai báo (đủ để một em lỡ nhắc lại một hai lần không bị dừng); chủ dự án có thể đổi.

## Bằng chứng

- `tests/test_english_session.py`:
  - `test_an_english_session_runs_with_the_deployed_router[EnglishOnlyProvider|QuotaProvider]`: router cấu hình như triển khai (`model_only_speech=True`, chuỗi hai model), model trả lời hoặc mọi model hết quota: buổi Tiếng Anh qua lời giảng đầu, vào item, có `ANSWER_SUBMITTED`, không có `MODEL_WAIT`; khi model trả lời thì có lời `source = LLM`. Hai test này **đỏ trên `main`** (đã chạy trước khi sửa).
  - `test_the_deployed_router_still_holds_a_mathematics_session_on_model_wait`: cùng router, buổi Toán vẫn dừng ở `MODEL_WAIT` như trước.
  - `test_an_answer_in_vietnamese_is_asked_again_in_english_then_graded_l1`, `test_a_student_who_only_repeats_the_tutor_ends_the_unit_without_passing`, `test_the_echo_rule_is_english_only`, kiểm modality trong `test_a_student_goes_through_unit_11_typing_and_speaking`, câu hỏi lại cả đề trong `test_a_mathematics_question_in_the_english_session_is_brought_back_to_the_lesson`.
- Golden Toán (`math-projection-before-eng4`, `math-prompts-before-eng5a`, `math-session-before-eng5b`, `math-reports-before-eng7b`, `rag-math-before-eng2`) xanh, không ghi lại.
- Học sinh mô phỏng (`scripts/eval_english_students.py`, PR #149): số trước/sau trong mô tả PR ENG-5c.

## Việc còn mở

- **L-9:** bước "nói theo cô" vẫn dùng `PROBE`/`VERIFY` kiểu Toán; cần trường `say_after_me` trong `ItemFacts` và bảng nước riêng (chỉ nhánh Tiếng Anh).
- **L-1, L-7:** nội dung unit (ENG-3c).
- Đường model cho `GroundedSpeaker` Tiếng Anh (DI-140 [OPEN]).
