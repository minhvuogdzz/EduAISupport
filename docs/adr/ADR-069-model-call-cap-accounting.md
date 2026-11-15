# ADR-069: Đếm ngân sách model call theo lời trả lời, không theo lần gửi (ENG-5f)

Ngày: 15/11/2026 · DI-153, DI-154, DI-155 · Task ENG-5f · Liên quan: ADR-017 (cap mỗi buổi), ADR-034 (chuỗi `TUTOR_MODELS`), ADR-041 (BRAIN-5, hồi quota theo bucket), ADR-057 (STEADY-1, DI-99/DI-100), ADR-066 (C1/C2, `ENGLISH_MAX_LLM_CALLS_PER_UNIT`)

## Bối cảnh

Lần chạy thật đầu tiên của Tiếng Anh Unit 11 (học sinh Vuong, 15/11/2026, buổi `01a1df0f…`, `cavat_dev`): 233 lời cô, 79% là câu soạn sẵn; từ event 1102 trở đi 100% là câu soạn sẵn, `OUTPUT_REJECTED MODEL_FALLBACK:session_cap` 24 lần. Đọc lại event (chỉ đọc) **[FACT]**:

- `state.activity.llm_calls = 160` (đúng cap). Tổng lần gửi thật (`attempts[].sent = true`) trong 115 kết quả `MODEL_CALLED` là **160 = 115 lần có lời trả lời + 45 lần bị từ chối**: 21 Groq 429 TPM (gpt-oss-120b), 11 Qwen `json_validate_failed`, 2 Qwen 5xx, 5 Gemini 2.5 Flash HTTP 400, 5 Gemini 3.8 Flash HTTP 504, 1 Gemini 4 argon 429 RPD.
- Nguyên nhân: `AIRouter._attempt_chat` cộng 1 vào `calls_made` cho **mỗi request đã gửi**, kể cả request bị 429/4xx/5xx; người gọi cộng `calls_made` vào bộ đếm của buổi. 28% ngân sách mất vào lần bị từ chối.
- Ba Gemini **không** bị thử mỗi lượt như báo cáo nghi: 148 sự kiện `MODEL_FALLBACK QUOTA` và 239 `UNAVAILABLE` phần lớn là lần **bỏ qua không gửi** (`sent = false`) nhờ cơ chế có sẵn: argon hết quota ngày bị bỏ qua tới lúc hồi (`retry_after_s ≈ 72.000`, BRAIN-5), 2.5/3.8 Flash nghỉ 30 s gấp đôi tới 5 phút (DI-99). Mỗi Flash chỉ được gửi 5 lần trong 18 phút.
- Lỗi 400 "Developer instruction is not enabled for api version v1": SDK `google-genai` 2.34 dựng client với `api_version = v1beta` (kiểm offline, kể cả khi truyền `HttpOptions(timeout=…)`). Gọi lại `gemini-2.5-flash` ngày 15/11 qua đúng adapter (system instruction + JSON schema) thì trả lời bình thường. **[FACT]** lỗi do phía Google trả về, không phải cấu hình adapter; không tái hiện được. 504 "Deadline expired" của 3.8 Flash tái hiện được: `timeout_s = 10` của `build_router` được SDK gửi thành hạn của server, 3.8 Flash (thinking LOW) không xong trong 10 s.
- Toán dùng chung router và cách đếm. 25 buổi gần nhất: lần gửi bị từ chối chiếm 10–50% số đếm (buổi chương Diện tích 28/10: 138/160, 46 lần bị từ chối). Chưa buổi Toán nào chạm cap, nhưng cùng lỗi tiềm ẩn.

## Đo nhu cầu lệnh gọi của một buổi Tiếng Anh (buổi Vuong)

Đọc event, chia buổi tại event 1102 (lần đầu chạm cap) **[FACT]**:

| | Trước 1102 | Sau 1102 | Cả buổi |
|---|---|---|---|
| Tin nhắn của con (`STUDENT_MESSAGE`) | 92 | 32 | 124 (+6 lần bấm gợi ý) |
| Lệnh gọi có model trả lời | 115 (92 lời cô `tutor_turn_en` + 23 bộ nghe `dialogue_listen_en_v1`) | 0 | 115 |
| Lời cô bị chặn vì cap | 0 | 24 | 24 |
| Lời model bị validator loại, thay bằng câu soạn sẵn | 18 (17 có `OUT_OF_UNIT_ENGLISH`) | (không gọi) | 18 |

