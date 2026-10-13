# Học sinh Vương học thử hai chương, từ chưa hiểu đến hiểu (2026-10-12/13)

## Bối cảnh

Chủ dự án yêu cầu cho tài khoản học sinh **Vuong** học hết các tình huống: từ chỗ không hiểu nhiều, gia sư giảng tới khi hiểu thì thôi. Số liệu được thu lại để trang giáo viên hiển thị bằng biểu đồ và bản đồ nhiệt.

Cách chạy: `scripts/simulate_learner.py --write`.

- Script đi qua **API buổi học thật**, cùng đường xử lý với web, ghi vào `cavat_dev`. Gia sư dùng Qwen như bản demo, tối đa 15 lần gọi model mỗi buổi, quá thì dùng câu mẫu.
- Danh tính Vương được gắn ở tầng máy chủ. Không dùng PIN.
- CLAUDE.md quy tắc 11 không cho script ghi vào `cavat_dev`. Lần này chạy vì chủ dự án yêu cầu trực tiếp. Các buổi do script tạo được liệt kê ở mục 6 để tách riêng được.

## 1. Học sinh giả lập "Vương"

- **Điểm xuất phát:** độ hiểu mỗi bài bắt đầu ở 0,12.
- **Hiểu dần:** độ hiểu tăng theo việc gia sư làm (gợi ý, làm mẫu, giảng lại, nhận xét câu sai). Khi chưa hiểu, Vương trả lời sai theo kiểu trẻ hay sai:
  - dời dấu phẩy;
  - đảo dấu so sánh;
  - liệt kê thiếu;
  - viết sai dạng (0,475 cho câu đòi phân số thập phân).
- **Tình huống xen kẽ** (mỗi bài một vài lần, chọn ngẫu nhiên có seed):
  - teencode ("ko bít lm j", "kbt", "hk hiu");
  - emoji, chữ kéo dài ("đúnggggg"), chữ o thay số 0;
  - dồn từ khóa ("phân số thập phân mẫu số tử số phần mười phần trăm");
  - tin rất dài, câu trả lời ở cuối;
  - hỏi nghĩa một từ, hỏi về bài trong lúc giảng (RAG);
  - than chán ("khó wá con hk làm đc đâu 😭"), nói chuyện ngoài bài;
  - bấm "xin gợi ý", kể lại sai trước rồi đúng sau.

## 2. Kết quả

| | Số thập phân | Diện tích tam giác, hình thang |
|---|---|---|
| Buổi học | 1 buổi, 189 lượt | 1 buổi, 162 lượt |
| Bài qua | 11/11 | 8/8 |
| Điểm hiểu bài tổng (M) | 91,2, mức 5 | 85,6, mức 4 |
| Điểm chương lúc đầu → cuối | 5,6 → 91,2 | 7,7 → 85,6 |
| Câu đã làm | 64 | 54 |
| Tự làm được / nhờ gợi ý / cần làm mẫu / chưa giải quyết | 38 / 23 / 2 / 1 | 29 / 24 / 1 / 0 |
| Gợi ý đã nhận | 41 | 36 |
| Tin nhắn của Vương | 203 | 159 |

Riêng chương Số thập phân, bảng giáo viên còn cộng thêm buổi học cũ chủ dự án tự làm trên bản 0.1.1, nên trang giáo viên ghi "2 buổi".

Điểm mỗi bài lúc qua (Số thập phân) dao động từ 80,5 (STP-T01, bài đầu, Vương cần 8 gợi ý) đến 96,7. Bài đầu luôn là bài khó nhất với Vương: độ hiểu xuất phát thấp, chưa có gợi ý nào giúp.

## 3. Tình huống trong hội thoại (bộ điều phối và ý định)

| | Số thập phân | Diện tích |
|---|---|---|
| Teencode | 26 | 25 |
| Emoji | 20 | 18 |
| Chữ kéo dài | 9 | 4 |
| Dồn từ khóa | 6 | 6 |
| Gia sư tự gợi ý thay vì lặp lại (UNSTICK) | 4 | 4 |
| Xin giúp, không biết | 8 | 6 |
| Lạc đề | 6 | 6 |
| Than chán, tự chê | 5 | 3 |
| Hỏi nghĩa một từ | 5 | 4 |
| Câu hỏi về bài (RAG): được trả lời / gác lại cho cô | 0 / 2 | 1 / 1 |

