# 09 — Student Model · Assessment · Learning Analytics

> PART 25 → PART 27. Nguồn chuẩn: khung đánh giá Toán ("Kế hoạch đánh giá mức độ hiểu bài của học sinh bằng dữ liệu trực quan", 60 mục) và khung đánh giá Tiếng Anh CAVAT v1.0 (16/09/2026).
> Mọi công thức ghi rõ **nguồn** hoặc là **Declared Interpretation (DI)**, tức diễn giải do dự án tự đặt, cần pedagogy lead duyệt và hiệu chỉnh bằng dữ liệu pilot. Việc này tuân theo yêu cầu "Strict algorithm and test gate" trong `ai_understanding_assessment_alignment.md` §9.

---

## PART 26 — ASSESSMENT (trích xuất từ hai tài liệu chính thức)

### 26.1. Khung Toán: những gì được trích xuất

**Dimensions (7 chiều tính toán):**

| Ký hiệu | Chiều | Evidence nguồn (lớp 5) | Nguồn |
|---|---|---|---|
| C | Correctness | Item mức A, B; đáp án cuối các item | §20 |
| R | Reasoning | Lượt "vì sao", lời giải thích; item mức C | §10, §16, §20 |
| A | Application | Item mức D (toán có lời) | §14, §20 |
| T | Transfer | Item mức E, bài biến thể (near/far) | §14, §17, §18, §20 |
| I | Independence | Hint level tối đa trước lần đúng đầu tiên | §11, §20 |
| S | Stability/Retention | **Chỉ** từ delayed probe (T1/T3/T7/T30) | §19, §20 |
| D | Diagnostic | Item error-detection | §15, §20 |

**Công thức composite (§20):**

```text
M = 0.20·C + 0.20·R + 0.15·A + 0.15·T + 0.10·I + 0.10·S + 0.10·D
```

**DI-1 (thiếu dữ liệu):** chiều nào có `effective_evidence < 1` thì bị loại, và các trọng số còn lại được chuẩn hóa lại:
`M = Σ_{d∈avail} w_d·μ_d / Σ_{d∈avail} w_d`. Chiều bị thiếu làm giảm confidence (26.3). Cách này nhất quán với ví dụ §55, nơi Retention "chưa đủ dữ liệu" mà vẫn có Mastery 74%.

**Question score (§35):** `QS = 0.35·Answer + 0.30·Reasoning + 0.15·Independence + 0.10·Difficulty + 0.10·Explanation`. Dùng cho **L3 AssessmentResult** hiển thị từng câu (ví dụ sai do tính nhầm vẫn có thể được 0.68). QS **không** đưa trực tiếp vào M. M lấy từ các chiều để tránh tính trùng.

**Independence mapping (§11 + DI-2 cho H3, H5):** H0 1.00 · H1 0.85 · H2 0.70 · H3 0.60 (DI) · H4 0.50 · H5 0.35 (DI) · H6 0.20 · H7 0.00.

**Phân loại lỗi và mức phạt (§34 + DI-3):**

| error_class | Ảnh hưởng tới C | Ảnh hưởng tới R | Ghi chú |
|---|---|---|---|
| CALCULATION (phương pháp đúng) | s = 0.5 | không trừ | "Penalty mastery phải thấp" §34 |
| FORMAT/UNIT | s = 0.7 | không trừ | DI |
| PROCEDURAL | s = 0 | s = 0.5 nếu giải thích một phần đúng | DI |
| CONCEPTUAL (misconception) | s = 0 | s = 0 | "Penalty phải lớn hơn" §34; ghi misconception |
| REASONING (đáp án đúng, lập luận sai) | s = 1 cho C | s = 0 | §10: không được cho cùng mức mastery với đáp án đúng + lập luận đúng |
| GUESS (đúng nhưng không giải thích được khi verify) | s = 1, weight × 0.5 | s = 0 | §2, §16 (DI về weight) |

**Trọng số theo độ khó (§31 + DI-4):** đúng: `w = 0.5 + difficulty`; sai: `w = 1.5 − difficulty`. Làm đúng câu khó là bằng chứng mạnh; làm sai câu khó là bằng chứng yếu về việc chưa hiểu.

