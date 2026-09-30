# 04 — AI Architecture · Model Strategy · Realtime Voice

> PART 11, PART 12, PART 20. Giá và thông số model lấy từ nguồn chính thức, xác minh ngày 2026-09-30 (xem mục "Nguồn" cuối file). Giá thay đổi thường xuyên, phải kiểm tra lại trước mỗi quyết định chi phí.

---

## PART 11 — AI ARCHITECTURE

### 11.1. Nguyên tắc

1. **LLM là một thành phần bị điều khiển, không phải bộ não của hệ thống.** Session, timer, activity, hint level, completion và mastery đều do code tất định quản lý.
2. **Mọi output của LLM là *đề xuất có cấu trúc*.** Nó đi qua validation trước khi có hiệu lực (tin nhắn gửi học sinh, nhãn evidence).
3. **Mọi lời gọi AI đều log được** (model, version prompt, token, chi phí, độ trễ, kết quả validate) và **truy vết được** về session, turn, event.
4. **Fail-closed về sư phạm, fail-soft về trải nghiệm.** Nếu AI lỗi hoặc output không hợp lệ, hệ thống không gửi nội dung chưa kiểm chứng. Thay vào đó dùng nội dung đã được giáo viên duyệt (HintTemplate), rồi mới báo lỗi.

### 11.2. Các "AI job" trong hệ thống

| Job | Khi nào | Model class | Đồng bộ? | Output | Validation |
|---|---|---|---|---|---|
| **Tutor turn** | Mỗi lượt tutor in-session | TUTOR_REASONING | Có (stream) | `TutorTurn` (structured) | Leak detector, 1 câu hỏi/lượt, độ dài, ngôn ngữ, grounding, move khớp directive |
| **Reasoning analysis** | Khi học sinh giải thích/viết lời giải | TUTOR_REASONING (gộp cùng tutor turn nếu được) | Có | `ReasoningLabels` (reasoning_quality 0–1, concept_usage, error_class đề xuất, misconception đề xuất + confidence) | Schema; confidence < ngưỡng → không thành evidence mạnh; mâu thuẫn với checker → checker thắng |
| **Material structuring** | Khi giáo viên upload | TUTOR_REASONING (chất lượng cao, không cần nhanh) | Không (worker) | `LessonDraft` (objectives, KCs, items, answers, common mistakes) | Schema + teacher review bắt buộc |
| **Hint authoring assist** | Khi soạn lesson | TUTOR_REASONING | Không | HintTemplate nháp | Teacher approve |
| **Session summary narrative** | Cuối session | LIGHTWEIGHT | Không | Nhận xét theo template, chỉ dùng số liệu đã tính | Không được đưa số không có trong input (kiểm tra số) |
| **Off-session chat** | Ngoài giờ (feature flag) | LIGHTWEIGHT | Có | Tin nhắn | Safety filter, topic guard, rate limit |
| **Embedding** | Ingestion, query ngoài session | EMBEDDING | Không/Có | Vector | — |
| **STT** | Voice input | STT | Có (streaming) | Transcript + confidence | Confidence gate; xác nhận lại với học sinh |
| **Realtime voice** | English Speaking | REALTIME_VOICE | Có | Audio + transcript + tool calls | Xem PART 20 |
| **Pronunciation** | English Speaking | PRONUNCIATION | Không/gần realtime | Điểm phát âm theo từ/âm vị | Data quality gate |
| **LLM-as-judge (eval)** | Offline, rải theo hạn mức | EVAL_JUDGE | Không | Điểm rubric | Hiệu chỉnh với nhãn giáo viên |

### 11.3. AI Gateway

```text
Business code ──► gateway.run(job: AIJob) ──► Router(model_class, policy_version, tenant) ──► ProviderAdapter
                                                   │                                        ├─ AnthropicAdapter
                                                   │                                        ├─ GoogleAdapter (Gemini, STT)
                                                   │                                        ├─ OpenAIAdapter
                                                   │                                        ├─ AzureSpeechAdapter
                                                   │                                        └─ LocalAdapter (Ollama, faster-whisper/PhoWhisper, bge-m3)
                                                   ├─ retry/timeout/circuit breaker
                                                   ├─ fallback chain (theo model class)
                                                   ├─ cost & latency accounting → AIRequestLog
                                                   └─ PII minimization (strip họ tên, id thật → pseudonym)
```

