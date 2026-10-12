# ADR-026: Qwen soạn phần tài liệu còn thiếu, có kiểm chứng (INGEST-3b)

**Trạng thái:** Đề xuất, 2026-10-12. Chủ dự án chờ duyệt:
- DI-46;
- prompt `ingest/prompts/draft-hints.v1.md` và `draft-node.v1.md`;
- từng phần do Qwen soạn (ở INGEST-4).

Code: `cavat/modules/ingest/drafting.py`. Lệnh: `make draft-teaching`.

Liên quan: ADR-025 (phương án dạy nháp), ADR-021 (lời nói có căn cứ), quy tắc 1, 2 và 7 của CLAUDE.md.

## Bối cảnh

INGEST-3a dựng phương án dạy chỉ từ chữ của tài liệu. Tài liệu không có:
- thang gợi ý cho từng câu;
- câu trả lời mẫu và cách nói được chấp nhận cho câu hỏi gợi mở;
- ý chính để con nói lại ở 12 tiết.

Chủ dự án chọn ngày 2026-10-12: "AI soạn, bám tài liệu", giáo viên duyệt.

## Quyết định

1. **Qwen chỉ soạn, không quyết định.** Mọi phần soạn phải qua bộ kiểm; phần không qua thì bị bỏ, **không thay bằng câu khác**.
2. **Gợi ý H1 (TASK), H2 (CONCEPT), H3 (STRATEGY)** cho mỗi câu luyện tập, 6 câu một lần gọi. Qwen chỉ được thấy quy tắc, các bước và lỗi sai của chính tiết đó.
   - Mỗi gợi ý qua **đúng bộ kiểm lời gia sư** (`validate_message` với nước đi HINT):
     - không lộ đáp án, kể cả nhắc riêng phương án đúng;
     - đúng một câu hỏi, đặt ở cuối;
     - số có trong đề;
     - tối đa 40 từ, chỉ tiếng Việt, gọi học sinh là "con", không khen trí thông minh.
   - Thuật ngữ Toán phải có trong đề hoặc quy tắc của tiết.
   - Ba bậc không được trùng nhau.
   - Căn cứ thuật ngữ là toàn bộ chữ của tiết, kèm chữ của các ký hiệu phép tính (× là nhân, : là chia; "7/10" là phân số có tử số và mẫu số).
   - Gợi ý bị loại được gửi sửa lại một lần, kèm lý do. Phần qua kiểm mới lấp vào bậc đó.
3. **Phần của từng tiết:**
   - câu trả lời mẫu (tối đa 35 từ) và 2–4 cách nói được chấp nhận cho mỗi câu hỏi gợi mở;
   - câu hỏi cho cách giảng còn thiếu;
   - 2–3 ý chính để con nói lại.

   Số và thuật ngữ phải có trong chữ của tiết. Cách nói được chấp nhận chỉ được dựa vào câu trả lời mẫu khi câu mẫu đó đã qua kiểm. Ý chính phải dùng từ của tiết (DI-46).
4. **Câu kiểm tra cuối chương không bao giờ được gửi cho model** (quy tắc 2).
5. **Lưu vết:**
   - Mỗi phần soạn được ghi lại (`drafts` trong `teaching_plans`): loại, vị trí, nội dung, model, kết quả kiểm.
   - Phương án vẫn là bản nháp đến khi giáo viên duyệt (INGEST-4).
   - Prompt là artifact có version (quy tắc 7).
6. **Hạn mức:**
   - Mỗi yêu cầu được lưu trên đĩa theo nội dung, nên dựng lại không tốn hạn mức.
   - Các lần gọi cách nhau 8 giây vì giới hạn 8.000 token/phút.
   - Prompt luôn dưới 3.000 token.

## Kết quả

Chi tiết ở `evals/reports/2026-10-12-drafting.md`.

| | Số thập phân | Hình học |
|---|---|---|
| Câu có đủ 3 bậc gợi ý | 73% | 88% |
| Ý chính để con nói lại | 52 | 22 |
| Chỗ còn thiếu (trước → sau) | 16 → 8 | 9 → 4 |

**[FACT]** Một gợi ý của câu đúng/sai lộ đáp án bằng lập luận ("đáy luôn song song, vì vậy chúng không thể vuông góc"). Bộ kiểm chưa bắt được dạng này, nên giáo viên phải duyệt.

## Hệ quả

- Gợi ý do Qwen soạn đi vào thang gợi ý của câu. Gia sư dùng chúng như câu mẫu, và lời Qwen nói lúc dạy vẫn qua bộ kiểm thêm một lần nữa.
- **Giới hạn:**
  - bộ kiểm chỉ xét căn cứ (số, thuật ngữ, từ ngữ), không xét được câu trả lời mẫu có **đúng ý** hay không;
  - cách nói được chấp nhận có thể quá rộng (ví dụ chấp nhận "phần thập phân" cho câu hỏi về mẫu số).

  Vì vậy giáo viên duyệt là bắt buộc (INGEST-4).
