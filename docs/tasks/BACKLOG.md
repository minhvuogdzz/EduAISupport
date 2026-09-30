# BACKLOG — việc giao cho các phiên Claude Code trên cloud

**Cách dùng.** Mở phiên mới trên claude.ai/code với repo `minhvuogdzz/EduAISupport`, nhánh `main`, rồi gửi:

> Đọc CLAUDE.md, rồi thực hiện task **T0X** trong docs/tasks/BACKLOG.md. Làm trên nhánh `task/T0X-<tên-ngắn>`, chạy `make lint` và `make test`, rồi mở PR vào `main`.

Mỗi phiên chỉ làm **một** task. Task cùng lane làm tuần tự; task khác lane chạy song song được.

## Quy tắc chung cho mọi task

- **Đọc trước:** `CLAUDE.md`, mục Revision trong `docs/blueprint/00-START-HERE.md`, và các PART ghi trong task.
- **Vị trí code:** code Python trong `services/api/cavat/`, test trong `services/api/tests/` (runner và eval ở `evals/`).
- **Test chạy offline:** không cần MongoDB Atlas, không cần Gemini API key, không gọi mạng. Phiên cloud **không có** secret.
- **Không commit secret,** không tạo file `.env` thật.
- **Trước khi mở PR:** `make lint` và `make test` phải xanh. Mô tả PR ghi rõ: đã làm gì, test gì, còn thiếu gì.
- **Nội dung sư phạm là DRAFT** (lesson.yaml, prompt, ngưỡng, DI). Không tự sửa. Nếu thấy cần sửa, ghi đề xuất vào PR để chủ dự án (giáo viên kiểm soát) duyệt.

## Database Safety Gate — bắt buộc cho mọi task có DB

* Có 3 môi trường dữ liệu logic tách biệt:

  * **`cavat_test`** — integration test trên MongoDB Atlas thật.
  * **`cavat_dev`** — dữ liệu phát triển/demo sau khi seed thủ công.
  * **`cavat_prod`** — production, chưa dùng ở giai đoạn hiện tại.
* Không task nào được dùng `cavat_dev` hoặc `cavat_prod` làm database test.
* Mọi test MongoDB Atlas thật phải có marker `@pytest.mark.atlas`.
* Atlas test phải tự skip khi cloud không có `MONGODB_URI`.
* Atlas test phải kiểm tra safety guard và chỉ được chạy nếu database là `cavat_test`.
* Atlas test phải cleanup dữ liệu trong `finally`/fixture teardown.
* `make seed` là lệnh duy nhất tạo demo data. Không được tự seed trong startup, migration, test hoặc `make test`.
* Mọi demo record phải có `is_demo: true`.
* Không test, fixture, seed hoặc cleanup script nào được phép chạm dữ liệu thật.
* Trước khi merge T07/T08, chủ repo phải chạy `make test` local với Atlas và xác nhận integration test đã chạy trên `cavat_test`.
* Nếu test chỉ chạy in-memory thì không được ghi trong PR rằng MongoDB Atlas đã được kiểm chứng.

### Database Safety Acceptance Checklist

Một task liên quan DB chỉ được coi là hoàn thành khi:

* [ ] Offline/in-memory tests pass.
* [ ] Atlas tests có `@pytest.mark.atlas`.
* [ ] Atlas tests chỉ dùng `cavat_test`.
* [ ] Có safety guard chống nhầm database.
* [ ] Atlas test cleanup chạy kể cả khi test fail.
* [ ] Không có auto-seed.
* [ ] `make seed` là explicit command.
* [ ] Demo records có `is_demo: true`.
* [ ] Không có code test/seed chạm `cavat_dev` hoặc `cavat_prod`.
* [ ] Với T07/T08: chủ repo đã chạy `make test` local trước merge.

## Khung đã có

