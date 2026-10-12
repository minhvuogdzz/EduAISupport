# Phiên học thử trên phương án đã phát hành (2026-10-12)

Chạy bằng `make trial` (`services/api/scripts/trial_sessions.py`).

- Script đọc các phương án đã phát hành trong database của `.env` (`cavat_dev`) và **không ghi gì** vào đó: buổi học chạy trong bộ nhớ.
- Gia sư dùng câu mẫu (template), không gọi Qwen. Vì vậy phiên học thử kiểm phần tất định: chấm đáp án, gợi ý, chuyển tiết, qua tiết. Nó không kiểm cách Qwen diễn đạt.

Bốn học sinh giả lập học từng chương từ đầu đến cuối:

| Kiểu | Cách trả lời |
|---|---|
| `gioi` | Trả lời đúng, kể lại đúng ý chính |
| `hay-sai` | Trả lời sai trước ("123"), xin gợi ý, rồi trả lời đúng |
| `sai-dang` | Trả lời sai dạng trước, mỗi tiết nói lạc đề một lần ("Cô ơi con thích đá bóng lắm"). Sai dạng là trả lời đúng giá trị nhưng sai cách viết: 0,475 cho câu "viết phân số thập phân", 49/100 cho câu "viết số thập phân", chỉ một giá trị x |
| `bi` | Nói "Con không biết ạ" ở lần đầu mỗi câu, rồi trả lời đúng |

## 1. Kết quả qua ba lần chạy

| Lần chạy | Số thập phân: tiết qua | Diện tích: tiết qua | Điều được sửa trước lần chạy |
|---|---|---|---|
| 1 (sau khi phát hành lần đầu) | 1/11 | 0/8 | — |
| 2 | 5/11 | 0/8 | Bộ chấm câu đáp án mở (DI-48) |
| 3 (cuối) | **11/11** | **8/8** | Chọn câu bù dạng câu còn thiếu (DI-49); sửa nội dung tiết theo mục 3 |

Lần chạy cuối, bản phát hành `tl-20261012142023`:

| Chương | Kiểu | Lượt | Tiết qua | Kết quả chấm | Gợi ý đã đưa | Gợi ý bị loại vẫn hiện | Sai dạng được chấm đúng |
|---|---|---|---|---|---|---|---|
| Số thập phân | gioi | 104 | 11/11 | 60 đúng | 0 | 0 | 0 |
| | hay-sai | 227 | 11/11 | 61 đúng, 50 sai, 11 không đọc được | 58 | 0 | 0 |
| | sai-dang | 137 | 11/11 | 60 đúng, 11 sai | 11 | 0 | 0 |
| | bi | 164 | 11/11 | 60 đúng, 60 xin giúp | 0 | 0 | 0 |
| Diện tích tam giác, hình thang | gioi | 83 | 8/8 | 51 đúng | 0 | 0 | 0 |
| | hay-sai | 193 | 8/8 | 53 đúng, 40 sai, 13 không đọc được | 51 | 0 | 0 |
| | sai-dang | 91 | 8/8 | 51 đúng | 0 | 0 | 0 |
| | bi | 134 | 8/8 | 51 đúng, 51 xin giúp | 0 | 0 | 0 |

- "Không đọc được" là câu trả lời "123" cho câu Đúng/Sai hoặc câu đáp án mở. Gia sư hỏi lại, không chấm sai.
- Kiểu `sai-dang` ở chương Diện tích không có câu nào để trả lời sai dạng nên giống `gioi`.

## 2. Lỗi phiên học thử tìm ra