**Trọng số theo hỗ trợ (DI-5):** evidence C/A/T có `w ×= max(independence, 0.3)`. Đúng sau H7 vẫn được ghi, nhưng có trọng số thấp.

**6 mức hiểu và dải (§4–§8):** 0: 0–19 NOT_LEARNED · 1: 20–39 RECOGNITION · 2: 40–59 PROCEDURAL · 3: 60–74 CONCEPTUAL · 4: 75–89 APPLIED · 5: 90–100 MASTERED.

**Gates:**
- `UNDERSTOOD` (§52): ≥ 3 successful evidence trên ≥ 2 cognitive levels và ≥ 2 dạng câu hỏi.
- `MASTERED` (§53): M ≥ 85 ∧ Confidence ≥ 75 ∧ A ≥ 80 ∧ S ≥ 70 ∧ không có critical misconception đang active.
- Thiếu S nhưng M cao → `PROVISIONALLY_MASTERED`. Sau khi có delayed evidence đạt → `MASTERED_STABLE` (§53).
- **DI-6 (gate theo chiều):** nhãn CONCEPTUAL yêu cầu có evidence R với μ_R ≥ 0.6; nhãn APPLIED yêu cầu có evidence A. Nếu M đủ dải nhưng thiếu evidence chiều tương ứng thì hạ xuống nhãn thấp hơn và gợi ý tutor thu thập evidence đó (§32 adaptive).

**Trạng thái cuối (§54):** `NOT_LEARNED, LEARNING, RECOGNIZED, PROCEDURAL, CONCEPTUAL, APPLIED, MASTERED (provisional), MASTERED_STABLE, AT_RISK, FORGOTTEN`, thêm `INSUFFICIENT_DATA` (DI-7: confidence < 30 thì hiển thị "chưa đủ dữ liệu" thay vì một con số).

**Visual zones (§25):** 90–100 xanh đậm · 75–89 xanh · 60–74 vàng · 40–59 cam · 0–39 đỏ. Tương thích với 6 mức (mức 0 và 1 cùng màu đỏ).

**Recommendation (§50) → C2 trong PART 4:** dải gốc 0–30 / 30–50 / 50–65 / 65–80 / 80–90 / 90+ lệch so với 6 mức. **Đề xuất DI-8 (chờ duyệt):**

| Dải M | Hành động tutor | Căn theo |
|---|---|---|
| < 40 | Micro Explain → Guided Example | Mức 0–1 |
| 40–59 | Guided Question (Socratic, hint sớm) | Mức 2 |
| 60–74 | Independent Practice + câu hỏi "vì sao" | Mức 3 |
| 75–89 | Transfer / biến thể | Mức 4 |
| ≥ 90 | Challenge / KC tiếp theo | Mức 5 |

**Evidence gốc (§9–§15, §30, §37):** correctness, partially correct, score, attempts; reasoning quality, logical consistency, concept usage, explanation completeness; hint levels; response time, time per step, pause time, total time; misconception type; transfer level; error detection, error explanation, correction accuracy; question metadata (KC, difficulty, cognitive level, skills, transfer, expected time).

**Interpretation (§23, §43, §44):** báo cáo giáo viên gồm tổng quan, điểm mạnh, điểm yếu, rủi ro, misconception nổi bật, khuyến nghị; báo cáo học sinh dùng ngôn ngữ đơn giản, "Đã nắm chắc / Cần luyện thêm / Mục tiêu tiếp theo".

### 26.2. Khung Tiếng Anh: những gì được trích xuất

