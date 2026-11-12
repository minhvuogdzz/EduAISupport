# ENG-POC-voice: giọng cô và bộ nghe cho Tiếng Anh lớp 5, unit "My family"

**Ngày:** 12/11/2026 · **Liên quan:** ADR-030 (giọng nói), ADR-053 (triển khai voice), ADR-016 (free-first), ADR-060 (khung đánh giá Tiếng Anh, phiên khác đang viết) · **Code:** `poc/english-voice/` (README chạy lại được) · **Số liệu đầy đủ:** `poc/english-voice/results/score.md`

## Tóm tắt

- **[FACT]** Bản đang dùng trong repo là VieNeu-TTS **v3 Turbo** (SDK `vieneu==3.8.3`, `Vieneu()` mặc định, ONNX Runtime CPU). Bản này có code-switching Việt–Anh: bộ phiên âm `sea-g2p` đổi từ tiếng Anh sang phiên âm IPA tiếng Anh ngay trong câu Việt (`Từ mother nghĩa là mẹ` → `t̪ˌy2 mˈʌðɚ ŋˈiə5 …`). Model, codec và bộ phiên âm đều Apache-2.0.
- **[FACT]** VieNeu đọc **mẫu câu tiếng Anh trọn câu** rõ: Whisper chép lại đúng nguyên văn 6/6 mẫu câu (đặt `vi` hoặc `en`). Câu cô nói kiểu "Con nói theo cô nhé: This is my father." cũng rõ (5/5 với `en`, 4/5 với `vi`).
- **[FACT]** VieNeu đọc **từ đơn đứng một mình** kém: khoảng một nửa số lần đọc bị lặp từ ("Mato. Mato.") hoặc nói thêm tiếng không có trong văn bản ("Grandmother, what happened there?"). "Sister" có lúc nghe thành "xí tự". Đặt từ vào câu dẫn tiếng Việt ("Con nói theo cô: mother.") thì sạch 11/12 lần, so với 7/12 khi để từ trần.
- **[FACT]** Whisper **tự nhận dạng ngôn ngữ thì không dùng được**: với giọng VieNeu, nó nhận câu tiếng Anh là tiếng Mã Lai rồi **dịch luôn** ("This is my mother" → "Ini ialah ibu saya"), còn từ đơn bị nhận thành tiếng Đức, Nhật, Hàn. Đúng 50% so với 95% khi đặt `en`.
- **[REC]** Dùng VieNeu cho Tiếng Anh của unit này, với điều kiện: lời cô **luôn đặt từ đích trong câu** (câu dẫn tiếng Việt hoặc mẫu câu), không gửi từ trần. Whisper: `language=en` cho bước nói theo mẫu, `language=vi` cho bước hỏi đáp có lời Việt; không bao giờ để tự nhận dạng.
- **[OPEN]** Chưa có giọng trẻ em thật. Mọi số ở đây là giọng tổng hợp, chỉ đo độ rõ của giọng cô và cách Whisper xử lý; chưa đo được Whisper nghe trẻ em lớp 5 nói tiếng Anh ra sao.

## 1. Bản model và giấy phép

| Thành phần | Bản trong repo | Giấy phép | Nguồn kiểm |
|---|---|---|---|
| SDK `vieneu` | 3.8.3 (`services/voice/requirements.txt`) | Apache-2.0 | PyPI |
| Model VieNeu-TTS v3 Turbo | `pnnbao-ump/VieNeu-TTS-v3-Turbo` (cache `var/storage/voice/hf`) | Apache-2.0 | Model card Hugging Face (tag `code-switching`, ngôn ngữ `vi`, `en`) |
| Codec MOSS-Audio-Tokenizer-Nano (ONNX) | `OpenMOSS-Team/MOSS-Audio-Tokenizer-Nano-ONNX` | Apache-2.0 | Model card Hugging Face |
| Bộ phiên âm `sea-g2p` | 0.10.0 | Apache-2.0 | PyPI |