| Đường dẫn | Trạng thái |
|---|---|
| `cavat/core/pedagogy.py` | Enum dùng chung: HintLevel, HintTarget, Move, Outcome, ErrorClass, ActivityType, ItemResolution |
| `cavat/modules/content/lesson_package.py` | Model, loader, `validate_package` cho lesson YAML (có test smoke) |
| `cavat/modules/assessment/vi_numbers.py`, `math_checker.py` | **Viết nháp, chưa có test**. T01 hoàn thiện |
| `cavat/main.py`, `config.py`, `db.py` | Health check, settings, AsyncMongoClient |
| `docs/pedagogy/math-g5/so-sanh-so-thap-phan/lesson.yaml` | Đặc tả bài 1, bản DRAFT |
| Chưa có code | `cavat/modules/tutor/`, `cavat/modules/ai_gateway/` (chỉ có `__init__.py`), `evals/runners/`, `apps/web/` |

## Sơ đồ phụ thuộc

```text
Lane A (lõi tutor, tuần tự):  T01 → T02 → T03 → T04 → T05 → T06
Lane B (dữ liệu và API):      T07 → T08        (T08 cần thêm T04)
Lane C (web):                 T09              (độc lập, dùng mock API)
Lane D (đánh giá):            T10              (cần T04)
Chạy song song được ngay:     T01, T07, T09
```

---

## T01 — Hoàn thiện bộ đọc số và bộ chấm Toán (Lane A)

**Đọc:** blueprint 05 (PART 15), 06 (PART 18), ADR-010 trong 02; `lesson.yaml`.

**Làm:**

1. Viết test cho `vi_numbers.py` với các input: `"0,25"`, `"0.25"`, `"1.250"` (ambiguous), `"1.234,5"`, `"3/4"`, `"75%"`; kiểm tra thêm `extract_numbers` (có span) và `format_vi`.
2. Viết test cho `math_checker.py` trên chính các item của `lesson.yaml`:

   | Loại item | Trường hợp phải test |
   |---|---|
   | compare | `"<"` đúng; `">"` sai + DEC-M01 (0,25…0,3); `"0,3 > 0,25"` đúng (đảo chiều); `"0,25 lớn hơn 0,3"` → M01; gõ không dấu `"be hon"`; 0,4…0,45 `">"` → M02; 0,05…0,5 `"="` → M03 (không phải M01); 2,1…1,99 `"<"` → M04; 0,50…0,5 `">"` → M05 (không phải M01) |
   | order (GP-06) | thứ tự đúng; thứ tự theo M01 → M01; chuỗi `">"` giảm dần vẫn được hiểu đúng |
   | numeric (GP-07) | `"6"` đúng; `"1"` → M01 |
   | choice (GP-08, GP-10) | `"Hoa ạ"` đúng (chữ "ạ" không bị hiểu thành phương án A); `"Lan"` → M01; `"gói kẹo A"` đúng |
   | boolean (GP-09) | `"sai"`, `"không đúng"` đúng; `"đúng"` → M01 |
   | intent | `""` → NO_RESPONSE; `"con không biết"` → HELP_REQUEST; `"cho con đáp án đi"` → ANSWER_DEMAND |

3. Sửa lỗi test phát hiện được. Giữ nguyên API công khai: `check_answer(item, text, pkg) -> CheckResult`, `parse_relation`, `parse_verdict`, `rule_family`.

**Xong khi:** ≥ 40 test pass, và mỗi bug rule M01–M05 có test cả trường hợp "khớp" lẫn "không áp dụng".

## T02 — Tutor policy và hint engine (Lane A, sau T01)

**Đọc:** blueprint 05 PART 15.2 (bảng luật R-*), PART 16.3.

**Làm:** tạo `cavat/modules/tutor/policy.py` gồm:

- **Dataclass:**
  - `HintPolicyConfig`: mức gợi ý tối đa theo activity (CONCEPT_CHECK H3, GUIDED_PRACTICE H7, INDEPENDENT_PRACTICE H5, EXIT_ASSESSMENT H1); leo thang +1 mỗi lượt, +2 khi học sinh có cảm xúc tiêu cực; ngưỡng misconception 0.7; frustration sau 3 lượt không tiến triển hoặc 240 s; verify_rate 0.5.
  - `StudentSnapshot`, `ItemState`, `PolicyInput`.
  - `PolicyDecision(move, level, target, misconception_id, resolution, reason_codes, rule_ids)`.