- **Dimensions:** subskill theo miền (Reading: literal/detail, main idea, sequence, cause–effect, vocabulary in context, inference, evidence, summary/retelling; Speaking: semantic adequacy, vocabulary & grammar, pronunciation/intelligibility, fluency, coherence, interaction, support required; Language knowledge; Learning support) (§3).
- **Metrics per skill (§13):** `mastery_estimate, confidence, evidence_count, independent_success_rate, supported_success_rate, support_dependency, first_pass_rate, difficulty_band, trend, last_seen, data_quality`.
- **Thang:** Rubric lõi 0–4: 0 No valid evidence · 1 Emerging · 2 Partial/Supported · 3 Independent · 4 Deep/Transfer (§10).
- **Support ladder:** S0 Independent · S1 Repeat · S2 Rephrase/slow · S3 Hint · S4 Choice · S5 Model (§9).
- **Threshold mastery (§10.1):** ≥ 2 evidence hợp lệ ở task hoặc thời điểm khác nhau, ≥ 1 lần S0/S1 ở độ khó mục tiêu; inference, evidence và interaction cần thêm delayed/transfer probe.
- **Evidence layers cho voice (§12.1):** audio, transcript, pedagogical.
- **Quy tắc cập nhật (§13):** đúng sau Model không tăng mastery ngang đúng độc lập; sai do ASR confidence thấp không giảm mastery mạnh; confidence tăng khi mẫu năng lực lặp lại ở nhiều dạng task và thời điểm.
- **DI-9 (trọng số support):** S0 1.0 · S1 0.9 · S2 0.7 · S3 0.5 · S4 0.3 · S5 0.1.
- **DI-10 (data quality):** `non_scorable` bị loại; ASR confidence < 0.6 thì `w × 0.3`, và chỉ cho phép *tăng*, không cho phép *giảm* mastery.
- **Interpretation (§14):** mô tả theo miền, ví dụ "Reading — Inference: Partial/Supported". Tránh "English = 8.2". Không tuyên bố "chuẩn Bộ" (§16).

### 26.3. Confidence (khung Toán §21, §33 + DI-11)

Confidence phụ thuộc số lượng câu hỏi, số loại bài, số lần kiểm tra, khoảng thời gian và độ nhất quán (§21). Công thức v1:

```text
confidence = 100 · f_n · f_div · f_span · f_cons
f_n    = 1 − exp(−N_eff / 6)                       # N_eff = tổng trọng số evidence của KC
f_div  = 0.4 + 0.6 · min(1, levels_covered / 4)    # số mức nhận thức khác nhau (A–E, Diag)
f_span = 0.70 nếu mọi evidence trong 1 session; 0.85 nếu ≥ 2 session; 1.0 nếu ≥ 2 session và cách nhau ≥ 3 ngày
f_cons = clip(1 − 2·std(điểm 8 evidence gần nhất), 0.5, 1.0)
```

Ví dụ kiểm tra độ hợp lý: 8 evidence trong 1 session, phủ B/C/D/Diag, độ lệch 0.075 → confidence ≈ 100·0.74·1.0·0.70·0.85 ≈ **44**. Như vậy một buổi học không đủ để "chắc chắn", phù hợp với tinh thần §21 và §52.

### 26.4. Assessment module: vị trí và ranh giới (Q12)

**Quyết định:** Assessment là **module riêng**, không nằm trong Tutor Runtime. Runtime **gọi** assessment theo hai cách:

| Đường | Đồng bộ | Làm gì | Vì sao |
|---|---|---|---|
| `assessment.check(item, response)` | Có (trong lượt) | MathChecker, bug rules, English rubric scoring (khi cần ngay) | Tutor cần biết đúng/sai để chọn move |
| `assessment.record_evidence(events)` → projector | Không (worker, vài giây) | Tạo Evidence (L1), AssessmentResult (L3), cập nhật Student Model (L4–L5) | Tất định, replay được, có version, tách khỏi độ trễ LLM |

Lý do tách: (1) assessment phải **deterministic và replayable** (alignment §4, §9), còn runtime thì không; (2) teacher override và re-projection khi đổi policy chỉ đụng tới assessment; (3) test độc lập.

### 26.5. Validation layer cho nhãn do LLM đề xuất (brief §41)

```text
LLM proposed_labels ─► Schema check ─► Range check ─► Cross-check với checker (checker thắng khi mâu thuẫn)
   ─► Confidence gate (≥ 0.6 → evidence bình thường; < 0.6 → evidence "unverified" w×0.3 hoặc loại)
   ─► Lấy mẫu human review (5% ở pilot, 100% với nhãn critical misconception đầu tiên của mỗi học sinh)
   ─► Evidence (L1)                     [EVIDENCE_REJECTED được log kèm lý do]
```

Không có code path nào cho phép LLM ghi trực tiếp vào `student_kc_state`. Chỉ projector (code) được ghi.

### 26.6. Teacher override

