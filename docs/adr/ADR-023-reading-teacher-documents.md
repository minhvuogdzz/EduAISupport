# ADR-023: Đọc tài liệu của giáo viên từng trang, có kiểm chứng (INGEST-1)

**Trạng thái:** Đề xuất, 2026-10-12. Chủ dự án chờ duyệt DI-43.
- Code: `library/extract.py` (đọc từng trang, kiểm chứng), `library/api.py` (`read_document`), `cavat/library_import.py` (`make library-import`).
- Liên quan: ADR-017 (Gemini cho ảnh và OCR), ADR-020 (luồng tài liệu của giáo viên), ADR-021 (lời nói có căn cứ).

## Bối cảnh

Chủ dự án đưa 18 file PDF cho hai chương demo, gồm lý thuyết, bài tập, phiếu luyện tập, đề kiểm tra (đều có file đáp án), giáo án và lỗi sai. Mục tiêu (D-T10) là gia sư tự đọc tài liệu rồi lên phương án dạy.

**[FACT] Hai chỗ lớp chữ của PDF làm mất nội dung:**
1. **Phân số in bằng ảnh nhỏ** (file Số thập phân): "Các phân số thập phân , , viết là 0,1 ; 0,01 ; 0,001". Câu 1 của bài tập mất cả bốn phân số của đề.
2. **Hình vẽ bằng nét vẽ** (file hình học): chỉ còn nhãn rời "H A B C 7 cm 12 cm", không biết cạnh nào là đáy, cạnh nào là chiều cao.

Bản đọc cũ (DOC-1) chỉ dùng OCR khi cả file không có chữ, nên **mất các phần này mà không báo gì**.

**[FACT] Lỗ hổng an toàn:** RAG đưa mọi tài liệu có chữ vào kho tìm kiếm. Một file đáp án tải lên sẽ thành nguồn để gia sư "nói có căn cứ" ra đáp án, trái với quy tắc 2 của CLAUDE.md.

## Quyết định

1. **Đọc PDF từng trang.** Trang có dấu hiệu mất nội dung (DI-43) được tách thành một PDF một trang và gửi Gemini với lời nhắc riêng: chép nguyên văn, phân số viết a/b, bảng mỗi hàng một dòng, hình vẽ mô tả trong `[Hình: …]` (đáy, đường cao, góc vuông, số đo).
2. **Kiểm chứng như lớp "khẳng định và bằng chứng" của 2T-KT.**
   - Bản Gemini chỉ thay lớp chữ khi giữ đủ mọi số của lớp chữ.
   - Không đủ: giữ lớp chữ và đánh dấu trang "cần xem lại".
   - Số chỉ Gemini đọc được (phân số trong ảnh) không có trong lớp chữ để đối chiếu. Vì vậy **một model khác đọc lại trang đó lần hai**: hai lần phải ra đúng các số ấy. Lệch thì trang được đánh dấu cho giáo viên, kèm các số bị lệch.
   - LaTeX trong bản đọc (`$\text{m}^2$`) được đưa về dạng thường (`m²`).
3. **Loại tài liệu mới:** bài giảng, phiếu luyện tập, đáp án, lỗi sai.
   - Đáp án và đề kiểm tra không bao giờ vào RAG.
   - Một file đáp án được nối với file đề của nó (`answers_for`).
4. **Bản đọc của Gemini được lưu trên đĩa** theo mã băm của trang và lời nhắc, kèm model đã đọc, nên đọc lại không tốn hạn mức. Mọi lời gọi đi qua `ai_gateway`. Chuỗi model miễn phí là `gemini-3.8-flash` → `gemini-2.5-flash` → `gemini-3.5-flash-lite` (mỗi model 20 lần/ngày).
5. **`make library-import DIR=tailieu`:**
   - Nhập cả thư mục qua đúng đường của nút tải lên.
   - Loại và chương lấy từ tên file `<STP|DTTGHT>-<loại>[-dapan]`.
   - Ghi vào database của `.env`. Đây là tài liệu thật của giáo viên, không phải dữ liệu demo.

## Kết quả trên 18 file của chủ dự án (2026-10-12)

- 31/77 trang được đọc lại: 12 trang có ảnh, 19 trang có hình vẽ hoặc trục số. Không trang nào thiếu số so với lớp chữ.
- 8 trang có số chỉ Gemini đọc được, đều là phân số dạng ảnh của chương Số thập phân:
  - 6 trang: hai model đọc khớp nhau;
  - **2 trang lệch nhau**, nên được đánh dấu cho giáo viên xem.
- **[FACT]** Trang 1 file đáp án bài tập, câu 2: ảnh gốc là a) 9/10, b) 6/100. Một model đọc thành 7/10 và 9/100, model kia đọc đúng.
  - Nếu chỉ đọc một lần, đáp án sai sẽ đi thẳng vào ngân hàng câu hỏi.
  - Đây là lý do có bước đọc hai lần, và có bước `MathChecker` đối chiếu đáp án với đề ở INGEST-2 (0,9 phải bằng 9/10).
- Lần chạy đầu hết hạn mức `gemini-3.8-flash` (20 lần/ngày) giữa chừng. Các trang thiếu được đọc lại bằng model dự phòng.
- `gemini-2.5-flash-lite` đã ngừng cho người dùng mới, nên thay bằng `gemini-3.5-flash-lite`.

## Hệ quả

- **Chi phí:** 31/77 trang của bộ tài liệu được Gemini đọc lại, mỗi trang một lần nhờ bộ nhớ đệm.
- **Tốc độ:** khoảng 1 trang mỗi phút trên free tier, chậm nhưng chỉ chạy một lần.
- **Giáo viên:**
  - tab Tài liệu hiện "Cần xem lại trang …" và "Không vào RAG";
  - trang chi tiết liệt kê từng trang được đọc lại cùng các số Gemini đọc thêm.
- **Bước sau:**
  - INGEST-2: tách câu và đáp án;
  - INGEST-3: đồ thị và phương án dạy;
  - INGEST-4: giáo viên duyệt;
  - RAG-3: đo lại RAG trên tài liệu thật.