- **[FACT]** Cache của repo chỉ có hai model trên; không có bản 0.3B hay 0.5B. Các bản đó là thế hệ trước, repo không tải.
- **[FACT]** Bản 0.3B hiện có model card ghi Apache-2.0 trên Hugging Face, khác với ghi chú CC BY-NC 4.0 được nhắc tới. Repo không dùng bản này nên không ảnh hưởng.
- **[FACT]** SDK ghi rõ bản v3 Nano (`mode="v3nano"`) đọc tiếng Anh và câu trộn kém hơn Turbo. Không được đổi sang Nano cho Tiếng Anh.
- **[OPEN]** Giấy phép bộ dữ liệu huấn luyện `pnnbao-ump/VieNeu-TTS-10k-ENVI` không đọc được công khai (trang yêu cầu đăng nhập). Giấy phép của model là Apache-2.0; ghi lại để chủ dự án biết.

## 2. Cách đo

- **Bộ câu (20 câu, `sentences.py`):** 6 từ đơn (mother, father, sister, brother, grandmother, grandfather); 6 mẫu câu ("This is my mother.", "She is my sister.", "He is my brother.", "Who is this?", "How many people are there in your family?", "There are four people in my family."); 5 câu cô nói trộn Việt–Anh ("Con nói theo cô nhé: This is my father.", "Từ mother nghĩa là mẹ."…); 3 câu kiểu học sinh trả lời ("Con nghĩ là mother.", "Dạ, this is my grandmother.", "Brother là anh trai ạ.").
- **Giọng cô:** VieNeu v3 Turbo, giọng "Ngọc Huyền" như `services/voice/server.py`, CPU Apple M1 Pro, fp32. Một câu khởi động trước khi tính giờ.
- **Giọng tham chiếu (`ref`):** câu thuần Anh do giọng hệ thống macOS "Samantha" (en_US) đọc. Câu trộn thì ghép phần Việt do VieNeu đọc với phần Anh do Samantha đọc. Đây cũng là bản thử của phương án dự phòng B ở mục 5.
- **Độ rõ (như ADR-030):** cho Groq `whisper-large-v3` nghe lại (`verbose_json`, `temperature=0`, như adapter `groq.py`), 3 cách đặt ngôn ngữ: `vi`, `en`, tự nhận dạng (không gửi `language`). Tổng 2 bộ audio × 20 câu × 3 cách = 120 lượt, nghỉ 3,5 giây giữa hai lượt.
- **Chỉ số:**
  - *Tỉ lệ từ đích đúng:* phần trăm từ tiếng Anh đích có trong bản chép (không xét thứ tự).
  - *WER phần Anh:* WER của cụm tiếng Anh đích so với đoạn khớp nhất trong bản chép; phần tiếng Việt xung quanh không tính.
  - *Cụm đúng nguyên văn:* WER phần Anh bằng 0.
  - Chuẩn hóa: chữ thường, bỏ dấu câu, "4" → "four".
- **Đo riêng từ đơn (`word_repeat.py`, `repeat_listen.py`):** mỗi từ × 5 cách viết × 4 lần đọc (VieNeu lấy mẫu ngẫu nhiên nên mỗi lần đọc khác nhau), đếm cụm tiếng bằng năng lượng. Sau đó cho Whisper nghe 2 lần đọc đầu của hai cách viết "Mother." và "Con nói theo cô: mother." (48 lượt).

## 3. Kết quả: VieNeu đọc tiếng Anh

### 3.1. Tốc độ trên CPU (M1 Pro)

| Nhóm | Thời gian tổng hợp trung bình (s) | Lâu nhất (s) | RTF trung bình |
|---|---:|---:|---:|
| Từ đơn | 0,76 | 1,36 | 0,65 |
| Mẫu câu | 0,47 | 0,65 | 0,28 |
| Câu cô (trộn) | 0,62 | 0,88 | 0,28 |
| Câu bé (trộn) | 0,45 | 0,58 | 0,27 |
| **Cả 20 câu** | 11,9 s cho 34,1 s âm thanh | | **0,35** |

