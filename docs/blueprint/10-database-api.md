# 10 — Database / ERD · API Design

> PART 28, PART 29.

---

## PART 28 — DATABASE / ERD

### 28.1. Quy ước

- PostgreSQL 16+. Khóa chính `uuid` (UUIDv7, sắp xếp được theo thời gian).
- **Mọi bảng chứa dữ liệu người học hoặc nội dung trường** có `school_id` + RLS policy (ADR-003).
- Timestamp dùng `timestamptz` (lưu UTC), hiển thị theo `Asia/Ho_Chi_Minh`.
- Bảng append-only (event, evidence, override, audit): không `UPDATE`/`DELETE` ở tầng ứng dụng. Có trigger chặn.
- JSONB cho phần bán cấu trúc có schema (validate ở app, có `schema_version`).
- Migration dùng Alembic. Mỗi migration có test up/down trên DB tạm (testcontainers).

### 28.2. ERD (lõi của MVP)

```mermaid
erDiagram
    SCHOOL ||--o{ CLASS : has
    SCHOOL ||--o{ USER_ACCOUNT : has
    USER_ACCOUNT ||--o| STUDENT_PROFILE : "is"
    USER_ACCOUNT ||--o| TEACHER_PROFILE : "is"
    USER_ACCOUNT ||--o| PARENT_PROFILE : "is"
    CLASS ||--o{ ENROLLMENT : has
    STUDENT_PROFILE ||--o{ ENROLLMENT : in
    CLASS ||--o{ TEACHING_ASSIGNMENT : has
    TEACHER_PROFILE ||--o{ TEACHING_ASSIGNMENT : has
    STUDENT_PROFILE ||--o{ GUARDIAN_LINK : has
    PARENT_PROFILE ||--o{ GUARDIAN_LINK : has
    GUARDIAN_LINK ||--o{ CONSENT : records

    SUBJECT ||--o{ KNOWLEDGE_COMPONENT : has
    KNOWLEDGE_COMPONENT ||--o{ KC_PREREQUISITE : "requires"
    KNOWLEDGE_COMPONENT ||--o{ MISCONCEPTION : has
    SUBJECT ||--o{ SKILL : has

    CLASS ||--o{ LESSON : owns
    LESSON ||--o{ LESSON_VERSION : versions
    LESSON_VERSION ||--o{ MATERIAL : uses
    MATERIAL ||--o{ MATERIAL_ARTIFACT : produces
    LESSON_VERSION ||--o| LESSON_PACKAGE : "published as"
    LESSON_VERSION ||--o{ ITEM : contains
    ITEM ||--o{ ITEM_KC : maps
    KNOWLEDGE_COMPONENT ||--o{ ITEM_KC : maps
    ITEM ||--o{ HINT_TEMPLATE : has
    ITEM ||--o| ANSWER_KEY : "sealed"
    LESSON_VERSION ||--o{ RAG_CHUNK : indexes

    CLASS ||--o{ SCHEDULE_RULE : has
    SCHEDULE_RULE ||--o{ SCHEDULE_OCCURRENCE : materializes
    SCHEDULE_OCCURRENCE ||--o{ LEARNING_SESSION : "per student"
    STUDENT_PROFILE ||--o{ LEARNING_SESSION : attends
    LEARNING_SESSION ||--|| TUTOR_CONTRACT : binds
    LEARNING_SESSION ||--o{ SESSION_ACTIVITY : runs
    SESSION_ACTIVITY ||--o{ ITEM_ATTEMPT : has
    LEARNING_SESSION ||--o{ SESSION_EVENT : logs
    SESSION_EVENT ||--o{ EVIDENCE : derives
    EVIDENCE ||--o{ ASSESSMENT_RESULT : feeds
    STUDENT_PROFILE ||--o{ STUDENT_KC_STATE : has
    STUDENT_PROFILE ||--o{ STUDENT_SKILL_STATE : has
    STUDENT_PROFILE ||--o{ REVIEW_SCHEDULE : has
    STUDENT_KC_STATE ||--o{ TEACHER_OVERRIDE : "may have"

    LEARNING_SESSION ||--o{ AI_REQUEST_LOG : costs
    LEARNING_SESSION ||--o{ AUDIO_ASSET : records
```