1. **Câu đáp án mở không chấm được (nghiêm trọng).**
   - Bản phát hành đầu có 61 câu như vậy (47 + 14): đọc số, nêu tên hàng, tìm các số tự nhiên x, điền dấu cho số đo, xếp tên, nêu nhiều kết quả. Bộ chấm trả "cần model đọc", nên gia sư nói mãi "Con đọc lại đề bài thật chậm…" rồi dừng tiết.
   - Học sinh `gioi` trả lời đúng 12 lần ở câu DTTGHT-BT-01 mà vẫn không qua.
   - Đã sửa bằng **DI-48** (`KeyFacts`): mỗi câu mở mang các "ý bắt buộc" rút từ đáp án của giáo viên, và `MathChecker` chấm tất định (quy tắc 2):
     - số, cho phép nhiều cách viết tương đương;
     - cụm từ;
     - dấu so sánh theo thứ tự;
     - thứ tự tên;
     - cặp "nhẹ nhất – bao C";
     - đọc số bằng chữ, không được viết lại chữ số.
   - 6 câu do giáo viên (ở đây là Claude theo ủy quyền) ghi tiêu chí bằng quyết định `item:<id>/facts`.
   - 2 câu không có tiêu chí chắc chắn nên bị loại khỏi phần dạy: STP-BT-14 (đáp án mở bất kỳ) và STP-BT-28 (thứ tự số đo nhiều đơn vị).
2. **Tiết dừng dù học sinh làm đúng hết.**
   - Tiết chỉ qua khi có thành công ở ít nhất 2 dạng câu. Gia sư chọn câu theo thứ tự danh sách, và ngân sách là 12 câu mỗi tiết.
   - STP-T06 có 14 câu điền số đứng trước câu so sánh. Học sinh `gioi` đạt độ thành thạo 99,7 nhưng tiết vẫn dừng vì "chưa đủ dạng".
   - Đã sửa bằng **DI-49** (`node-policy/0.2.0`): khi danh sách dài hơn ngân sách còn lại và câu bù dạng còn thiếu nằm quá xa, câu đó được đưa lên trước. Chính sách cũ vẫn giữ trong các trường hợp khác (toàn bộ test chính sách cũ vẫn qua).
3. **Nội dung tiết mà lần duyệt đầu bỏ sót.** Phiên học thử hiện ra các câu như "Bài: Đáy và đường cao của tam giác / Bước 2: Làm với cả ba loại. / Đáp số: Làm với cả ba loại..", nên Claude đọc lại toàn bộ lý thuyết, câu hỏi gợi mở và ví dụ mẫu của 19 tiết. Các sửa đổi:
   - 2 câu trả lời mẫu sai kiến thức: "hình thang vuông có **một** góc vuông", "85 m = **1,085** km";
   - 3 ví dụ mẫu trùng số liệu với câu bài tập hoặc đề kiểm tra, làm lộ đáp án. Có ví dụ tính ra 18, đúng đáp án câu DTTGHT-DE2-6;
   - 7 ví dụ mẫu là hoạt động trong giáo án chứ không phải bài giải, và 1 ví dụ dính mã LaTeX;
   - 5 câu hỏi gợi mở không có câu trả lời mẫu;
   - 5 bộ "ý chính" không phải ý ("dễ nhầm", "Đường cao phải ... với đáy");
   - 2 phương pháp sai tiết hoặc bị cắt;
   - 2 câu trả lời mẫu không khớp chính danh sách cách nói được chấp nhận.

   Chi tiết ở `evals/reports/2026-10-12-review-log.md`, mục 5.
4. **Đáp án mẫu bị cắt giữa câu** khi đáp án xuống dòng (DTTGHT-BT-01). Đã sửa bằng cách nối các dòng tới hết câu.

## 3. Giới hạn của phiên học thử

- Học sinh giả lập trả lời bằng chính đáp án và ý chính của giáo viên. Phiên thử kiểm luồng và bộ chấm, không đo được việc dạy có hiệu quả với trẻ thật.
- Không gọi Qwen: lời gia sư là câu mẫu. Phần Qwen diễn đạt được kiểm riêng ở `make eval-hard` và `make eval-grounded`.
- Bước "giải thích vì sao" chấp nhận câu chung chung "Vì con làm theo quy tắc cô dạy". Đây là hành vi sẵn có của vòng câu hỏi, chưa sửa trong đợt này.
- Đề kiểm tra cuối chương không chạy trong phiên thử. Đáp án và kiểu chấm của 79 câu đề đã được đọc khi duyệt.
- Gợi ý do Qwen soạn theo lô 6 câu. Sửa một câu làm cả lô được soạn lại, nên mỗi lần sửa câu phải đọc lại gợi ý (đã làm ở các đợt 3 và 4). Từ đợt 4, quyết định duyệt gợi ý lưu kèm nguyên văn chữ đã đọc.
