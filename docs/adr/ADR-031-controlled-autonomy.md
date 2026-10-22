# ADR-031: Qwen chọn nước đi trong giới hạn của chính sách (AUTO-1)

**Trạng thái:** Đề xuất, 2026-10-19.
- Chủ dự án yêu cầu làm bước "Qwen tự chủ có kiểm soát" mà ADR-022 gọi là CTX-2 (2026-10-19). Mã CTX-2 đã dùng cho bộ điều phối hội thoại (ADR-028), nên việc này mang mã **AUTO-1**.
- Chủ dự án chờ duyệt: DI-62 (tập nước đi được phép), prompt chọn nước đi (`CHOOSE_SYSTEM`).
- Code:
  - tập nước đi và bước kiểm lại: `tutor/policy.py` (`options`, `accept`);
  - Qwen chọn: `tutor/chooser.py` (`ModelChooser`, `RecordedChooser`);
  - nối vào vòng làm bài: `tutor/item_loop.py` (`_chosen`), `teaching/loop.py`, `session/chapter_service.py`, `session/api.py`.
- Liên quan: ADR-017 (Qwen bám câu mẫu), ADR-022 (gia sư theo ngữ cảnh), DI-61 (dành lượt gọi Qwen).

## Bối cảnh

Đến CTX-1, Qwen có hai việc:
- **đọc** câu khó hiểu của con (đề xuất nhãn);
- **nói** nước đi mà chính sách đã chọn.

Chính sách vẫn chọn **mọi** nước đi. Ở nhiều lượt, nhiều nước đi đều hợp sư phạm:
- câu sai đầu tiên: hỏi "con làm thế nào?" hoặc gợi ý bậc 1;
- con hỏi nghĩa một từ: giải thích từ đó, hoặc đưa thẳng gợi ý cùng bậc.

Luật cứng chọn giống nhau cho mọi đứa trẻ. Một cô giáo nhìn câu con vừa gõ thì có thể chọn khác. ADR-022 gọi bước tiếp theo là: chính sách đưa ra các nước đi được phép kèm giới hạn, Qwen chọn một nước và nói lý do, chính sách kiểm lại và có quyền chặn.

## Quyết định

1. **Chính sách đưa ra tập nước đi được phép** (`policy.options`, DI-62).
   - Phương án `A` luôn là nước của chính sách. Có tối đa 3 phương án.
   - **Không phương án nào giúp nhiều hơn nước của chính sách:** cùng bậc gợi ý hoặc thấp hơn. Không bao giờ có lời giải mẫu (H6) hay lời giải đầy đủ (H7). Không vượt bậc cao nhất của câu bài tập.
   - **Lượt nào không có lựa chọn** (tập rỗng):
     - bài kiểm tra cuối bài (`EXIT_ASSESSMENT`);
     - nước đi kết thúc câu (đúng, đóng câu), trừ một trường hợp (AUTO-5, 2026-10-22): con trả lời đúng, câu không bị lấy mẫu để hỏi "vì sao" (R-VERIFY), chưa hỏi "vì sao", chưa xem lời giải mẫu, không phải bài kiểm tra. Khi đó phương án `B` là hỏi "vì sao" rồi mới sang câu. Hỏi "vì sao" không giúp gì thêm, và câu đóng sau lời giải thích của con với cùng mức hoàn thành;
     - các luật cố định: hết giờ (R-TIME), bế tắc (R-FRUSTRATION), lời giải đầy đủ (R-FULL), hỏi hai nguyên nhân (R-PROBE-CAUSE), trần gợi ý của bài kiểm tra, lỗi tính nhầm (R-SLIP), "vì sao" trước gợi ý (R-STRONG-PRIOR), giảm bậc (R-DEESCALATE), hết lượt;
     - lượt không phải con trả lời (bắt đầu câu, im lặng).
