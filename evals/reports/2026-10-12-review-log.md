# Nhật ký duyệt phương án dạy hai chương (2026-10-12)

Tài liệu này ghi lại **cái gì đã được duyệt, ai duyệt, duyệt bằng cách nào, cái gì bị loại hoặc sửa, và cái gì chưa duyệt**. Nó làm bằng chứng cho phần "giáo viên kiểm soát nội dung" trong luận văn.

## 1. Ủy quyền

- Ngày 2026-10-12, chủ dự án (giáo viên kiểm soát) đã xem hết tài liệu và cho phép Claude tự duyệt toàn bộ thay mình, với điều kiện ghi lại phần đã duyệt và chưa duyệt. Lời chủ dự án: "anh cho phép em tự động duyệt toàn bộ tài liệu hộ anh vì anh duyệt thì nó bị lâu".
- Mọi quyết định của Claude được lưu với `by = "claude (ủy quyền chủ dự án 2026-10-12)"`, kèm thời điểm và lý do (`reason`). Quyết định do chủ dự án tự bấm trên trang giáo viên mang mã tài khoản giáo viên và được giữ nguyên.
- Các quyết định nằm trong document `teaching_plans` của database `cavat_dev`. Bản sao đầy đủ (kèm nguyên văn từng gợi ý đã duyệt) xuất bằng `make review-export` vào `var/storage/reports/` (không đưa lên git vì có chữ trích từ tài liệu của giáo viên). Chủ dự án có thể xem, hoàn tác (`DELETE …/decisions`) hoặc sửa từng quyết định trên trang `/teacher/plans/<chương>`.

## 2. Cách duyệt

1. **Đọc toàn bộ.** Mỗi câu được dạy và đề kiểm tra cuối chương được in kèm đề, đáp án của giáo viên, kiểu chấm máy sẽ dùng, và mọi gợi ý H1–H3 do Qwen soạn. Claude đọc từng dòng: 789 gợi ý ở lần đọc đầu. Sau đó, mỗi lần Qwen soạn lại thì đọc lại phần đổi: 86 câu ở đợt 2, 40 gợi ý ở đợt 3, 61 gợi ý ở đợt 4.
2. **Tiêu chí loại gợi ý:**
   - sai kiến thức (ví dụ "1 tạ = 10 kg");
   - hướng sai chiều hoặc thiếu bước (bỏ "chia 2" trong công thức hình thang);
   - lộ đáp án (nhất là câu Đúng/Sai);
   - lệch khỏi câu hỏi;
   - dùng phép tính chưa học (chia cho 100);
   - câu tiếng Việt sai.

   Gợi ý bị loại không được thay bằng chữ Claude tự viết, nên câu đó còn ít bậc gợi ý hơn.
3. **Kiểm loại bỏ đúng chỗ.** Mỗi quyết định loại ghi kèm vài chữ của gợi ý đã đọc. Script chỉ ghi quyết định khi chữ đó còn nằm trong gợi ý hiện tại, nên không thể loại nhầm một gợi ý khác. Nội dung gợi ý bị loại được chép vào lý do.
4. **Câu và đáp án.**
   - Câu `VERIFIED` (bộ kiểm tất định khớp đáp án) được duyệt sau khi Claude đọc đề và đáp án.
   - Câu `UNCHECKED` hoặc `REVIEW` (câu lời văn, câu Đúng/Sai lý thuyết mà bộ kiểm không tự kiểm được) được Claude đọc và tự kiểm đáp án.
   - Claude **không** mở lại ảnh trang PDF gốc cho từng câu: phần đọc tài liệu đã được kiểm bằng hai model ở INGEST-1/2.
5. **Phần thiếu của tiết.** Cách giảng thứ hai, ví dụ có nhiều bước và câu chuyển giao được soạn bổ sung bám theo tài liệu lý thuyết và giáo án của chính tiết đó. Lý do ghi rõ phần tài liệu được dựa vào. Không thêm câu bài tập ngoài tài liệu.
6. **Phát hành và học thử.** Mỗi chương chỉ được phát hành khi mọi tiết đã duyệt và bộ kiểm hợp lệ của gia sư không còn báo thiếu. Việc duyệt diễn ra qua bốn đợt:

   | Đợt | Nội dung | Phát hành |
   |---|---|---|
   | 1 | Sửa đề và đáp án đọc nhầm; soạn bổ sung phần còn thiếu của 7 tiết | — |
   | 2 | Đọc từng gợi ý (loại 67), duyệt từng câu và từng tiết | `tl-20261012135700` / `…135701` |
   | 3 | Sau phiên học thử lần 1: ghi tiêu chí chấm câu mở; đọc lại **toàn bộ** lý thuyết, câu hỏi gợi mở, ví dụ mẫu của 19 tiết và sửa lỗi | `tl-20261012141234` / `…141236` |
   | 4 | Đọc lại gợi ý được Qwen soạn lại (61 gợi ý, loại thêm 9). Từ đây quyết định duyệt gợi ý lưu kèm nguyên văn chữ đã đọc | `tl-20261012141931` / `…141933`, rồi `tl-20261012142023` (cả hai chương) |

   **Ghi nhận trung thực:** ở đợt 2, Claude duyệt tiết khi mới đọc kỹ phần bổ sung của 7 tiết thiếu, chưa đọc kỹ lý thuyết và ví dụ mẫu của mọi tiết. Phiên học thử lộ ra các lỗi đó (mục 3), và đợt 3 đã đọc lại, sửa hết. Bản dạy hiện hành là `tl-20261012142023`.

## 3. Lỗi tìm ra khi duyệt và đã sửa trong code

Khi đọc kiểu chấm của từng câu, Claude tìm ra các lỗi sau. Mỗi lỗi đã được sửa ở bộ đọc đáp án (`ingest/teaching.py`) hoặc bộ chấm (`MathChecker`), và có test. Đây là các lỗi mà bộ kiểm tự động trước đó không bắt được:

Số câu dưới đây là số câu đổi kiểu chấm so với bản trên `main` trước buổi duyệt (đếm bằng script trên cả ngân hàng câu):

| Lỗi | Hậu quả nếu không sửa | Số câu |
|---|---|---|
| Đáp án diện tích "S = 12 × 7 : 2 = 42 cm²" bị đọc thành Đúng/Sai ("S" = Sai) | Bé trả lời 42 bị chấm sai | 6 |
| "0,475 = ……" (viết phân số thập phân) chấm theo giá trị | Bé chép lại 0,475 vẫn được chấm đúng | 12 |
| "49/100 = ……" (viết số thập phân) chấm theo giá trị | Bé chép lại 49/100 vẫn được chấm đúng | 13 |
| "x = 2 ; 3 ; 4 ; 5" đọc thành số 2 | Bé chỉ ghi 2 đã được chấm đúng | 5 |
| Một dòng có bốn cặp so sánh chỉ chấm cặp đầu | Đề kiểm tra chấm sai ba ý | 2 |
| "17,002 tấn" không đọc được vì chữ "tấn" | Câu chấm được bằng số lại thành đáp án mở (khi đó chưa chấm tự động được) | 5 |
| Bài lời văn, câu viết số, câu làm tròn trong đề kiểm tra là đáp án mở | Nay chấm tất định theo kết quả cuối của lời giải | 59 |
| Câu đáp án mở không có cách chấm: gia sư hỏi lại mãi rồi dừng tiết (phiên học thử phát hiện) | Bé trả lời đúng vẫn không qua tiết; 0/8 tiết hình học | 61 |
| Tiết cần 2 dạng câu nhưng chọn câu theo thứ tự danh sách, hết 12 câu vẫn một dạng (phiên học thử phát hiện) | Bé làm đúng hết vẫn bị dừng tiết | STP-T06 và các tiết tương tự |
| Duyệt một câu đã chuyển chặng làm hỏng việc dựng lại phương án | Lỗi khi dựng lại phương án | (lỗi code) |

Ở nhóm 59 câu, các câu hỏi nhiều ý vẫn là đáp án mở (chấm theo `KeyFacts`, DI-48), không ép thành một số. Đó là các câu có nhiều câu hỏi, hỏi "các …", "nào … và …", và các câu có số đo nhiều đơn vị mà đề không nói đơn vị kết quả (ví dụ đáy 3 dm, cao 25 cm: cả 375 cm² lẫn 3,75 dm² đều đúng).