- **Hàm `decide(inp, cfg) -> PolicyDecision`:** tất định, thực thi các luật:

  | Nhóm | Luật |
  |---|---|
  | Hết giờ | R-TIME |
  | Trả lời đúng | R-CORRECT, R-VERIFY, R-TEACH-BACK |
  | Cần xác nhận | R-CONFIRM |
  | Im lặng | R-NO-RESPONSE (nhắc nhẹ tối đa 2 lần, sau đó H1) |
  | Xin trợ giúp | R-HELP-REQUEST (lần đầu OFFER_CHOICE) |
  | Không đọc được câu trả lời | R-REDIRECT |
  | Kẹt lâu | R-FRUSTRATION (H6), sau đó R-FULL (H7) |
  | Bài đánh giá cuối | R-ASSESS-CAP |
  | Tính nhầm | R-SLIP |
  | Có misconception rõ | R-MISC-HIGH (COGNITIVE_CONFLICT, nhảy tối đa +2 và ít nhất lên H2) |
  | Sai lần đầu | R-FIRST-WRONG (PROBE), hoặc R-WEAK-PRIOR (H1) nếu học sinh yếu |
  | Sai tiếp | R-ESCALATE |

- Mỗi quyết định ghi `rule_ids`.

**Xong khi:**
- Mỗi luật có ít nhất một test.
- Không có đường nào vượt mức gợi ý tối đa của activity.
- Resolution đúng với `resolution_for`: H0 → INDEPENDENT, ≤ H5 → SUPPORTED, H6–H7 → WORKED.

## T03 — Template renderer và output validator (Lane A, sau T02)

**Đọc:** PART 13.4, 14, 15.3; trong `lesson.yaml` xem hints, counter_examples, worked_solution, verify_prompt.

**Làm:**

- **`tutor/renderer.py`**, `TemplateRenderer.render(ctx) -> RenderResult`:
  - Sinh câu tiếng Việt cho mọi Move, xưng "cô" – "con".
  - Chọn hint theo thứ tự: đúng (target, level) → cùng target mức thấp hơn → `generic_hints` → câu dự phòng.
  - Điền `{left}`/`{right}` cho counter_examples.
  - WORKED_GUIDANCE hiện mọi bước trừ bước cuối.
  - FULL_EXPLANATION = explanation + mời học sinh nói lại.
- **`tutor/validator.py`**, `validate_message(...) -> ValidationResult`, bắt các lỗi:
  - **Lộ đáp án:** câu khẳng định "SỐ QUAN_HỆ SỐ" trùng đáp án đúng; dạng "x = đáp án"; khớp `leak_patterns` trên văn bản đã bỏ dấu. Câu hỏi kiểu "số nào lớn hơn?" **không** phải lộ đáp án.
  - Nhiều hơn 1 dấu "?".
  - Thiếu câu hỏi khi move yêu cầu.
  - Dài hơn 60 từ.
  - Hỏi thông tin cá nhân.
  - Khen trí thông minh.

**Xong khi:**
- Render mọi cặp (item PRACTICE × move) đều không vi phạm validator, bằng test tham số hóa.
- Có test lộ đáp án cả dương tính lẫn âm tính.

## T04 — Item loop, state machine tầng 3 (Lane A, sau T03)

**Đọc:** PART 16.2 (Item Tutoring Loop), 10.4 (event catalog).

**Làm:** tạo `tutor/item_loop.py` với `ItemTutor(item, package, activity, renderer, cfg, snapshot)`, có hai hàm `start()` và `on_student(text, seconds)`.

- Các pha: AWAITING, AWAITING_CHOICE, AWAITING_CONFIRM, VERIFYING, TEACH_BACK, RESOLVED.
- Áp dụng quyết định của policy vào `ItemState`.
- Ghi transcript và event theo envelope PART 10.3, bản rút gọn, chưa cần DB: QUESTION_SHOWN, ANSWER_SUBMITTED, POLICY_DECISION, HINT_DELIVERED, MISCONCEPTION_DETECTED, TUTOR_MESSAGE_SENT, ITEM_RESOLVED.
- Kiểm tra mọi tin nhắn gửi đi bằng validator.