- Interface theo **job + model class**, không theo vendor (ADR-007).
- **Route được chọn ở backend** từ `modelPolicy` trong Tutor Contract và trạng thái session. Client **không bao giờ** gửi tên model (brief §55).
- Mỗi adapter khai báo capability (`structured_output`, `prompt_cache`, `streaming`, `mid_conversation_system`, `audio_in`, `audio_out`). Orchestrator dùng capability, không dùng tên vendor.

### 11.4. Output có cấu trúc của một lượt tutor

```json
{
  "message_vi": "Con thử nhìn chữ số ở hàng phần mười của hai số xem, số nào lớn hơn?",
  "move": "HINT",
  "hint_level": "H2",
  "hint_target": "CONCEPT",
  "asks_question": true,
  "reveals_final_answer": false,
  "proposed_labels": {
    "student_reasoning_quality": 0.3,
    "suspected_misconception": "DEC-M01",
    "misconception_confidence": 0.8,
    "affect": "neutral"
  },
  "grounding_refs": ["pkg:lesson-17@v3#concept-2"]
}
```

Orchestrator **không tin** các trường tự khai như `reveals_final_answer`. Validator độc lập kiểm tra lại (PART 13).

---

## PART 12 — MODEL STRATEGY

### 12.1. Phân vai model

> **v0.2 (D-T4, free-first):** mặc định của mọi model class là lựa chọn miễn phí. Model trả phí chỉ còn là mốc so sánh trong eval (ADR-016).

| Model class | Vai trò | Yêu cầu | Mặc định (miễn phí) | Fallback miễn phí | So sánh tùy chọn (trả phí) |
|---|---|---|---|---|---|
| TUTOR_REASONING | Dạy in-session, phân tích lập luận, cấu trúc hóa tài liệu | Tiếng Việt tự nhiên, tuân thủ instruction, structured output, cache, độ trễ thấp | **`gemini-3.8-flash`** (free tier; context caching miễn phí), chốt theo POC 1 | `gemini-3.5-flash`, `gemini-2.5-flash`; model mở chạy local qua Ollama (dev/offline) | `claude-opus-5-5`, `claude-sonnet-5-5` |
| LIGHTWEIGHT | Chat ngoài giờ, tóm tắt, phân loại, chuẩn hóa voice | Nhanh, an toàn | `gemini-3.5-flash-lite` | `gemini-3.1-flash-lite`, `gemini-2.5-flash-lite` | `claude-haiku-4-5` |
| EVAL_JUDGE | Chấm offline trong eval | Chất lượng cao, không cần nhanh | `gemini-2.5-pro` (free tier) hoặc `gemini-3.8-flash` với thinking cao | — | `claude-opus-5-5` |
| REALTIME_VOICE | English Speaking | Audio 2 chiều, barge-in, tool calling | **`gemini-3.8-live`** (free tier), chốt theo POC 6 | Cascade: STT + `gemini-3.8-flash` + TTS | `gpt-realtime-2.1-mini` |
| STT | Toán (tiếng Việt), English (fallback) | vi-VN, streaming, confidence | Web Speech API của trình duyệt (prototype); `gemini-3.5-transcribe-live` (free tier) | PhoWhisper (VinAI) hoặc faster-whisper chạy local (cần kiểm tra license) | `gpt-4o-transcribe` |
| TTS | Đọc câu hỏi, giọng mẫu English | Tự nhiên, vi-VN và en | `gemini-3.8-flash-tts` (free tier) | `SpeechSynthesis` của trình duyệt; Piper chạy local | — |
| EMBEDDING | RAG | Đa ngôn ngữ (Việt/Anh) | Gemini Embedding 2 (free tier) | `bge-m3` hoặc `multilingual-e5` chạy local | `text-embedding-3-small` |
| PRONUNCIATION | English Speaking | Điểm theo từ/âm vị | Azure Speech gói F0 (5 giờ/tháng; **cần xác minh** F0 có pronunciation assessment) | — | Azure trả phí |

### 12.2. Bảng giá đã xác minh (dùng cho cost model, PART 32)

**Claude** (Anthropic first-party API, bảng model được cache ngày 2026-09-25 trong tài liệu chính thức của Claude API):