- Tỉ lệ đo được: **1,25 lệnh gọi thành công cho mỗi tin nhắn của con** (1 lời cô + 0,25 bộ nghe). Trung bình 1.816 token/lệnh (tối đa 2.285), cả buổi 208.797 token.
- Phần sau 1102 cần: 24 lời cô bị chặn + khoảng 0,25 × 32 = 8 lần bộ nghe, tức ~32. **Cả buổi cần ~147 lệnh thành công** (124 × 1,25 = 155 nếu tính theo tỉ lệ).
- Sau DI-153 với cap 160: cả 124 tin nhắn của buổi này đều được gọi model, 0 lần chạm cap, nhưng chỉ dư khoảng 5–13 lệnh. Một học sinh cần nhiều gợi ý hơn, hoặc một buổi ~150 tin nhắn (150 × 1,25 = 188), sẽ chạm cap 160 trước khi kết thúc.
- **ENG-5g** (lời phản hồi sau chấm do model sinh): trong buổi này có 38 lời phản hồi soạn sẵn (`TEACH:FEEDBACK`) và 16 lời mời kể lại (`RETELL_PROMPT`). Nếu phản hồi sau chấm chuyển sang model, mỗi tin nhắn tốn thêm ~0,3 lệnh (38/124), thành ~1,55 lệnh/tin nhắn; nếu chuyển cả lời mời kể lại thì ~1,7. Buổi Vuong khi đó cần ~192–211 lệnh; buổi 150 tin nhắn cần ~233–255.
- Cách tính đề xuất: **cap = số tin nhắn tối đa của một buổi × số lệnh mỗi tin nhắn × 1,2** (dư 20% cho gợi ý và trả lời lại). Với 124 tin nhắn × 1,55 × 1,2 ≈ 231 và 150 × 1,3 (hiện nay) × 1,2 ≈ 234, nên **240** đủ cho cả hai. Nếu ENG-5g chuyển cả lời mời kể lại và buổi dài tới 150 tin nhắn (150 × 1,7 × 1,2 ≈ 306), cần **~300**. Đo lại `calls/tin nhắn` sau ENG-5g rồi đặt con số cuối cùng.
- Số liệu này không giải thích hết cảm giác "câu mẫu": cả trước khi chạm cap, 18/115 lời model (16%) bị validator loại (phần lớn `OUT_OF_UNIT_ENGLISH`) rồi thay bằng câu soạn sẵn, cộng với các lời soạn sẵn theo thiết kế (phản hồi, chuyển nút). Những phần đó thuộc validator và ENG-5g, không thuộc ADR này.

## Quyết định

1. **DI-153 (đếm theo lời trả lời):** `ChatOutcome.calls_made` (phần tính vào cap, người gọi cộng vào `llm_calls`) bằng **1 khi có model trả lời, 0 khi cả chuỗi không trả lời**, dù chuỗi đã thử bao nhiêu model. Lời bị validator loại sau đó vẫn tính (model đã trả lời). Cap kiểm một lần trước khi đi chuỗi (`calls_used ≥ cap` thì `SESSION_CAP`, không gửi). Số request thật vẫn đọc được: `ChatOutcome.calls_sent` (đếm `attempts[].sent`), trace (`calls_sent`) dùng trường này. Cap vẫn là trần tuyệt đối số lời model của một buổi; lần bị từ chối không tốn token (429) hoặc tốn rất ít, và đã bị giới hạn bởi quota tracker + thời gian nghỉ.
2. **DI-154 (từ chối của chính request nghỉ dài ngay):** `ModelUnavailable` mang `status` HTTP (Groq, Gemini). Status 4xx trừ 408/409/429 (bad request, model không có, sai khóa) cho model nghỉ ngay `MAX_UNAVAILABLE_REST` (5 phút) thay vì 30 s đầu; 5xx/timeout giữ DI-99; 429 giữ hồi theo bucket provider báo (BRAIN-5, `retry_after`/RPD). Tái dùng `_unavailable_until`, không thêm cơ chế mới.
3. **DI-155 (cap Tiếng Anh 240):** `ENGLISH_MAX_LLM_CALLS_PER_UNIT` mặc định 240 (từ 160). Theo bảng đo ở trên: buổi Vuong cần ~147–155 lệnh thành công hiện nay và ~192–211 lệnh khi có ENG-5g; 240 = cách tính (tin nhắn × lệnh/tin nhắn × 1,2) cho 124 tin nhắn với ENG-5g, hoặc 150 tin nhắn như hiện nay. Chỉ buổi Tiếng Anh đọc biến này (C1, C2); `MAX_LLM_CALLS_PER_CHAPTER = 160` và `MAX_LLM_CALLS_PER_SESSION = 40` của Toán giữ nguyên. **[OPEN]** chủ dự án duyệt con số; token 240 × 1.816 (trung bình đo được) ≈ 436.000 token/buổi, chia cho các model của chuỗi (mỗi model có quota ngày riêng). Đo lại sau ENG-5g; nếu cả lời mời kể lại cũng do model nói và buổi dài 150 tin nhắn thì cần ~300.

## Hệ quả

- Toán: không đổi chấm, mastery, prompt, policy hay golden (`tests/golden/` không ghi lại, `make test` xanh). Thay đổi duy nhất thấy được: lần bị từ chối không còn rút ngắn phần buổi có lời model; cap 160/40 vẫn chặn sau đúng 160/40 lời trả lời. Ngưỡng nửa ngân sách của chooser và listener (đọc `calls_used`) giờ đo theo lời trả lời.
- Trace và `MODEL_CALLED.attempts` giữ nguyên: vẫn thấy mọi lần gửi, lỗi và `retry_after_s`.
- **[REC]** thứ tự chuỗi (không tự sửa `.env`): khi `TUTOR_MODELS` trống, chuỗi là `gemini-4-argon, gemini-2.5-flash, gemini-3.8-flash, gpt-oss-120b, qwen, gpt-oss-20b`. Argon hết quota ngày sớm và 3.8 Flash thường 504 ở hạn 10 s, nên mỗi lần chúng hồi, một lượt của con chờ thêm tới ~10 s. Đề xuất cân nhắc `GEMINI_TUTOR_FALLBACKS='["gemini-2.5-flash"]'` (bỏ 3.8 Flash khỏi chuỗi chat; vẫn dùng cho ảnh) hoặc đặt Groq lên trước bằng `TUTOR_MODELS`. 21 lần Groq 429 TPM (8.000 token/phút) cho thấy giới hạn phút của gpt-oss-120b là nút cổ chai tiếp theo.
