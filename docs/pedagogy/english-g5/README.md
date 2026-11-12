# Nội dung dạy Tiếng Anh lớp 5 (ENG-3)

Ngày: 12/11/2026 · Trạng thái: **DRAFT, chủ dự án duyệt mặc định ngày 12/11/2026** (sửa bất kỳ lúc nào; ghi vào mục Lịch sử).

Thư mục này chứa dữ liệu dạy học của môn Tiếng Anh, theo đúng khuôn của môn Toán (`docs/pedagogy/math-g5/`):
một file chương (`ChapterPackage`) cho đồ thị tri thức của unit và các file bài (`LessonPackage`) chứa mục tiêu,
lỗi hay gặp và ngân hàng câu. Tên file khác Toán có chủ ý (mục 3, "Tên file").
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
    ├── unit.yaml                               ChapterPackage: đồ thị 6 nút, lý thuyết, phương pháp, bài mẫu, "con nói lại"
    ├── lesson-1-did-you.yaml                   LessonPackage: VOCAB, PAST, DIDYOU (SGK tr.6–7)
    ├── lesson-2-what-did-your-family-do.yaml   LessonPackage: WHATDID (SGK tr.8–9)
    ├── lesson-3-family-trip.yaml               LessonPackage: STRESS, TRIP (SGK tr.10–11)
    └── sources.yaml                            mọi bài tập của sách, trang, trạng thái đáp án; nguồn gốc 47 câu
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
2. Bản trích gần nguyên văn (để đối chiếu) nằm ngoài repo, ở `var/storage/english-sources/unit-11/` (git bỏ qua): `sgk-unit11.md`, `sgv-unit11.md`, `taphuan-notes.md`.
3. Đáp án lấy từ **Key, audio script và Suggested answers của SGV**, ghi số trang. Đáp án suy ra mà SGV không có thì không dùng; bài mở hoặc trò chơi ghi `NO_ANSWER` trong `sources.yaml`.
4. **Bản quyền, repo công khai:** repo không chứa ảnh trang, PDF hay nguyên văn cả trang/cả bài. Chỉ có danh sách từ, mẫu câu ngắn, câu hỏi luyện tập kèm đáp án và trang nguồn; lời giảng và cách dạy viết lại bằng lời của phiên. Bài đọc tr.11 được thay bằng đoạn tóm tắt viết lại (lesson-3, concept C3).

## 3. Quy ước file

- **Tên file:** file chương là `unit.yaml`, file bài là `lesson-N-<tên>.yaml`, **không** dùng tên `chapter.yaml` / `lesson.yaml` như Toán. Lý do: lúc chạy, `chapter_service.chapter_sources()` (`services/api/cavat/modules/session/chapter_service.py:130`) và `lesson_packages()` (`services/api/cavat/modules/session/service.py:98`) tự nạp mọi file mang hai tên đó dưới `docs/pedagogy`, không lọc theo môn. Đặt tên như Toán sẽ (a) làm hỏng việc nạp chương vì schema chương chưa nhận `english` (đã thấy: `make test` lỗi ở `test_bandit.py`), và (b) khi schema đã mở, đưa unit Tiếng Anh vào danh sách chương/bài của gia sư Toán trước khi có cô lập môn (luật S1, F1). Xem G0 ở mục 6.
- **Schema:** `ChapterPackage` (`services/api/cavat/modules/content/chapter_package.py`) và `LessonPackage` (`lesson_package.py`), không thêm trường nào (luật: không sửa code ở task này). Chỗ schema chưa đủ ghi ở mục 6.
- **Mã:** unit `eng-g5-u11-family-time`; lesson `eng-g5-u11-l1..l3`; nút `ENG5-U11-<TÊN>`; câu `U11-<nút>-<loại>-<số>` với loại `CC` (kiểm tra hiểu), `CP` (cùng làm / nói theo cô), `PR` (luyện tập), `TR` (vận dụng); lỗi `ENG5-U11-M01..M12`.
- **Nguồn từng câu:** dòng chú thích ngay trên câu: `[SGK tr.N …]`, `[SGV tr.N …]` là câu của sách; `[SOẠN THÊM]` là câu phiên soạn. Bảng đầy đủ ở `sources.yaml`.
- **Mức nhận thức** theo ADR-060 mục 3.2: A nhận biết, B theo mẫu, C hiểu vì sao (trả lời bằng tiếng Việt), D vận dụng trong tình huống của bài, E bối cảnh mới, DIAG tìm lỗi.
- **Câu trả lời dạng câu:** `answer.type: open` + `facts.phrases`. Mỗi nhóm là các cách nói được chấp nhận cho một ý, so khớp sau chữ thường. Ví dụ "We ate some seafood." được chấp nhận nhờ tách thành hai nhóm `[["we ate"], ["seafood"]]`. Biến thể ngoài đáp án của SGV chỉ là cách viết tương đương (có/không "some", dạng rút gọn); biến thể khác chờ chủ dự án duyệt (luật N4).
- **Tranh trong sách** được tả bằng lời ngay trong `stem` ("Trong tranh, cả nhà đang ăn tôm, cua, cá ở Nha Trang…").
- **Gợi ý** theo thang DI-112: H1 câu hỏi định hướng, H2 nhắc khái niệm, H4 cho một phần (bắt buộc cho câu PRACTICE như Toán), H3 chiến lược khi cần.
- **Câu "nói theo cô"** nằm trong `completion` của nút: được ghi bằng chứng nhưng không tính thành công (DI-108).
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