DI mới: **DI-47** (duyệt và đọc đáp án), **DI-48** (`KeyFacts`: chấm tất định câu đáp án mở), **DI-49** (`node-policy/0.2.0`: đưa câu bù dạng còn thiếu lên trước) trong `docs/plan/plan-v1-teaching-knowledge-graph.md`.

## 4. Số liệu

| | Số thập phân | Diện tích tam giác, hình thang |
|---|---|---|
| Tiết (node) duyệt — chủ dự án trên trang giáo viên | 2 | 0 |
| Tiết (node) duyệt — Claude theo ủy quyền | 9 | 8 |
| Phần của tiết soạn bổ sung (cách giảng, ví dụ, phương pháp, ý chính) | 47 | 46 |
| Tiết hạ số dạng câu hỏi (DI-47) | 4 | 0 |
| Câu luyện tập/kiểm tra hiểu: duyệt | 184 | 118 |
| Câu đề kiểm tra cuối chương: duyệt | 46 | 33 |
| Câu loại | 4 | 0 |
| Câu sửa đề | 21 | 0 |
| Câu sửa đáp án | 2 | 0 |
| Câu chuyển chặng (thành câu chuyển giao) | 1 | 2 |
| Câu mở: ghi tiêu chí chấm thủ công (facts) | 0 | 6 |
| Gợi ý AI soạn: duyệt (đã đọc từng gợi ý) | 410 | 302 |
| Gợi ý AI soạn: loại | 50 | 31 |
| Bản nháp AI bị bộ kiểm tự động chặn trước khi tới giáo viên (không dạy) | 293 | 117 |
| Câu trong tài liệu không tiết nào dùng (không dạy, chưa duyệt) | 0 | 4 |

## 5. Chi tiết từng quyết định (trừ các quyết định 'duyệt' — xem bản xuất `make review-export`)

### Số thập phân (bản phát hành `tl-20261012142023`)

**Tiết chủ dự án tự duyệt (giữ nguyên) (2):**

- `STP-T01` lúc 2026-10-12 09:47 UTC
- `STP-T02` lúc 2026-10-12 09:47 UTC

**Câu bị loại (4):**

- `STP-BT-06` — Câu dựa vào hình 100 ô vuông tô màu; đề không mô tả hình nên bé không làm được trong khung chat.
- `STP-BT-14` — Đọc lại sau phiên học thử: đáp án mở (bất kỳ ba trong chín số 1,21 … 1,29); bộ chấm tất định chưa đọc được kiểu đáp án này.
- `STP-BT-28` — Đọc lại sau phiên học thử: đáp án là thứ tự các số đo viết bằng nhiều đơn vị; bộ chấm tất định chưa đọc được thứ tự đó.
- `STP-BT-30` — Câu dựa vào hình tia số; mô tả hình (M sát 3,5) không khớp đáp án 3,7 và bé không xem được hình trong khung chat.

**Câu được sửa hoặc chuyển chặng (24):**

- `STP-BT-02a/answer` = “9/10” — Đáp án đọc nhầm 7/10; 0,9 = 9/10 (kiểm tra bằng phép đổi).
- `STP-BT-02b/answer` = “6/100” — Đáp án đọc nhầm 9/100; 0,06 = 6/100 (kiểm tra bằng phép đổi).
- `STP-PH01-1/stem` = “Viết thành số thập phân: / 49/100 = ……” — Đề phiếu chỉ in phép viết, tiêu đề phiếu nói yêu cầu; ghi yêu cầu vào đề để bé đọc trong khung chat.
- `STP-PH01-2/stem` = “Viết thành số thập phân: / 7/10 = ……” — Đề phiếu chỉ in phép viết, tiêu đề phiếu nói yêu cầu; ghi yêu cầu vào đề để bé đọc trong khung chat.
- `STP-PH01-3/stem` = “Viết thành số thập phân: / 9/10 = ……” — Máy đọc mất tử số của phân số (đề chỉ còn '10 = ……'); đáp án 0,9 của giáo viên cho thấy phân số là 9/10. Ghi thêm yêu cầu của phiếu vào đề.
- `STP-PH01-4/stem` = “Viết thành phân số thập phân: / 1,02 = ……” — Đề phiếu chỉ in phép viết, tiêu đề phiếu nói yêu cầu; ghi yêu cầu vào đề để bé đọc trong khung chat. Đáp án là phân số thập phân, bộ chấm đòi đúng dạng.
- `STP-PH01-5/stem` = “Viết thành phân số thập phân: / 3,1 = ……” — Đề phiếu chỉ in phép viết, tiêu đề phiếu nói yêu cầu; ghi yêu cầu vào đề để bé đọc trong khung chat. Đáp án là phân số thập phân, bộ chấm đòi đúng dạng.
- `STP-PH01-6/stem` = “Viết thành phân số thập phân: / 2,4 = ……” — Đề phiếu chỉ in phép viết, tiêu đề phiếu nói yêu cầu; ghi yêu cầu vào đề để bé đọc trong khung chat. Đáp án là phân số thập phân, bộ chấm đòi đúng dạng.
- `STP-PH01-7/stem` = “Viết thành số thập phân: / 16 99/100 = ……” — Đề phiếu chỉ in phép viết, tiêu đề phiếu nói yêu cầu; ghi yêu cầu vào đề để bé đọc trong khung chat.
- `STP-PH01-8/stem` = “Viết thành số thập phân: / 12 796/1000 = ……” — Đề phiếu chỉ in phép viết, tiêu đề phiếu nói yêu cầu; ghi yêu cầu vào đề để bé đọc trong khung chat.
- `STP-PH03-7/stem` = “Viết thành phân số thập phân: / 2,1 = ……” — Đề phiếu chỉ in phép viết, tiêu đề phiếu nói yêu cầu; ghi yêu cầu vào đề để bé đọc trong khung chat. Đáp án là phân số thập phân, bộ chấm đòi đúng dạng.
- `STP-PH03-8/stem` = “Viết thành phân số thập phân: / 0,08 = ……” — Đề phiếu chỉ in phép viết, tiêu đề phiếu nói yêu cầu; ghi yêu cầu vào đề để bé đọc trong khung chat. Đáp án là phân số thập phân, bộ chấm đòi đúng dạng.
- `STP-PH04-1/stem` = “Điền dấu >, <, = thích hợp vào chỗ chấm: / 19,5 …… 19,376” — Đề phiếu chỉ in phép viết, tiêu đề phiếu nói yêu cầu; ghi yêu cầu vào đề để bé đọc trong khung chat.
- `STP-PH04-2/stem` = “Điền dấu >, <, = thích hợp vào chỗ chấm: / 6,44 …… 6,466” — Đề phiếu chỉ in phép viết, tiêu đề phiếu nói yêu cầu; ghi yêu cầu vào đề để bé đọc trong khung chat.
- `STP-PH04-3/stem` = “Điền dấu >, <, = thích hợp vào chỗ chấm: / 16,69 …… 16,069” — Đề phiếu chỉ in phép viết, tiêu đề phiếu nói yêu cầu; ghi yêu cầu vào đề để bé đọc trong khung chat.
- `STP-PH04-4/stem` = “Điền dấu >, <, = thích hợp vào chỗ chấm: / 2,6 …… 2,60” — Đề phiếu chỉ in phép viết, tiêu đề phiếu nói yêu cầu; ghi yêu cầu vào đề để bé đọc trong khung chat.
- `STP-PH04-5/stem` = “Điền dấu >, <, = thích hợp vào chỗ chấm: / 16,6 …… 16,60” — Đề phiếu chỉ in phép viết, tiêu đề phiếu nói yêu cầu; ghi yêu cầu vào đề để bé đọc trong khung chat.
- `STP-PH04-6/stem` = “Điền dấu >, <, = thích hợp vào chỗ chấm: / 20,63 …… 20,42” — Đề phiếu chỉ in phép viết, tiêu đề phiếu nói yêu cầu; ghi yêu cầu vào đề để bé đọc trong khung chat.
- `STP-PH04-7/stem` = “Điền dấu >, <, = thích hợp vào chỗ chấm: / 20,43 …… 20,09” — Đề phiếu chỉ in phép viết, tiêu đề phiếu nói yêu cầu; ghi yêu cầu vào đề để bé đọc trong khung chat.
- `STP-PH04-8/stem` = “Điền dấu >, <, = thích hợp vào chỗ chấm: / 20,5 …… 20,50” — Đề phiếu chỉ in phép viết, tiêu đề phiếu nói yêu cầu; ghi yêu cầu vào đề để bé đọc trong khung chat.
- `STP-PH08-8/stage` = “transfer” — Tài liệu tiết 8 không có bài toán thực tế; chọn câu đổi ngược chiều với cặp đơn vị chưa có trong ví dụ (cm² → mm²) làm câu chuyển giao gần.
- `STP-PH11-1/stem` = “Điền dấu >, <, = thích hợp vào chỗ chấm: / 3,849 …… 3,4” — Đề phiếu chỉ in phép viết, tiêu đề phiếu nói yêu cầu; ghi yêu cầu vào đề để bé đọc trong khung chat.
- `STP-PH11-2/stem` = “Điền dấu >, <, = thích hợp vào chỗ chấm: / 16,05 …… 16,467” — Đề phiếu chỉ in phép viết, tiêu đề phiếu nói yêu cầu; ghi yêu cầu vào đề để bé đọc trong khung chat.
- `STP-PH12-1/stem` = “Viết thành phân số thập phân: / 8,316 = ……” — Đề phiếu chỉ in phép viết, tiêu đề phiếu nói yêu cầu; ghi yêu cầu vào đề để bé đọc trong khung chat. Đáp án là phân số thập phân, bộ chấm đòi đúng dạng.