- Override có phạm vi (một AssessmentResult, hoặc trạng thái KC của học sinh), có lý do bắt buộc và được audit.
- Projection áp dụng override như một **prior mới** tại thời điểm override. Evidence sau thời điểm đó tiếp tục cập nhật từ prior này. UI luôn hiển thị "đã được giáo viên điều chỉnh".
- AI flag ("AI chấm sai") tạo mục trong hàng đợi review, và sau khi xác nhận thì được đưa vào eval dataset.

---

## PART 25 — STUDENT MODEL

### 25.1. Cấu trúc

**Math: `student_kc_state` (mỗi học sinh × KC):**

```json
{
  "student_id": "…", "kc_id": "KC-DEC-CMP", "policy_version": "mp-1.0",
  "dimensions": {
    "C": {"alpha": 7.2, "beta": 1.9, "mean": 0.79, "n_eff": 7.1},
    "R": {"alpha": 3.1, "beta": 1.4, "mean": 0.69, "n_eff": 2.5},
    "A": {"mean": 0.81, "n_eff": 2.0}, "T": {"mean": null, "n_eff": 0},
    "I": {"mean": 0.74, "n_eff": 6.0}, "S": {"mean": null, "n_eff": 0}, "D": {"mean": 1.0, "n_eff": 1.0}
  },
  "mastery": 77.4, "confidence": 44, "level": 4, "state": "APPLIED",
  "gates": {"understood": true, "mastered": false, "reason": ["S missing", "confidence < 75"]},
  "misconceptions": [{"id": "DEC-M01", "count": 2, "last_seen": "…", "status": "RESOLVING"}],
  "attempts": 11, "correct": 8, "hints": 5, "avg_time_s": 71,
  "last_seen": "…", "forgetting_risk": "LOW", "trend": "UP", "velocity_7d": 12.0,
  "evidence_ids_tail": ["…"], "overridden_by_teacher": false
}
```

**English: `student_skill_state` (mỗi học sinh × skill):** các field của khung English §13, cộng `rubric_level_current` (0–4) và `support_profile` (phân phối S0–S5).

**Cấp học sinh:** attendance, completion rate, active minutes, average hints per item, response latency, persistence (tỉ lệ item không bỏ cuộc), answer change rate (khung Toán §29). Các metric hành vi này **không** dùng để đánh giá "thông minh hay kém".

### 25.2. Thuật toán cập nhật v1 (DI-12, thay thế được khi có dữ liệu)

- Mỗi chiều d của mỗi KC là một phân phối **Beta(α, β)**, prior Beta(1, 1).
- Mỗi evidence e có `score s_e ∈ [0,1]` và `weight w_e` (tích của các trọng số: độ khó, hỗ trợ, data quality, error class). Cập nhật: `α += w·s`, `β += w·(1−s)`.
- `μ_d = α/(α+β)`. M theo 26.1 (DI-1). Confidence theo 26.3.
- Retention S chỉ được cập nhật từ delayed probe, với score = kết quả probe (có trọng số theo khoảng cách ngày).
- Forgetting risk (§40, DI-13): `risk = 1 − exp(−days_since_last / τ)`, với `τ = 7 · (1 + reviews_passed) · (0.5 + μ_S)` (dùng 0.5 khi thiếu S). Risk > 0.6 → `AT_RISK`, lập ReviewSchedule.
- Learning velocity (§39): chênh lệch M trung bình tuần này so với tuần trước.
- Knowledge tracing nâng cao (BKT/DKT) để **sau pilot**, khi có đủ dữ liệu so sánh (O12).

**Tính tất định:** projector là hàm thuần `project(evidence_stream, policy_version) → state`. Có test golden: cùng input thì cùng output byte-for-byte. Khi đổi policy thì re-project toàn bộ và lưu version song song.

### 25.3. Student Model được dùng ở đâu

| Nơi dùng | Dữ liệu | Mục đích |
|---|---|---|
| Contract compile | mastery/confidence KC tiên quyết, ReviewSchedule đến hạn | Bỏ qua hoặc giữ WARMUP_REVIEW, chọn item khởi đầu |
| Policy engine (mỗi lượt) | Snapshot (đóng băng đầu session, cập nhật cục bộ trong session) | R-STRONG-PRIOR, R-WEAK-PRIOR, chọn độ khó |
| Prompt L4 | Tóm tắt ngắn | Cá nhân hóa lời nói (không đưa số liệu nhạy cảm) |
| Reports | Toàn bộ | Teacher, Student, Parent |