**Trạng thái đáp án** (`sources.yaml`): 24 câu `VERIFIED_SGV`, 3 câu `FROM_TEXT`, 20 câu `AUTHORED`.
Bài của sách không thành câu chấm điểm: 5 bài `NO_ANSWER` (L2 Ex6 trò chơi, L3 Ex3 chant, L3 Ex5 viết mở, L3 Ex6 Project, Review 3 Ex5 viết mở) và 3 bài `NEEDS_AUDIO` (L1 Ex4, L1 Ex6, L2 Ex4: SGV có đáp án nhưng cần file nghe; L1 Ex4 câu 4 và L1 Ex6 chỗ (3) được chuyển thành câu đọc).

**Lỗi hay gặp** (misconceptions, ánh xạ sang mã lỗi DI-107 của ADR-060):

| Mã | Lỗi | Nút | Mức | Mã DI-107 gần nhất |
|---|---|---|---|---|
| M01 | Hỏi chuyện đã qua mà dùng do / bỏ did | DIDYOU | CRITICAL | `EN_STRUCTURE` |
| M02 | Did + động từ quá khứ ("Did you swam?") | DIDYOU | CRITICAL | `EN_STRUCTURE` |
| M03 | Nhầm Yes, I did với Yes, I do / Yes, I will | DIDYOU | CRITICAL | `EN_STRUCTURE` |
| M04 | Kể chuyện đã qua bằng động từ nguyên mẫu | PAST | CRITICAL | `EN_STRUCTURE` |
| M05 | Thêm -ed cho động từ có dạng riêng (taked, eated) | PAST | NORMAL | `EN_STRUCTURE` |
| M06 | Nhầm nghĩa giữa các cụm hoạt động | VOCAB | NORMAL | `EN_MEANING` |
| M07 | Sau We dùng động từ nguyên mẫu | WHATDID | CRITICAL | `EN_STRUCTURE` |
| M08 | Câu hỏi Wh- về quá khứ thiếu did / dùng do | WHATDID | NORMAL | `EN_STRUCTURE` |
| M09 | Trả lời lệch câu hỏi Wh- | WHATDID | NORMAL | `EN_MEANING` |
| M10 | Nhấn vào từ chức năng (did, you, to) | STRESS | NORMAL | (phát âm, không chấm: chỉ dùng cho câu chọn) |
| M11 | Kể chuyến đi lẫn động từ nguyên mẫu | TRIP | CRITICAL | `EN_STRUCTURE` |
| M12 | Trả lời lệch câu hỏi khi kể chuyến đi | TRIP | NORMAL | `EN_MEANING` |

## 5. Kiểm tra