| Model | ID | Input $/1M | Output $/1M | Cache read $/1M | Ghi chú |
|---|---|---|---|---|---|
| Claude Opus 5.5 | `claude-opus-5-5` | 4.00 | 20.00 | 0.20 | Thinking luôn bật; điều khiển bằng `effort` (mặc định `medium`); forced `tool_choice` không hỗ trợ → dùng structured outputs |
| Claude Sonnet 5.5 | `claude-sonnet-5-5` | 2.00 | 10.00 | 0.20 | Effort mặc định `high` |
| Claude Haiku 4.5 | `claude-haiku-4-5` | 1.00 | 5.00 | **[ASSUME]** ~0.10 | Context 200K |

**[FACT]** Claude trên Vertex AI và Bedrock có bảng giá riêng của đối tác. Nếu đi qua Vertex (phương án cloud trả phí của v0.1) phải tra giá Vertex.

**Gemini Live / audio** (trang giá Gemini API):

| Model | Audio in | Audio out | Text in/out | Free tier | Dữ liệu free tier dùng để cải thiện sản phẩm |
|---|---|---|---|---|---|
| `gemini-3.8-live` | $3.00/1M tok (~$0.005/phút) | $12.00/1M tok (~$0.018/phút) | $0.75 / $4.50 per 1M | Có | **Có** |
| `gemini-3.1-flash-live-preview` | như trên | như trên | như trên | Có | **Có** |
| `gemini-3.5-transcribe-live` | $3.50/1M (~$0.005/phút) | — | text out ~$0.004/phút | Có | **Có** |
| Gemini Embedding 2 | — | — | Text $0.20/1M | Có | **Có** |

**Gemini text models và TTS: free tier** (trang giá Gemini API, xác minh 2026-09-30):

| Model | Free tier | Context caching ở free tier | Giá trả phí in/out per 1M (tham khảo) |
|---|---|---|---|
| `gemini-3.8-flash` | Có | Có (miễn phí) | $0.75 / $3.75 (đến 31/12/2026, sau đó tăng) |
| `gemini-3.5-flash` | Có | Có (miễn phí) | $1.50 / $9.00 |
| `gemini-3.5-flash-lite` | Có | Không | $0.30 / $2.50 |
| `gemini-3.1-flash-lite` | Có | Không | $0.25 / $1.50 |
| `gemini-2.5-pro` | Có | Không | $1.25 / $10.00 |
| `gemini-2.5-flash` | Có | Không | $0.30 / $2.50 |
| `gemini-2.5-flash-lite` | Có | Không | $0.10 / $0.40 |
| `gemini-3.1-pro-preview` | **Không** | — | $2.00 / $12.00 |
| `gemini-3.8-flash-tts`, `gemini-3.8-flash-lite-tts` | Có | — | — |

**[OPEN]** Hạn mức free tier (RPM, TPM, RPD) **không được công bố trên trang tài liệu**. Hạn mức áp dụng **theo project** (không theo API key) và chỉ xem được trong AI Studio. Ghi số thực tế vào `docs/poc/free-tier-quota.md` ở Ngày 1.

**OpenAI** (trang giá developers.openai.com):

| Model | Audio in | Cached audio in | Audio out | Text in/out |
|---|---|---|---|---|
| `gpt-realtime-2.1` | $32/1M | $0.40/1M | $64/1M | $4 / $24 |
| `gpt-realtime-2.1-mini` | $10/1M | $0.30/1M | $20/1M | $0.60 / $2.40 |
| `gpt-4o-transcribe` | $0.006/phút | — | — | — |
| `gpt-realtime-whisper` | $0.017/phút | — | — | — |
| `text-embedding-3-small` | — | — | — | $0.02/1M |

**Chưa xác minh được:**
- **[OPEN]** Giá Azure Pronunciation Assessment. Trang giá hiển thị giá theo region động; nguồn bên thứ ba nói khoảng $1/giờ. **[FACT]** Gói F0 có 5 giờ realtime STT miễn phí/tháng.
- **[ASSUME]** Deepgram Nova-3 multilingual ~$0.0092/phút (nguồn bên thứ ba).

### 12.3. Về khái niệm "free" (brief §17)