**Phần của tiết được soạn bổ sung hoặc sửa (51):**

- `STP-T01/pass_rule/min_forms` — DI-47: sau khi loại câu STP-BT-06 (hình 100 ô không mô tả), các câu còn lại đều chấm kiểu số (viết số thập phân / viết phân số thập phân, bộ chấm phân biệt hai dạng bằng NumericAnswer.form).
- `STP-T01/worked_examples/WE1/answer` — Đọc lại sau phiên học thử: ví dụ mẫu là hoạt động trong giáo án, không phải bài giải; thay bằng bài giải theo khung GHI NHỚ của tài liệu lý thuyết.
- `STP-T01/worked_examples/WE1/problem` — Đọc lại sau phiên học thử: ví dụ mẫu là hoạt động trong giáo án, không phải bài giải; thay bằng bài giải theo khung GHI NHỚ của tài liệu lý thuyết.
- `STP-T01/worked_examples/WE1/steps` — Đọc lại sau phiên học thử: ví dụ mẫu là hoạt động trong giáo án, không phải bài giải; thay bằng bài giải theo khung GHI NHỚ của tài liệu lý thuyết.
- `STP-T02/worked_examples/WE1/answer` — Đọc lại sau phiên học thử: ví dụ mẫu là hoạt động trong giáo án, không phải bài giải; thay bằng bài giải theo khung GHI NHỚ của tài liệu lý thuyết.
- `STP-T02/worked_examples/WE1/problem` — Đọc lại sau phiên học thử: ví dụ mẫu là hoạt động trong giáo án, không phải bài giải; thay bằng bài giải theo khung GHI NHỚ của tài liệu lý thuyết.
- `STP-T02/worked_examples/WE1/steps` — Đọc lại sau phiên học thử: ví dụ mẫu là hoạt động trong giáo án, không phải bài giải; thay bằng bài giải theo khung GHI NHỚ của tài liệu lý thuyết.
- `STP-T03/theory/T1/accept` — Phiên học thử: chính câu trả lời mẫu không khớp danh sách cách nói được chấp nhận (gia sư đáp 'Mình cùng xem lại nhé' cho câu đúng); thêm cách nói của câu trả lời mẫu.
- `STP-T03/theory/T2/accept` — Đọc lại sau phiên học thử: câu hỏi gợi mở chưa có câu trả lời mẫu, gia sư không đối chiếu được câu bé trả lời.
- `STP-T03/theory/T2/reply` — Đọc lại sau phiên học thử: câu hỏi gợi mở chưa có câu trả lời mẫu, gia sư không đối chiếu được câu bé trả lời.
- `STP-T03/worked_examples/WE1/answer` — Đọc lại sau phiên học thử: ví dụ mẫu là hoạt động trong giáo án, không phải bài giải; thay bằng bài giải theo khung GHI NHỚ của tài liệu lý thuyết.
- `STP-T03/worked_examples/WE1/problem` — Đọc lại sau phiên học thử: ví dụ mẫu là hoạt động trong giáo án, không phải bài giải; thay bằng bài giải theo khung GHI NHỚ của tài liệu lý thuyết.
- `STP-T03/worked_examples/WE1/steps` — Đọc lại sau phiên học thử: ví dụ mẫu là hoạt động trong giáo án, không phải bài giải; thay bằng bài giải theo khung GHI NHỚ của tài liệu lý thuyết.
- `STP-T04/explain/key_ideas` — Đọc lại sau phiên học thử: ý chính không phải là ý (câu hỏi hoặc chữ bị cắt); viết lại theo khung GHI NHỚ. Cũ: 'dễ nhầm'.
- `STP-T05/theory/T1/accept` — Phiên học thử: chính câu trả lời mẫu không khớp danh sách cách nói được chấp nhận (gia sư đáp 'Mình cùng xem lại nhé' cho câu đúng); thêm cách nói của câu trả lời mẫu.
- `STP-T05/theory/T2/accept` — Soạn bổ sung theo tài liệu lý thuyết/giáo án của tiết (validator đòi ≥ 2 cách giảng khác biểu diễn).
- `STP-T05/theory/T2/ask` — Soạn bổ sung theo tài liệu lý thuyết/giáo án của tiết (validator đòi ≥ 2 cách giảng khác biểu diễn).
- `STP-T05/theory/T2/reply` — Soạn bổ sung theo tài liệu lý thuyết/giáo án của tiết (validator đòi ≥ 2 cách giảng khác biểu diễn).
- `STP-T05/theory/T2/representation` — Soạn bổ sung theo tài liệu lý thuyết/giáo án của tiết (validator đòi ≥ 2 cách giảng khác biểu diễn). Giáo án tiết 5 chuẩn bị 'tia số dài'.
- `STP-T05/theory/T2/text` — Soạn bổ sung theo tài liệu lý thuyết/giáo án của tiết (validator đòi ≥ 2 cách giảng khác biểu diễn).
- `STP-T05/worked_examples/WE2/answer` — Đáp số của ví dụ trong tài liệu.
- `STP-T05/worked_examples/WE2/steps` — Ví dụ trong tài liệu viết gộp một bước; tách đúng nội dung đó thành 3 bước.
- `STP-T06/theory/T1/accept` — Đọc lại sau phiên học thử: câu trả lời mẫu sai (ghi 1,085 km cho 85 m).
- `STP-T06/theory/T1/reply` — Đọc lại sau phiên học thử: câu trả lời mẫu sai (ghi 1,085 km cho 85 m).
- `STP-T06/theory/T2/accept` — Soạn bổ sung theo tài liệu lý thuyết/giáo án của tiết (validator đòi ≥ 2 cách giảng khác biểu diễn).
- `STP-T06/theory/T2/ask` — Soạn bổ sung theo tài liệu lý thuyết/giáo án của tiết (validator đòi ≥ 2 cách giảng khác biểu diễn).
- `STP-T06/theory/T2/reply` — Soạn bổ sung theo tài liệu lý thuyết/giáo án của tiết (validator đòi ≥ 2 cách giảng khác biểu diễn).
- `STP-T06/theory/T2/representation` — Soạn bổ sung theo tài liệu lý thuyết/giáo án của tiết (validator đòi ≥ 2 cách giảng khác biểu diễn). Tài liệu lý thuyết có bảng đơn vị đo.
- `STP-T06/theory/T2/text` — Soạn bổ sung theo tài liệu lý thuyết/giáo án của tiết (validator đòi ≥ 2 cách giảng khác biểu diễn).
- `STP-T07/pass_rule/min_forms` — DI-47: mọi câu của tiết trong tài liệu cùng một dạng (viết số đo); không tự đặt câu ngoài tài liệu.
- `STP-T07/theory/T1/accept` — Đọc lại sau phiên học thử: câu hỏi gợi mở chưa có câu trả lời mẫu, gia sư không đối chiếu được câu bé trả lời.
- `STP-T07/theory/T1/reply` — Đọc lại sau phiên học thử: câu hỏi gợi mở chưa có câu trả lời mẫu, gia sư không đối chiếu được câu bé trả lời.
- `STP-T08/pass_rule/min_forms` — DI-47: mọi câu của tiết trong tài liệu cùng một dạng (viết số đo); không tự đặt câu ngoài tài liệu.
- `STP-T09/pass_rule/min_forms` — DI-47: sau khi loại câu STP-BT-30 (hình tia số), các câu còn lại của tiết đều cùng dạng làm tròn số.
- `STP-T09/theory/T2/accept` — Đọc lại sau phiên học thử: câu hỏi gợi mở chưa có câu trả lời mẫu, gia sư không đối chiếu được câu bé trả lời.
- `STP-T09/theory/T2/reply` — Đọc lại sau phiên học thử: câu hỏi gợi mở chưa có câu trả lời mẫu, gia sư không đối chiếu được câu bé trả lời.
- `STP-T09/worked_examples/WE1/answer` — Đọc lại sau phiên học thử: ví dụ mẫu là hoạt động trong giáo án, không phải bài giải; thay bằng bài giải theo khung GHI NHỚ của tài liệu lý thuyết.
- `STP-T09/worked_examples/WE1/problem` — Đọc lại sau phiên học thử: ví dụ mẫu là hoạt động trong giáo án, không phải bài giải; thay bằng bài giải theo khung GHI NHỚ của tài liệu lý thuyết.
- `STP-T09/worked_examples/WE1/steps` — Đọc lại sau phiên học thử: ví dụ mẫu là hoạt động trong giáo án, không phải bài giải; thay bằng bài giải theo khung GHI NHỚ của tài liệu lý thuyết.
- `STP-T10/theory/T1/reply` — Câu trả lời mẫu do AI soạn lập luận sai (dựa vào 9,96); viết lại theo quy tắc trong tài liệu.
- `STP-T10/theory/T2/accept` — Soạn bổ sung theo tài liệu lý thuyết/giáo án của tiết (validator đòi ≥ 2 cách giảng khác biểu diễn).
- `STP-T10/theory/T2/ask` — Soạn bổ sung theo tài liệu lý thuyết/giáo án của tiết (validator đòi ≥ 2 cách giảng khác biểu diễn).
- `STP-T10/theory/T2/reply` — Soạn bổ sung theo tài liệu lý thuyết/giáo án của tiết (validator đòi ≥ 2 cách giảng khác biểu diễn).
- `STP-T10/theory/T2/representation` — Soạn bổ sung theo tài liệu lý thuyết/giáo án của tiết (validator đòi ≥ 2 cách giảng khác biểu diễn).
- `STP-T10/theory/T2/text` — Soạn bổ sung theo tài liệu lý thuyết/giáo án của tiết (validator đòi ≥ 2 cách giảng khác biểu diễn).
- `STP-T10/worked_examples/WE1/answer` — Bảng trong tài liệu: 5,678 → 5,68.
- `STP-T10/worked_examples/WE1/problem` — Ví dụ lấy từ bảng trong quy tắc của tài liệu lý thuyết (5,678 → 5,68).
- `STP-T10/worked_examples/WE1/steps` — Theo 3 bước của quy tắc trong tài liệu.
- `STP-T11/explain/key_ideas` — Đọc lại sau phiên học thử: ý chính không phải là ý (câu hỏi hoặc chữ bị cắt); viết lại theo khung GHI NHỚ. Cũ: 'mình còn yếu mạch nào'.
- `STP-T11/method/rule` — Đọc lại sau phiên học thử: phương pháp chỉ có câu 'mình còn yếu mạch nào'; chép sơ đồ tóm tắt chương của tài liệu lý thuyết.
- `STP-T11/method/steps` — Đọc lại sau phiên học thử: sơ đồ tóm tắt chương của tài liệu lý thuyết.

