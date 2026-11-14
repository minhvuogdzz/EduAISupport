# ADR-064: Giọng nói cho module Tiếng Anh (ENG-6)

Ngày: 14/11/2026 · DI-132, DI-133, DI-134, DI-135 · Liên quan: ADR-030 (giọng nói), ADR-053, ADR-060 (DI-109, DI-111), `docs/poc/english-voice-decision.md` (PR #139), `docs/plan/english-module-rules.md` (luật V1–V4, E1–E3, S1, F3)

## Bối cảnh

- **[FACT]** Trước ENG-6, `POST /v1/voice/transcribe` gọi Whisper với `language="vi"` cố định và trả `{text, model}`. Adapter Groq đọc `avg_logprob`/`no_speech_prob` của từng segment chỉ để bỏ đoạn im lặng (VOICE-3). `ItemResolved.asr_confidence` có sẵn nhưng không ai điền. `STUDENT_MESSAGE` không giữ tham chiếu tới bản ghi âm.
- **[FACT]** POC (PR #139): Whisper `en` nghe cụm Anh đúng 95%, `vi` 75%, tự nhận dạng 50% (nhận tiếng Anh giọng Việt thành tiếng Mã Lai rồi dịch). `en` có lúc dịch tiếng Việt sang từ đích ("anh trai" thành "brother"). VieNeu đọc từ trần kém (lặp, thêm tiếng), đọc "ate" thành "are", và bảng động từ "go, went" hỏng hẳn.
- Luồng Toán đang ổn định; chủ dự án yêu cầu giọng nói của Toán giữ y hệt (Whisper `vi`, VieNeu tiếng Việt, VOICE-3, nút micro và luồng hiện có).

## Quyết định

1. **Hồ sơ giọng theo môn** (`voice/listening.py`, `VoiceProfile`): khác biệt giữa hai môn là dữ liệu của hồ sơ, không phải nhánh `if subject == "english"` rải trong session (luật S2).
   - Toán: luôn `vi`, không ghi lượt nói, không hỏi lại, đọc cả lời cô qua `speech_text` như ADR-030.
   - Tiếng Anh: ngôn ngữ theo bước (DI-132), ghi lượt nói (DI-135), hỏi lại khi nghe chưa rõ (DI-134), đọc lời cô theo kế hoạch (DI-133).
   - Môn thiếu hoặc lạ là lỗi (`check_subject`), không rơi về Toán.
2. **Backend chọn ngôn ngữ**; client chỉ gửi lại đúng giá trị phiên cho phép (quy tắc 4, luật F3). State view có thêm trường tùy chọn `voice: {language, allowed, speech}`. `transcribe` nhận `session_id` và `language`; ngôn ngữ ngoài `allowed` bị từ chối 422 trước khi gọi Whisper. Không có `session_id` thì là Toán như trước.
3. **Adapter Groq trả q** (DI-109) trong `Transcription.confidence`; `AIRouter.transcribe` từ chối mọi ngôn ngữ ngoài `vi`/`en` (không bao giờ để Whisper tự nhận dạng).
4. **Sự kiện mới `VOICE_TURN_RECORDED`** (luật E1): `school_id`, `voice_turn_id`, `message_ref`, `audio_ref` (đường dẫn trong `var/storage/voice/in`), `language`, `asr_confidence`, `model`, `heard`, `edited`. Không event cũ nào đổi tên, đổi nghĩa hay đổi trường. Trường chỉ điền `item_id` của tin nhắn vào `message_ref` (không đặt tên `item_id`) để replay item không bao giờ đọc event này.
5. **Lời cô Tiếng Anh** (`voice/english_speech.py`, `POST /v1/voice/speech-plan`): từ đích luôn trong câu (luật V2b); "ate" và bảng động từ đọc bằng giọng tiếng Anh của trình duyệt; cờ `ENGLISH_TTS_RISKY`.
6. **Web** (chỉ phần micro/giọng): khi state view báo `speech: "mixed"`, web gửi `session_id` + ngôn ngữ backend báo, gửi lại `voice_turn_id` với lệnh trả lời, đọc lời cô theo kế hoạch, và hiện lời cô xin nói lại. Phiên Toán gửi đúng request cũ (không thêm trường).

## Các DI

### DI-132: ngôn ngữ Whisper theo bước và cách tính q

1. Toán: luôn `vi`, ở mọi bước.
2. Tiếng Anh: `en` **chỉ** khi phiên đang chờ câu trả lời của item (`awaiting = ANSWER`, `expecting = ANSWER`) và item có `response_language = "en"` (nói theo mẫu, hỏi đáp tiếng Anh). Mọi trường hợp khác là `vi`:
   - `response_language = "vi"` (giải nghĩa);
   - `"either"` (câu trộn): chọn `vi` vì `en` dịch lời Việt sang từ đích (nhận nhầm là đúng), còn `vi` vẫn nghe trọn mẫu câu Anh (6/6 ở POC);
   - bước "vì sao" (`expecting = EXPLANATION`), lời đáp lý thuyết, "con nói lại" (giải thích bằng tiếng Việt, DI-111);
   - item chưa khai `response_language` (trường do ENG-3b thêm; đọc bằng `getattr`, nên ENG-6 không phụ thuộc thứ tự gộp).
3. q (DI-109) = exp(trung bình `avg_logprob` có trọng số độ dài segment), với:
   - độ dài segment = `end - start` (giây); không segment nào có độ dài dương thì mọi segment cùng trọng số;
   - tính trên **mọi** segment, kể cả segment bộ lọc VOICE-3 bỏ khỏi chữ: q nói Whisper chắc tới đâu về cả lượt;
   - q = 0 khi mọi segment có `no_speech_prob > 0,6`;
   - q = None khi provider không trả segment có `avg_logprob` (không bịa độ tin cậy);
   - kẹp vào [0, 1], làm tròn 4 chữ số để event giống nhau trên mọi máy.
   Công thức và ngưỡng vẫn là **[ASSUME]** chờ hiệu chỉnh trên tập vàng giọng trẻ thật (ADR-060 mục 10, ENG-9).

### DI-133: lời cô Tiếng Anh gửi giọng đọc

1. Câu tiếng Anh một hoặc hai từ, không có câu dẫn, được thêm câu dẫn "Con nói theo cô:" (cách viết sạch nhất ở POC: 3/24 lần thừa tiếng, Whisper nghe đúng 11/12). Endpoint `/v1/voice/speech` của phiên Tiếng Anh cũng tự thêm câu dẫn nếu nhận một từ trần.
2. Câu tiếng Anh trọn câu, hoặc phần Anh sau dấu hai chấm, gửi VieNeu nguyên văn (POC: rõ 6/6). Số trong phần Anh đọc bằng tiếng Anh ("4" thành "four"); không dùng `speech_text` của Toán (nó đọc "x", "-", ":" thành "nhân", "trừ", "chia" và số bằng tiếng Việt).
3. "Rủi ro" = có từ "ate", hoặc một cặp nguyên mẫu/quá khứ của bảng động từ Unit 11 đứng cạnh nhau (go/went, eat/ate, buy/bought, take/took, swim/swam, see/saw, do/did, have/had, visit/visited, collect/collected, make/made, play/played). Với `ENGLISH_TTS_RISKY=browser` (mặc định), phần Anh rủi ro đọc bằng giọng en-US của trình duyệt (phương án B của POC: bản ghép Việt VieNeu + Anh giọng hệ thống được Whisper nghe đúng 100%); phần Việt quanh nó vẫn là VieNeu. `vieneu` gửi tất cả cho VieNeu (vẫn giữ luật 1).
4. **[REC] chưa làm:** audio đã được chủ dự án nghe duyệt cho các câu cố định của giáo án (lưu ở `var/storage/voice/approved/`), dùng trước giọng trình duyệt. Cần một bước duyệt bằng tai và một endpoint phát audio đã duyệt; để lại cho task giao diện Tiếng Anh (ENG-7) hoặc task riêng.
5. Nhược điểm đã biết: giọng trình duyệt khác nhau theo thiết bị; máy không có giọng en-US thì trình duyệt dùng giọng mặc định.

### DI-134: cô xin nói lại khi nghe chưa rõ

1. Chỉ phiên Tiếng Anh. Response của `transcribe` có `ask_again = true` khi không nghe được chữ nào, q = 0, hoặc q < `ENGLISH_ASR_MIN_CONFIDENCE` (mặc định 0,6, cùng ngưỡng DI-109).
2. Web không tự gửi câu đó: hiện "Cô nghe chưa rõ lắm. Con bấm micro nói lại giúp cô, hoặc bấm Gửi nếu đúng là vậy nhé." kèm chữ cô nghe được. Con nói lại (lượt mới, q mới) hoặc bấm "Gửi" (câu gửi với q thấp; projector áp DI-109: đúng thì w × 0,3, sai thì không có evidence).
3. Không tăng bậc gợi ý, không chấm, không tốn lượt gọi model: xin nói lại xảy ra trước khi câu trả lời tới vòng dạy.
4. Toán không hỏi lại (giữ ADR-030: chữ rỗng thì "Cô chưa nghe rõ, con nói lại nhé." như cũ).

### DI-135: lượt nói trong event log

1. Phiên Tiếng Anh: `transcribe` ghi `<uuid>.json` cạnh bản ghi âm trong `var/storage/voice/in/<ngày>/<băm học sinh>/` (luật V3: audio không vào database) và trả `voice_turn_id = <ngày>/<uuid>`. Lệnh trả lời gửi lại id đó. Server đọc bản ghi từ đĩa, kiểm đúng học sinh và đúng buổi học, rồi ghi `VOICE_TURN_RECORDED` ngay sau `STUDENT_MESSAGE` của cùng lệnh (actor `system`). Client không gửi q, ngôn ngữ hay đường dẫn audio nên không thể làm q thấp trông như cao. Id sai định dạng, của người khác hoặc đã mất thì bị bỏ qua (câu trả lời giữ nguyên, không có q).
2. `ITEM_RESOLVED` có `modality = "VOICE"` và `asr_confidence = q` khi câu trả lời được chấm **quyết định item** (lệnh cuối cùng có `ANSWER_SUBMITTED` của item đó) là câu nói và được gửi đúng như đã nghe. Item thường đóng ở lượt sau (câu "vì sao"), nên q lấy từ lượt trả lời đã chấm, không từ lượt đóng item. Câu gõ, hoặc câu nói mà chữ gửi khác chữ nghe được (`edited = true`), thì `asr_confidence` để None.
3. Chỉ điền thêm vào event mà vòng dạy đã tạo; logic chấm, chính sách dạy và replay không đổi. Replay dựng lại item từ `STUDENT_MESSAGE` và không đọc lại payload `ITEM_RESOLVED`, nên không lệch.
4. Lệnh thử lại sau khi model bận (recovery) giữ `voice_turn_id` trong lệnh đã lưu; lượt nói chỉ ghi một lần.
5. **Toán không ghi `VOICE_TURN_RECORDED` và không điền `asr_confidence`** (hồ sơ Toán `record_turns = false`): event của buổi Toán giữ đúng như ADR-030. Bật cho Toán (ví dụ để giáo viên nghe lại) là quyết định của chủ dự án sau này, chỉ cần đổi hồ sơ.

## Cấu hình mới (luật C1, C3)

| Biến | Mặc định | Nghĩa |
|---|---|---|
| `ENGLISH_ASR_MIN_CONFIDENCE` | `0.6` | DI-134: dưới ngưỡng này cô xin nói lại |
| `ENGLISH_TTS_RISKY` | `browser` | DI-133: `browser` hoặc `vieneu` cho "ate" và bảng động từ |

## Hạn mức

- **[FACT]** Mỗi lượt nói là một request Whisper; ENG-6 không nghe hai lần (`vi` và `en`) cho một lượt. Hạn mức Whisper riêng với Qwen: 20 request/phút, 2.000 request/ngày, 28.800 giây âm thanh/ngày (`docs/poc/free-tier-quota.md`).
- **[OPEN]** Chưa đo số lượt Whisper của một buổi Tiếng Anh thật (chưa có unit chạy được trong session, ENG-3b/ENG-5 chưa gộp; chưa có giọng trẻ thật). Ước lượng ở `docs/poc/free-tier-quota.md`, cần đo lại ở ENG-9.

## Hệ quả

- Toán: request, response, tệp lưu và event của giọng nói giữ nguyên (test `tests/test_voice.py` cũ không sửa vẫn qua; test mới kiểm phiên Toán không ghi event mới, response không thêm trường). Trường `voice` mới trong state view là trường tùy chọn (luật F1).
- Phụ thuộc: `Item.response_language` (ENG-3b), projector đọc `asr_confidence` (ENG-4), trang Tiếng Anh dùng `useVoiceLive` với `session` (ENG-7). Endpoint nghe lại audio cho giáo viên (luật F5) chưa làm; `audio_ref` trong event là chỗ để làm.
- Giới hạn: số đo q, ngưỡng 0,6 và cách đọc của giọng trình duyệt đều chưa kiểm trên giọng trẻ em thật.