- Ba file bài đọc được bằng `load_lesson_package` hiện có và qua `validate_package` không lỗi.
- `unit.yaml` **chưa** đọc được bằng `load_chapter` vì `ChapterPackage.subject` chỉ nhận `"math"` (khoảng trống G1). Để kiểm đồ thị mà không sửa code, đọc YAML, thay tạm `subject` thành `"math"` trong bộ nhớ, rồi chạy `validate_chapter`. Kết quả ngày 12/11/2026: không lỗi; thứ tự học VOCAB → PAST → DIDYOU → WHATDID → STRESS → TRIP; mọi câu đều được một nút dùng.

```bash
cd services/api && .venv/bin/python - <<'EOF'
from pathlib import Path
import yaml
from cavat.modules.content.chapter_package import Chapter, ChapterPackage, validate_chapter
from cavat.modules.content.lesson_package import load_lesson_package, validate_package
unit = Path("../../docs/pedagogy/english-g5/unit-11-family-time")
raw = yaml.safe_load((unit / "unit.yaml").read_text(encoding="utf-8"))
raw["subject"] = "math"  # tạm, chỉ để chạy validate_chapter (G1)
pkg = ChapterPackage.model_validate(raw)
lessons = {lp.lesson_id: lp for lp in (load_lesson_package(unit / rel) for rel in pkg.lessons)}
for lp in lessons.values():
    print(lp.lesson_id, len(lp.items), validate_package(lp))
items = {it.id: (it, lp) for lp in lessons.values() for it in lp.items}
print(validate_chapter(Chapter(package=pkg, lessons=lessons, _items=items)))
EOF
```

## 6. Khoảng trống schema