### 28.3. Bảng chính (trường quan trọng)

**identity / org**

| Bảng | Trường chính |
|---|---|
| `school` | id, name, timezone, data_region, settings(jsonb), status |
| `user_account` | id, school_id, kind (STUDENT/TEACHER/PARENT/SCHOOL_ADMIN), display_name, status, created_at |
| `credential` | user_id, type (PASSWORD/PIN/PICTURE/OTP_PHONE/OTP_EMAIL/OIDC), secret_hash (argon2id), failed_count, locked_until |
| `student_profile` | user_id, given_name, family_name (mã hóa cột), grade, date_of_birth (tùy chọn, mã hóa), pseudonym_id (dùng cho AI) |
| `class` | id, school_id, name, grade, school_year |
| `enrollment` | class_id, student_id, status, from, to |
| `teaching_assignment` | class_id, teacher_id, subject_id, role |
| `guardian_link` | student_id, parent_id, relationship, verified_at, verified_by |
| `consent` | guardian_link_id, consent_version, scopes (AI_TUTORING, VOICE_RECORDING, TRANSCRIPT_RETENTION, ANALYTICS), granted_at, revoked_at, evidence_ref |

**curriculum**

| Bảng | Trường chính |
|---|---|
| `subject`, `grade_level` | code (math/english), name |
| `knowledge_component` | id (mã ổn định, ví dụ KC-DEC-CMP), subject, grade, name, description, version, status |
| `kc_prerequisite` | kc_id, prerequisite_kc_id, strength |
| `misconception` | id (DEC-M01), kc_id, description, bug_rule(jsonb), counter_examples(jsonb), severity (CRITICAL/NORMAL) |
| `skill` | id (reading.inference), subject, grade_band, description |

**content**

| Bảng | Trường chính |
|---|---|
| `lesson` | id, school_id, class_id?, subject, grade, title, owner_teacher_id |
| `lesson_version` | id, lesson_id, version_no, status (DRAFT/IN_REVIEW/APPROVED/PUBLISHED/ARCHIVED), metadata(jsonb, §22.3), approved_by, approved_at, published_at |
| `material` | id, school_id, lesson_version_id?, uploader_id, storage_key, mime, size, sha256, status |
| `material_artifact` | material_id, kind (PAGE_TEXT/PAGE_IMAGE/STRUCTURE/VALIDATION_REPORT), page_no, content(jsonb)/storage_key |
| `lesson_package` | id, lesson_version_id, content(jsonb bất biến), content_hash, built_at |
| `item` | id, lesson_version_id, purpose (PRACTICE/EXIT/REVIEW/HOMEWORK), cognitive_level, difficulty, transfer, expected_time_s, stem(jsonb), answer_spec(jsonb, chỉ cho PRACTICE), isomorphic_group, visibility |
| `answer_key` | item_id, answer_spec(jsonb), **chỉ module assessment đọc được** (schema/role riêng) |
| `item_kc` | item_id, kc_id, weight |
| `hint_template` | item_id, target, level, text, source (TEACHER/AI_APPROVED), approved_by |
| `rag_document`, `rag_chunk` | school_id, class_id, lesson_version_id, subject, grade, visibility, status, text, heading_path, source_ref(jsonb), embedding vector(N), embedding_model, tsv tsvector |

**scheduling / session**

| Bảng | Trường chính |
|---|---|
| `schedule_rule` | id, school_id, class_id, subject, weekdays, start_time, duration_min, valid_from/to, created_by |
| `lesson_assignment` | schedule_rule_id / occurrence_id, lesson_id, mode (FIXED/NEXT_IN_PLAN) |
| `schedule_occurrence` | id, rule_id, starts_at, ends_at, lesson_version_id?, status |
| `learning_session` | id, school_id, occurrence_id, student_id, kind (LESSON/HOMEWORK/REVIEW), lifecycle_state, state_version, contract_id, started_at, ended_at, active_seconds, resumable_until, end_reason |
| `tutor_contract` | id, session_id, contract(jsonb), content_hash, schema_version, compiled_at |
| `session_activity` | id, session_id, activity_key, type, status, started_at, ended_at, outcome(jsonb) |
| `item_attempt` | id, session_activity_id, item_id, variant_id, loop_state, attempt_no, max_hint_level, outcome, resolved_at |
| `session_event` | **partition theo tháng**; envelope PART 10.3; unique(session_id, sequence_no) |
| `outbox` | cho job/notification (transactional outbox) |