**Gợi ý bị loại (50):**

- `STP-BT-13:H2` — Đọc lại sau phiên học thử: Hướng sai: so x với phần nguyên của 2,9 và 5,1 sẽ bỏ sót số 5. [Nội dung: Con nhớ rằng khi so sánh số thập phân, ta so sánh phần nguyên trước. Số tự nhiên x có phần nguyên là x. Con sẽ so sánh x với phần nguyên của hai số giới hạn, đúng không?]
- `STP-BT-13:H3` — Sai: bỏ mất số 5 (5 < 5,1) và nói 'phần nguyên' của số tự nhiên. [Nội dung: Con hãy liệt kê các số tự nhiên có phần nguyên lớn hơn 2 và nhỏ hơn 5?]
- `STP-BT-17c:H3` — Dùng phép chia cho 100 chưa học ở chương này. [Nội dung: Con có thể chia 45 dm² cho bao nhiêu để ra m²?]
- `STP-BT-17d:H3` — Dùng phép chia cho 100 chưa học ở chương này. [Nội dung: Con có thể đổi 8 cm² thành dm² bằng cách chia cho bao nhiêu?]
- `STP-BT-18b:H3` — Dùng phép chia số thập phân chưa học ở chương này. [Nội dung: Con thực hiện phép chia 7 cho 100, kết quả sẽ là bao nhiêu?]
- `STP-BT-24a:H3` — Cách làm sai (4,7 m = 470 cm, không phải thêm một chữ số vào 4,70). [Nội dung: Con có thể viết 4,7 m thành 4,70 m rồi thêm một chữ số, sẽ được bao nhiêu?]
- `STP-BT-24b:H3` — Cách làm sai (0,6 kg = 600 g, kg → g là 3 bước). [Nội dung: Con có thể viết 0,6 kg thành 0,60 kg rồi thêm một chữ số, sẽ được bao nhiêu?]
- `STP-BT-24c:H3` — Cách làm sai, gây rối. [Nội dung: Con có thể viết 3,05 m² thành 3,0500 m² rồi thêm hai chữ số, sẽ được bao nhiêu?]
- `STP-BT-24d:H2` — Sai chính tả thuật ngữ ('khoảng lượng') và nói 'thêm chữ số thập phân' khi đổi ra đơn vị bé. [Nội dung: Từ tấn sang kilogram, mỗi bước thêm một chữ số thập phân theo quy tắc độ dài/khoảng lượng, nhớ không?]
- `STP-BT-24d:H3` — Cách làm sai, gây rối. [Nội dung: Con có thể viết 2,5 tấn thành 2,5000 tấn rồi thêm ba chữ số, sẽ được bao nhiêu?]
- `STP-BT-25a:H3` — Gợi ý chứa luôn kết quả đổi (lộ đáp án). [Nội dung: Con có thể viết 2,5 m thành 250 cm rồi so sánh với 250 cm, dấu nào phù hợp?]
- `STP-BT-25b:H2` — Sai: kg → g là 3 bước, và số chữ số thập phân giảm chứ không tăng. [Nội dung: Theo quy tắc, chuyển kilogram sang gram bằng cách thêm một chữ số thập phân, con nhớ không?]
- `STP-BT-29:H1` — Đọc lại sau phiên học thử: Thuật ngữ 'bất đẳng thức' ngoài chương trình lớp 5. [Nội dung: Con cần tìm chữ số x lớn nhất để bất đẳng thức đúng. Con có thể so sánh từng chữ số của hai số thập phân không?]
- `STP-BT-34:H1` — Sai thuật ngữ: 'hàng mười' thay vì 'hàng phần mười'. [Nội dung: Cô muốn con viết độ dài 1 km 85 m dưới dạng km thập phân và làm tròn tới hàng mười?]
- `STP-PH01-1:H3` — Mơ hồ, dễ làm bé đặt dấu phẩy sai vị trí (49,0). [Nội dung: Con sẽ đặt dấu phẩy sau bao nhiêu chữ số khi viết 49/100 thành số thập phân?]
- `STP-PH01-2:H3` — Mơ hồ (như PH01-1). [Nội dung: Con sẽ đặt dấu phẩy sau bao nhiêu chữ số khi chuyển 7/10?]
- `STP-PH01-3:H3` — Mơ hồ (như PH01-1). [Nội dung: Con sẽ đặt dấu phẩy sau bao nhiêu chữ số khi viết 9/10?]
- `STP-PH01-7:H2` — Sai diễn đạt ('dạng 1/100') và chứa phần đáp án 0,99. [Nội dung: Cô nhớ rằng phân số 99/100 là dạng 1/100, viết thành 0,99 theo quy tắc các phân số thập phân, phải không?]
- `STP-PH01-7:H3` — Gần như đưa đáp án 16,99. [Nội dung: Con thử viết phần nguyên 16 và sau đó ghép phần thập phân 0,99 lại thành một số, con thấy thế nào?]
- `STP-PH01-8:H2` — Sai diễn đạt và chứa phần đáp án 0,796. [Nội dung: Nhắc lại, phân số 796/1000 là dạng 1/1000, viết là 0,796 theo quy tắc, đúng không?]
- `STP-PH01-8:H3` — Gần như đưa đáp án 12,796. [Nội dung: Con có thể ghép phần nguyên 12 với phần thập phân 0,796 để tạo số mới không?]
- `STP-PH02-1:H2` — Chữ số 4 trong 64,138 ở bên trái dấu phẩy; gợi ý hướng sai sang phần thập phân. [Nội dung: Con có biết hàng nào nằm ngay bên phải dấu phẩy trong số thập phân không?]
- `STP-PH02-1:H3` — Như H2: hướng bé đếm phần thập phân trong khi chữ số ở hàng đơn vị. [Nội dung: Con có thể đếm các chữ số bên phải dấu phẩy, rồi xem chữ số 4 nằm ở vị trí nào?]
- `STP-PH02-4:H2` — Bỏ sót hàng đơn vị ngay bên trái dấu phẩy, dễ làm bé nhầm hàng. [Nội dung: Con có nhớ các vị trí bên trái dấu phẩy là hàng chục, hàng trăm, … không?]
- `STP-PH02-6:H3` — Gợi ý chứa luôn đáp án 3,22. [Nội dung: Con hãy xác định chữ số nào ở hàng phần mười trong số 3,22 không?]
- `STP-PH02-7:H3` — Sai kiến thức: phần mười, phần trăm nằm sau dấu phẩy. [Nội dung: Con có thể viết số bao nhiêu đơn vị, mười và trăm trước dấu phẩy?]
- `STP-PH03-4:H2` — Gợi ý nói thẳng đáp án Đ/S (lộ đáp án). [Nội dung: Kiểm tra quy tắc: 17,9 và 17,90 có cùng giá trị vì 0 ở cuối, đúng không?]
- `STP-PH03-6:H3` — Gợi ý nói thẳng đáp án Đ/S (lộ đáp án). [Nội dung: Con có đồng ý rằng 17,5 và 17,50 có cùng giá trị?]
- `STP-PH05-5:H3` — Gợi ý chứa luôn đáp án (các số 2 đến 5). [Nội dung: Con sẽ xem các số nguyên từ 2 đến 5, sau đó kiểm tra xem chúng có nằm trong khoảng không, muốn thử không?]
- `STP-PH05-6:H3` — Gợi ý chứa luôn đáp án (các số 18 đến 21). [Nội dung: Con có thể bắt đầu bằng cách liệt kê các số nguyên từ 18 đến 21, sau đó kiểm tra chúng có nằm trong khoảng không, muốn thử không?]
- `STP-PH05-7:H2` — Đọc lại sau khi Qwen soạn lại (lô 6 câu có câu đổi): Diễn đạt khó hiểu ('tìm khoảng trống'). [Nội dung: Con nhớ lại quy tắc so sánh phần nguyên và phần thập phân để tìm khoảng trống nhé?]
- `STP-PH05-7:H3` — Đọc lại sau phiên học thử: Diễn đạt rối ('số giới hạn'), khó hiểu với bé. [Nội dung: Con hãy bắt đầu bằng cách viết ra các số tự nhiên gần với số giới hạn nhỏ hơn, rồi kiểm tra xem chúng có nhỏ hơn số giới hạn lớn hơn không nhé?]
- `STP-PH05-8:H1` — Đọc lại sau phiên học thử: Thuật ngữ 'số nguyên dương' ngoài chương trình lớp 5. [Nội dung: Con cần tìm các số tự nhiên x thỏa mãn điều kiện trong đề bài. Con có thể nghĩ đến các số nguyên dương gần với hai số đã cho không?]
- `STP-PH05-8:H3` — Đọc lại sau phiên học thử: Diễn đạt rối và dễ làm bé bỏ sót số 2. [Nội dung: Con hãy viết ra các số tự nhiên bắt đầu từ số nhỏ hơn phần nguyên của số giới hạn lớn hơn, rồi kiểm tra xem chúng có lớn hơn số giới hạn nhỏ hơn không nhé?]
- `STP-PH06-7:H2` — Sai chiều: đổi cm → mm thì dấu phẩy dời sang phải, số chữ số thập phân giảm. [Nội dung: Cô nhớ rằng 1 cm = 10 mm, theo quy tắc độ dài mỗi bước tăng 1 chữ số thập phân, phải không?]
- `STP-PH06-7:H3` — Mơ hồ, dễ làm bé viết 1,10. [Nội dung: Con thử viết 1,1 cm thành mm bằng cách thêm chữ số nhé?]
- `STP-PH06-8:H2` — Sai chiều (như PH06-7). [Nội dung: Theo quy tắc, 1 cm bằng 10 mm, mỗi bước tăng 1 chữ số thập phân, nhớ chưa?]
- `STP-PH06-8:H3` — Mơ hồ, dễ làm bé viết 8,80. [Nội dung: Con thử viết 8,8 cm thành mm bằng cách thêm chữ số nhé?]
- `STP-PH07-1:H2` — Sai kiến thức: 1 tạ = 100 kg. [Nội dung: Cô nhớ rằng 1 tạ = 10 kg, và cần ghi số thập phân với 2 chữ số, đúng không?]
- `STP-PH07-6:H2` — Sai kiến thức: 1 tạ = 100 kg. [Nội dung: Cô nhớ 1 tạ = 10 kg và kết quả sẽ có 2 chữ số thập phân, đúng không?]
- `STP-PH07-7:H2` — Sai chiều: đổi kg → g thì số chữ số thập phân giảm. [Nội dung: Quy tắc đổi khối lượng từ đơn vị lớn sang nhỏ là thêm bao nhiêu chữ số thập phân?]
- `STP-PH07-8:H2` — Sai chiều: đổi yến → kg thì số chữ số thập phân giảm. [Nội dung: Khi đổi từ đơn vị lớn sang nhỏ, mỗi bước ta thêm bao nhiêu chữ số thập phân?]
- `STP-PH08-1:H2` — Sai chiều: đổi về đơn vị lớn thì phần thập phân thêm 2 chữ số mỗi bước. [Nội dung: Khi đổi diện tích từ đơn vị nhỏ lên lớn, mỗi bước ta bớt 2 chữ số thập phân, đúng không?]
- `STP-PH08-2:H2` — Sai chiều (như PH08-1). [Nội dung: Khi đổi diện tích từ đơn vị nhỏ lên lớn, mỗi bước ta bớt 2 chữ số thập phân, đúng không?]
- `STP-PH08-3:H2` — Sai chiều (như PH08-1). [Nội dung: Khi đổi diện tích từ đơn vị nhỏ lên lớn, mỗi bước ta bớt 2 chữ số thập phân, đúng không?]
- `STP-PH08-4:H2` — Sai chiều: 2,2 m² = 220 dm², đổi ra đơn vị bé thì dấu phẩy dời sang phải. [Nội dung: Khi đổi diện tích từ đơn vị lớn xuống nhỏ, mỗi bước ta thêm 2 chữ số thập phân, đúng không?]
- `STP-PH08-5:H2` — Sai chiều (như PH08-4). [Nội dung: Khi đổi diện tích từ đơn vị lớn xuống nhỏ, mỗi bước ta thêm 2 chữ số thập phân, đúng không?]
- `STP-PH08-6:H2` — Sai chiều (như PH08-4). [Nội dung: Khi đổi diện tích từ đơn vị lớn xuống nhỏ, mỗi bước ta thêm 2 chữ số thập phân, đúng không?]
- `STP-PH08-8:H2` — Sai chiều (như PH08-4). [Nội dung: Cô nhớ rằng 1 cm² = 100 mm², mỗi bước chuyển đổi diện tích thêm 2 chữ số thập phân?]
- `STP-PH11-5:H3` — Câu sai tiếng Việt ('vị thập phân'), khó hiểu với bé. [Nội dung: Con sẽ xem chữ số ở vị thập phân thứ nhất của 21,57, con sẽ làm gì với nó?]

