# ADR-071: Sửa các lỗi còn lại của buổi Tiếng Anh sau lần chạy thật thứ hai của học sinh Vuong (ENG-5h)

Ngày: 16/11/2026 · DI-165 … DI-176 · Task ENG-5h · Luật `docs/plan/english-module-rules.md` · Liên quan: ADR-042 (BRAIN-6), ADR-065, ADR-069 (ENG-5f), ADR-070 (ENG-5g)

## Bối cảnh

Ngày 15/11/2026, sau khi #154, #155, #156 đã merge (main `f9be05d`), tài khoản Vuong học lại Unit 11 trên server thật (session `01a1e020-74d5-75f5-88b6-c66b319c5453`, `cavat_dev`, 5 phút, 61 lời cô, 57 lệnh gọi model, COMPLETED). Lời model ở lượt hội thoại lên 77% (lần 1: 35%), không còn câu lặp nguyên văn ≥ 3 lần, nhưng còn 12 lỗi **[FACT]** (đọc từ event của buổi, chỉ đọc):

1. "con đói quá cô ơi" → REDIRECT của model "Con có muốn thử nói câu We took a boat trip around the bay không?"; "hôm nay con buồn" → "Con ơi, cô sẽ đọc câu mẫu rồi mời con nói lại nhé: …". Không một chữ ghi nhận cảm xúc.
2. "We ate seafod." (đủ câu, sai chính tả; bộ chấm: `EN_SLIP`) → gợi ý chung của bài "Con trả lời bằng một câu tiếng Anh trọn vẹn giúp cô nhé?" (GENERIC, sau khi lời model bị loại).
3. CONFIRM_ADVANCE "… Giờ mình thử chuyển sang việc cả nhà đi dạo biển nhé." trong khi câu kế là quà lưu niệm.
4. U11-VO-PR-04 "Chưa đúng. They seashells collected." chấm CORRECT (item chấm phán đoán đúng/sai), cô khen "Con đã nói đúng!" mà không nói câu sửa sai trật tự từ.
5. U11-VO-CP-01 (nói theo cô): 4 gợi ý gần giống nhau, 2 giống hệt từng chữ ("Con ơi, cô đọc mẫu cho con nghe nhé. Câu này kể chuyện đi thuyền: … Con thử nói theo cô nha?"). Nguyên nhân: với item "nói theo cô", `task_for_en` trả **cùng một nhiệm vụ** (`SAY_AFTER_ME_TASK`) cho mọi nước đi và mọi mức gợi ý, kể cả CONFIRM_ADVANCE.
6. Lời model có câu hỏi tiếng Anh không có trong bài ("đúng với câu hỏi Did you take photos?" khi đề hỏi "Did you buy some postcards there?") và emoji 😊 (giọng cô sẽ đọc).
7. Hỏi Toán khi cô vừa mời "Con thử nói theo cô nha?" → "Bây giờ con trả lời giúp cô câu này nhé: Con thử nói theo cô nha?" (ghép câu cuối của cô vào lời "trả lời câu này").
8. COGNITIVE_CONFLICT "Câu có 'yesterday' (hôm qua)…" cho "We eat seafood." ở U11-VO-PR-02 (đề không có "yesterday").
9. Sau FULL_EXPLANATION, "We took a bot trip around the bay." được coi là lời giải thích, cô nói "Con thử nói lại theo cô nhé: …" rồi vẫn sang câu mới (CONFIRM_ADVANCE dùng nhiệm vụ "nói theo cô", xem 5).
10. 11 lời cô chứa nguyên câu mẫu "We took a boat trip around the bay"; retell "đúng một phần" dán cả danh sách 8 cụm.
11. Báo cáo phụ huynh: VOCAB không có lỗi điển hình (chỉ nút "cần luyện" có `mistakes`), một lỗi `examples: []` ("eated"), `sessions.total` đếm cả buổi "mình dừng ở đây" 0 phút.
12. Gemini: `gemini-2.5-flash` HTTP 400 "Developer instruction is not enabled for api version v1", mỗi lượt ghi 3 sự kiện `MODEL_FALLBACK`.

## Quyết định