- **[FACT]** Nạp model mất 26 s (model đã có trong cache); câu khởi động 1,1 s.
- **[FACT]** Từ đơn có RTF cao vì những lần đọc bị lặp sinh ra âm thanh dài gấp đôi.
- **[FACT]** Nhanh hơn số đo ở ADR-030 (RTF khoảng 0,75 trên cùng loại máy). Bản SDK bây giờ là 3.8.3; ADR-030 không ghi bản lúc đo.

### 3.2. Độ rõ (Whisper nghe lại giọng VieNeu)

| Nhóm | n | `vi`: từ đích đúng | `en`: từ đích đúng | tự nhận dạng: từ đích đúng |
|---|---:|---:|---:|---:|
| Từ đơn | 6 | 50% | 83% | 33% |
| Mẫu câu | 6 | **100%** | **100%** | 33% |
| Câu cô (trộn) | 5 | 80% | **100%** | 80% |
| Câu bé (trộn) | 3 | 67% | 100%* | 67% |
| **Tất cả** | 20 | 75% | **95%** | 50% |

\* Có một câu được tính đúng nhờ Whisper dịch tiếng Việt sang tiếng Anh, không phải nghe được từ đích (xem 4.2).

Với giọng tham chiếu, `en` và tự nhận dạng đều đúng 100%, còn `vi` đúng 95%. Nghĩa là phần lớn lỗi ở bảng trên đến từ cách VieNeu đọc, không phải từ Whisper.

### 3.3. Các dạng lỗi của VieNeu

1. **[FACT] Từ trần bị lặp hoặc có thêm tiếng.** Khi văn bản chỉ có một từ ("Mother."), VieNeu hay đọc từ đó hai lần hoặc nói thêm tiếng không có trong văn bản:
   - Whisper (`en`) nghe được: "Mato. Mato.", "Fado. Fado.", "Brother. Brother Siu.", "Grandmother, what happened there?", "Mother, father.".
   - Đếm năng lượng trên 24 lần đọc mỗi cách viết, số lần có nhiều cụm tiếng hơn mong đợi: `Mother.` 8/24, `mother` 11/24, `Từ: mother.` 5/24, `Con nói theo cô: mother.` 3/24.
   - Whisper (`en`) xác nhận: từ trần sạch 7/12 lần, từ trong câu dẫn sạch 11/12 lần. Lần lỗi còn lại có thêm đuôi "Mê sự điểm".
2. **[FACT] Một số từ đọc lệch âm.**
   - "Sister" trần nghe thành "xí tự" / "See To." ở cả ba cách đặt ngôn ngữ (w3). Trong mẫu câu "She is my sister." thì đúng.
   - "Từ mother nghĩa là mẹ." nghe thành "Từ mơ từ nghĩa là mẹ" (`vi`): từ Anh kẹp giữa hai âm tiết Việt.
   - "Brother là anh trai ạ." nghe thành "Bluto là anh trai ạ": từ Anh đứng đầu câu ngắn.
3. **[FACT] Mẫu câu trọn vẹn và câu có dấu hai chấm dẫn vào cụm Anh thì ổn định:** "Con nói theo cô nhé: This is my father.", "Cô hỏi nhé: Who is this?", "Giỏi lắm! Con đọc lại nhé: She is my sister." đều được chép lại đúng nguyên văn ở cả ba cách đặt ngôn ngữ.

### 3.4. Kết luận cho giọng cô

- **[REC] Dùng được VieNeu v3 Turbo cho Tiếng Anh unit "My family"**, không cần thêm dịch vụ. Nhưng giáo án/lời cô phải theo quy ước:
  - không bao giờ gửi một từ tiếng Anh đứng riêng: luôn có câu dẫn tiếng Việt kết thúc bằng dấu hai chấm, ví dụ "Con nói theo cô: mother.";
  - để cụm Anh sau dấu hai chấm hoặc ở cuối câu; tránh đặt từ Anh đứng đầu câu ngắn, hoặc kẹp giữa hai âm tiết Việt ("Từ mother nghĩa là mẹ" nên viết thành "Mother: nghĩa là mẹ" hay "Con nhớ nhé: mother, nghĩa là mẹ"). **[ASSUME]** Hai cách viết thay thế này chưa đo, cần đo lại trước khi chốt.
  - Quy ước này đặt ở tầng viết lại chữ để đọc (giống `speech_text` của Toán), không phải trong prompt.