**assessment / learner**

| Bảng | Trường chính |
|---|---|
| `evidence` | id, school_id, student_id, session_id, source_event_ids[], kc_id / skill_id, dimension, score, weight, validity, construct, support_level, error_class, misconception_id, policy_version, supersedes_id |
| `assessment_result` | id, item_attempt_id, question_score / rubric_level, breakdown(jsonb), policy_version |
| `student_kc_state` | (student_id, kc_id, policy_version) PK; state(jsonb theo PART 25.1); updated_at |
| `student_skill_state` | (student_id, skill_id, policy_version) PK; state(jsonb) |
| `review_schedule` | student_id, kc_id/skill_id, due_at, kind (T1/T3/T7/T30), status |
| `teacher_override` | id, target_type, target_id, before(jsonb), after(jsonb), reason, teacher_id, created_at |
| `ai_flag` | id, session_event_id, teacher_id, category, note, status |

**ops**

| Bảng | Trường chính |
|---|---|
| `ai_request_log` | id, school_id?, session_id?, tutor_run_id, job_type, model_class, provider, model, prompt_version, input/output/cache_read/cache_write tokens, cost_usd, latency_ms, ttft_ms, stop_reason, validation_result, fallback_used |
| `rag_retrieval_log` | id, rag_request_id, session_id?, query, scope(jsonb), results(jsonb), latency_ms |
| `audio_asset` | id, school_id, session_id, storage_key, duration_ms, codec, purpose, retention_until, flagged |
| `audit_entry` | id, school_id, actor_id, action (VIEW_TRANSCRIPT/EXPORT/OVERRIDE/…), target, ip, at |
| `policy_version` | kind (PROMPT/TUTOR/HINT/MASTERY/MODEL/SAFETY), version, content_hash, released_at |

### 28.4. Index và partition quan trọng

- `session_event (session_id, sequence_no)`, `(student_id, occurred_at)`, partition theo tháng của `occurred_at`.
- `evidence (student_id, kc_id, created_at)`.
- `learning_session (student_id, lifecycle_state)`, `(occurrence_id)`.
- `rag_chunk` HNSW trên `embedding` + GIN trên `tsv` + btree trên `(school_id, subject, grade, status)`.

---

## PART 29 — API DESIGN

### 29.1. Nguyên tắc

- API theo **domain resource và command**, không theo màn hình.
- Command thay đổi state dùng `POST` + `Idempotency-Key` header + `expected_state_version` trong body.
- Mọi response lỗi có dạng `{ "error": { "code": "INVALID_STATE", "message": "...", "details": {...} } }`.
- Versioning: tiền tố `/v1`.
- Không endpoint nào nhận tên model hoặc provider từ client.
- OpenAPI sinh từ FastAPI → sinh TS client cho frontend.

### 29.2. Nhóm endpoint

**/auth**
```text
POST /v1/auth/student/login          {class_code, username, pin}
POST /v1/auth/login                  {email, password}                 (teacher)
POST /v1/auth/otp/request | /verify  (parent)
POST /v1/auth/logout
```

**/users, /students, /teachers, /parents, /classes**
```text
GET  /v1/me
GET  /v1/classes/{id}                          (teacher/admin)
POST /v1/classes/{id}/students                 (teacher cấp tài khoản học sinh)
POST /v1/classes/{id}/students/{sid}/reset-pin
POST /v1/students/{sid}/guardian-invitations   (teacher → parent)
POST /v1/guardian-invitations/{token}/accept   (parent)
POST /v1/guardian-links/{id}/consents          (parent: ghi nhận consent)
GET  /v1/students/me/today                     (student: buổi học hôm nay)
```