Task ENG-3 không sửa code. Các trường dưới đây cần thêm ở task cài đặt (theo `docs/plan/english-module-rules.md`, PR #138). Thứ tự là mức cần thiết.

| # | Chỗ thiếu | Hiện làm tạm | Đề xuất |
|---|---|---|---|
| G0 | Bộ nạp nội dung lúc chạy tìm file theo **tên** (`**/chapter.yaml`, `**/lesson.yaml`) trong toàn bộ `docs/pedagogy`, không theo môn. | Đặt tên `unit.yaml`, `lesson-N-….yaml` để bộ nạp bỏ qua. | Bộ nạp đọc `subject` và chỉ trả gói của môn mà buổi học đang chạy (luật S1); khi đó đổi tên file về `chapter.yaml` / `lesson.yaml` cho giống Toán. |
| G1 | `ChapterPackage.subject` là `Literal["math"]` nên `load_chapter` từ chối unit Tiếng Anh. (`LessonPackage.subject` đã nhận `"english"`.) | Ghi `subject: english`; kiểm bằng cách thay tạm trong bộ nhớ (mục 5). | `Literal["math", "english"]`, bắt buộc, không mặc định (luật N1). |
| G2 | Chưa có kiểu đáp án cho **từ/câu tiếng Anh với danh sách biến thể chấp nhận** và chuẩn hóa DI-110 (chữ thường, bỏ dấu câu, mở rộng I'm/didn't…, `allow_name`). `open` + `facts.phrases` là so khớp chuỗi con: không phân biệt ranh giới từ, không ánh xạ câu sai sang lỗi, và mọi câu đều tính là cùng "dạng" `open` ở gate UNDERSTOOD. | `open` + `facts.phrases` tách theo ý. | Kiểu `phrase`: `accept: [câu…]`, `required: [[cụm…]]`, `normalize: en-vi/1`, `wrong_answers: {mẫu: mã lỗi}` (ví dụ `"we eat seafood" → ENG5-U11-M07`). DI-106 đã liệt kê `phrase` là một "dạng câu hỏi". |
| G3 | Chưa có kiểu **xếp từ thành câu**: `OrderAnswer` chỉ nhận số. | Không có câu xếp từ. | Kiểu `word_order`: `tokens`, `accept` (các thứ tự đúng). DI-106 gọi là `order`. |
| G4 | `Item` không có **nguồn và trạng thái đáp án** (`extra="forbid"`). | Chú thích YAML trên từng câu + `sources.yaml`. | `source: {doc, page, ref}`, `origin: BOOK \| AUTHORED`, `answer_status: VERIFIED_SGV \| FROM_TEXT \| AUTHORED \| NO_ANSWER` (rút từ ADR-024). Câu `AUTHORED` chưa duyệt không được dạy. |
| G5 | Không chỉ định được **ngôn ngữ trả lời** của câu, mà POC giọng nói yêu cầu policy chọn ngôn ngữ Whisper theo bước (không tự nhận dạng). | Suy từ mức: câu C trả lời bằng tiếng Việt, câu khác bằng tiếng Anh; câu chọn nghĩa (mức A) chấp nhận tiếng Việt. | `response_language: en \| vi \| either` trên `Item` (và trên `TheoryVariant.ask`). |
| G6 | Không có chỗ cho **tranh/âm thanh** của câu. | Tả tranh bằng lời trong `stem`. | `media: [{kind: picture \| audio, description, ref}]`; `ref` trỏ `var/storage`, không commit. |
| G7 | Không có **đoạn ngữ liệu dùng chung** cho nhiều câu (bài đọc). | Lặp đoạn tóm tắt trong `stem` và để ở `concepts` C3 của lesson-3. | `stimuli: [{id, text, source}]` ở lesson, `Item.stimulus_id`. |
| G8 | `Misconception` không có **lớp lỗi** DI-107 (`EN_STRUCTURE`, `EN_MEANING`…). | Bảng ánh xạ ở mục 4. | `error_class` trên `Misconception` (projector đọc lớp lỗi để tính điểm s). |
| G9 | Lời giảng trộn Việt–Anh không đánh dấu **đoạn tiếng Anh**, nên TTS không biết đoạn nào cần đọc bằng giọng/bộ âm tiếng Anh. | Đặt câu tiếng Anh trong dấu nháy đơn, luôn có lời dẫn tiếng Việt kết thúc bằng dấu hai chấm. | Quy ước đánh dấu, ví dụ `[[en: We swam in the sea.]]`, hoặc trường `say` có các đoạn kèm ngôn ngữ. |
| G10 | Câu "nói theo cô" chỉ nhận ra được qua việc nằm trong `completion`. | Đặt trong `completion`. | `Item.kind: say_after_me` để validator lộ đáp án cho phép cô đọc câu mẫu trước (DI-108). |

Không phải khoảng trống: `HintLevel` H0–H7 dùng chung được với thang DI-112 (chỉ đổi lời gợi ý); quan hệ tiên quyết giữa các lesson được đồ thị chương giữ, giống Toán.

## 7. Cần chủ dự án kiểm lại

1. **Đáp án đọc qua ảnh.** Mọi đáp án `VERIFIED_SGV` đọc từ ảnh trang SGV. Nên liếc lại nhất là: SGV tr.182 (Key L1 Ex4, Ex5, Ex6), tr.186–187 (Key L2 Ex4, Ex5), tr.189–190 (Key L3 Ex2, Ex4), tr.252–253 (Key Review 3).
2. **"Sa Pa" hay "Fansipan"** (SGK tr.9 Ex5 câu 2): tranh ghi "FANSIPAN MOUNTAIN", SGV ghi "Sa Pa". Ngân hàng chưa dùng chỗ trống này; nếu dùng, cần quyết định có nhận "Fansipan" không.
3. **20 câu soạn thêm** (`AUTHORED`): duyệt nội dung và đáp án, nhất là các câu mức C (lời giải thích bằng tiếng Việt chấm bằng `facts.phrases`, có thể quá rộng hoặc quá hẹp) và câu E `U11-TR-TR-02` (bài mở, chỉ kiểm "went to" và "last").
4. **Đoạn tóm tắt bài đọc** tr.11 (lesson-3, C3): đã viết lại bằng lời khác; xem có đủ khác bản gốc không.
5. **Tên nút và ranh giới nút** (6 nút; "When did you go …?" gộp vào WHATDID).

## 8. Lịch sử

| Ngày | Việc | Người |
|---|---|---|
| 12/11/2026 | ENG-3: tạo Unit 11 "Family time" (6 nút, 3 lesson, 47 câu) từ SGK/SGV/tài liệu tập huấn NXB Giáo dục. Chủ dự án duyệt mặc định. | phiên Claude Code ENG-3 |
