# ADR-025: Phương án dạy nháp dựng từ tài liệu của giáo viên (INGEST-3a)

**Trạng thái:** Đề xuất, 2026-10-12. Chủ dự án chờ duyệt DI-45.
- Code: `cavat/modules/ingest/theory.py` (đọc lý thuyết, giáo án, lỗi sai), `cavat/modules/ingest/teaching.py` (dựng gói chương).
- Lệnh: `make teaching-plan`. API giáo viên: `GET/POST /v1/teachers/teaching-plans/{chương}`.
- Liên quan: ADR-018 (đồ thị tri thức), ADR-024 (ngân hàng câu), kế hoạch v1 mục 5.

## Bối cảnh

Gia sư dạy theo gói chương (`ChapterPackage` cùng các `LessonPackage`): mỗi bài có lý thuyết, phương pháp, bài mẫu, phần "con nói lại" và các câu theo 4 mức. Gói hiện có do Claude soạn tay (`docs/pedagogy/…`). Chủ dự án muốn gia sư tự đọc tài liệu của giáo viên rồi lên phương án dạy.

**Chủ dự án quyết ngày 2026-10-12:** mỗi tiết của giáo án là một bài (node); gợi ý do AI soạn bám tài liệu và giáo viên duyệt (INGEST-3b); tài liệu nhân, chia số thập phân anh sẽ bổ sung.

## Quyết định

1. **Không dùng model.** Mọi nội dung dạy là chữ của tài liệu, kèm trang nguồn.
2. **Mỗi tiết có bài (không tính tiết ôn tập) là một node.**
   - Tiết có tên "luyện tập, ứng dụng, thực tế, vận dụng, hình ghép, công thức ngược" là node vận dụng (IMPLEMENT). Các tiết còn lại là node khái niệm (BASIC).
   - Quan hệ:
     - mỗi node khái niệm cần node khái niệm trước nó (PREREQUISITE);
     - node vận dụng áp dụng các node khái niệm của cùng bài SGK, hoặc của cả chương khi bài đó là luyện tập chung (APPLICATION).
3. **Nội dung của mỗi node:**
   - hai cách giảng:
     - bước "Khám phá" của giáo án, minh họa bằng đồ dùng ở mục "Chuẩn bị";
     - khung GHI NHỚ của lý thuyết.
     Mỗi cách kết thúc bằng một "Câu hỏi gợi mở" của tiết.
   - phương pháp: khung GHI NHỚ và các bước "Bước 1. …". Không có khung riêng thì dùng quy tắc bé tự nói ở bước Củng cố, nếu cũng không có thì dùng quy tắc chung của bài SGK.
   - bài mẫu: các khung VÍ DỤ kèm lời giải và "Đáp số". Không có thì dùng phần trình diễn ở bước Khám phá.
   - con nói lại: quy tắc trong ngoặc kép ở bước Củng cố, tách thành các ý chính.
   - lỗi sai: mục "Khi bé sai" của tiết, và các "Lỗi k" của tài liệu lỗi sai gắn vào tiết gần nhất.
4. **Ghép lý thuyết vào tiết (DI-45):**
   - Mỗi mục lý thuyết được ghép vào tiết cùng bài SGK có nhiều từ "phân biệt" chung nhất. Tên tiết và tên mục tính gấp ba. Từ có ở mọi tiết của bài thì không tính (trọng số kiểu IDF).
   - Mỗi khung VÍ DỤ được ghép riêng, ví dụ khung khối lượng vào tiết khối lượng.
5. **Câu hỏi lấy từ ngân hàng câu (ADR-024), theo tiết mà giáo án ghi:**
   - "Kiểm tra hiểu" là câu kiểm tra; "Cùng làm" là câu cùng làm; "Luyện tập" và phiếu của tiết là câu luyện tập; "Vận dụng" là câu vận dụng.
   - Tiết không có câu kiểm tra hiểu thì dùng câu đầu tiên của phiếu tiết đó.
   - Câu CONFLICT, DISPUTED, NO_ANSWER **không bao giờ được dạy**.
   - Đề kiểm tra thành bài kiểm tra cuối chương (EXIT). Phiếu của tiết ôn tập thành câu ôn tập (REVIEW).
   - Mỗi đáp án được chuyển sang dạng mà bộ chấm dùng: so sánh, sắp xếp, số, trắc nghiệm, đúng/sai, hoặc câu mở.
6. **Lưu trữ:** collection `teaching_plans`, mỗi chương một document, trạng thái DRAFT đến khi giáo viên duyệt (INGEST-4). Những gì bộ kiểm hợp lệ của gia sư còn đòi được ghi trong `problems`. Câu không đưa vào được ghi trong `left_out`, kèm lý do.

## Kết quả trên tài liệu thật (2026-10-12)

| Chương | Bài | Câu bài tập và phiếu | Kiểm tra cuối chương | Còn thiếu |
|---|---|---|---|---|
| Số thập phân | 11 | 177 | 46 | 22 |
| Diện tích tam giác, hình thang | 8 | 118 | 33 | 13 |

- **Phần còn thiếu chủ yếu do tài liệu:**
  - 13 tiết không có câu vận dụng (tài liệu chỉ có 6 câu vận dụng mỗi chương);
  - 12 tiết có bước Củng cố là câu hỏi chứ không trích quy tắc, nên chưa có ý chính để con nói lại;
  - 5 tiết luyện tập chỉ có một cách giảng.
- **Không đưa vào:** 3 câu Số thập phân bị đọc sai (ADR-023); câu 10 và 23 của bài tập hình học vì giáo án không có tiết nào dùng.
- **[OPEN] Giới hạn của cách ghép theo từ ngữ:** mục "Viết số thập phân thành phân số thập phân" được ghép vào tiết 2 thay vì tiết 3. Giáo viên sửa ở bước duyệt (INGEST-4).

## Hệ quả

- **INGEST-3b (Qwen soạn, có kiểm chứng, giáo viên duyệt):**
  - câu trả lời mẫu và cách nói được chấp nhận cho câu hỏi gợi mở;
  - ý chính để con nói lại;
  - thang gợi ý H1–H3;
  - câu hỏi kết cho cách giảng còn thiếu.
- **Chủ dự án quyết thêm:** cách xử lý tiết thiếu câu vận dụng. Có thể bổ sung tài liệu, cho AI soạn câu (bộ chấm kiểm lại), hoặc với tiết khái niệm thì không đòi bằng chứng vận dụng (đổi DI-6).