### Diện tích tam giác, hình thang (bản phát hành `tl-20261012142023`)

**Câu được sửa hoặc chuyển chặng (8):**

- `DTTGHT-BT-01/facts` = “{'order': ['nhọn', 'vuông', 'tù'], 'pairs': [['ngoài', '3']]}” — Đọc lại sau phiên học thử: tiêu chí chấm: đúng thứ tự nhọn – vuông – tù và nói hình 3 có đường cao nằm ngoài.
- `DTTGHT-BT-02/facts` = “{'phrases': [['đáy'], ['chiều cao']], 'numbers': [['2']]}” — Đọc lại sau phiên học thử: tiêu chí chấm: có 'đáy', 'chiều cao' và số 2.
- `DTTGHT-BT-05/facts` = “{'phrases': [['ah']], 'pairs': [['bé', 'ab'], ['lớn', 'dc']]}” — Đọc lại sau phiên học thử: tiêu chí chấm: đáy bé AB, đáy lớn DC, đường cao AH.
- `DTTGHT-BT-06/facts` = “{'phrases': [['đáy lớn'], ['đáy bé'], ['chiều cao']], 'numbers': [['2']]}” — Đọc lại sau phiên học thử: tiêu chí chấm: đáy lớn, đáy bé, chiều cao và số 2.
- `DTTGHT-BT-12a/facts` = “{'numbers': [['375', '3,75']]}” — Đọc lại sau phiên học thử: tiêu chí chấm: 375 (cm²) hoặc 3,75 (dm²) — đề không nói đơn vị kết quả.
- `DTTGHT-BT-12b/facts` = “{'numbers': [['4800', '48', '0,48']]}” — Đọc lại sau phiên học thử: tiêu chí chấm: 4800 cm², 48 dm² hoặc 0,48 m².
- `DTTGHT-BT-13/stage` = “transfer” — Tam giác vuông: bé phải tự nhận ra hai cạnh góc vuông là đáy và đường cao (câu hỏi gợi mở của giáo án tiết 3) — tình huống mới, dùng làm câu chuyển giao.
- `DTTGHT-BT-27b/stage` = “transfer” — Bài toán thực tế (thu hoạch thóc theo diện tích) có trong giáo án tiết 7: dùng làm câu chuyển giao.