**/lessons, /materials, /exercises (items)**
```text
POST /v1/lessons                               (teacher)
POST /v1/lessons/{id}/versions                 (tạo draft version)
POST /v1/materials                             (upload, trả upload URL ký sẵn) → POST /v1/materials/{id}/process
GET  /v1/lesson-versions/{id}                  (draft + validation report)
PATCH /v1/lesson-versions/{id}                 (sửa draft)
POST /v1/lesson-versions/{id}/submit-review | /approve | /publish | /archive
GET  /v1/lesson-versions/{id}/items
PUT  /v1/items/{id} , PUT /v1/items/{id}/hints
```

**/schedules**
```text
POST /v1/classes/{id}/schedule-rules
PATCH /v1/schedule-rules/{id}
PATCH /v1/schedule-occurrences/{id}            (đổi giờ, hủy, đổi lesson)
GET  /v1/classes/{id}/calendar?from&to
```

**/sessions (runtime — command-style)**
```text
GET  /v1/sessions/{id}/state                   → snapshot đầy đủ (lifecycle, activity, item, transcript item hiện tại, state_version)
GET  /v1/sessions/{id}/stream                  → SSE (tutor tokens, state changes, time warnings, heartbeat)
POST /v1/sessions/{id}/join
POST /v1/sessions/{id}/responses               {item_attempt_id, kind: ANSWER|STEP|EXPLANATION|MESSAGE, content, modality, expected_state_version}
POST /v1/sessions/{id}/hint-requests           {item_attempt_id, preference?: SMALL|EXAMPLE}
POST /v1/sessions/{id}/choices                 {choice_id}              (micro choices do tutor đưa ra)
POST /v1/sessions/{id}/pause | /resume | /exit
POST /v1/sessions/{id}/teacher-actions         {action: PAUSE_TUTOR|RESUME|END_EARLY|EXTEND|MESSAGE, ...}  (teacher)
```

**/tutor (off-session, feature flag)**
```text
POST /v1/tutor/conversations                   (tạo hội thoại off-session; server chọn LIGHTWEIGHT)
POST /v1/tutor/conversations/{id}/messages
```
Không có `/tutor/chat` in-session tách rời. Trong giờ học, mọi tương tác đi qua `/sessions`.

**/assessment, /progress, /reports**
```text
GET  /v1/students/{sid}/progress?subject=math          (role-aware: student/parent/teacher có view khác)
GET  /v1/students/{sid}/kcs/{kc}/evidence              (teacher)
GET  /v1/classes/{id}/mastery-matrix?subject=math      (teacher)
GET  /v1/classes/{id}/misconceptions?from&to           (teacher)
POST /v1/assessment/overrides                          (teacher)
GET  /v1/sessions/{id}/report                          (teacher/parent/student view)
GET  /v1/sessions/{id}/transcript                      (teacher; audit)
POST /v1/sessions/{id}/ai-flags                        (teacher)
```

**/rag** (nội bộ và teacher)
```text
POST /v1/rag/search                    (teacher tìm trong tài liệu của mình; student không có quyền gọi trực tiếp)
```

**/voice**
```text
POST /v1/sessions/{id}/voice/stt-token         (ephemeral credential cho STT streaming, gắn session, TTL ngắn)
POST /v1/sessions/{id}/voice/realtime-token    (ephemeral token realtime provider, gắn contract; English Speaking)
POST /v1/sessions/{id}/voice/utterances        (upload audio segment + metadata nếu đi qua server)
```

**/notifications**
```text
GET  /v1/notifications
PATCH /v1/notifications/{id}/read
PUT  /v1/me/notification-preferences
```

### 29.3. Ví dụ command và response

```http
POST /v1/sessions/7f3.../responses
Idempotency-Key: 4a1c-...
Content-Type: application/json

{
  "item_attempt_id": "c19...",
  "kind": "ANSWER",
  "content": {"text": "0,25 > 0,3"},
  "modality": "TEXT",
  "expected_state_version": 42
}
```

```json
{
  "accepted": true,
  "state_version": 43,
  "tutor_turn_id": "b77...",
  "stream": "/v1/sessions/7f3.../stream"
}
```

Lời tutor được stream qua SSE với `event: tutor.delta`, sau đó `event: tutor.final` (kèm `move`, `hint_level` cho UI hiển thị "gợi ý mức 2") và `event: state` (state mới).