- **[REC] Lưu đệm (cache) audio các câu cố định của giáo án** (đã có ở `var/storage/voice/tts/`). Chủ dự án nghe duyệt bản đã lưu một lần; vì VieNeu lấy mẫu ngẫu nhiên, mỗi lần tạo lại có thể khác.
- **[OPEN]** Có nên kiểm tự động từng audio (đếm cụm tiếng / cho Whisper nghe lại) rồi tạo lại khi lỗi hay không, hay chỉ cần chủ dự án duyệt bằng tai? Bộ câu cố định của một unit nhỏ, nên duyệt bằng tai là khả thi.

## 4. Kết quả: Whisper nghe cụm tiếng Anh

### 4.1. Bảng tổng (tỉ lệ cụm đích đúng nguyên văn)

| Audio | `vi` | `en` | tự nhận dạng |
|---|---:|---:|---:|
| Giọng VieNeu | 75% | 95% | 50% |
| Giọng tham chiếu / ghép | 95% | 100% | 100% |

### 4.2. Điều quan sát được

- **[FACT] Tự nhận dạng nguy hiểm.** Giọng Anh có âm sắc Việt bị nhận thành tiếng Mã Lai và bị **dịch** (p1, p3, p5, p6: "Ada empat orang dalam keluarga saya."). Từ đơn bị nhận thành tiếng Đức ("Vater"), Nhật ("シート") hay Hàn ("브래더"). Giọng trẻ em Việt nói tiếng Anh nhiều khả năng cũng có âm sắc tương tự, nên rủi ro này còn lớn hơn.
- **[FACT] `en` nghe cụm Anh tốt nhất, nhưng dịch phần Việt.**
  - "Brother là anh trai ạ." thành "Bluto is my brother.": từ "brother" trong bản chép đến từ việc **dịch "anh trai"**, không phải nghe được.
  - "Dạ, this is my grandmother." thành "That this is my grandmother.".
  - Đây là rủi ro **nhận nhầm là đúng**: nếu bé chỉ nói tiếng Việt "anh trai", Whisper `en` có thể vẫn trả về "brother". **[ASSUME]** Suy từ một ca giọng tổng hợp; cần đo với giọng thật.
- **[FACT] `vi` giữ đúng lời Việt và nghe trọn mẫu câu Anh** (6/6), kể cả câu trộn kiểu học sinh "Con nghĩ là Mother.".
  - Điểm yếu là từ đơn: giọng VieNeu 3/6, giọng tham chiếu 5/6.
  - `vi` cũng có lúc dịch: "Father" (giọng chuẩn) thành "Cha".
  - Từ Anh đọc lệch thường bị viết lại thành âm tiết Việt ("Phá đơ", "Xí tự").
- **[FACT] Whisper không phải bộ chấm phát âm.** Mô hình ngôn ngữ kéo bản chép về từ đúng: "Brother" đọc lệch vẫn có thể ra "brother". Bản chép đúng chưa chắc bé phát âm đúng.

### 4.3. Đề xuất đặt ngôn ngữ theo bước dạy