**[FACT]** Các model Gemini ở trên có *free tier*; trang giá ghi rõ dữ liệu ở free tier được dùng để cải thiện sản phẩm. Không API nào trong danh sách là "free" vô điều kiện: free tier có hạn mức request, có thể thay đổi, và không có cam kết SLA.

**v0.2 (D-T3, D-T4):** chủ dự án chấp nhận dùng free tier, kể cả với dữ liệu thật của học sinh, vì đây là sản phẩm nội bộ để kiểm thử và phần pháp lý đã được xử lý. Hệ quả thiết kế:

- **Hạn mức là ràng buộc chính** thay cho tiền. Mọi lời gọi AI ghi vào `ai_request_log` để theo dõi mức tiêu thụ theo ngày (PART 31, 32.0).
- **Không phụ thuộc một nguồn duy nhất:** fallback chain gồm model free khác → model local → template đã duyệt.
- **Vẫn tối thiểu hóa PII trong prompt** (tên gọi, không họ). Việc này không tốn chi phí và là thực hành tốt nên được giữ.

### 12.4. In-session vs out-of-session routing (brief §29, Q9)

```text
Request đến ai_gateway
  └─ SessionContext có session ACTIVE hợp lệ + contract.modelPolicy.route = IN_SESSION ?
        ├─ Có  → TUTOR_REASONING (model theo contract) + full orchestration + RAG + Student Model + Assessment
        └─ Không → LIGHTWEIGHT, với OffSessionPolicy:
                   - không mở official session, không ghi completion/assessment
                   - không đổi schedule
                   - chỉ giải thích đơn giản, không dùng lesson package chưa tới giờ
                   - rate limit (ví dụ 20 tin/ngày), topic guard, safety filter
                   - log như "informal interaction" (không phải evidence chính thức)
```

**Có làm được không?** Có. Routing là quyết định **server-side** dựa trên trạng thái session. Rủi ro duy nhất là học sinh cố "kéo" chat ngoài giờ thành bài học chính thức. Cách chặn: off-session **không có quyền** ghi evidence hay completion ở mức dữ liệu (không có code path nào cho phép), không phải chỉ "prompt bảo đừng".

### 12.5. Chiến lược tiết kiệm (v0.2: tiết kiệm hạn mức free tier; nếu trả phí: tiết kiệm tiền)

1. **Caching**: prefix ổn định (constitution → subject module → lesson package → student snapshot), phần biến động (directive, lượt mới) đặt sau cùng. **[FACT]** Trang giá Gemini ghi context caching miễn phí ở free tier cho `gemini-3.8-flash` và `gemini-3.5-flash`. Claude (nếu dùng làm mốc) hỗ trợ *mid-conversation system messages* để chèn directive mà không phá cache.
2. **Không gọi LLM khi không cần**: kiểm tra đáp án bằng code; lượt "đúng rồi, sang câu tiếp" dùng template. Mỗi lời gọi bớt được là một request hạn mức được giữ lại.
3. **Thinking thấp** cho tutor turn (câu ngắn, move đã được policy chọn sẵn); thinking cao chỉ cho cấu trúc hóa tài liệu và eval judge.
4. **Giới hạn output**: tin nhắn tutor ≤ 60 từ (phù hợp trẻ lớp 5), vừa nhanh vừa đúng sư phạm.
5. **Eval có kế hoạch**: eval đầy đủ tốn nhiều request, nên chạy subset trên PR và rải eval đầy đủ theo ngày; student simulator dạng scripted không tốn request; judge chạy trên mẫu.
6. **Routing theo model class**: hạn mức thường tính riêng cho từng model **[ASSUME, kiểm tra trong AI Studio]**, nên việc nhẹ (tóm tắt, phân loại, chuẩn hóa voice) dùng LIGHTWEIGHT để giữ hạn mức của model tutor cho giờ học.

### 12.6. Xử lý lỗi, hết hạn mức, refusal và fallback

- Gateway luôn kiểm tra trạng thái kết thúc của response (safety block hoặc `finish_reason` của Gemini; `stop_reason: "refusal"` của Claude nếu dùng) trước khi đọc nội dung.
- **Hết hạn mức (HTTP 429)** là lỗi dự kiến ở free tier: không retry dồn dập; chuyển ngay sang model kế tiếp trong fallback chain và ghi `MODEL_FALLBACK`.
- Fallback chain cho TUTOR_REASONING (v0.2): `gemini-3.8-flash` → `gemini-3.5-flash` → `gemini-2.5-flash` → model local (nếu bật) → **HintTemplate đã duyệt** (không LLM). Session không bao giờ bị kẹt vì provider.

