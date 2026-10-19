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

  * **`cavat_test`** (hoặc `cavat_test_<12 ký tự hex>`, một database tạm cho mỗi test) — integration test trên MongoDB Atlas thật.
  * **`cavat_dev`** — dữ liệu phát triển/demo sau khi seed thủ công.
  * **`cavat_prod`** — production, chưa dùng ở giai đoạn hiện tại.
* Không task nào được dùng `cavat_dev` hoặc `cavat_prod` làm database test.
* Mọi test MongoDB Atlas thật phải có marker `@pytest.mark.atlas`.
* Atlas test phải tự skip khi cloud không có `MONGODB_URI`.
* Atlas test phải gọi safety guard dạng allow-list (`cavat_test` hoặc `cavat_test_<12 ký tự hex>`) trước mọi thao tác ghi hoặc xóa; tên khác thì fail ngay.
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
* [ ] Atlas tests chỉ dùng database họ `cavat_test` (qua safety guard allow-list).
* [ ] Có safety guard chống nhầm database.
* [ ] Atlas test cleanup chạy kể cả khi test fail.
* [ ] Không có auto-seed.
* [ ] `make seed` là explicit command.
* [ ] Demo records có `is_demo: true`.
* [ ] Không có code test/seed chạm `cavat_dev` hoặc `cavat_prod`.
* [ ] Với T07/T08: chủ repo đã chạy `make test` local trước merge.

## Đã có trên `main`

| Phần | Trạng thái |
|---|---|
| `cavat/core/pedagogy.py` | Enum dùng chung: HintLevel, HintTarget, Move, Outcome, ErrorClass, ActivityType, ItemResolution |
| `cavat/core/events.py` | **Hợp đồng event**: `EventType` và payload có kiểu (QUESTION_SHOWN, ANSWER_SUBMITTED, EXPLANATION_SUBMITTED, POLICY_DECISION, HINT_DELIVERED, ITEM_RESOLVED...). Bên sinh event là T04, bên đọc là T10 |
| `cavat/modules/tutor/contracts.py` | **Hợp đồng tutor**: `StudentSnapshot`, `ItemState`, `PolicyInput`, `PolicyDecision`, `RenderContext`, `RenderedMessage`, `MessageRenderer`, `ValidationResult`. T02, T03, T04, T06b dùng chung, **không định nghĩa lại** |
| `cavat/modules/content/lesson_package.py` | Model, loader, `validate_package` cho lesson YAML |
| `cavat/modules/assessment/` | Bộ đọc số vi-VN và bộ chấm Toán, bug rule M01–M05 (T01, 256 test) |
| `cavat/core/repository.py`, `memory_db.py`, `db_guard.py`, `modules/*/repository.py` | Tầng MongoDB, repository theo module, guard cho test Atlas (T07) |
| `apps/web` | Web app học sinh và giáo viên (T09): chạy mock (`make web`) hoặc API thật (`make web-live`, T13) |
| `cavat/modules/tutor/policy.py` | Policy gợi ý tất định, mọi quyết định có `rule_ids` (T02, bổ sung ở T04). Bản `hint-policy/0.5.0` (ADR-019: đọc ý định học sinh trước khi chấm) |
| `cavat/modules/tutor/renderer.py`, `validator.py` | Câu mẫu cho mọi move và bộ chặn output (T03). Câu chữ trong `PHRASES` đã được chủ dự án duyệt ngày 2026-10-01 |
| `cavat/modules/tutor/item_loop.py` | `ItemTutor`: vòng lặp một câu hỏi, probe tách nguyên nhân, sinh event (T04) |
| `cavat/modules/ai_gateway/` | Groq (Qwen, Whisper), Gemini (ảnh), router có chuỗi dự phòng và trần lượt gọi, model giả, `make ai-ping` (T06a) |
| `cavat/modules/tutor/prompt_builder.py`, `llm_renderer.py`, `prompts/` | Qwen diễn đạt nước đi, câu mẫu làm dự phòng; câu EXIT chỉ dùng câu mẫu (T06b bản gọn). Từ `llm-renderer.v2`: Qwen chỉ diễn đạt PROBE, HINT, COGNITIVE_CONFLICT, NUDGE, REDIRECT và phải bám câu mẫu |
| `cavat/modules/session/service.py`, `api.py` | API một buổi học 8 câu; bật Qwen bằng `TUTOR_RENDERER=llm`, mặc định câu mẫu (T08 bản gọn); danh sách buổi học và transcript cho giáo viên (T13). `make api-memory` chạy API với database trong bộ nhớ |

### Phần còn thiếu của các task đã gộp (bản gọn)

- **T06b:** chưa phân tích câu "vì sao" của học sinh thành `reasoning_quality`. Chưa có eval regression cho prompt (chờ T05).
- **T08:** chưa có `GET /v1/sessions/{id}/stream` (SSE), hẹn giờ im lặng (trigger `SILENCE`), giới hạn thời gian buổi học. Auth vẫn là header tạm `X-Demo-Student` và `X-Demo-Teacher` (chờ T12).
- **T13:** `apps/web/src/api/contract.ts` vẫn viết tay, chưa sinh từ OpenAPI. Vì chưa có SSE, web đọc `GET /state` sau mỗi lệnh rồi tự phát stream.
- **An toàn:** event `SAFETY_FLAGGED` đã được ghi, chưa có màn hình cho giáo viên.
- **Bộ chặn lộ đáp án** với câu trắc nghiệm và đúng/sai chỉ dựa vào `leak_patterns`; cần T05 để đo.
- **Gemini `describe_image`:** `make ai-ping` trả HTTP 503 ngày 2026-10-01, chưa rõ nguyên nhân.
| `docs/adr/ADR-017-model-roles-qwen-gemini.md` | **Qwen trên Groq là bộ não tutor**; Gemini chỉ cho ảnh/OCR và giọng nói |
| `docs/poc/free-tier-quota.md` | Hạn mức free đo thật của Groq và Gemini, cách tắt suy luận của Qwen |