**Xong khi:** có test hội thoại cho bốn kịch bản (học sinh mang M01, xin gợi ý, im lặng, trả lời đúng ngay); mọi item đều kết thúc và không lộ đáp án.

## T05 — Học sinh ảo và runner POC 1 bằng template (Lane A, sau T04)

**Đọc:** PART 33 (POC 1), 45.2–45.3.

**Làm:**

- **`evals/synthetic_students.py`:** 6 profile (strong, average, weak, inconsistent, low_confidence, misconception_heavy). Tất định theo seed. Mỗi câu trả lời kèm "ý định thật" để đo độ chính xác chẩn đoán.
- **`evals/runners/poc1.py`:** CLI `python -m evals.runners.poc1 --adapter template`.
  - Chạy các item PRACTICE. Item nào kết thúc ở mức WORKED thì cho làm lại bằng item song sinh.
  - Metrics: leak rate, question ratio, diagnosis accuracy (dùng `rule_family`), phân bố move/level/resolution, số lượt mỗi item.
  - Xuất `evals/reports/*.json` và transcript Markdown để chủ dự án đọc.
- Thêm `make poc1`.

**Xong khi:**
- Chạy hai lần cho kết quả giống hệt.
- Leak = 0; question ratio ≥ 0.85; diagnosis ≥ 0.8 với profile misconception_heavy.

## T06 — AI Gateway, Gemini adapter và LLM renderer (Lane A, sau T05)

**Đọc:** PART 11, 12 (bảng model free-first, 12.6 fallback), 14 (prompt L1–L5).

**Làm:**

- **`ai_gateway/base.py`:**
  - `ModelClass`, `TutorTurnOut` cùng JSON schema viết tay, **không có nullable** (dùng `""` và `-1` làm giá trị trống).
  - Các lỗi `QuotaExceeded`, `ModelUnavailable`, `InvalidModelOutput`.
- **`ai_gateway/gemini.py`** (google-genai 2.x, đã kiểm tra API):
  - Gọi `genai.Client(api_key)` và `client.models.generate_content(model, contents, config=...)`.
  - `config = types.GenerateContentConfig(system_instruction=..., response_mime_type="application/json", response_json_schema=..., thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW))`.
  - `errors.ClientError` có code 429 → `QuotaExceeded`.
  - Không đặt temperature.
- **Prompt:**
  - `tutor/prompts/constitution.v1.md`, `math_g5.v1.md`.
  - `tutor/prompt_builder.py`: L1–L4 ổn định đặt trước, L5 directive đặt cuối. Đáp án item EXIT không bao giờ vào prompt.
- **`tutor/llm_renderer.py`:**
  - PRESENT, CONFIRM_ADVANCE, CLOSE_ITEM, OFFER_CHOICE, ASK_CONFIRM dùng template để tiết kiệm hạn mức.
  - Các move khác gọi LLM → validate → nếu lỗi thì retry 1 lần kèm danh sách lỗi → vẫn lỗi thì fallback template.
- **Runner:** thêm `--adapter gemini` và `--max-llm-calls` (mặc định 150) để giữ hạn mức free; thêm `make poc1-gemini`.

**Xong khi:**
- Test bằng fake model, không gọi mạng: lộ đáp án bị chặn và fallback; lỗi 429 → fallback ngay.
- Chủ dự án tự chạy `make poc1-gemini` ở máy local, vì cloud không có key.

## T08 — Session API cho một lesson (Lane B, sau T04 và T07)

**Đọc:** PART 24 (SessionContext), 29 (API).

**Làm:**

* **Endpoint FastAPI:**

  * `POST /v1/sessions` (tạo session demo)
  * `POST /v1/sessions/{id}/join`
  * `POST /v1/sessions/{id}/responses` (có `Idempotency-Key` và `expected_state_version`)
  * `POST /v1/sessions/{id}/hint-requests`
  * `GET /v1/sessions/{id}/state`
  * `GET /v1/sessions/{id}/stream` (SSE)