---

## PART 27 — LEARNING ANALYTICS

### 27.1. Views theo role

| View | Student | Parent | Teacher |
|---|---|---|---|
| Ngôn ngữ | Rất đơn giản, tích cực | Dễ hiểu, không thuật ngữ | Có thuật ngữ, có evidence |
| Completion/attendance | Chuỗi ngày học (không gây áp lực) | ✅ số buổi, buổi bỏ lỡ, buổi dở dang | ✅ theo lớp |
| Understanding | "Đã nắm chắc / Cần luyện thêm" theo chủ đề | Trạng thái định tính theo chủ đề | Mastery + confidence + 7 chiều theo KC |
| Strengths/Weaknesses | 2–3 điểm | 2–3 điểm + gợi ý hỗ trợ ở nhà | Chi tiết + misconception + evidence drill-down |
| Trend | Tiến bộ tuần này | Xu hướng 4 tuần | Timeline mastery, velocity |
| Class | — | — | Heatmap lớp × KC, lỗi phổ biến, học sinh cần chú ý |
| Lesson effectiveness | — | — | Pre/post mastery theo lesson, tỉ lệ WORKED, thời gian |

**Trạng thái định tính dùng chung hai môn (DI-14),** cho Student và Parent:

| Nhãn hiển thị | Math (state) | English (rubric/support) |
|---|---|---|
| Chưa đủ dữ liệu | INSUFFICIENT_DATA | evidence_count < 2 |
| Đang làm quen | NOT_LEARNED, LEARNING, RECOGNIZED | rubric 1 |
| Làm được khi có hỗ trợ | PROCEDURAL | rubric 2 / phần lớn S2–S4 |
| Tự làm được | CONCEPTUAL, APPLIED | rubric 3 với S0/S1 |
| Vững và vận dụng | MASTERED, MASTERED_STABLE | rubric 4 + transfer |
| Cần ôn lại | AT_RISK, FORGOTTEN | trend giảm |

### 27.2. Biểu đồ (khung Toán §56) và thời điểm đưa vào

| Biểu đồ | Role | Phase | Lý do |
|---|---|---|---|
| Mastery gauge + confidence bar | Teacher, Student | Vertical slice | Cơ bản |
| Student × KC matrix (heatmap) | Teacher | Vertical slice (bảng màu đơn giản) | Giá trị lớn nhất cho giáo viên |
| Misconception chart (lớp và học sinh) | Teacher | Vertical slice | Có từ ngày đầu nhờ bug rules |
| Session timeline (activity, hint, outcome) | Teacher | Vertical slice | Truy vết Socratic |
| Radar 6 trục | Teacher | MVP | Cần đủ chiều (A, T, D) |
| Mastery timeline | Teacher, Parent | MVP | Cần ≥ 2 tuần dữ liệu |
| Knowledge graph (prerequisite + màu) | Teacher | Pilot | Cần KC graph ổn định |
| Retention / forgetting risk | Teacher | Pilot | Cần delayed probe |
| Learning behavior dashboard | Teacher | Pilot | Cần baseline |

### 27.3. Analytics bắt buộc từ ngày đầu (Q14)

Không phải dashboard đẹp, mà là **dữ liệu đúng và đủ** để mọi phân tích sau này làm được:

1. 100% event theo schema, có `sequence_no`, correlation id và policy/prompt version.
2. Attendance và completion theo session.
3. Kết quả từng item: outcome, support level tối đa, số hint, thời gian, modality.
4. Misconception frequency (học sinh và lớp).
5. Chỉ số Socratic: leak, reject rate, move fidelity mẫu.
6. Độ trễ và chi phí mỗi session (AI request log).
7. Mastery + confidence theo KC cho teacher view (kể cả khi confidence thấp, hiển thị kèm cảnh báo).

### 27.4. Cách xây

- MVP: read models là **materialized views và bảng projection trong Postgres**, được refresh bởi projector. Charts dùng thư viện FE (dễ đảo ngược).
- Sau pilot: CDC sang warehouse (BigQuery hoặc ClickHouse) cho phân tích cohort và nghiên cứu.
- Mọi con số trên dashboard có tooltip "vì sao", liên kết về danh sách evidence. Parent view không có drill-down transcript, trừ khi trường cho phép.
