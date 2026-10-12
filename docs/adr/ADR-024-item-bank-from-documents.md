# ADR-024: Ngân hàng câu hỏi nháp từ tài liệu của giáo viên, mọi đáp án được kiểm (INGEST-2)

**Trạng thái:** Đề xuất, 2026-10-12. Chủ dự án chờ duyệt DI-44.
- Code: `cavat/modules/ingest/` (`parse.py`, `plan.py`, `verify.py`, `build.py`, `service.py`, `api.py`), `assessment/vi_words.py`.
- Lệnh: `make item-bank`, `make eval-items`.
- Liên quan: ADR-023 (đọc tài liệu), quy tắc 2 của CLAUDE.md (đáp án bài kiểm tra không vào prompt).

## Bối cảnh

INGEST-1 đã đưa 18 file của chủ dự án vào thư viện. Bước này biến bài tập, phiếu luyện tập và đề kiểm tra thành từng câu kèm đáp án, để INGEST-3 lên phương án dạy và gia sư cho con luyện.

Một đáp án đọc từ tài liệu có thể sai theo ba cách:
1. tài liệu sai;
2. bản đọc sai (INGEST-1 đã gặp: phân số 9/10 trong ảnh bị đọc thành 7/10);
3. đáp án bị ghép nhầm câu.

Đáp án sai mà vào ngân hàng câu thì gia sư sẽ chấm sai học sinh.

## Quyết định

1. **Tách câu tất định, không dùng model.**
   - Ba kiểu trình bày của chủ dự án:
     - bài tập: "Phần k · <mức>", câu đánh số liền nhau;
     - phiếu: "Phiếu k · Tiết k", in hai cột;
     - đề: "Đề số k", phần I trắc nghiệm, phần II tự luận B1…;
   - đáp án ở hai dạng: hàng bảng `|` (trang Gemini đọc) hoặc nhãn đứng riêng một dòng (lớp chữ).
   - Câu nhỏ a), b), c) và phương án A. B. C. D. được tách riêng.
   - Đáp án đề có lời giải từng bước (B2a, B2b) thì các bước được gộp lại cho câu B2.
2. **Gắn câu vào tiết theo chính giáo án.** Giáo án ghi "Bài tập câu 1, 2, 6 … Phiếu luyện tập số 1" cho từng tiết. Đề kiểm tra thuộc tiết ôn tập cuối chương.
3. **Kiểm từng đáp án với đề, chính xác bằng phân số, không dùng model:**
   - mọi phép tính và so sánh viết trong đáp án phải đúng, có đổi đơn vị;
   - đổi phân số, hỗn số, số đo; làm tròn theo hàng đề nêu;
   - điền dấu so sánh (đúng số của đề); sắp xếp; tìm số tự nhiên x; tìm chữ số x;
   - hàng và giá trị của chữ số; cấu tạo số ("gồm 17 đơn vị, 1 phần mười…");
   - đọc và viết số thập phân bằng chữ;
   - diện tích tam giác, hình thang, tam giác vuông, hình thang vuông, hình ghép; tính ngược chiều cao hoặc đáy;
   - trắc nghiệm: chọn đúng một phương án, lời giải kết thúc đúng giá trị của phương án đó; đúng/sai của mệnh đề có số.
4. **Có căn cứ.**
   - Mỗi số có từ 2 chữ số trở lên trong đáp án phải có trong đề (so theo giá trị, kể cả đổi đơn vị), hoặc là kết quả mà một bước kiểm đã tự tính, hoặc là một vế của phép "=" đúng.
   - Số không như vậy thì câu vào trạng thái "cần xem lời giải": đáp án vẫn đúng, chỉ có một số trong lời giải cần giáo viên liếc qua.
5. **Trạng thái của từng câu:**

   | Trạng thái | Nghĩa |
   |---|---|
   | VERIFIED | đã kiểm, khớp |
   | REVIEW | đáp án khớp, cần xem lời giải |
   | CONFLICT | mâu thuẫn |
   | DISPUTED | có số mà hai lần đọc ở INGEST-1 không khớp |
   | UNCHECKED | không bước kiểm nào áp dụng được; giáo viên duyệt |
   | NO_ANSWER | không có đáp án |

6. **Lưu trữ:** một document mỗi chương trong collection `item_banks` (ghi một lần). Dựng lại thì thay document cũ. Chỉ giáo viên đọc được, vì có đáp án đề kiểm tra.

## Kết quả trên tài liệu thật (2026-10-12)

| Chương | Số câu | VERIFIED | REVIEW | CONFLICT + DISPUTED | UNCHECKED |
|---|---|---|---|---|---|
| Số thập phân | 234 | 224 | 3 | 3 | 4 |
| Diện tích tam giác, hình thang | 155 | 125 | 1 | 0 | 29 |

- **3 câu CONFLICT/DISPUTED đều là lỗi đọc thật của INGEST-1:**
  - câu 2a: "0,9 = 7/10";
  - câu 2b: 9/100 thay vì 6/100;
  - phiếu 1 câu 3: "10" thay vì 9/10.
- **4 câu REVIEW** có số trung gian hợp lệ trong lời giải ("tô 3 cột, 30 ô").
- **Độ nhạy (`make eval-items`):** đổi lần lượt từng chữ số của mọi đáp án đã khớp (mỗi chữ số thử 2 cách), bộ kiểm bắt được 2000/2060 lần (97,1%) ở Số thập phân và 1360/1382 lần (98,4%) ở hình học.
- **Còn lọt:** chữ số trong lời giải bằng chữ ("hàng phần trăm"), bước giữa của lời giải tìm chữ số x, ví dụ tự đặt trong đề mở.
- **Câu UNCHECKED** là câu khái niệm (đúng/sai về đường cao, chọn đơn vị), câu mở, câu dựa hoàn toàn vào hình vẽ. Phải để giáo viên duyệt (INGEST-4).
- **Giáo án:** hai câu bài tập hình học (10 và 23) chưa tiết nào dùng. Đây là phát hiện để chủ dự án bổ sung giáo án.

## Hệ quả

- **INGEST-3** dùng ngân hàng này:
  - câu VERIFIED đưa vào phương án dạy;
  - câu CONFLICT, DISPUTED, NO_ANSWER không bao giờ được dạy khi giáo viên chưa sửa;
  - câu REVIEW và UNCHECKED cần giáo viên duyệt.
- Bộ đọc số bằng chữ (`vi_words`) dùng lại được cho bộ chấm khi học sinh trả lời bằng chữ.