| Bước | Bé nói gì | `language` đề xuất | Lý do / cách chấm |
|---|---|---|---|
| Nói theo mẫu (từ, mẫu câu) | Lặp lại cụm Anh đã biết trước | **`en`** | Nhận cụm Anh tốt nhất (95–100%). Chấm theo từ đích, bỏ qua từ thừa. Ghi nhận rủi ro dịch: chỉ dùng khi đích là tiếng Anh. |
| Hỏi đáp tiếng Anh ("Who is this?" → "This is my mother.") | Câu Anh, có thể kèm "Dạ", "ạ" | **`en`** | Như trên. Mất "Dạ" không ảnh hưởng chấm cụm Anh. |
| Giải nghĩa / câu trộn ("mother nghĩa là gì?" → "mẹ", "con nghĩ là mother") | Lời Việt, có thể kèm từ Anh | **`vi`** | Giữ đúng lời Việt, tránh dịch. Cụm Anh trong câu Việt vẫn nghe được (mẫu câu 100%, câu trộn 67–80% trên giọng VieNeu). |
| Mọi bước | | **không bao giờ tự nhận dạng** | Nhận sai ngôn ngữ và dịch. |

- **[REC]** Chính sách dạy (không phải client, quy tắc 4) chọn `language` theo bước. Adapter `groq.py` đã nhận tham số `language` sẵn.
- **[REC]** Chấm câu trả lời tiếng Anh tất định theo danh sách từ/cụm đích của item (như `MathChecker` cho Toán), chuẩn hóa chữ thường, dấu câu và số, chấp nhận từ thừa xung quanh. Khung cụ thể do ADR-060 quyết định.
- **[OPEN]** Có thể thử thêm tham số `prompt` của Whisper với từ vựng của unit (mother, father…) để giảm "Phá đơ"/"Xí tự" ở chế độ `vi`. Chưa đo; cũng có thể làm tăng nhận nhầm là đúng.
- **[OPEN]** Có thể nghe hai lần (`vi` và `en`) cho câu trả lời ngắn, rồi so: cụm đích chỉ có trong bản `en` mà bản `vi` có nghĩa tiếng Việt thì nghi là bị dịch. Cách này tốn gấp đôi hạn mức Whisper; chỉ cân nhắc nếu đo giọng thật cho thấy nhận nhầm là đúng nhiều.

## 5. Phương án dự phòng (chỉ đề xuất, chưa cài)

Nếu khi chủ dự án nghe thử hoặc đo giọng thật thấy VieNeu đọc tiếng Anh chưa đủ chuẩn để làm mẫu phát âm:

- **A. Kokoro-82M (local, CPU, ONNX).** Giấy phép Apache-2.0 (model card `hexgrad/Kokoro-82M` và bản ONNX `onnx-community/Kokoro-82M-v1.0-ONNX`). Có giọng en-US/en-GB, nhỏ (82M tham số). Chạy được trong venv voice riêng, sau `ai_gateway` như VieNeu. Dùng **riêng cho cụm tiếng Anh**, ghép với phần Việt của VieNeu như bộ `ref` ở đây. Nhược điểm: giọng đổi giữa câu (cô Việt rồi giọng Anh khác). **[OPEN]** Chưa đo tốc độ và độ rõ trong repo.
- **B. Giọng tiếng Anh của trình duyệt (Web Speech `speechSynthesis`, en-US) cho riêng cụm tiếng Anh.**
  - Miễn phí, không cài gì. Repo đã có `browserVoice` làm dự phòng tiếng Việt.
  - **[FACT]** Bản ghép VieNeu (Việt) + giọng hệ thống macOS (Anh) ở đây được Whisper nhận đúng 100% (`en`, tự nhận dạng) và 95% (`vi`). Trên macOS/Safari/Chrome, `speechSynthesis` dùng chính các giọng hệ thống này.
  - Nhược điểm: chất lượng và giọng khác nhau theo thiết bị (Windows, Android); không lưu đệm phía server được; ghép thời điểm giữa audio server và giọng trình duyệt phức tạp hơn.
- **Không đề xuất:** Piper. Mã nguồn MIT, nhưng mỗi giọng có giấy phép bộ dữ liệu riêng (ví dụ `en_US-lessac` dùng dữ liệu Blizzard 2013, có giới hạn), phải kiểm từng giọng. Cũng không đề xuất dịch vụ TTS trả phí.

## 6. Giới hạn

