# Vương học lại hai chương với bản mới (2026-10-13)

Lệnh `scripts/simulate_learner.py --write-at-end` chạy trên `cavat_dev`, tài khoản Vương. Gia sư dùng Qwen, tối đa 15 lần gọi model mỗi buổi; cả ba buổi đều dùng hết 15 lần, nên phần lớn lời gia sư là câu mẫu đã duyệt.

Bản mới gồm:
- DI-52: hỏi lại bài đã học;
- DI-53: nhắc bài gốc khi làm sai;
- DI-54: nhận ra lỗi sai trong tài liệu;
- DI-55: chấm "vì sao";
- DI-56: làm lại câu bù dạng.

Học sinh giả lập khi sai thì phần lớn sai đúng kiểu tài liệu nêu, và khi chưa hiểu thì trả lời "vì sao" chung chung trước.

## Kết quả

| | Số thập phân | Diện tích tam giác, hình thang |
|---|---|---|
| Buổi | 2 buổi. Buổi 1 bị cắt ngang vì mạng, chạy tiếp thì dừng ở 4/11; buổi 2 qua hết | 1 buổi |
| Tiết qua | 11/11 | 8/8 |
| Điểm chương lúc đầu → cuối (buổi cuối) | 5,6 → 85,6 | 7,7 → 87,9 |
| Câu đã giải quyết (tự làm / có gợi ý / làm mẫu / chưa giải quyết) | 17 / 14 / 1 / 1 (buổi 2) | 42 / 12 / 3 / 1 |
| Hỏi lại bài cũ: nhớ được / tổng số lần hỏi (DI-52) | 4/6 | 7/9 |
| Nhắc bài gốc sau lần sai đầu (DI-53) | 7 | 10 |
| "Vì sao" chung chung được hỏi lại (DI-55) | 4 | 4 |
| Câu "vì sao" theo điểm (0,2 / 0,6 / 1,0) | 4 / 13 / 1 | 4 / 21 / 0 |
| Lỗi sai nhận ra (DI-54) | STP-T01-M2 ×5, STP-T07-M2 ×1, STP-T09-M1 ×2 | DTTGHT-T07-M1 ×1 |
| Làm lại câu bù dạng (DI-56) | 0 | 2 |
| Teencode / emoji / dồn từ khóa / gỡ bế tắc | 31 / 28 / 4 / 6 | 26 / 11 / 5 / 3 |

## Sự cố trong lúc chạy và cách xử lý

1. **Học sinh giả lập trả lời phần nhớ lại bằng bài mới vừa vào.** Script lấy độ hiểu của bài mới (còn thấp) khi được hỏi lại bài cũ, nên lần nhớ lại nào cũng trượt. Lần chạy đó đã được chuyển sang `*_archive`, script đã sửa.
2. **Mạng tới Atlas bị đứt** (DNS), rồi chậm còn khoảng 0,08 MB/giây.
   - Lúc đó lộ ra một lỗi hiệu năng thật: mỗi request đọc lại toàn bộ phương án dạy (2,78 MB), vì bộ nhớ đệm dùng `id(database)`. Đã sửa: khóa theo client và tên database, có test.
   - Script có thêm `--resume`, tự thử lại khi mạng lỗi, và `--write-at-end`: chạy trong bộ nhớ rồi ghi mỗi buổi một lần.
3. **Hai chỗ chặn qua tiết** (DI-56):
   - luật bù dạng câu bị tắt khi gia sư đang theo dõi một lỗi sai;
   - tiết có đúng một câu khác dạng thì không qua được nếu bé sai câu đó.

## Dữ liệu đã chuyển sang archive (khôi phục được)

| Buổi | Lý do |
|---|---|
| `01a130cd-…`, `01a130e2-…` | Lần chạy ngày 12/10, trước bản mới |
| `01a13486-…`, `01a13489-…` | Học sinh giả lập trả lời sai phần nhớ lại |

Buổi `01a114ff-…` là buổi chủ dự án tự học, không bị động tới.
