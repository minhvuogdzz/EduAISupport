# Nội dung dạy Tiếng Anh lớp 5 (ENG-3)

Ngày: 12/11/2026, cập nhật 13/11/2026 (ENG-3b) · Trạng thái: **DRAFT, chủ dự án duyệt mặc định ngày 12/11/2026; 20 câu soạn thêm được chủ dự án duyệt ngày 13/11/2026** (sửa bất kỳ lúc nào; ghi vào mục Lịch sử).

Thư mục này chứa dữ liệu dạy học của môn Tiếng Anh, theo đúng khuôn của môn Toán (`docs/pedagogy/math-g5/`):
một file chương (`ChapterPackage`) cho đồ thị tri thức của unit và các file bài (`LessonPackage`) chứa mục tiêu,
lỗi hay gặp và ngân hàng câu. Từ ENG-3b (ADR-062) tên file và cấu trúc thư mục giống Toán; bộ nạp chọn gói theo `subject`.
Dữ liệu này là nguồn cho RAG môn Tiếng Anh (ADR-061, PR #140) và cho vòng dạy 6 bước (ADR-059).
Khung đánh giá áp dụng là ADR-060 (PR #138).

Gia sư là **gia sư ôn bài ở nhà** sau khi con đã học trên lớp. Cô giảng bằng tiếng Việt; từ và mẫu câu đích nói
bằng tiếng Anh và **luôn nằm trong một câu trọn vẹn** ("Con nói theo cô: We swam in the sea."), vì POC giọng nói
(PR #139) cho thấy VieNeu đọc một từ tiếng Anh đứng riêng kém.

## 1. Unit hiện có

| Unit | Thư mục | Nguồn |
|---|---|---|
| Unit 11 "Family time" (chủ đề "Me and my family") | `unit-11-family-time/` | SGK Tiếng Anh 5 Global Success tập hai, tr.6–11 và Review 3 tr.36–37; SGV tr.177–190, 250–254 |

```
english-g5/
├── README.md                                   (file này)
└── unit-11-family-time/
    ├── chapter.yaml                                  ChapterPackage: đồ thị 6 nút, lý thuyết, phương pháp, bài mẫu, "con nói lại"
    ├── lesson-1-did-you/lesson.yaml                  LessonPackage: VOCAB, PAST, DIDYOU (SGK tr.6–7)
    ├── lesson-2-what-did-your-family-do/lesson.yaml  LessonPackage: WHATDID (SGK tr.8–9)
    ├── lesson-3-family-trip/lesson.yaml              LessonPackage: STRESS, TRIP (SGK tr.10–11)
    └── sources.yaml                                  mọi bài tập của sách (kể cả bài không thành câu) và bảng tổng hợp 47 câu
```

## 2. Nguồn và cách trích

**Nguồn** (ấn phẩm công khai chính thức của NXB Giáo dục Việt Nam trên https://taphuan.nxbgd.vn, loại nguồn dự án cho phép):

| Tài liệu | Trang đã đọc |
|---|---|
| SGK Tiếng Anh 5 Global Success, tập hai | 4–5 (Book map), 6–11 (Unit 11), 36–37 (Review 3) |
| SGV Tiếng Anh 5 Global Success | 177–190 (Unit 11: mục tiêu, các bước dạy, audio script, Key), 250–254 (Review 3) |
| Tài liệu tập huấn, bồi dưỡng GV Tiếng Anh 5 | 2 (mục lục), 7 (kiểm tra đánh giá, yêu cầu cuối lớp 5), 27–28 (quy trình hoạt động) |

**Cách trích:**
1. Sách chỉ có ảnh trang, không có lớp chữ. Phiên ENG-3 đọc từng trang bằng trình duyệt trong app, phóng to từng vùng. Không tải file, không vượt chặn.
2. Bản trích gần nguyên văn (để đối chiếu) nằm ngoài repo, ở `var/storage/english-sources/unit-11/` của checkout chính (trên máy chủ dự án: `/Users/mac/Documents/Code Space/EduAISupport/var/storage/english-sources/unit-11/`), gồm `sgk-unit11.md`, `sgv-unit11.md`, `taphuan-notes.md`. Thư mục `var/` bị git bỏ qua: bản trích **chỉ có trên máy chủ dự án**, không có trong repo, CI hay phiên cloud. Mỗi file ghi URL nguồn và cách quy đổi số ảnh trang sang số trang in (SGK: ảnh = trang + 2; SGV: ảnh = trang + 1).
3. Đáp án lấy từ **Key, audio script và Suggested answers của SGV**, ghi số trang (trường `answer_source` của câu). Đáp án suy ra mà SGV không có thì không dùng; bài mở hoặc trò chơi ghi `NO_ANSWER` trong `sources.yaml` và không bao giờ thành câu (validator từ chối, DI-126).
4. **Bản quyền, repo công khai:** repo không chứa ảnh trang, PDF hay nguyên văn cả trang/cả bài. Chỉ có danh sách từ, mẫu câu ngắn, câu hỏi luyện tập kèm đáp án và trang nguồn; lời giảng và cách dạy viết lại bằng lời của phiên. Bài đọc tr.11 được thay bằng đoạn tóm tắt viết lại (lesson-3, concept C3).

## 3. Quy ước file

- **Tên file và môn (ENG-3b, ADR-062):** file chương là `chapter.yaml`, mỗi bài một thư mục con có `lesson.yaml`, giống Toán. Bộ nạp (`chapter_service.chapter_sources(subject)`, `chapters(subject)`, `service.lesson_packages(subject)`) đọc `subject` của từng file và chỉ trả gói của môn được hỏi; đường gọi không nêu môn là Toán (DI-124), nên unit này không vào buổi học, trang hay danh sách nào của Toán. Một chương không trộn môn (mọi lesson cùng `subject` với chương).
- **Schema:** `ChapterPackage` (`services/api/cavat/modules/content/chapter_package.py`) và `LessonPackage` (`lesson_package.py`) với các trường ENG-3b ở mục 6. Mọi trường mới là tùy chọn đối với Toán; với gói `subject: english`, `validate_package` bắt buộc chúng.
- **Mã:** unit `eng-g5-u11-family-time`; lesson `eng-g5-u11-l1..l3`; nút `ENG5-U11-<TÊN>`; câu `U11-<nút>-<loại>-<số>` với loại `CC` (kiểm tra hiểu), `CP` (cùng làm / nói theo cô), `PR` (luyện tập), `TR` (vận dụng); lỗi `ENG5-U11-M01..M12`.
- **Nguồn từng câu** (DI-126): `source: {doc, page, ref}` (trang in của câu), `answer_source` (trang SGV có đáp án; bắt buộc khi `answer_status: VERIFIED_SGV`), `origin: BOOK | AUTHORED`, `answer_status: VERIFIED_SGV | FROM_TEXT | AUTHORED`, `review` (câu `AUTHORED` chỉ được dạy khi `status: APPROVED`, có người và ngày duyệt). Dòng chú thích `[SGK tr.N …]` / `[SOẠN THÊM]` trên câu vẫn giữ để đọc nhanh; `sources.yaml` là bảng tổng hợp, có test kiểm khớp.
- **Mức nhận thức** theo ADR-060 mục 3.2: A nhận biết, B theo mẫu, C hiểu vì sao (trả lời bằng tiếng Việt), D vận dụng trong tình huống của bài, E bối cảnh mới, DIAG tìm lỗi.
- **Ngôn ngữ trả lời** (`response_language`): `en` câu đích tiếng Anh; `vi` câu mức C giải thích bằng tiếng Việt; `either` câu chọn nghĩa mức A (chấp nhận tiếng Việt, ADR-060 mục 5) và câu tìm lỗi (con có thể nói "eated sai, phải là ate").
- **Câu trả lời tiếng Anh:** `answer.type: phrase` (DI-125): `accept` là câu mẫu đã duyệt, `required` là các ý phải có (mỗi nhóm là các cách nói được chấp nhận cho một ý), `normalize: en-vi/1` (DI-110), `wrong_answers` chỉ gồm câu sai mà chính mô tả hiểu lầm đã nêu (ví dụ `"we eat seafood" → ENG5-U11-M07`), `allow_name` cho bài kể tự do. Biến thể ngoài đáp án của SGV chỉ là cách viết tương đương đã có từ ENG-3; biến thể khác chờ chủ dự án duyệt (luật N4). Câu mức C trả lời bằng tiếng Việt giữ `open` + `facts.phrases`. Bộ chấm `phrase` là việc của ENG-4.
- **Tranh trong sách** được tả bằng lời ngay trong `stem` ("Trong tranh, cả nhà đang ăn tôm, cua, cá ở Nha Trang…").
- **Gợi ý** theo thang DI-112: H1 câu hỏi định hướng, H2 nhắc khái niệm, H4 cho một phần (bắt buộc cho câu PRACTICE như Toán), H3 chiến lược khi cần.
- **Câu "nói theo cô"** có `kind: say_after_me`, trả lời bằng `en`, và chỉ được nằm trong `completion` của nút: được ghi bằng chứng nhưng không tính thành công (DI-108; `validate_chapter` kiểm).
- **Nút BASIC VOCAB, PAST, STRESS** có `require_application: false` như nút cơ bản của Toán (DI-6); bằng chứng vận dụng nằm ở DIDYOU, WHATDID, TRIP. Mọi nút vẫn `require_explanation: true` (DI-111): mỗi nút có ít nhất một câu mức C và một câu "con nói lại".

## 4. Unit 11: đồ thị và nội dung

```
VOCAB ──PRE──▶ PAST ──PRE──▶ DIDYOU ──APP──┐
                  └──PRE──▶ WHATDID ──APP──┴─▶ TRIP (IMPLEMENT)
                                └──PRE──▶ STRESS
(DIDYOU ~SIMILAR~ WHATDID)
```

| Nút | Tầng | Nội dung | Lesson |
|---|---|---|---|
| `ENG5-U11-VOCAB` | BASIC | 8 cụm: swim, take photos, collect seashells, walk on the beach, take a boat trip around the bay, eat seafood, see some interesting places, buy souvenirs | l1 |
| `ENG5-U11-PAST` | BASIC | Dạng quá khứ: -ed (walked, collected, visited) và dạng riêng (swam, took, ate, saw, bought, went, were) | l1 |
| `ENG5-U11-DIDYOU` | BASIC | Did you …? – Yes, I did. I … / No, I didn't. | l1 |
| `ENG5-U11-WHATDID` | BASIC | What did your family do in …? – We …; When did you go to …? – We went there last … | l2 |
| `ENG5-U11-STRESS` | BASIC | Rhythm: 'When did you 'go to 'London? / 'What did they 'do in 'Finland? | l3 |
| `ENG5-U11-TRIP` | IMPLEMENT | Kể và hỏi đáp về chuyến đi của gia đình; đọc hiểu đoạn kể ngắn | l3 |

**Ngân hàng câu: 47 câu**, 27 từ sách (SGK/SGV) và 20 câu soạn thêm.

| Mức | A | B | C | D | E | DIAG | Tổng |
|---|---|---|---|---|---|---|---|
| Số câu | 8 | 23 | 7 | 3 | 1 | 5 | 47 |

| Nút | Kiểm tra hiểu | Cùng làm | Luyện tập | Vận dụng | Mức có |
|---|---|---|---|---|---|
| VOCAB | 1 | 1 | 4 | 0 | A, B, C, DIAG |
| PAST | 1 | 1 | 6 | 0 | A, B, C, DIAG |
| DIDYOU | 1 | 1 | 5 | 1 | A, B, C, D, DIAG |
| WHATDID | 1 | 1 | 7 | 1 | A, B, C, D, DIAG |
| STRESS | 1 | 0 | 5 | 0 | A, B, C |
| TRIP | 1 | 1 | 5 | 2 | B, C, D, DIAG, E |

**Trạng thái đáp án** (trường `answer_status` của câu; tổng hợp ở `sources.yaml`): 24 câu `VERIFIED_SGV`, 3 câu `FROM_TEXT`, 20 câu `AUTHORED` (đã duyệt 13/11/2026).
**Kiểu đáp án** (ENG-3b): 23 `phrase`, 17 `choice`, 5 `open` (mức C tiếng Việt), 2 `boolean`.
Bài của sách không thành câu chấm điểm: 5 bài `NO_ANSWER` (L2 Ex6 trò chơi, L3 Ex3 chant, L3 Ex5 viết mở, L3 Ex6 Project, Review 3 Ex5 viết mở) và 3 bài `NEEDS_AUDIO` (L1 Ex4, L1 Ex6, L2 Ex4: SGV có đáp án nhưng cần file nghe; L1 Ex4 câu 4 và L1 Ex6 chỗ (3) được chuyển thành câu đọc).

**Lỗi hay gặp** (misconceptions; trường `error_class` theo mã lỗi DI-107 của ADR-060 mục 5, DI-127):

| Mã | Lỗi | Nút | Mức | `error_class` (DI-107) |
|---|---|---|---|---|
| M01 | Hỏi chuyện đã qua mà dùng do / bỏ did | DIDYOU | CRITICAL | `EN_STRUCTURE` |
| M02 | Did + động từ quá khứ ("Did you swam?") | DIDYOU | CRITICAL | `EN_STRUCTURE` |
| M03 | Nhầm Yes, I did với Yes, I do / Yes, I will | DIDYOU | CRITICAL | `EN_SHORT_ANSWER` |
| M04 | Kể chuyện đã qua bằng động từ nguyên mẫu | PAST | CRITICAL | `EN_TENSE` |
| M05 | Thêm -ed cho động từ có dạng riêng (taked, eated) | PAST | NORMAL | `EN_VERB_FORM` |
| M06 | Nhầm nghĩa giữa các cụm hoạt động | VOCAB | NORMAL | `EN_MEANING` |
| M07 | Sau We dùng động từ nguyên mẫu | WHATDID | CRITICAL | `EN_TENSE` |
| M08 | Câu hỏi Wh- về quá khứ thiếu did / dùng do | WHATDID | NORMAL | `EN_STRUCTURE` |
| M09 | Trả lời lệch câu hỏi Wh- | WHATDID | NORMAL | `EN_MEANING` |
| M10 | Nhấn vào từ chức năng (did, you, to) | STRESS | NORMAL | `EN_STRUCTURE` (chọn sai mẫu nhịp, là mẫu đích của nút; không chấm phát âm) |
| M11 | Kể chuyến đi lẫn động từ nguyên mẫu | TRIP | CRITICAL | `EN_TENSE` |
| M12 | Trả lời lệch câu hỏi khi kể chuyến đi | TRIP | NORMAL | `EN_MEANING` |

## 5. Kiểm tra

- `load_chapter` đọc được unit; ba bài và cả chương qua `validate_package` / `validate_chapter` không lỗi; thứ tự học VOCAB → PAST → DIDYOU → WHATDID → STRESS → TRIP; mọi câu đều được một nút dùng.
- Test tự động: `services/api/tests/test_subject_content.py` (bộ nạp theo môn, schema, Unit 11, `sources.yaml` khớp với các file lesson, trang duyệt của giáo viên).
- Trang duyệt phương án dạy của giáo viên: `GET /v1/teachers/chapters?subject=english` liệt kê unit; `GET /v1/teachers/chapters/eng-g5-u11-family-time` cho toàn bộ nội dung kèm nguồn, trạng thái đáp án và trạng thái duyệt của từng câu.

```bash
cd services/api && .venv/bin/python - <<'EOF'
from cavat.modules.session import chapter_service
from cavat.modules.content.chapter_package import validate_chapter
from cavat.modules.content.lesson_package import validate_package
unit = chapter_service.chapters("english")["eng-g5-u11-family-time"]
for lp in unit.lessons.values():
    print(lp.lesson_id, len(lp.items), validate_package(lp))
print(validate_chapter(unit), unit.topological_order())
EOF
```

## 6. Khoảng trống schema

ENG-3 không sửa code nên ghi lại các khoảng trống dưới đây. **ENG-3b (ADR-062, 13/11/2026)** đóng G0, G1, G2, G3, G4, G5, G8, G10; G6, G7, G9 để sau.

| # | Chỗ thiếu | Trạng thái |
|---|---|---|
| G0 | Bộ nạp tìm file theo **tên** (`**/chapter.yaml`, `**/lesson.yaml`) trong toàn bộ `docs/pedagogy`, không theo môn. | **Đóng (ENG-3b).** Bộ nạp đọc `subject` và chỉ trả gói của môn được hỏi; mọi đường gọi không nêu môn là Toán (DI-124); hai file trùng mã chương/bài là lỗi. File đã đổi tên về `chapter.yaml` / `lesson.yaml`. |
| G1 | `ChapterPackage.subject` chỉ nhận `"math"`. | **Đóng (ENG-2, PR #140):** `Literal["math","english"]`, bắt buộc. ENG-3b thêm: chương không trộn môn. Mọi gói Toán (file và kế hoạch đã xuất bản) đều có `subject` từ đầu dự án, nên gói không cần luật "thiếu là Toán" (khác tài liệu giáo viên, DI-120). |
| G2 | Chưa có kiểu đáp án cho câu tiếng Anh với biến thể chấp nhận và chuẩn hóa DI-110. | **Đóng phần schema (DI-125).** Kiểu `phrase`: `accept`, `required`, `normalize: en-vi/1`, `wrong_answers`, `allow_name`. 23 câu đã chuyển. **Bộ chấm `phrase` là ENG-4**: cho tới khi ENG-4 gộp, `MathChecker` không chấm kiểu này (buổi học Tiếng Anh chưa mở nên không đường nào gọi tới). |
| G3 | Chưa có kiểu xếp từ thành câu. | **Đóng phần schema (DI-125).** Kiểu `word_order`: `tokens`, `accept` (mỗi thứ tự là hoán vị của `tokens`). Unit 11 chưa có câu xếp từ (sách không có bài loại này). Bộ chấm là ENG-4. |
| G4 | `Item` không có nguồn và trạng thái đáp án. | **Đóng (DI-126).** `source`, `answer_source`, `origin`, `answer_status`, `review`; câu `AUTHORED` chưa duyệt không qua validator; `NO_ANSWER` không bao giờ là câu. |
| G5 | Không chỉ định được ngôn ngữ trả lời. | **Đóng cho câu (DI-126):** `response_language: en`, `vi` hoặc `either`. Chưa có trên `TheoryVariant.ask` (ENG-5/ENG-6 thêm khi cần). |
| G6 | Không có chỗ cho tranh/âm thanh của câu. | Để sau. Tranh vẫn tả bằng lời trong `stem`. Đề xuất giữ: `media: [{kind, description, ref}]`, `ref` trỏ `var/storage`. |
| G7 | Không có đoạn ngữ liệu dùng chung cho nhiều câu (bài đọc). | Để sau. Đoạn tóm tắt vẫn lặp trong `stem` và ở concept C3 của lesson-3. Đề xuất giữ: `stimuli` ở lesson, `Item.stimulus_id`. |
| G8 | `Misconception` không có lớp lỗi DI-107. | **Đóng (DI-127).** `error_class` theo mã DI-107 (bắt buộc ở gói Tiếng Anh); bảng ở mục 4. Ánh xạ mã → `ErrorClass` của projector là ENG-4. |
| G9 | Lời giảng trộn Việt–Anh không đánh dấu đoạn tiếng Anh cho TTS. | Để sau (ENG-5/ENG-6). Quy ước tạm giữ nguyên: câu tiếng Anh trong dấu nháy đơn, lời dẫn tiếng Việt kết thúc bằng dấu hai chấm. |
| G10 | Câu "nói theo cô" chỉ nhận ra qua việc nằm trong `completion`. | **Đóng.** `kind: say_after_me` (3 câu: U11-VO-CP-01, U11-DY-CP-01, U11-WD-CP-01); validator buộc nằm ở `completion` và trả lời `en`. |

Không phải khoảng trống: `HintLevel` H0–H7 dùng chung được với thang DI-112 (chỉ đổi lời gợi ý); quan hệ tiên quyết giữa các lesson được đồ thị chương giữ, giống Toán.

## 7. Cần chủ dự án kiểm lại

1. **Đáp án đọc qua ảnh.** Mọi đáp án `VERIFIED_SGV` đọc từ ảnh trang SGV. Nên liếc lại nhất là: SGV tr.182 (Key L1 Ex4, Ex5, Ex6), tr.186–187 (Key L2 Ex4, Ex5), tr.189–190 (Key L3 Ex2, Ex4), tr.252–253 (Key Review 3).
2. **"Sa Pa" hay "Fansipan"** (SGK tr.9 Ex5 câu 2): tranh ghi "FANSIPAN MOUNTAIN", SGV ghi "Sa Pa". Ngân hàng chưa dùng chỗ trống này; nếu dùng, cần quyết định có nhận "Fansipan" không.
3. **20 câu soạn thêm** (`AUTHORED`): **chủ dự án đã duyệt ngày 13/11/2026** (trường `review` của từng câu). Khi chạy thật vẫn nên theo dõi các câu mức C (lời giải thích tiếng Việt chấm bằng `facts.phrases`) và câu E `U11-TR-TR-02` (bài mở, chỉ kiểm "went to" và "last").
4. **Đoạn tóm tắt bài đọc** tr.11 (lesson-3, C3): đã viết lại bằng lời khác; xem có đủ khác bản gốc không.
5. **Tên nút và ranh giới nút** (6 nút; "When did you go …?" gộp vào WHATDID).

## 8. Lịch sử

| Ngày | Việc | Người |
|---|---|---|
| 12/11/2026 | ENG-3: tạo Unit 11 "Family time" (6 nút, 3 lesson, 47 câu) từ SGK/SGV/tài liệu tập huấn NXB Giáo dục. Chủ dự án duyệt mặc định. | phiên Claude Code ENG-3 |
| 13/11/2026 | Chủ dự án duyệt toàn bộ 20 câu soạn thêm (`AUTHORED`). | chủ dự án |
| 13/11/2026 | ENG-3b (ADR-062): đổi tên về `chapter.yaml` + `lesson-N-*/lesson.yaml`; bộ nạp theo môn; 23 câu `open` tiếng Anh chuyển sang `phrase` (accept = câu mẫu đã duyệt, required = các nhóm `facts.phrases` cũ, không thêm biến thể); ghi `source`, `answer_source`, `origin`, `answer_status`, `review` (20 câu duyệt 13/11/2026), `response_language`, `kind: say_after_me` vào từng câu; `error_class` cho M01–M12 theo bảng DI-107 (tinh hơn cột "gần nhất" cũ: M03 `EN_SHORT_ANSWER`, M04/M07/M11 `EN_TENSE`, M05 `EN_VERB_FORM`, M10 `EN_STRUCTURE`). Version chương và bài 0.1.0 → 0.2.0. | phiên Claude Code ENG-3b |