- **[FACT]** Chưa có giọng trẻ em thật. Cả hai bộ audio là giọng tổng hợp người lớn, đọc rõ, không tiếng ồn. Số đo ở đây là **cận trên**: Whisper nghe trẻ em thật chắc chắn kém hơn.
- **[FACT]** Mỗi câu chỉ một lần đọc ở phép đo chính (VieNeu lấy mẫu ngẫu nhiên). Chỉ phần từ đơn có 4 lần đọc. n nhỏ (20 câu), nên tỉ lệ phần trăm chỉ là chỉ báo, không phải ước lượng thống kê.
- **[FACT]** Đếm cụm tiếng bằng năng lượng là cách thô (grandmother có thể tách hai cụm). Kết luận về từ trần dựa vào bản chép của Whisper, không chỉ vào số cụm.
- **[FACT]** Chỉ đo `whisper-large-v3` (model đang cấu hình), không đo `whisper-large-v3-turbo`.
- **[OPEN]** Bộ lọc VOICE-3 (bỏ segment khi `no_speech_prob > 0,6` và `avg_logprob < -0,5`) chưa được kiểm với câu trả lời một từ tiếng Anh, vốn ngắn và có độ tin cậy thấp. Có nguy cơ bỏ mất câu trả lời đúng.

## 7. Đo bổ sung khi có bản ghi giọng học sinh thật

Chủ dự án đã được phép dùng giọng học sinh cho kiểm thử.

1. **Ghi:** mỗi em đọc 20 câu trong `sentences.py`, 2 lần, bằng chính thiết bị và micro sẽ dùng (laptop/tablet ở nhà, có tiếng nền thật). Đặt file vào `var/storage/poc/english-voice/child/<mã-em>/<id>.wav`. Không commit; mã em là mã ẩn danh.
2. **Thêm ca sai có chủ đích:** em nói tiếng Việt thay vì tiếng Anh ("anh trai"), nói sai từ ("father" thay "mother"), nói dở ("mo…"), im lặng. Dùng để đo nhận nhầm là đúng, chỉ số quan trọng nhất cho việc chấm.
3. **Nhãn chuẩn:** giáo viên (chủ dự án) nghe và ghi lại em thực sự nói gì, kèm đánh giá phát âm đạt/chưa đạt.
4. **Đo:** cùng `listen.py` / `score.py` (thêm `"child"` vào `SETS`), với `vi` và `en`. Thêm hai chỉ số:
   - *nhận nhầm là đúng*: em không nói từ đích mà bản chép có;
   - *bỏ sót*: em nói đúng mà bản chép không có, hoặc bị bộ lọc VOICE-3 bỏ.
   Tách theo bước dạy và theo em.
5. **Ngưỡng chấp nhận** (ví dụ nhận nhầm là đúng ≤ 5%) phải đánh dấu là DI và do chủ dự án duyệt; khung đánh giá ADR-060 quyết định cách dùng.

## 8. Việc còn mở

- **[OPEN]** Đo hai cách viết thay thế cho câu giải nghĩa ("Mother: nghĩa là mẹ") và câu có từ Anh đứng đầu.
- **[OPEN]** Chủ dự án nghe audio mẫu và quyết định VieNeu có đủ làm mẫu phát âm không, hay cần phương án A/B.
- **[OPEN]** Thử `prompt` của Whisper với từ vựng unit; kiểm bộ lọc VOICE-3 với câu trả lời một từ.
- **[OPEN]** Đo giọng trẻ em thật theo mục 7, trước khi bật chấm bằng giọng nói cho Tiếng Anh.

## Audio mẫu để nghe

Không commit (gitignore `var/`). Đã chép sang checkout chính: `var/storage/poc/english-voice/`.

- `vieneu/<id>.wav`: VieNeu đọc 20 câu. Nghe w1, w3, w4, w5 để thấy lỗi từ trần; p1–p6, t1, t4, t5 để thấy mẫu câu tốt.
- `ref/<id>.wav`: giọng tham chiếu, câu trộn là bản ghép (phương án B).
- `repeat/`: lần đọc từ trần ("Word_mother_0.wav"…) so với từ trong câu dẫn ("Con_nói_word_mother_0.wav"…).