---

## PART 20 — REALTIME VOICE

### 20.1. Hai bài toán voice khác nhau

| | Math Voice-to-Text | English Realtime Speaking |
|---|---|---|
| Mục đích | Kênh nhập liệu thay cho gõ phím | Chính là năng lực được dạy và đánh giá |
| Ngôn ngữ | Tiếng Việt (có thuật ngữ toán) | Tiếng Anh của trẻ Việt (L2) |
| Độ trễ cần | Thấp vừa phải (xác nhận được) | Rất thấp (hội thoại tự nhiên) |
| Evidence | Nội dung câu trả lời (sau chuẩn hóa) | Semantic + pronunciation + fluency + interaction + support (khung English §6, §12) |
| Kiến trúc | STT streaming → normalizer → xác nhận → tutor text | Speech-to-speech hoặc cascade (POC 6) |

### 20.2. Math Voice-to-Text pipeline

```text
Mic (Web Audio, 16kHz mono) ──► STT streaming (vi-VN, có phrase hints: "phần", "phẩy", "phần trăm", "mét vuông"…)
  ──► Transcript + confidence
  ──► MathSpeechNormalizer
        ├─ Rule-based (tất định): "hai phần ba" → 2/3 ; "không phẩy năm" → 0,5 ; "hai mươi lăm phần trăm" → 25%
        │   "ba mét vuông" → 3 m² ; "bốn phẩy hai ki-lô-mét trên giờ" → 4,2 km/giờ
        ├─ Fallback LLM (LIGHTWEIGHT) khi rule không parse được → output có schema + confidence
        └─ Gắn cờ out_of_grade_scope ("âm năm", "x bình phương")
  ──► Echo-back xác nhận: "Con muốn trả lời 2/3 đúng không?" (bắt buộc khi confidence < ngưỡng hoặc là câu trả lời assessment)
  ──► Nếu là câu hỏi/meta ("con không hiểu bước này", "tại sao phải chia cho 3") → intent = QUESTION/HELP → Orchestrator
```

**v0.2 (free-first):** prototype dùng Web Speech API của Chrome (vi-VN, miễn phí, không cần server); bản chính chọn giữa `gemini-3.5-transcribe-live` (free tier) và PhoWhisper/faster-whisper chạy local (miễn phí, không phụ thuộc hạn mức), theo kết quả spike STT (O3).

Quy tắc evidence: câu trả lời qua voice **chỉ thành evidence sau khi được xác nhận**. Nếu ASR confidence thấp mà không xác nhận được thì evidence `validity = LOW` và không trừ mastery (theo tinh thần khung English §13 và quy tắc R7).

### 20.3. English Realtime Speaking: hai kiến trúc ứng viên

**Kiến trúc A — Speech-to-speech có orchestrator điều khiển**

```text
Browser ◄──WebRTC/WebSocket──► Realtime model (Gemini Live / OpenAI Realtime)
                                  ▲   │ tool calls: report_turn(skill, support_level, semantic_score_hint…)
      Orchestrator ──instructions─┘   ▼
      (session.update theo activity)  Voice Gateway (server) ← ghi audio + transcript + tool calls → Event ledger
```

- Ưu: độ trễ thấp nhất, giọng tự nhiên, barge-in tốt.
- Nhược: model realtime tự quyết lời nói từng lượt; orchestrator chỉ điều khiển gián tiếp (instructions + tool). Tuân thủ Socratic và support coding khó kiểm chứng hơn. Chất lượng suy luận sư phạm thường thấp hơn model reasoning.
- Bảo mật: client kết nối trực tiếp với provider → cần **ephemeral token** do server cấp, gắn với session. Không bao giờ để lộ API key.

**Kiến trúc B — Cascade (STT → Orchestrator + LLM → TTS)**

```text
Browser ──audio──► Voice Gateway ──► STT streaming (en) ──► Orchestrator/Policy ──► TUTOR_REASONING ──► TTS streaming ──► Browser
                                    └─► lưu audio → Pronunciation assessment (song song, không chặn lượt)
```