## Kế hoạch v1 (hiện hành, duyệt 2026-10-06)

Chi tiết: `docs/plan/plan-v1-teaching-knowledge-graph.md`, ADR-018, D-T9 đến D-T11. Gia sư **dạy** theo vòng 7 bước trên đồ thị tri thức; Hybrid RAG và mọi thành phần AI **tự xây**. Credit cloud đã hết: các task làm ở local, mỗi task một nhánh và một PR.

### Mốc 1: vòng dạy chạy được ở phần đầu chương Số thập phân (7 node)

| Task | Nội dung | Thay task cũ | Trạng thái |
|---|---|---|---|
| M1-1 | Ghi kế hoạch vào repo | — | Xong (PR #24) |
| M1-2 | Khuôn gói chương (đồ thị hai tầng, quan hệ, nội dung theo 4 mức, quy tắc qua node), bộ đọc, bộ kiểm tra; gói chương Số thập phân phần đầu (nháp) | — | Xong: khuôn và bộ kiểm tra (PR #25); gói chương 7 node `docs/pedagogy/math-g5/chuong-so-thap-phan/chapter.yaml` và bài `khai-niem-so-thap-phan` (M1-2b, nháp chờ duyệt) |
| M1-3 | Điểm từng node: projector tất định theo PART 25.2 và 26.1, cổng qua node (DI-15), điểm khởi đầu từ tiên quyết (DI-16) | T10 | Xong: `assessment/projector.py`, policy `node-mastery/0.1.0`, chấm phần con nói lại `assessment/retell.py` |
| M1-2c | Thêm 2–3 câu luyện cho mỗi node (nháp chờ duyệt) để còn câu mới khi quay về node tiên quyết giữa buổi (kế hoạch 5.4, [OPEN]) | — | Bỏ: hai chương giờ dựng từ tài liệu của chủ dự án (DATA-1, DATA-2), câu luyện lấy từ ngân hàng câu |
| M1-4 | Chính sách dạy theo node (luật `N-*`) | — | Xong: `teaching/node_policy.py` (policy `node-policy/0.1.0`), trạng thái dạy `teaching/state.py`, sự kiện `NODE_DECISION` |
| M1-5 | Hybrid RAG tự xây: chia đoạn, BM25 hai bản, chỉ mục vector, RRF, xếp hạng lại theo sư phạm, ghi vết; model class `EMBEDDING`; bộ câu hỏi đánh giá đầu tiên | — | Xong: RAG-1 (PR #39) |
| M1-6 | Bộ máy vòng dạy 7 bước, dùng vòng kèm từng câu ở bước luyện tập; test hội thoại trọn 7 node | — | Xong: `teaching/loop.py` (mẫu câu `teaching-templates/0.1.0`); hội thoại trọn 7 node chạy offline, tiếp tục được từ sự kiện đã lưu |
| M1-7 | Nối vào API buổi học và web: bản đồ node, lời giảng, ô giải thích | T08, T13 (mở rộng) | Xong: buổi học theo chương qua API, màn học sinh có bản đồ và 7 bước, màn giáo viên "Bộ não gia sư" (`GET /report`); lưu lịch sử hội thoại và học tiếp qua nhiều buổi (M1-7b) |
| M1-8 | Học sinh ảo: lỗi sai và chỗ hổng tiên quyết; không công nhận "đã hiểu" sai | T05 | Xong: học sinh giả lập "Vương" (`make simulate`, CTX-2 PR #52, SIM-2 PR #59) |
| M1-9 | Qwen diễn đạt lời giảng neo vào đoạn của Hybrid RAG; chạy thử thật | T06b (mở rộng) | Xong: RAG-2 (PR #40) |

### Giao diện hoàn chỉnh (yêu cầu 2026-10-06)

Chủ dự án yêu cầu giao diện hoàn chỉnh, đẹp, có thêm vai trò phụ huynh, tham khảo phong cách trang lac-buddy-ai-companion.lovable.app. Phần mức hiểu bài phải hiển thị đúng hai khung đánh giá (blueprint PART 27.1, 25, 56).

| Task | Nội dung | Trạng thái |
|---|---|---|
| UI-1 | Hệ thiết kế (màu, font Be Vietnam Pro, thẻ, linh vật tự vẽ), trang giới thiệu, trang chủ học sinh có tiến bộ của chương, vai trò phụ huynh (`/parent`, mức hiểu bằng chữ DI-14, xu hướng 4 tuần, gợi ý ở nhà), màn học và trang giáo viên theo giao diện mới; endpoint `GET /v1/students/me/overview`, `GET /v1/parents/children/{code}` | Xong (PR #32) |
| UI-2 | Bảng theo dõi lớp cho giáo viên: chỉ số tổng, bản đồ nhiệt học sinh × bài theo vùng màu PART 25, biểu đồ lỗi hay gặp, học sinh cần chú ý; báo cáo từng học sinh có đồng hồ điểm M kèm độ tin cậy, radar 6 trục, tiến bộ theo ngày, hoạt động học, chi tiết từng bài (khung Toán §23–§28, §39, §43–§46, §56, §57) | Xong: `GET /v1/teachers/class`, `GET /v1/teachers/students/{id}`, trang Lớp học và Báo cáo học sinh |

### Gia sư hiểu học sinh và bộ test khó (góp ý 2026-10-06)

Chủ dự án chạy thử và chỉ ra: giao diện chữ quá to; gia sư chưa xử lý "không biết", "là sao", lạc đề; gia sư nói quá ít lời; test quá dễ. Tham khảo kiến trúc gia sư của repo Edubot (ADR-019).

| Task | Nội dung | Trạng thái |
|---|---|---|
| TQ-1 | Đọc ý định học sinh trước khi chấm, luật R-OFF-TOPIC, R-CLARIFY, R-AFFECT (`hint-policy/0.5.0`), câu dẫn ấm hơn (`template-renderer.v3`), lời đáp câu hỏi lý thuyết (`teaching-templates/0.2.0`), prompt v2, 10 vai học sinh khó chạy offline; màn học chữ nhỏ lại | Xong (PR #34) |
| UI-3 | Thu gọn các trang còn lại: tiêu đề và con số nhỏ một bậc, ghi chú cách tính của giáo viên gấp vào "Cách tính" | Xong |
| TQ-2 | Chạy 10 vai học sinh khó với Qwen thật, giám khảo LLM chấm từng lượt (sư phạm, an toàn, cảm xúc, chính xác, lộ đáp án) như Edubot; báo cáo `docs/poc/` | Xong: `make eval-hard`, báo cáo `evals/reports/2026-10-07-hard-students-live.md` (19 lượt, 0 lộ đáp án) |
| TQ-3 | Chấm lời giải thích "vì sao" (vai "đúng mà lý do sai": "vì con đoán") | Xong: WHY-1 (PR #57, DI-55) |

### Tài khoản, tài liệu giáo viên, RAG (yêu cầu 2026-10-07, ADR-020)

| Task | Nội dung | Trạng thái |
|---|---|---|
| ACC-1 | 1 học sinh, 1 phụ huynh, 1 giáo viên cố định (`make accounts`), đăng nhập bằng PIN, token ký HMAC, phụ huynh gắn với con, tên học sinh lấy từ tài khoản | Xong (PR #37) |
| ACC-2 | Không đăng xuất, chỉ chuyển vai: nút Học sinh / Phụ huynh / Giáo viên ở đầu trang, mỗi vai một màu; lần đầu mở một vai trên máy thì nhập PIN của vai đó, sau đó chuyển một chạm (giữ đăng nhập riêng từng vai). Bỏ ô "Con tên là gì?": chế độ chạy thử cũng chỉ có 1 học sinh mẫu (An). Đã xóa 5 buổi cũ trước khi có tài khoản trong `cavat_dev` (chủ dự án đồng ý 2026-10-12) | Xong |
| DOC-1 | Thư viện tài liệu của giáo viên: tải lên (PDF, DOCX, ảnh), lưu file gốc ở `var/storage/`, đọc ra chữ, gắn chương/bài; trang xem nội dung bài (lý thuyết, ví dụ, câu hỏi, gợi ý, đáp án, trạng thái duyệt) | Xong (PR #38) |
| RAG-1 | Hybrid RAG tự xây (M1-5): chia đoạn theo cấu trúc, BM25 hai bản, embedding Gemini, chỉ mục vector tự viết, RRF, xếp hạng lại theo sư phạm, ghi vết; trang tra cứu cho giáo viên; bộ câu hỏi Recall@k, MRR | Xong: tab RAG của giáo viên, `make eval-rag` (plan v1 mục 5.5.6; báo cáo `evals/reports/2026-10-07-rag-gemini.md`) |
| RAG-2 | Gia sư nói theo đoạn truy xuất, có nguồn (M1-9); validator kiểm tra bám đoạn và không lộ đáp án. Yêu cầu rút từ RAG-1, xem danh sách dưới bảng | Xong: ADR-021, `make eval-grounded`, báo cáo `evals/reports/2026-10-07-grounded-live.md`; đủ 21 ca với `grounded-speech/0.2.2`: `evals/reports/2026-10-13-grounded-live.md` |
| SAFE-1 | Cờ an toàn lên màn hình giáo viên: lượt hội thoại có chip đỏ, lớp học có lý do "cần xem ngay"; nhận diện câu đáng lo (DI-41) cả lúc làm bài tập; trước đó chỉ ghi sự kiện `SAFETY_FLAGGED` mà chưa ai thấy. Bước "giáo viên đã xem": nút "Cô đã xem" ở trang lớp, lưu riêng ở `safety_reviews` (không ghi vào sổ của buổi học), cờ mới sau lúc xem thì hiện lại | Xong |
| CTX-1 | Gia sư hiểu và đáp theo ngữ cảnh (ADR-022): Qwen đọc câu không rõ (đề xuất nhãn, ghi `MESSAGE_READ`), nước đi EXPLAIN, prompt v3 có định hướng và ví dụ, Qwen viết tự do nhưng phải giữ ý chính; vá lỗi câu Qwen nhắc riêng phương án đúng của câu trắc nghiệm | Xong. `make eval-hard` chạy thật: 3 vai CTX được 5,0/4,8/5,0/5,0 (báo cáo 2026-10-08) |
| TQ-3 | Giám khảo của `make eval-hard` nhận lượt dạng các dòng có nhãn (dạng JSON khiến nó chấm 1/1/1/1 "không có phản hồi"); chặn câu Qwen gọi học sinh sai xưng hô (`WRONG_ADDRESS`, cả lời có căn cứ `grounded-speech/0.2.2`) | Xong |
| AUTO-1 | Bước tới Qwen tự chủ (ADR-022 gọi là CTX-2; mã này đã dùng cho bộ điều phối, PR #52): chính sách đưa các nước đi được phép, không nước nào giúp nhiều hơn nước của chính sách; Qwen chọn nước và nêu lý do; chính sách kiểm lại. ADR-031, DI-62 | Xong. Đã so với `TUTOR_CHOOSER=policy` trên học sinh mô phỏng (AUTO-2, DI-62): chưa đủ để kết luận, Qwen giữ nước của chính sách cả 4 lần chọn. Còn: đo trên học sinh thật, với nhiều lần chọn hơn |
| RAG-3 | Câu con tự hỏi trong lúc làm bài tập (không phải bài kiểm tra): trả lời có căn cứ mà không lộ đáp án câu đang làm; prompt `grounded.v2` chọn đoạn trả lời đúng câu hỏi thay vì đoạn đứng đầu (ca G09) | Một phần: RAG-3 (PR #53, DI-50) giới hạn phạm vi và báo "bài sau"; định tuyến về tiết đã học DI-57 (EVAL-1, PR #60) |
| DATA-1 | Chương Số thập phân dựng lại từ tài liệu thật của chủ dự án: INGEST-1..4 trên các file `STP-*` | Xong: phát hành 2026-10-12 (INGEST-5, PR #51), 11 tiết |
| DATA-2 | Chương Diện tích hình tam giác, hình thang: INGEST-1..4 trên các file `DTTGHT-*`, kèm bài nền nhân, chia số thập phân (chủ dự án quyết 2026-10-12: "vẫn dạy") | Xong phần chương: phát hành 2026-10-12 (PR #51), 8 tiết. **Chưa:** bài nền nhân, chia số thập phân, vì chưa có tài liệu `NHANCHIA-*` |
| INGEST-1 | Đọc tài liệu từng trang có kiểm chứng (ADR-023, DI-43): Gemini đọc lại trang có ảnh, hình vẽ, trục số; mọi số của lớp chữ phải có trong bản đọc; loại tài liệu mới (bài giảng, phiếu, đáp án, lỗi sai); **đáp án và đề kiểm tra không vào RAG**; `make library-import DIR=tailieu` | Xong |
| INGEST-2 | Ngân hàng câu nháp (ADR-024, DI-44): tách bài tập, phiếu, đề thành câu nhỏ kèm đáp án, gắn tiết theo giáo án, kiểm mọi đáp án với đề bằng tính toán chính xác và kiểm "có căn cứ"; `make item-bank`, `make eval-items` (độ nhạy 97,1% / 98,4%), API giáo viên `/v1/teachers/item-banks/…` | Xong |
| INGEST-3a | Phương án dạy nháp (ADR-025, DI-45): mỗi tiết một node; cách giảng, phương pháp, bài mẫu, "con nói lại", lỗi sai lấy nguyên văn từ tài liệu kèm trang; câu theo 4 mức từ ngân hàng câu; đáp án chuyển sang dạng bộ chấm dùng; `make teaching-plan`, API giáo viên | Xong |
| INGEST-3b | Qwen soạn phần tài liệu không có (ADR-026, DI-46): thang gợi ý H1–H3 qua bộ kiểm của gia sư, câu trả lời mẫu và cách nói được chấp nhận, ý chính để con nói lại; câu kiểm tra không bao giờ gửi model; lưu vết từng phần; `make draft-teaching` | Xong |
| INGEST-4a | Quyết định của giáo viên (ADR-027): duyệt, loại, sửa câu, gợi ý và phần của bài; thêm cách giảng hoặc bài mẫu; chuyển mức câu; giữ qua mọi lần dựng lại; phát hành khi mọi bài đã duyệt và không còn chỗ thiếu; gia sư dạy bản phát hành, buổi cũ phát lại đúng version | Xong |
| INGEST-4b | Trang duyệt `/teacher/plans/:chương` (từ tab Bài học): từng bài với trang nguồn, sửa cách giảng, câu trả lời mẫu, quy tắc, ý chính; từng câu với trạng thái kiểm, sửa đáp án, bỏ câu, chuyển mức; gợi ý có nhãn "AI soạn" với nút duyệt, sửa, loại; mục câu chưa được dạy (đáp án đọc lệch) để sửa; nút phát hành | Xong |
| RAG-3 | Đánh giá lại Hybrid RAG trên tài liệu thật: bộ câu hỏi mới có phần giữ riêng, chạy `make eval-rag LIVE=1`, báo số liệu | Xong: `make eval-rag-published` (RAG-3, PR #53); tập giữ riêng v2 đóng băng, định tuyến DI-57 (EVAL-1, PR #60) |

**RAG-2, những điều RAG-1 đã chốt cho bước nối với gia sư:**
- Câu truy vấn ghép câu học sinh vừa nói với tên, mô tả bài và mã lỗi sai vừa gặp (plan 5.5.3). Nhưng **"có căn cứ" phải tính trên chính câu của học sinh**: ghép tên bài vào thì câu lạc đề nào cũng gần nội dung chương hơn.
- Đang chờ học sinh trả lời câu kiểm tra của cách giảng T thì đoạn T vào prompt **không kèm lời đáp** (`Chunk.extra["reply"]`).
- **Kiểm chứng câu Qwen nói với đoạn neo**, như lớp kiểm chứng "khẳng định và bằng chứng" của 2T-KT:
  - mọi số, số thập phân, phân số và thuật ngữ của bài trong câu trả lời phải có trong đoạn neo hoặc trong câu học sinh;
  - lệch thì dùng câu đã duyệt;
  - ghi tỉ lệ bị loại vào eval.
- Không có căn cứ: gia sư quay về nội dung chính của bài và ghi câu hỏi cho giáo viên; không gọi Qwen để trả lời câu đó.
- Sự kiện `RAG_RETRIEVED` (mã đoạn, điểm từng tín hiệu, có căn cứ hay không) nằm trong document buổi học. Tab Hội thoại của giáo viên hiện nguồn của từng câu gia sư nói.
- Eval: chạy lại `make eval-rag LIVE=1` khi đổi tham số; thêm vào bộ câu hỏi các câu học sinh thật hỏi (lấy từ log), có nhãn do giáo viên duyệt.

### Mốc 2 và Mốc 3

Đã xong: đường đọc tài liệu tự xây (INGEST-1..5), hai chương dựng từ tài liệu thật và đã phát hành, chấm lời giải thích (WHY-1), báo cáo giáo viên. Giọng nói quay lại demo (D-T12, ADR-030, VOICE-1/2, PR #55, #58).

### Sau Mốc 3 (2026-10-13 đến 2026-10-16)

| Task | Nội dung | Trạng thái |
|---|---|---|
| TEACH-1, TEACH-2 | Hỏi lại ý chính của bài đã học (N-RECALL, DI-52); nhắc bài gốc sau câu sai đầu (DI-53) | Xong (PR #54, #55) |
| MISC-1 | Nhận ra lỗi sai điển hình của giáo viên trong đáp án sai (DI-54) | Xong (PR #56) |
| SIM-2 | "Vương" học lại hai chương; làm lại câu bù dạng (DI-56) | Xong (PR #59) |
| EVAL-1 | Đánh giá cho luận văn: định tuyến DI-57, chấm số đọc bằng chữ DI-58, tập giữ riêng đóng băng bằng thẻ git | Xong (PR #60) |
| PAPER-2..11 | Bài báo: bản dài `docs/paper/cavat-paper.tex`, bản 8 trang `cavat-paper-compact.tex`, số liệu sinh bằng `make paper-data` | Xong (PR #61–#71) |
| FIX-1 | Thành thạo tạm thời từ M ≥ 85 theo §53 (DI-59, `node-mastery/0.3.0`); luật "lộ đáp án" kiểm cả câu trắc nghiệm (B1 15/25 → 18/25); ghi nguồn từng lượt của CAVAT | Xong (PR #72) |
| LLM-1 | Lần kiểm cuối dùng trần từ theo câu mẫu, lời đã duyệt không còn bị thay bằng câu chung chung; sửa tại chỗ hai lỗi hình thức (DI-60) | Xong (PR #73) |
| LLM-2 | Dành lượt gọi Qwen cho giải thích, gợi ý, kéo về bài; giữ trần 15 (DI-61) | Xong (PR #74) |
| DOCS-1 | BACKLOG theo đúng hiện trạng; bản REV-ECIT 2026 vào `docs/paper/rev-ecit-2026/` | Xong |

### Việc còn mở

- **Thử với học sinh thật (chiều 8 của khung đánh giá):** chủ dự án để sau (2026-10-16).
- **Bài nền nhân, chia số thập phân** cho chương hình học: chờ tài liệu `NHANCHIA-*.pdf`.
- **Bài báo:** số liệu và chữ của ba bản đã khớp lần chạy lại ngày 19/10 (PAPER-12, PR #76): B1 18/25, CAVAT 0/24 với 8 lượt Qwen viết. Luận văn viết sau.
- **Duyệt nội dung:** 1 324/1 326 quyết định duyệt do trợ lý AI làm theo ủy quyền; chủ dự án nên tự duyệt lại một phần trước khi bảo vệ.
- **AUTO-1:** đã làm (ADR-031). Đã so với `TUTOR_CHOOSER=policy` trên học sinh mô phỏng (AUTO-2, DI-62): chênh lệch không đủ để kết luận, vì mỗi buổi chỉ có 2 lần chọn và Qwen giữ nước của chính sách cả 4 lần. Chưa đo trên học sinh thật.

## Kế hoạch theo đợt (cũ, trước 2026-10-06)

Mỗi dòng là một phiên cloud. Các task trong cùng một đợt chạy song song được vì chỉ phụ thuộc vào phần đã có trên `main` và vào hai file hợp đồng ở trên.

```text
Đợt 1 (mở ngay):        T02 policy · T03 renderer+validator · T06a gateway Groq/Gemini · T10 projector
                        T11 make seed · T12 đăng nhập            (T11, T12 là phụ, mở khi còn quota)
Đợt 2 (sau T02 + T03):  T04 item loop          · T06b LLM renderer + prompt gọn  (T06b cần thêm T06a)
Đợt 3 (sau T04):        T05 học sinh ảo + POC 1 · T08 session API
Đợt 4 (sau T08):        T13 nối web với API thật · T14 nhập tài liệu giáo viên · T15 giọng nói Toán
```

**Thứ tự ưu tiên nếu hết quota:** T02, T03, T04, T05 (chứng minh được Socratic offline), sau đó T06a, T06b, T08, T13 (có buổi học chạy thật trên web), sau đó T10, các task còn lại.

**Tình trạng ngày 2026-10-01:** T02, T03, T04, T06a, T06b (bản gọn), T08 (bản gọn) và T13 đã gộp; một buổi học 8 câu đã chạy trọn từ trình duyệt tới API với Qwen thật. Credit cloud đã hết, các task còn lại làm ở local theo thứ tự: T10 (projector), T05 (học sinh ảo), rồi các task khác.

**Quy tắc riêng cho nhóm tutor:** dùng dataclass trong `tutor/contracts.py` và payload trong `core/events.py`. Nếu thấy hợp đồng thiếu, chỉ được **thêm trường có giá trị mặc định** và ghi rõ trong PR. Đổi tên hay xóa trường thì phải dừng và hỏi chủ dự án.

---

## T02 — Tutor policy và hint engine (đợt 1)

**Đọc:** blueprint 05 PART 15.2 (bảng luật R-*), 16.3; `tutor/contracts.py`.

**Làm:** tạo `cavat/modules/tutor/policy.py` với `HintPolicyConfig` và hàm thuần `decide(inp: PolicyInput, cfg) -> PolicyDecision`.

- **`HintPolicyConfig`:** mức gợi ý tối đa theo activity (CONCEPT_CHECK H3, GUIDED_PRACTICE H7, INDEPENDENT_PRACTICE H5, EXIT_ASSESSMENT H1); leo thang +1 mỗi lượt, +2 khi học sinh có cảm xúc tiêu cực; ngưỡng misconception 0.7; frustration sau 3 lượt không tiến triển hoặc 240 s; verify_rate 0.5; nhắc khi im lặng tối đa 2 lần.
- **Luật:** R-TIME, R-CORRECT, R-VERIFY, R-TEACH-BACK, R-CONFIRM, R-NO-RESPONSE, R-HELP-REQUEST (lần đầu OFFER_CHOICE), R-REDIRECT, R-FRUSTRATION (H6) rồi R-FULL (H7), R-ASSESS-CAP, R-SLIP, R-MISC-HIGH (COGNITIVE_CONFLICT, nhảy tối đa +2 và ít nhất lên H2), R-FIRST-WRONG (PROBE) hoặc R-WEAK-PRIOR (H1), R-ESCALATE. Mỗi quyết định ghi `rule_ids`.

**Xong khi:**
- Mỗi luật có ít nhất một test, dựng `PolicyInput` bằng item thật của `lesson.yaml` và `CheckResult` từ `check_answer`.
- Không có đường nào vượt mức gợi ý tối đa của activity (test tham số hóa trên mọi activity).
- Resolution đúng `resolution_for`: H0 → INDEPENDENT, ≤ H5 → SUPPORTED, H6–H7 → WORKED.

## T03 — Template renderer và output validator (đợt 1)

**Đọc:** PART 13.4, 14, 15.3; `tutor/contracts.py`; trong `lesson.yaml` xem hints, counter_examples, worked_solution, verify_prompt.

**Làm:**
- **`tutor/renderer.py`**, `TemplateRenderer` implement `MessageRenderer`:
  - Câu tiếng Việt cho mọi `Move`, xưng "cô" – "con".
  - Chọn hint theo thứ tự (đổi ngày 2026-10-01, xem PART 15.3): template đúng mức của item → của `generic_hints` → template mạnh nhất dưới mức đó của item → của `generic_hints` → câu dự phòng; `SELF_CHECK` và `FORMAT` tra theo target trước. Ghi `hint_ref`.
  - Điền `{left}`/`{right}` cho counter_examples. WORKED_GUIDANCE hiện mọi bước trừ bước cuối. FULL_EXPLANATION = explanation + mời học sinh nói lại.
- **`tutor/validator.py`**, hàm `validate_message(text, ctx) -> ValidationResult` (khớp `MessageValidator`):
  - ANSWER_LEAK: câu khẳng định "SỐ QUAN_HỆ SỐ" trùng đáp án, dạng "x = đáp án", `leak_patterns` áp trên văn bản chữ thường **còn dấu** (quy ước mới trong header `lesson.yaml`; pattern đã có `\b`). Câu hỏi kiểu "số nào lớn hơn?" không phải lộ đáp án. Không kiểm tra lộ đáp án khi move là FULL_EXPLANATION.
  - MULTIPLE_QUESTIONS, MISSING_QUESTION (theo `MOVES_REQUIRING_QUESTION`), TOO_LONG (> `ctx.max_words`), PII_REQUEST, INTELLIGENCE_PRAISE, UNGROUNDED_NUMBER, EMPTY.

**Xong khi:** render mọi cặp (item PRACTICE × move) đều qua validator (test tham số hóa, dùng `PolicyDecision` dựng tay nên không cần T02); có test lộ đáp án cả dương tính lẫn âm tính.

## T06a — AI Gateway: Groq (Qwen, Whisper) và Gemini (ảnh) (đợt 1)

**Đọc:** ADR-017, `docs/poc/free-tier-quota.md`, PART 11–12.

**Làm:**
- **`ai_gateway/base.py`:** `ModelClass`, `ChatRequest`/`ChatResult` (có usage token), lỗi `QuotaExceeded` (kèm thời điểm reset nếu có), `ModelUnavailable`, `InvalidModelOutput`; `QuotaTracker` đọc header `x-ratelimit-*`.
- **`ai_gateway/groq.py`:** gọi API tương thích OpenAI bằng `httpx`, không thêm SDK. Chat dùng `reasoning_effort: "none"` và `response_format` json_schema strict (cả hai đã được kiểm chứng). Từ chối gửi khi ước lượng prompt > 3.000 token. 429 → `QuotaExceeded`. Có `transcribe(audio, language="vi")` dùng `whisper-large-v3`.
- **`ai_gateway/gemini.py`:** chỉ `describe_image(image_bytes, prompt)` cho ảnh hình học và đề bài chụp, google-genai 2.x với `thinking_level=LOW`. Không dùng Gemini cho chat.
- **`ai_gateway/router.py`:** chọn theo `ModelClass`, chuỗi dự phòng (Qwen → gpt-oss-120b → báo cho bên gọi dùng câu mẫu), trần `MAX_LLM_CALLS_PER_SESSION`.
- **`ai_gateway/fake.py`:** model giả có kịch bản, cho mọi test.
- `make ai-ping`: gọi thử Groq và Gemini một lần bằng khóa trong `.env` (chạy ở máy local).

**Xong khi:** test offline bằng `httpx.MockTransport` cho thấy: JSON hợp lệ được parse; 429 chuyển sang model dự phòng rồi báo dùng câu mẫu; prompt quá dài bị từ chối trước khi gửi; không file nào ngoài `ai_gateway/` import SDK hay URL của nhà cung cấp.

## T10 — Assessment projector v1 (đợt 1)

**Đọc:** blueprint 09 (PART 25–26 và DI-1…DI-14); `core/events.py`.

**Làm:** `assessment/projector.py`, hàm thuần có `policy_version`:
1. Đọc payload `ITEM_RESOLVED`, `ANSWER_SUBMITTED`, `EXPLANATION_SUBMITTED` (validate bằng `PAYLOAD_MODELS`) → evidence theo 7 chiều C, R, A, T, I, S, D.
2. Evidence → phân phối Beta theo từng chiều; tính M (chuẩn hóa lại trọng số khi thiếu chiều), confidence (DI-11), trạng thái và các gate UNDERSTOOD, MASTERED, PROVISIONALLY_MASTERED.
3. Ghi kết quả qua repository `evidence` và `student_kc_states` đã có (T07).

**Xong khi:** golden test tất định trên chuỗi event dựng tay; cả 14 tình huống tối thiểu của alignment contract §9 có test; nhãn từ LLM có độ tin cậy thấp không thành evidence mạnh.

## T11 — Lệnh `make seed` cho dữ liệu demo (đợt 1, phụ)

**Đọc:** CLAUDE.md quy tắc 11–25. Đây là thay đổi về an toàn dữ liệu, phải ghi rõ trong PR.

**Làm:** `python -m cavat.seed` với hai lệnh `make seed` và `make seed-clear`. Tạo 1 trường, 1 lớp, 1 giáo viên, 5 học sinh, 1 phụ huynh, 1 bài đã xuất bản từ `lesson.yaml`. Mọi bản ghi có `is_demo: true`; `seed-clear` chỉ xóa bản ghi `is_demo: true`. Chạy lại không tạo trùng.

**Xong khi:** test bằng database in-memory: seed hai lần không trùng; clear không chạm bản ghi không có `is_demo`; không đường code nào khác gọi seed (startup, test, migration).

## T12 — Đăng nhập học sinh và giáo viên (đợt 1, phụ)

**Đọc:** PART 30.2, ADR-004; repository `users` (T07).

**Làm:** học sinh đăng nhập bằng mã lớp + tên + PIN 6 số; giáo viên bằng email + mật khẩu (argon2id); cookie HttpOnly; khóa tạm sau 5 lần sai; giáo viên đặt lại PIN. Endpoint `/v1/auth/*` theo PART 29.

**Xong khi:** test offline cho đăng nhập đúng, sai, bị khóa, cách ly giữa hai trường.

## T04 — Item loop, state machine tầng 3 (đợt 2, sau T02 và T03)

**Đọc:** PART 16.2, 10.4; `tutor/contracts.py`, `core/events.py`.

**Làm:** `tutor/item_loop.py`, `ItemTutor(item, package, activity, renderer, validator, cfg, snapshot)` với `start()` và `on_student(text, seconds)`.
- Các pha: AWAITING, AWAITING_CHOICE, AWAITING_CONFIRM, VERIFYING, TEACH_BACK, RESOLVED.
- Cập nhật `ItemState`; gọi `decide`; render; validate (lỗi thì retry một lần, rồi dùng câu mẫu dự phòng).
- Sinh event bằng payload trong `core/events.py`, kết thúc mỗi câu bằng một `ITEM_RESOLVED` đầy đủ trường.

- **Bổ sung vào `policy.py` (phần T02 còn thiếu):**
  - R-VERIFY: sau câu trả lời đúng, hỏi "vì sao" theo `verify_rate`, và luôn hỏi với câu có `requires_explanation`. Dùng `verify_prompt` của câu hoặc `default_verify_prompt` của bài.
  - R-TEACH-BACK: đúng sau khi đã giải mẫu (H6/H7) thì yêu cầu học sinh nói lại cách làm.
  - Ghi `rule_ids` cho mọi quyết định, kể cả PRESENT, CONFIRM_ADVANCE, ASK_CONFIRM, REDIRECT.
- **Câu hỏi tách nguyên nhân (`probe`, GP-08, GP-08b):** khi `CheckResult.detail["probe_option"]` có giá trị, hỏi `probe.prompt` (một câu so sánh, chấm bằng `parse_relation`). Học sinh so sánh sai thì ghi `probe.if_wrong` (DEC-M01). So sánh đúng thì ghi `probe.if_correct` (APPLY-TIME-SPEED, không tính vào KC-DEC-CMP). Không trả lời thì không gắn misconception nào.
- Khi `CheckResult.detail` có `ambiguous_misconceptions` (ví dụ M01 và M05 cùng dự đoán), không chọn COGNITIVE_CONFLICT cho một lỗi cụ thể và không ghi `MISCONCEPTION_DETECTED`.

**Xong khi:** test hội thoại cho bốn kịch bản (học sinh mang M01, xin gợi ý, im lặng, trả lời đúng ngay) và cho probe của GP-08 (cả hai nhánh); mọi câu đều kết thúc, không lộ đáp án; mọi payload validate được bằng `PAYLOAD_MODELS`.

## T06b — LLM renderer và prompt gọn (đợt 2, sau T03 và T06a)

**Đọc:** PART 14, ADR-017 (giới hạn 8.000 token/phút của Groq).

**Làm:**
- `tutor/prompts/constitution.v1.md`, `math_g5.v1.md`; `tutor/prompt_builder.py` dựng prompt **≤ 3.000 token**: hiến chương ngắn, câu hỏi hiện tại, gợi ý mẫu liên quan làm điểm tựa, 4–6 lượt gần nhất, directive. Với câu EXIT, `answer`, `rubric` và `sample_answer` không bao giờ vào prompt (có test kiểm tra).
- `tutor/llm_renderer.py` implement `MessageRenderer`: PRESENT, CONFIRM_ADVANCE, CLOSE_ITEM, OFFER_CHOICE, ASK_CONFIRM luôn dùng câu mẫu; move khác gọi gateway → validator → retry 1 lần kèm lỗi → câu mẫu. Hết trần lượt gọi thì dùng câu mẫu.
- Phân tích câu "vì sao" của học sinh thành `reasoning_quality` (đề xuất, có `label_confidence`).

**Xong khi:** test bằng model giả: lộ đáp án bị chặn rồi dùng câu mẫu; 429 dùng câu mẫu ngay; prompt dựng từ mọi item PRACTICE đều ≤ 3.000 token (ước lượng).

## T05 — Học sinh ảo và runner POC 1 (đợt 3, sau T04)

**Đọc:** PART 33 (POC 1), 45.2–45.3; `docs/poc/free-tier-quota.md`.

**Làm:**
- `evals/synthetic_students.py`: 6 profile (strong, average, weak, inconsistent, low_confidence, misconception_heavy), tất định theo seed, mỗi câu trả lời kèm "ý định thật".
- `evals/runners/poc1.py`: `--renderer template|llm`, `--max-llm-calls` (mặc định 15). Chạy các câu PRACTICE, làm lại bằng câu song sinh khi kết thúc WORKED. Metrics: leak rate, question ratio, diagnosis accuracy (dùng `rule_family`), phân bố move/level/resolution, số lượt mỗi câu, số lần gọi LLM và token. Xuất `evals/reports/*.json` và transcript Markdown.
- `make poc1` (câu mẫu, offline) và `make poc1-llm` (chạy local với khóa Groq).

**Xong khi:** chạy hai lần cho kết quả giống hệt; leak = 0; question ratio ≥ 0.85; diagnosis ≥ 0.8 với profile misconception_heavy.

## T08 — Session API cho một bài (đợt 3, sau T04 và T07)

**Đọc:** PART 24 (SessionContext), 29 (API); phần giả định ở cuối `apps/web/README.md` (web đang chờ API khớp các giả định đó).

**Làm:**
- **Endpoint FastAPI:** `POST /v1/sessions` (tạo buổi demo), `POST /v1/sessions/{id}/join`, `POST /v1/sessions/{id}/responses` (có `Idempotency-Key` và `expected_state_version`), `POST /v1/sessions/{id}/hint-requests`, `POST /v1/sessions/{id}/choices`, `GET /v1/sessions/{id}/state`, `GET /v1/sessions/{id}/stream` (SSE).
- Chạy item loop theo activity plan tối giản: CONCEPT_CHECK → GUIDED_PRACTICE → EXIT_ASSESSMENT → SUMMARY.
- Auth tạm bằng header `X-Demo-Student` nếu T12 chưa xong; ghi rõ là tạm.
- Test API mặc định dùng database in-memory. Test Atlas (nếu có) phải theo quy tắc 12–14. Không tự tạo dữ liệu demo khi startup.

**Xong khi:** gửi trùng `Idempotency-Key` không tạo event trùng; sai `state_version` → 409; toàn bộ test chạy offline; chủ repo chạy `make test` ở máy local trước khi gộp (quy tắc 22).

## T13 — Nối web với API thật (đợt 4, sau T08)

**Làm:** theo mục "Nối API thật" trong `apps/web/README.md`: sinh kiểu từ OpenAPI, viết `HttpSessionApi`, chọn mock hoặc HTTP bằng biến môi trường, chỉ import mock khi dùng mock.

**Xong khi:** `make web-check` xanh; một buổi học chạy hết từ web tới API ở máy local.

**Trạng thái (2026-10-01):** đã làm, trừ việc sinh kiểu từ OpenAPI. Chạy bằng `make api` (hoặc `make api-memory`) và `make web-live`; chi tiết ở `apps/web/README.md`, mục "API thật".

## T14 — Nhập tài liệu giáo viên (đợt 4)

**Đọc:** PART 22; ADR-017 (LlamaParse cho PDF/PPTX, Gemini vision cho trang scan và hình vẽ).

**Làm:** pipeline tải lên → LlamaParse → bản nháp `LessonPackage` (LLM Qwen dựng cấu trúc, ≤ 3.000 token mỗi lần, chia theo trang) → `MathChecker` kiểm tra đáp án → giáo viên duyệt. Ảnh hình học đi qua `describe_image` của Gemini.

**Xong khi:** test offline bằng output LlamaParse đã ghi sẵn; bản nháp qua `validate_package` hoặc báo đúng lỗi.

## T15 — Giọng nói cho Toán (đợt 4)

**Đọc:** PART 20.2; kết quả Whisper trong `docs/poc/free-tier-quota.md`.

**Làm:** bộ chuẩn hóa phát ngôn toán tiếng Việt (sửa "bớ" → "bé", "phần 10" → "phần mười", "phẩy"...), xác nhận lại câu trả lời bằng giọng nói trước khi chấm, Whisper qua gateway.

**Xong khi:** test offline trên bộ transcript mẫu; câu trả lời bằng giọng nói chỉ thành evidence sau khi học sinh xác nhận.

---

## Việc của chủ dự án (làm ở máy local, không giao cloud)

- [x] Chép credentials Atlas vào `services/api/.env`, `make setup`, `make db-ping`.
- [x] Khóa Groq, Gemini, LlamaCloud trong `services/api/.env` (đã kiểm tra hoạt động ngày 2026-10-01).
- [x] Review `lesson.yaml` (2026-10-01): đã sửa theo review và quyết định của chủ dự án; `test_lesson_content.py` giữ các quy tắc này trong CI.
- [x] 2026-10-01: duyệt DI "học sinh im lặng sau H6 thì cô giải thích trọn vẹn (H7) rồi mời con nói lại" (R-FULL, `hint-policy/0.3.0`).
- [x] 2026-10-01: duyệt 4 câu kiểm tra cuối mới (EX-05…EX-08).
- [x] 2026-10-01: duyệt các DI của T04: hỏi "vì sao" ở 30% số câu trả lời đúng (`verify_rate`), trần 12 lượt học sinh mỗi câu (`MAX_STUDENT_TURNS`), và "không nói lại được sau H7 thì ghi `UNRESOLVED`".
- [x] 2026-10-01: duyệt câu chữ: `PHRASES` trong `tutor/renderer.py`, câu tổng kết và nhãn lựa chọn trong `session/service.py`, hai file prompt `v1` trong `tutor/prompts/`.
- [ ] Duyệt các DI ở blueprint 09.
- [ ] Duyệt DI `ANCHOR_COVERAGE = 0.6` (`tutor/llm_renderer.py`): câu của AI phải giữ ít nhất 60% số từ của câu mẫu, nếu không thì dùng câu mẫu.
- [x] 2026-10-01 (sau buổi chạy thử của chủ dự án): duyệt ba thay đổi nhịp độ của cô: (1) chọn gợi ý theo mức trước (`template-renderer.v2`); (2) lượt xin gợi ý không tính là lượt "bí" của R-FRUSTRATION; (3) câu trả lời cho "con làm thế nào?" là lời giải thích, không tính là một lần trả lời sai mới (`hint-policy/0.4.0`).
- [ ] Duyệt hai DI đi kèm thay đổi (2): học sinh gõ "cho con đáp án" cũng không tính là lượt "bí"; đã đưa hết gợi ý tới mức 5 mà học sinh vẫn xin thì cô giải mẫu (H6).
- [ ] Quyết định: 12 trên 32 gợi ý mức 1 của bài 1 là "Con đọc to hai số…", viết cho lúc có giọng nói; có viết lại cho bản gõ chữ không.
- [ ] Duyệt 3 gợi ý được viết lại khi review T03 (GP-09, GP-09b và gợi ý chung TASK mức 1), rồi xác nhận cả bài để chuyển `lesson.yaml` từ DRAFT sang APPROVED.
- [ ] Chụp phần còn lại của bảng hạn mức Gemini (`gemini-3.8-live` và các dòng bị cắt).
- [ ] Hỏi luật sư về điều khoản tuổi của Google và Groq (xem cuối `docs/poc/free-tier-quota.md`).
- [ ] Sau T05: chạy `make poc1-llm` và đọc transcript trong `evals/reports/`.