**Phần của tiết được soạn bổ sung hoặc sửa (46):**

- `DTTGHT-T01/explain/key_ideas` — Đọc lại sau phiên học thử: ý chính không phải là ý (câu hỏi hoặc chữ bị cắt); viết lại theo khung GHI NHỚ. Cũ: 'Đường cao phải ... với đáy'.
- `DTTGHT-T01/method/rule` — Đọc lại sau phiên học thử: phương pháp bị cắt ('Đường cao phải ... với đáy'); chép định nghĩa của tài liệu lý thuyết.
- `DTTGHT-T01/method/steps` — Đọc lại sau phiên học thử: theo tài liệu lý thuyết và giáo án tiết 1.
- `DTTGHT-T01/worked_examples/WE1/answer` — Đọc lại sau phiên học thử: ví dụ mẫu là hoạt động trong giáo án, không phải bài giải; thay bằng bài giải theo khung GHI NHỚ của tài liệu lý thuyết.
- `DTTGHT-T01/worked_examples/WE1/problem` — Đọc lại sau phiên học thử: ví dụ mẫu là hoạt động trong giáo án, không phải bài giải; thay bằng bài giải theo khung GHI NHỚ của tài liệu lý thuyết.
- `DTTGHT-T01/worked_examples/WE1/steps` — Đọc lại sau phiên học thử: ví dụ mẫu là hoạt động trong giáo án, không phải bài giải; thay bằng bài giải theo khung GHI NHỚ của tài liệu lý thuyết. Tài liệu: trong tam giác vuông, cạnh góc vuông này là đường cao ứng với cạnh góc vuông kia.
- `DTTGHT-T02/worked_examples/WE1/answer` — Đọc lại sau phiên học thử: ví dụ mẫu là hoạt động trong giáo án, không phải bài giải; thay bằng bài giải theo khung GHI NHỚ của tài liệu lý thuyết.
- `DTTGHT-T02/worked_examples/WE1/problem` — Đọc lại sau phiên học thử: ví dụ mẫu là hoạt động trong giáo án, không phải bài giải; thay bằng bài giải theo khung GHI NHỚ của tài liệu lý thuyết. Số liệu lấy từ ví dụ của tài liệu.
- `DTTGHT-T02/worked_examples/WE1/steps` — Đọc lại sau phiên học thử: ví dụ mẫu là hoạt động trong giáo án, không phải bài giải; thay bằng bài giải theo khung GHI NHỚ của tài liệu lý thuyết.
- `DTTGHT-T03/explain/key_ideas` — Ý chính theo 5 bước của tài liệu.
- `DTTGHT-T03/method/rule` — Phương pháp chỉ có tên '5 bước…'; chép đủ 5 bước từ tài liệu lý thuyết (trang 5).
- `DTTGHT-T03/method/steps` — 5 bước trong tài liệu lý thuyết (trang 5).
- `DTTGHT-T03/theory/T2/accept` — Soạn bổ sung theo tài liệu lý thuyết/giáo án của tiết (validator đòi ≥ 2 cách giảng khác biểu diễn).
- `DTTGHT-T03/theory/T2/ask` — Soạn bổ sung theo tài liệu lý thuyết/giáo án của tiết (validator đòi ≥ 2 cách giảng khác biểu diễn).
- `DTTGHT-T03/theory/T2/reply` — Soạn bổ sung theo tài liệu lý thuyết/giáo án của tiết (validator đòi ≥ 2 cách giảng khác biểu diễn).
- `DTTGHT-T03/theory/T2/representation` — Soạn bổ sung theo tài liệu lý thuyết/giáo án của tiết (validator đòi ≥ 2 cách giảng khác biểu diễn). Tài liệu lý thuyết: tam giác bằng nửa hình chữ nhật chứa nó.
- `DTTGHT-T03/theory/T2/text` — Soạn bổ sung theo tài liệu lý thuyết/giáo án của tiết (validator đòi ≥ 2 cách giảng khác biểu diễn).
- `DTTGHT-T04/theory/T1/accept` — Đọc lại sau phiên học thử: câu hỏi gợi mở chưa có câu trả lời mẫu, gia sư không đối chiếu được câu bé trả lời.
- `DTTGHT-T04/theory/T1/reply` — Đọc lại sau phiên học thử: câu hỏi gợi mở chưa có câu trả lời mẫu, gia sư không đối chiếu được câu bé trả lời.
- `DTTGHT-T04/theory/T2/accept` — Đọc lại sau phiên học thử: câu trả lời mẫu lệch ý chính của bài (chung chiều cao).
- `DTTGHT-T04/theory/T2/reply` — Đọc lại sau phiên học thử: câu trả lời mẫu lệch ý chính của bài (chung chiều cao).
- `DTTGHT-T04/worked_examples/WE4/answer` — Đọc lại sau phiên học thử: ví dụ mẫu trùng số liệu với một câu bài tập/đề kiểm tra nên lộ đáp án; đổi số liệu, giữ cách giải của tài liệu.
- `DTTGHT-T04/worked_examples/WE4/problem` — Đọc lại sau phiên học thử: ví dụ mẫu trùng số liệu với một câu bài tập/đề kiểm tra nên lộ đáp án; đổi số liệu, giữ cách giải của tài liệu. (trùng câu DTTGHT-BT-14)
- `DTTGHT-T04/worked_examples/WE4/steps` — Đọc lại sau phiên học thử: ví dụ mẫu trùng số liệu với một câu bài tập/đề kiểm tra nên lộ đáp án; đổi số liệu, giữ cách giải của tài liệu.
- `DTTGHT-T04/worked_examples/WE5/answer` — Đọc lại sau phiên học thử: ví dụ mẫu trùng số liệu với một câu bài tập/đề kiểm tra nên lộ đáp án; đổi số liệu, giữ cách giải của tài liệu.
- `DTTGHT-T04/worked_examples/WE5/problem` — Đọc lại sau phiên học thử: ví dụ mẫu trùng số liệu với một câu bài tập/đề kiểm tra nên lộ đáp án; đổi số liệu, giữ cách giải của tài liệu. (trùng câu DTTGHT-BT-24; bản cũ còn dính mã LaTeX)
- `DTTGHT-T04/worked_examples/WE5/steps` — Đọc lại sau phiên học thử: ví dụ mẫu trùng số liệu với một câu bài tập/đề kiểm tra nên lộ đáp án; đổi số liệu, giữ cách giải của tài liệu.
- `DTTGHT-T05/method/rule` — Đọc lại sau phiên học thử: phương pháp của tiết nhận biết hình thang lại là công thức diện tích; chép định nghĩa của tài liệu lý thuyết.
- `DTTGHT-T05/method/steps` — Đọc lại sau phiên học thử: định nghĩa trong tài liệu lý thuyết.
- `DTTGHT-T05/theory/T2/accept` — Đọc lại sau phiên học thử: câu trả lời mẫu sai kiến thức.
- `DTTGHT-T05/theory/T2/reply` — Đọc lại sau phiên học thử: câu trả lời mẫu sai kiến thức ('một góc vuông'); tài liệu: hình thang vuông có hai góc vuông.
- `DTTGHT-T05/worked_examples/WE1/answer` — Đọc lại sau phiên học thử: ví dụ mẫu là hoạt động trong giáo án, không phải bài giải; thay bằng bài giải theo khung GHI NHỚ của tài liệu lý thuyết.
- `DTTGHT-T05/worked_examples/WE1/problem` — Đọc lại sau phiên học thử: ví dụ mẫu là hoạt động trong giáo án, không phải bài giải; thay bằng bài giải theo khung GHI NHỚ của tài liệu lý thuyết.
- `DTTGHT-T05/worked_examples/WE1/steps` — Đọc lại sau phiên học thử: ví dụ mẫu là hoạt động trong giáo án, không phải bài giải; thay bằng bài giải theo khung GHI NHỚ của tài liệu lý thuyết.
- `DTTGHT-T06/explain/key_ideas` — Đọc lại sau phiên học thử: ý chính không phải là ý (câu hỏi hoặc chữ bị cắt); viết lại theo khung GHI NHỚ. Cũ: 'Vì sao chia 2', 'vì sao cộng hai đáy'.
- `DTTGHT-T06/theory/T2/accept` — Đọc lại sau phiên học thử: bỏ cách nói 'chia đều', 'quy tắc nhân chia' (không đúng ý).
- `DTTGHT-T07/theory/T2/accept` — Soạn bổ sung theo tài liệu lý thuyết/giáo án của tiết (validator đòi ≥ 2 cách giảng khác biểu diễn).
- `DTTGHT-T07/theory/T2/ask` — Soạn bổ sung theo tài liệu lý thuyết/giáo án của tiết (validator đòi ≥ 2 cách giảng khác biểu diễn).
- `DTTGHT-T07/theory/T2/reply` — Soạn bổ sung theo tài liệu lý thuyết/giáo án của tiết (validator đòi ≥ 2 cách giảng khác biểu diễn).
- `DTTGHT-T07/theory/T2/representation` — Soạn bổ sung theo tài liệu lý thuyết/giáo án của tiết (validator đòi ≥ 2 cách giảng khác biểu diễn). Tài liệu lý thuyết: ghép hai hình giống nhau được hình bình hành.
- `DTTGHT-T07/theory/T2/text` — Soạn bổ sung theo tài liệu lý thuyết/giáo án của tiết (validator đòi ≥ 2 cách giảng khác biểu diễn).
- `DTTGHT-T08/theory/T2/accept` — Đọc lại sau phiên học thử: câu hỏi gợi mở chưa có câu trả lời mẫu, gia sư không đối chiếu được câu bé trả lời.
- `DTTGHT-T08/theory/T2/reply` — Đọc lại sau phiên học thử: câu hỏi gợi mở chưa có câu trả lời mẫu, gia sư không đối chiếu được câu bé trả lời.
- `DTTGHT-T08/worked_examples/WE2/answer` — Đọc lại sau phiên học thử: ví dụ mẫu trùng số liệu với một câu bài tập/đề kiểm tra nên lộ đáp án; đổi số liệu, giữ cách giải của tài liệu.
- `DTTGHT-T08/worked_examples/WE2/problem` — Đọc lại sau phiên học thử: ví dụ mẫu trùng số liệu với một câu bài tập/đề kiểm tra nên lộ đáp án; đổi số liệu, giữ cách giải của tài liệu. (bản cũ tính ra 18 = đáp án câu đề kiểm tra DTTGHT-DE2-6)
- `DTTGHT-T08/worked_examples/WE2/steps` — Đọc lại sau phiên học thử: ví dụ mẫu trùng số liệu với một câu bài tập/đề kiểm tra nên lộ đáp án; đổi số liệu, giữ cách giải của tài liệu.