Mọi thay đổi dạy/chấm là nhánh theo môn (đọc `package.subject`); Toán đi đúng đường cũ.

1. **DI-165 (cảm xúc trước, BRAIN-6 cho Tiếng Anh):** `feeling_of` (luật tất định, có/không dấu) nhận "đói/khát", "buồn", "mệt/buồn ngủ", "chán" trong lời con. Khi có và nước đi không phải chấm/đóng câu: (a) model nhận `FEELING_TASK_EN` (đáp lại đúng chữ con nói, ấm áp, không giảng, không đọc câu tiếng Anh, không hỏi "con có muốn … không", rồi mời quay lại); (b) lời model không chứa chữ cảm xúc (hay chữ đi kèm: "ăn", "thương", "nghỉ"…) hoặc đọc câu tiếng Anh ≥ 3 từ bị loại `FEELING_IGNORED`; (c) lời soạn sẵn dự phòng `FEELINGS_EN` (hai cách nói mỗi cảm xúc, chờ chủ dự án duyệt). Không đổi chấm, gợi ý hay mastery.
2. **DI-166 (sai chính tả):** bộ chấm ghi từ sai vào `detail.slips` ("seafod"). Gợi ý/PROBE/VERIFY/COGNITIVE_CONFLICT/OFFER_CHOICE của câu `EN_SLIP` nói "chỉ có chữ «seafod» viết chưa đúng chính tả" (không đọc chính tả đúng, không đòi "câu trọn vẹn"); `[MÁY CHẤM]` nói cùng ý; lời model không nhắc chữ đó bị loại `MISSES_SLIP`.
3. **DI-167 (trật tự từ của câu sửa):** item đúng/sai Tiếng Anh: khi phán đoán đúng và câu tiếng Anh con sửa có đúng các từ của câu đúng trong lời giải đã duyệt nhưng khác thứ tự, `detail.word_order` = câu đúng. **Điểm giữ nguyên CORRECT** (item chấm phán đoán; mastery không đổi). VERIFY nói "câu con sửa bị đảo trật tự từ … nên mình nói: They collected seashells." và hỏi con nói lại; lời model không nói trật tự bị loại `MISSES_WORD_ORDER`.
4. **DI-168 (ví dụ đối chiếu có căn cứ):** ở gói Tiếng Anh, một ví dụ đối chiếu nói "câu có (chữ) 'X'" chỉ dùng được khi đề của item có X; nếu không còn ví dụ nào, policy không chọn COGNITIVE_CONFLICT (như item không có ví dụ). Toán: không đổi.
5. **DI-169 (chờ con nói lại):** item "nói theo cô", sau câu mẫu (H7), lời con là câu tiếng Anh ≥ 3 từ chưa đúng thì được chấm, cô chỉ chữ cần xem lại và đọc lại câu mẫu ("Chữ «bot» chưa đúng, câu mẫu là: …"), rồi **chờ** câu trả lời (REDIRECT `SAY_AGAIN`, `R-SAY-AGAIN-EN`), một lần mỗi item. Câu đúng giữ đường cũ.
6. **DI-170 (gợi ý leo bậc, không lặp, không hứa câu sau):** `SAY_AFTER_ME_LADDER` theo mức policy (1 đọc chậm, 2 chia cụm, 3–4 một từ khó, 5–6 nửa câu, 7 cả câu); các nước đi khác của item "nói theo cô" dùng nhiệm vụ của chính nước đi đó. Mọi gợi ý/giảng thêm "không lặp lại câu chữ cô đã nói". Kiểm tất định: `REPEATS_EARLIER` (trùng ≥ 70% từ với một lời cô trước của item, hoặc đọc lại câu mẫu khi nó đã được nói 2 lần, trừ FULL_EXPLANATION/đóng câu), `PREVIEWS_NEXT` (câu "sang …" có chữ ngoài lời chuyển câu), `INVITES_AFTER_CLOSE` (đóng câu mà mời "thử nói/nói lại/nói theo").
7. **DI-171 (không bịa câu hỏi tiếng Anh):** đoạn tiếng Anh có "?" trong lời model phải nằm trong lời của item hoặc của nút của item; không thì `INVENTED_QUESTION`.
8. **DI-172 (emoji):** emoji bị xóa tất định khỏi lời model trước khi kiểm; validator Tiếng Anh (`english-validator/1.2.0`) có mã `EMOJI` cho cả lời soạn sẵn.
9. **DI-173 (lời của vòng dạy):** khi con hỏi Toán mà câu cuối của cô là lời mời ("Con thử nói theo cô nha?"), cô hỏi lại đề của item; lời "môn khác" nêu "Toán" (bộ lọc `english_off_topic` chỉ bắt câu Toán); câu quy tắc liệt kê cả danh sách cụm được rút còn ý + một ví dụ khi báo ý retell còn thiếu (`teaching-templates-en/0.2.0`).
10. **DI-174 (Gemini 400, nguyên nhân gốc):** `google-genai` 3.x dựng client với `api_version = "v1"` (2.x là `"v1beta"`, kiểm offline: 2.34 → v1beta, 3.3.0 → v1). Ở v1, `system_instruction` và `response_json_schema` bị từ chối đúng lỗi 400 đã thấy. `pyproject.toml` cho phép `google-genai>=2.0`; một môi trường cài không kèm `constraints.txt` (2.25.0) nhận 3.x. Adapter nay luôn đặt `HttpOptions(api_version="v1beta")` cho chat, ảnh và embedding. Đây là sửa trong code, không phải `.env`. 504 của 3.8 Flash vẫn là hạn 10 s (ADR-069); đề xuất cấu hình giữ như ADR-069.
11. **DI-175 (log fallback):** `MODEL_FALLBACK` chỉ ghi khi model đã thật sự được gửi và không trả lời; model bị bỏ qua vì đang nghỉ (`sent = false`) vẫn nằm trong `MODEL_CALLED.attempts`. Áp dụng chung cho Toán (chỉ là log, không replay, không chấm).
12. **DI-176 (báo cáo Tiếng Anh):** mọi nút (cả nút đã vững) có `mistakes`; ví dụ của dạng quá khứ sai đứng một mình là "eated → ate"; `sessions` và `session_list` của view Tiếng Anh chỉ đếm buổi con có nói/hỏi/chọn (buổi mở khi mọi nút đã qua và buổi mở rồi bỏ không lời không còn được tính). Web phụ huynh hiện "Lỗi con từng gặp" dưới bài đã vững. `/v1/parents/me/child` không `?chapter=` vẫn trả Toán (khóa Toán giữ nguyên, rule F1); web đã tự mở môn học gần nhất qua `/v1/parents/me/child/subjects` (#155).

## Version

- `tutor-prompt-en.v4`, `english-session/1.3.0`, `template-renderer-en.v2`, `teaching-templates-en/0.2.0`, `english-validator/1.2.0`.
- **Giữ nguyên số Toán:** `template-renderer.v14`, `teaching-templates/0.19.0`, `node-mastery/0.3.0`, `node-policy/0.5.0`, prompt Toán. Golden `tests/golden/` không ghi lại.

## Hệ quả

- Lời cô Tiếng Anh: thêm 9 mã từ chối của lời model; mỗi mã có ghi chú cho lần thử lại (`_RETRY_NOTES`), nên tỉ lệ lời model có thể giảm nhẹ khi model hay vi phạm. Đo lại ở lần chạy thật kế tiếp.
- **[OPEN]** Danh sách cảm xúc, ngưỡng 0,7 của `REPEATS_EARLIER`, ngưỡng 2 lần đọc câu mẫu và lời soạn sẵn mới (`FEELINGS_EN`, `SLIP_EN`, `WORD_ORDER_EN`, `SAY_AGAIN_EN`) là khai báo, chờ chủ dự án duyệt.
- **[OPEN]** Lỗi của các nút PAST/DIDYOU/WHATDID/STRESS/TRIP chưa kiểm lại được bằng người thật (mastery của Vuong mang sang). Cần một học sinh mới cho lần chạy 3.
- **[REC]** Ghi `google-genai` trong `pyproject.toml` là `>=2.0,<4` không cần nữa vì adapter đặt version; vẫn khuyên cài bằng `-c constraints.txt` như Dockerfile.