* Chạy item loop theo activity plan tối giản: CONCEPT_CHECK → GUIDED_PRACTICE → EXIT_ASSESSMENT → SUMMARY.
* Auth tạm bằng header `X-Demo-Student`; ghi rõ trong code và PR rằng đây là tạm.
* API test mặc định dùng repository in-memory và không cần Atlas.
* Nếu bổ sung API integration test với Atlas thì test phải đánh dấu `@pytest.mark.atlas`, chỉ sử dụng `cavat_test`, có safety guard và cleanup.
* `POST /v1/sessions` tạo session demo không đồng nghĩa với auto-seed database; test/demo fixture phải chủ động tạo dữ liệu trong test hoặc thông qua `make seed` theo đúng policy.
* Không được để API startup hoặc test startup tự tạo demo data vào `cavat_dev`.

**Xong khi:**

* Test API với repository in-memory: gửi trùng `Idempotency-Key` không tạo event trùng; sai `state_version` → 409.
* Có thể chạy test toàn bộ offline trong cloud.
* Nếu có Atlas integration test: chỉ chạy trên `cavat_test`, có safety guard và cleanup.
* Không có đường code nào tự động ghi demo/test data vào `cavat_dev` hoặc `cavat_prod`.
* Chủ repo chạy `make test` local trước khi merge PR.

## T08 — Session API cho một lesson (Lane B, sau T04 và T07)

**Đọc:** PART 24 (SessionContext), 29 (API).

**Làm:**

- **Endpoint FastAPI:**
  - `POST /v1/sessions` (tạo session demo)
  - `POST /v1/sessions/{id}/join`
  - `POST /v1/sessions/{id}/responses` (có `Idempotency-Key` và `expected_state_version`)
  - `POST /v1/sessions/{id}/hint-requests`
  - `GET /v1/sessions/{id}/state`
  - `GET /v1/sessions/{id}/stream` (SSE)
- Chạy item loop theo activity plan tối giản: CONCEPT_CHECK → GUIDED_PRACTICE → EXIT_ASSESSMENT → SUMMARY.
- Auth tạm bằng header `X-Demo-Student`; ghi rõ trong code và PR rằng đây là tạm.

**Xong khi:** test API với repository in-memory: gửi trùng `Idempotency-Key` không tạo event trùng; sai `state_version` → 409.

## T09 — Khung web app (Lane C, chạy song song được)

**Làm:** tạo `apps/web` bằng React + TypeScript + Vite (pnpm).

- **Màn hình học sinh:** câu hỏi, ô trả lời, nút xin gợi ý, khung hội thoại, hiển thị số kiểu 0,25.
- **Màn hình giáo viên:** xem transcript.
- Gọi API qua client sinh từ OpenAPI, hoặc dùng mock nếu T08 chưa xong.
- Chữ to, dễ đọc cho trẻ 10–11 tuổi.
- Thêm `make web`.

**Xong khi:** `pnpm build` pass và app chạy được với mock.

## T10 — Assessment projector v1 (Lane D, sau T04)

**Đọc:** blueprint 09 (PART 25–26 và các DI-1…DI-14).

**Làm:** tạo `assessment/projector.py`, là hàm thuần có `policy_version`, đi qua các bước:

1. Event → evidence theo 7 chiều C, R, A, T, I, S, D.
2. Evidence → phân phối Beta theo từng chiều.
3. Tính M, chuẩn hóa lại trọng số khi thiếu chiều.
4. Tính confidence (DI-11).
5. Suy ra trạng thái và các gate UNDERSTOOD, MASTERED, PROVISIONALLY_MASTERED.

**Xong khi:** golden test cho kết quả tất định, và cả 14 tình huống tối thiểu của alignment contract §9 đều có test.

---

## Việc của chủ dự án (làm ở máy local, không giao cloud)

- [ ] Chép credentials Atlas vào `services/api/.env` (lệnh ở README), rồi chạy `make setup` và `make db-ping`.
- [ ] Duyệt `docs/pedagogy/math-g5/so-sanh-so-thap-phan/lesson.yaml` (misconception, gợi ý, bài song sinh) và các DI ở blueprint 09.
- [ ] Tạo Gemini API key trên AI Studio, ghi hạn mức free tier vào `docs/poc/free-tier-quota.md`.
- [ ] Sau khi T06 merge: chạy `make poc1-gemini` và đọc transcript trong `evals/reports/`.