**Gợi ý bị loại (31):**

- `DTTGHT-BT-01:H3` — Đọc lại sau khi Qwen soạn lại (lô 6 câu có câu đổi): Hướng sai: loại tam giác (nhọn, vuông, tù) xét theo góc, không theo chân đường cao. [Nội dung: Con hãy nhìn vào vị trí chân đường cao của từng hình để phân loại nhé?]
- `DTTGHT-BT-02:H2` — Lộ nội dung cần điền. [Nội dung: Con nhớ công thức S = a × h : 2 với a là đáy, h là chiều cao chưa?]
- `DTTGHT-BT-02:H3` — Đưa nguyên đáp án cần điền. [Nội dung: Con có thể viết “độ dài đáy” vào chỗ đầu, “chiều cao tương ứng” vào chỗ thứ hai, và “2” vào chỗ cuối không?]
- `DTTGHT-BT-06:H2` — Lộ nội dung cần điền. [Nội dung: Công thức cần điền là S = (a + b) × h : 2, trong đó a, b, h là các đại lượng đã học, nhớ không?]
- `DTTGHT-BT-06:H3` — Đưa nguyên đáp án cần điền. [Nội dung: Con có thể viết (đáy lớn + đáy bé) × chiều cao : 2 vào chỗ trống, muốn thử không?]
- `DTTGHT-BT-09a:H2` — Gợi ý nói thẳng đáp án Đ/S (lộ đáp án). [Nội dung: Đường cao phải vuông góc với đáy, câu a nói gì về điều này?]
- `DTTGHT-BT-09a:H3` — Đọc lại sau khi Qwen soạn lại (lô 6 câu có câu đổi): Gợi ý nhắc 'quy tắc đó' của bậc H2 đã bị loại: bé không biết quy tắc nào. [Nội dung: Con hãy kiểm tra xem câu a có khớp với quy tắc đó không?]
- `DTTGHT-BT-09b:H2` — Gợi ý không liên quan đến câu hỏi (nói về đường cao vuông góc với đáy). [Nội dung: Đường cao phải vuông góc với đáy, câu b liên quan tới đáy của hình thang, có đúng không?]
- `DTTGHT-BT-09c:H2` — Gợi ý không liên quan đến câu hỏi (nói về đường cao vuông góc với đáy). [Nội dung: Đường cao phải vuông góc với đáy, câu c nói về công thức diện tích, có liên quan không?]
- `DTTGHT-BT-09c:H3` — Gợi ý nói thẳng đáp án Đ/S (lộ đáp án). [Nội dung: Con có nhớ công thức tính diện tích tam giác cần chia cho 2 không?]
- `DTTGHT-BT-12a:H3` — Đọc lại sau khi Qwen soạn lại (lô 6 câu có câu đổi): Gợi ý bỏ mất bước 'chia 2', dẫn bé tới kết quả sai. [Nội dung: Con có thể bắt đầu đổi đáy 3 dm sang cm trước, rồi mới nhân với chiều cao 25 cm, được không?]
- `DTTGHT-BT-12b:H3` — Đọc lại sau khi Qwen soạn lại (lô 6 câu có câu đổi): Gợi ý bỏ mất bước 'chia 2', dẫn bé tới kết quả sai. [Nội dung: Con thử đổi đáy 1,2 m thành cm rồi mới nhân với chiều cao 80 cm, được không?]
- `DTTGHT-BT-17a:H3` — Gợi ý bỏ mất bước 'chia 2', dẫn bé tới kết quả sai. [Nội dung: Con có thể cộng 4,5 cm và 2,5 cm rồi nhân với 3 cm không?]
- `DTTGHT-BT-17b:H3` — Gợi ý bỏ mất bước 'chia 2', dẫn bé tới kết quả sai. [Nội dung: Con thử cộng 1,2 m và 0,8 m rồi nhân với 0,6 m nhé?]
- `DTTGHT-BT-17c:H3` — Gợi ý bỏ mất bước 'chia 2', dẫn bé tới kết quả sai. [Nội dung: Con có thể cộng 6,4 cm và 3,6 cm rồi nhân với 5 cm không?]
- `DTTGHT-BT-17d:H3` — Gợi ý bỏ mất bước 'chia 2', dẫn bé tới kết quả sai. [Nội dung: Con thử cộng 7 dm và 3,5 dm rồi nhân với 4 dm nhé?]
- `DTTGHT-BT-18:H3` — Đọc lại sau khi Qwen soạn lại (lô 6 câu có câu đổi): Gợi ý bỏ mất bước 'chia 2', dẫn bé tới kết quả sai. [Nội dung: Con hãy cộng hai đáy lại với nhau trước, rồi nhân với chiều cao nhé?]
- `DTTGHT-BT-22:H3` — Đọc lại sau khi Qwen soạn lại (lô 6 câu có câu đổi): Gợi ý bỏ mất bước 'chia 2', dẫn bé tới kết quả sai. [Nội dung: Con hãy cộng hai đáy lại với nhau trước, rồi nhân với chiều cao nhé?]
- `DTTGHT-BT-27a:H3` — Đọc lại sau khi Qwen soạn lại (lô 6 câu có câu đổi): Gợi ý bỏ mất bước 'chia 2', dẫn bé tới kết quả sai. [Nội dung: Con hãy cộng hai đáy lại với nhau trước, rồi nhân với chiều cao nhé?]
- `DTTGHT-BT-30b:H3` — Sai: (18 + 12) × 2 : 2 đã là phần tăng thêm, cộng vào diện tích cũ ra 180 chứ không phải phần tăng. [Nội dung: Con hãy tính (18 + 12) × 2 ÷ 2 rồi cộng vào diện tích cũ để biết tăng bao nhiêu?]
- `DTTGHT-PH01-7:H2` — Gợi ý không liên quan đến câu hỏi (nói về đường cao vuông góc với đáy). [Nội dung: Đường cao phải vuông góc với đáy, con có nhớ không?]
- `DTTGHT-PH01-8:H3` — Đọc lại sau khi Qwen soạn lại (lô 6 câu có câu đổi): Gợi ý gần như nói thẳng đáp án Đ. [Nội dung: Con hãy liên hệ xem ê-ke có giúp vẽ đường cao chính xác không?]
- `DTTGHT-PH05-1:H2` — Gợi ý nói thẳng đáp án Đ/S (lộ đáp án). [Nội dung: Cô nhắc rằng trong hình thang, hai cạnh đối song song nhau được gọi là đáy, đúng không?]
- `DTTGHT-PH05-2:H2` — Gợi ý nói thẳng đáp án Đ/S (lộ đáp án). [Nội dung: Cô nhắc rằng đáy luôn song song, vì vậy chúng không thể vuông góc, con có đồng ý không?]
- `DTTGHT-PH05-3:H2` — Gợi ý nói thẳng đáp án Đ/S (lộ đáp án). [Nội dung: Cô nhắc rằng trong hình thang vuông, có hai góc vuông nằm ở cùng một đáy, con nhớ không?]
- `DTTGHT-PH05-4:H2` — Gợi ý nói thẳng đáp án Đ/S (lộ đáp án). [Nội dung: Cô nhắc rằng chiều cao luôn vuông góc với hai đáy, không phải bất kỳ cạnh nào, con hiểu chứ?]
- `DTTGHT-PH05-5:H1` — Sai: câu hỏi nói về mọi hình thang, không riêng hình thang vuông. [Nội dung: Cô muốn con biết đường cao của hình thang vuông có tính chất gì, con có nhận ra không?]
- `DTTGHT-PH05-5:H2` — Gợi ý nói thẳng đáp án Đ/S (lộ đáp án). [Nội dung: Cô nhắc rằng trong hình thang vuông, đường cao luôn vuông góc với cả hai đáy, đúng không?]
- `DTTGHT-PH05-6:H2` — Gợi ý nói thẳng đáp án Đ/S (lộ đáp án). [Nội dung: Cô nhắc rằng đáy lớn là cạnh có độ dài lớn hơn so với đáy bé, con nhớ không?]
- `DTTGHT-PH07-7:H3` — Gợi ý bỏ mất bước 'chia 2', dẫn bé tới kết quả sai. [Nội dung: Con có thể cộng đáy lớn 14 cm và đáy bé 7 cm trước, rồi nhân với chiều cao 8 cm được không?]
- `DTTGHT-PH07-8:H3` — Gợi ý bỏ mất bước 'chia 2', dẫn bé tới kết quả sai. [Nội dung: Con thử cộng đáy lớn 11 cm và đáy bé 4 cm rồi nhân với chiều cao 4 cm nhé?]