- Ưu: **cùng runtime Socratic với Toán** (policy, validator, evidence). Kiểm soát tuyệt đối từng lượt.
- Nhược: độ trễ cao hơn (STT endpointing + LLM + TTS), cần tối ưu streaming. Barge-in phải tự xử lý.

**Khuyến nghị [REC]:** POC 6 đo cả hai trên cùng 3 kịch bản speaking lớp 5 (mini interview, picture story, 2–3 sentence retell):

| Metric | Ngưỡng chấp nhận ban đầu |
|---|---|
| Độ trễ end-of-speech → audio đầu tiên, p95 | ≤ 1.5s (A), ≤ 2.5s (B) |
| Tuân thủ "không nói hộ, để học sinh nói hết" | ≥ 90% lượt |
| Support level được ghi đúng (so với chấm tay) | ≥ 85% |
| Transcript + audio lưu đủ cho assessment | 100% |
| Mức dùng hạn mức/phút | Đo thực tế |

Nếu A đạt tuân thủ, chọn A cho hội thoại và giữ B cho các activity cần kiểm soát chặt (assessment speaking). Hybrid là kết quả khả dĩ nhất.

**v0.2 (free-first):** A dùng `gemini-3.8-live` (free tier); B dùng Web Speech API hoặc `gemini-3.5-transcribe-live` + `gemini-3.8-flash` + `gemini-3.8-flash-tts`. Cả hai đều miễn phí. POC 6 dùng giọng học sinh thật (D-T3).

### 20.4. Quy tắc sửa lỗi khi nói (English, theo khung English §16)

| Tình huống | Hành vi |
|---|---|
| Lỗi không cản trở nghĩa, không thuộc target skill | **Không ngắt**. Ghi nhận, có thể *recast* nhẹ ở lượt sau |
| Lỗi thuộc target skill của lesson (ví dụ dùng "because") | Delayed feedback cuối lượt: recast → mời nói lại |
| Lỗi cản trở nghĩa | Hỏi làm rõ ("Do you mean…?") → rephrase |
| Học sinh im lặng > N giây | S1 repeat → S2 rephrase/slow → S3 hint… (Support Ladder) |
| Học sinh đang nói | Không ngắt, trừ khi vượt thời lượng lượt tối đa của activity |
| Pronunciation | Không sửa realtime (trừ activity phát âm chuyên biệt). Tổng hợp cuối activity, chọn 1–2 âm ưu tiên |

### 20.5. Đánh giá voice và các ràng buộc

- Mỗi lượt voice tạo 3 lớp dữ liệu: **audio**, **transcript** (+confidence, alignment), **pedagogical** (prompt, construct, support, semantic score, tutor action). **[FACT]** Theo khung English §12.1.
- Không chấm Speaking chỉ từ transcript. Semantic adequacy và pronunciation/fluency là các chiều riêng.
- Noise hoặc mic kém → `non_scorable`, yêu cầu nói lại, không trừ điểm.
- Trình duyệt: `getUserMedia` cần HTTPS và quyền mic. Kiểm tra mic trước buổi học (pre-flight). Fallback sang text nếu mic không dùng được (`VOICE_FALLBACK_TO_TEXT`).
- Tích hợp voice **ở phase English Speaking** (sau khi runtime text đã ổn định), không phải trong vertical slice đầu (Q13).

---

## Nguồn (xác minh 2026-09-30)

- Claude models & pricing: tài liệu chính thức Claude API (bảng model cache 2026-09-25)
- [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing) (gồm free tier của text, TTS, Live, embedding)
- [Gemini API rate limits](https://ai.google.dev/gemini-api/docs/rate-limits) (hạn mức áp dụng theo project, chỉ xem được trong AI Studio)
- [OpenAI API pricing](https://developers.openai.com/api/docs/pricing)
- [Azure Speech pricing](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/speech-services/) (giá hiển thị động theo region; chỉ xác nhận được gói F0 5 giờ/tháng)
- Tham khảo bên thứ ba (chưa xác minh chính thức): [Deepgram pricing — smallest.ai](https://smallest.ai/blog/deepgram-pricing-plans-cost-what-you-get-in-2026), [Gemini Live cost at scale — tokenkarma](https://tokenkarma.app/blog/gemini-live-api-pricing-voice-agents-2026/)