## 4. Lỗi tìm ra trong lúc chạy và đã sửa

1. **Bế tắc ở bước kể lại.** Vương kể lại "bỏ số 0 ở giữa thì không". Câu kết thúc bằng "không" nên bị coi là câu hỏi, và gia sư đáp "Cô ghi lại các câu con hỏi…" hơn 200 lần liên tiếp. Đã sửa ở hai chỗ:
   - câu phủ định ở cuối là câu kể (`student-intent/0.2.0`);
   - sau hai lần gia sư đáp hoặc nhắc lại, tin tiếp theo được đọc là câu trả lời (ADR-028).
2. **Gỡ bế tắc nhầm.** Câu khen "Đúng rồi! … sang câu tiếp theo" lặp lại ở câu mới, nhưng bộ điều phối (bản đầu) coi đó là gia sư lặp lại và đưa gợi ý cho câu mới khi bé chưa làm gì. Lần chạy đầu bị lỗi này: 18 lần "gỡ bế tắc", phần lớn là sai.
   - Hai buổi của lần chạy đó **đã được chuyển sang** `learning_sessions_archive` và `events_archive`: 2 buổi, 1.276 sự kiện. Chúng không bị xóa hẳn và khôi phục được.
   - Lần chạy lại chỉ còn 4 lần gỡ bế tắc mỗi chương, đều đúng chỗ.
3. **Teencode lọt vào truy vấn RAG.** Truy vấn từng dùng nguyên câu teencode ("phần thập phân là **j** vậy cô?"). Giờ truy vấn được giải mã teencode trước, còn lời của bé vẫn gửi Qwen nguyên văn.
4. **Lời đáp sai sự thật khi gác câu hỏi.** Khi không tìm được câu trả lời chắc chắn, gia sư từng nói "Câu này nằm ngoài bài mình đang học", trong khi câu hỏi là về chính chương. Câu mẫu đã sửa (`teaching-templates/0.3.1`).

## 5. Giới hạn (nói thẳng)

- **RAG theo phạm vi bài chưa trả lời được câu hỏi định nghĩa về bài trước.** Vương hỏi "phần thập phân là gì" khi đang học bài sắp xếp (STP-T05), nhưng định nghĩa nằm ở STP-T02. Đoạn truy xuất là của T05/T04, không có định nghĩa, nên câu hỏi bị gác cho cô. "Đường cao là gì" ở DTTGHT-T03 cũng vậy (định nghĩa ở T01; độ tương đồng 0,63, dưới ngưỡng 0,65).
  - Đề xuất task sau: truy xuất theo ý định "X là gì", ưu tiên bài tiên quyết định nghĩa X, kèm bộ câu hỏi giữ riêng cho `make eval-rag`.
- **Không ghi nhận lỗi sai (misconception) nào.** Phương án dựng từ tài liệu chưa gắn đáp án sai điển hình với lỗi sai. Vì vậy biểu đồ lỗi sai trống, dù Vương trả lời sai nhiều lần.
- **Bước "vì sao" chấp nhận câu chung chung.** Câu "Vì con làm theo quy tắc cô dạy" vẫn được nhận.
- **Học sinh giả lập trả lời bằng chính đáp án và ý chính của giáo viên** khi đã hiểu. Số liệu cho thấy luồng dạy và cách chấm, không đo hiệu quả với trẻ thật.
- **Hai buổi học diễn ra trong vài chục phút của một ngày,** nên đường "tiến bộ theo ngày" chỉ có một điểm. Biểu đồ mới "Từ chưa hiểu đến hiểu" vẽ theo từng bằng chứng.

## 6. Các buổi do script tạo trên tài khoản Vương

| Chương | Mã buổi | Lượt | Kết quả |
|---|---|---|---|
| Số thập phân | `01a130cd-c69b-703c-9949-d117718fc820` | 189 | COMPLETED, 11/11 |
| Diện tích tam giác, hình thang | `01a130e2-5468-76c3-a447-66faf1ec3df9` | 162 | COMPLETED, 8/8 |

- Buổi `01a114ff-678d-7282-a7a0-ce77c4fafcb9` là buổi chủ dự án tự học trước đó (bản 0.1.1). Em không đụng tới.
- Danh sách cũng được ghi ở `var/storage/reports/simulated-sessions.json`.