2. **Qwen chọn một phương án và nói lý do** (`chooser.ModelChooser`).
   - Model class `LIGHTWEIGHT`, JSON chặt, `choice` là enum đúng các mã của tập.
   - Qwen thấy đề bài, lời cô vừa nói, lời con vừa gõ và mô tả từng phương án bằng lời của cô giáo. Qwen **không** thấy đáp án (quy tắc 2).
   - Lý do (một câu) để giáo viên đọc trong tab Hội thoại.
3. **Chính sách kiểm lại** (`policy.accept`).
   - Chỉ phương án có trong tập mới được chơi. Phương án khác `A` mang luật `R-CHOICE` và mã `MODEL_CHOICE` trong `POLICY_DECISION`.
   - Mã ngoài tập thì chính sách giữ nước của mình và ghi `accepted: false`.
   - Lời nói ra vẫn qua đủ bộ kiểm chứng như mọi nước đi: lộ đáp án, một câu hỏi, độ dài, căn cứ, an toàn.
4. **Ghi lại và phát lại.**
   - Mỗi lần chọn ghi sự kiện `MOVE_CHOSEN`: các nước được đưa ra, mã được chọn, nước đã chơi, lý do, có được nhận không.
   - Dựng lại buổi học từ sự kiện thì đọc bản ghi (`RecordedChooser`), không gọi model lần nữa. Vì chính sách tất định, tập nước đi khi phát lại giống hệt lúc chạy, nên cùng mã cho cùng nước đi.
   - Mastery và đánh giá vẫn là projection tất định từ sự kiện (quy tắc 3). Qwen không ghi điểm.
5. **Hạn mức** (DI-62).
   - Bộ chọn chỉ tiêu lượt gọi trong **nửa đầu** trần của buổi (7 trên 15). Nửa sau dành cho việc diễn đạt các nước đi quan trọng (DI-61).
   - Hết hạn mức, model hỏng hoặc trả JSON sai thì chính sách giữ nước của mình. Không có sự kiện nào được ghi.
   - Chỉ bật khi gia sư dùng Qwen (`TUTOR_RENDERER=llm`). `TUTOR_CHOOSER=policy` tắt riêng bộ chọn, để so sánh có và không có nó.

## Vì sao không cho Qwen tự chủ hơn

Nếu để Qwen tự quyết cả việc nói đáp án, lên bậc gợi ý cao hơn hay tự ghi điểm thì phải đổi quy tắc 1–3 của dự án. ADR-022 đã ghi: việc đó cần một ADR riêng do chủ dự án quyết. AUTO-1 giữ nguyên các quy tắc đó:
- quy tắc 1: chính sách quyết định những nước nào được phép, và kiểm lại nước được chọn;
- quy tắc 2: Qwen không thấy đáp án; `MathChecker` chấm;
- quy tắc 3: mastery vẫn là projection tất định, phát lại được.

## Hệ quả

- **Giáo viên:** tab Hội thoại có chip "Qwen chọn nước này: [lý do]", rê chuột thấy các nước chính sách cho phép.
- **Chi phí:** tối đa 1 lần gọi `LIGHTWEIGHT` (prompt khoảng 400 token) ở mỗi lượt có lựa chọn, trong nửa đầu trần.
- **Đo lường:**
  - Offline: 16 test (`tests/test_move_chooser.py`). Có một lưới 1.728 tổ hợp trạng thái chứng minh không phương án nào giúp nhiều hơn chính sách, và có test phát lại.
  - Chạy thật: `simulate_learner.py --measure` in số lần chọn theo dạng "nước của chính sách → nước đã chơi" và lý do. Lần đầu (1 buổi Số thập phân, 2026-10-19): Qwen chọn ở 2 lượt, cả 2 trong tập; chi tiết ở mục DI-62 của kế hoạch.
- **Chưa đo:** AUTO-1 có giúp trẻ học tốt hơn không. Việc đó cần so sánh trên học sinh (thật hoặc mô phỏng) với `TUTOR_CHOOSER=policy`, và chưa làm.