**Chưa duyệt, không dạy (4):**

- `DTTGHT-BT-10a` — không tiết nào trong giáo án dùng câu này
- `DTTGHT-BT-10b` — không tiết nào trong giáo án dùng câu này
- `DTTGHT-BT-10c` — không tiết nào trong giáo án dùng câu này
- `DTTGHT-BT-23` — không tiết nào trong giáo án dùng câu này

## 6. Phần chưa duyệt và giới hạn (nói thẳng)

- **Câu bị loại vì chưa chấm tự động được:** STP-BT-14 (đáp án mở bất kỳ) và STP-BT-28 (thứ tự số đo nhiều đơn vị). Hai câu này vẫn nằm trong tài liệu và có thể dạy lại khi có cách chấm.
- **Câu không dạy, chưa duyệt:** 4 câu hình học (DTTGHT-BT-10a/b/c, BT-23) không tiết nào trong giáo án dùng nên không vào phương án. Chủ dự án có thể gắn chúng vào một tiết sau.
- **Bản nháp AI bị chặn tự động:** 410 bản nháp (theo lần soạn cuối) (gợi ý, câu trả lời mẫu, cách nói, ý chính) bị bộ kiểm chặn trước khi tới bước duyệt. Chúng không được dạy và Claude không đọc từng bản. Lý do chặn được thống kê trong `evals/reports/2026-10-12-drafting.md`.
- **Đề kiểm tra cuối chương:** 79 câu đã được đọc và duyệt. Đáp án đề kiểm tra không bao giờ vào prompt (CLAUDE.md quy tắc 2).
- **Giới hạn của việc Claude duyệt:**
  - Claude là model AI, không phải giáo viên đứng lớp.
  - Claude đọc chữ do máy đọc từ PDF, không xem hình.
  - Các câu dựa vào hình được giữ khi đề có mô tả hình bằng chữ (`[Hình: …]`) đủ số đo, và bị loại khi không có.
  - Phần Claude soạn bổ sung (mục 5) là nội dung sư phạm mới. Chủ dự án nên đọc lại phần này trước khi dùng với học sinh thật.
- **Phiên học thử:** kết quả ở `evals/reports/2026-10-12-trial-sessions.md`. Lần chạy cuối, 4 kiểu học sinh giả lập học hết 11/11 tiết Số thập phân và 8/8 tiết Diện tích. Không gợi ý bị loại nào hiện ra, và không câu sai dạng nào được chấm đúng.
