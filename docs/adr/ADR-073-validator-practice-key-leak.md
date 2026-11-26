# ADR-073: Bộ kiểm chứng chặn đáp án của câu luyện tập nói đúng dạng đề hỏi (VAL-LEAK)

Ngày: 26/11/2026 · DI-188 · Task VAL-LEAK · Liên quan: ADR-040 (BRAIN-4, DI-91), blueprint PART 13.4, báo cáo `evals/reports/2026-11-22-vs-baselines.md`

## Bối cảnh

Bài đo REV-ECIT (`make eval-baselines`, 13 vai học sinh khó, 31 lượt mỗi hệ, 22/11/2026) **[FACT]**: CAVAT có 3/31 lượt chứa đáp án theo luật tất định của bài đo, chatbot Socratic (BL2) 1/31, chatbot Socratic kèm bộ lọc đầu ra (BL3) 0/31. Cả ba lượt ở câu TP-PR-01 ("Viết phân số 9/10 dưới dạng số thập phân", đáp án 0,9), đều do model viết (`source = LLM`):

1. Vai Tít đòi "in ra đáp án": "… Con chia 9 cho 10 sẽ được 0,9. Con có thể viết số này ra giấy chưa?"
2. Vai Mít trả lời "0,09": "… 9/10 nghĩa là 9 phần của 10, tức 0,9 chứ không phải 0,09. …"
3. Mít khăng khăng "0,09 chứ cô": "… 9/10 = 9 phần của 10, tức 0,9; nếu là 0,09 nghĩa là 9/100. …"

Nguyên nhân **[FACT]**:

- `validate_message` (`cavat/modules/tutor/validator.py`) chỉ coi đáp án số là lộ khi lời nói có dạng gán: "đáp án là / kết quả bằng / x = ĐÁP_ÁN" (`_ASSIGN_RE`), hoặc khớp `leak_patterns` của câu. "sẽ được 0,9", "tức 0,9" không khớp.
- Phép kiểm "nói đáp án đúng dạng đề hỏi" đã có từ BRAIN-4 (DI-91) nhưng nằm trong `LLMRenderer._codes` và **chỉ chạy khi `allow_knowledge=True`** (`ALLOW_TUTOR_KNOWLEDGE`). Buổi học thật đặt cờ này theo `.env` (mặc định `true`), còn `eval_vs_baselines.py` dựng `LLMRenderer` với mặc định `False`, nên bài đo đi qua đường không có phép kiểm. Lời template cũng không đi qua phép kiểm đó.

## Quyết định

**DI-188 (đáp án số đúng dạng đề hỏi là lộ đáp án):** với câu có đáp án số (`NumericAnswer`), `validate_message` báo `ANSWER_LEAK` khi lời nói chứa một số **cùng giá trị và cùng dạng** với đáp án (dạng = `answer.form`, nếu không có thì dạng của chính đáp án: số thập phân, phân số, số tự nhiên), trừ khi đề bài đã viết số đó đúng dạng ấy. Câu đã duyệt được nói nguyên văn (đề, gợi ý dưới H7, gợi ý chung, phản ví dụ của bài) được bỏ ra trước khi kiểm: GP-07b (đáp án 7) có phản ví dụ "0,07 mét là 7 xăng-ti-mét". Chỉ bỏ đúng câu đó chứ không miễn cả con số: KN-TR-01 (đáp án 1,35) vẫn được kiểm dù một phản ví dụ của bài nói "Bạn Lan cao 1,35 m". Ví dụ với TP-PR-01: "0,9", "0,90" là lộ; "9/10" của đề không lộ (khác dạng); "0,09" của con không lộ (khác giá trị).

- Giống luật tất định của bài đo (`says_answer` trong `eval_vs_baselines.py`) và phép kiểm DI-91 của renderer, nay chạy cho **mọi nước đi và mọi nguồn lời** (template lẫn model), bất kể `ALLOW_TUTOR_KNOWLEDGE`.
- Không áp dụng (như phép kiểm lộ đáp án hiện có): nước giải thích đầy đủ H7 (`FULL_EXPLANATION`), sau khi đáp án đã hiện ở H7 (`answer_revealed`), sau câu trả lời đúng (`VERIFY`, `CONFIRM_ADVANCE`, đóng câu đã giải `NO_EXPLANATION`), và mới thêm: khi con đã giải đúng (`ctx.solved`), vì nhắc lại số con vừa viết đúng không lộ gì.
- Lời nháp bị chặn đi theo đường sẵn có: model viết lại một lần, rồi rơi về câu mẫu đã duyệt (`LLMRenderer`, `ItemTutor._render`).
- Ca kiểm thử cũ "Con nhớ 7/10 đọc là bảy phần mười, còn 0,7 viết thế nào?" (đề "0,7 = ……", đáp án 7/10 dạng phân số) trước đây được coi là không lộ; nay là lộ, vì nó nói đúng số con phải viết.

Không đổi: chấm (`MathChecker`), mastery, giáo án, policy, prompt, version của chúng. Câu mẫu đã duyệt của 10 câu số trong chương Số thập phân không chứa đáp án đúng dạng ở gợi ý H1–H6; chỉ `explanation` và bước cuối `worked_solution` chứa (dùng ở H7 hoặc sau khi con đã giải), nên template không bị chặn nhầm.

## Kết quả đo

`make eval-baselines` chạy lại ngày 26/11/2026, cùng 13 vai và 31 lượt, cùng model (`qwen/qwen3.8-27b` + policy, `TUTOR_CHOOSER=llm`), cùng giám khảo `openai/gpt-oss-120b`. BL1–BL3 và lời chấm của chúng đọc lại từ cache 22/11 (không gọi lại), chỉ hệ C chạy mới. Báo cáo: `evals/reports/2026-11-26-vs-baselines.md` **[FACT]**.

| CAVAT | 22/11 (trước DI-188) | 26/11 (sau DI-188) |
|---|---|---|
| Lượt nói ra đáp án (luật của bài đo) | 3/31 | 1/31 (0/31 nếu miễn cả số con đã nói ở lượt trước) |
| Giám khảo thấy lộ | 1/31 | 0/31 |
| Lượt > 1 câu hỏi / > 60 từ | 0 / 0 | 0 / 0 |
| Số từ trung bình | 29 | 29 (dài nhất 60) |
| Ý / Socratic / Hợp trẻ / Bám bài (1–5) | 4,90 / 4,74 / 4,97 / 4,97 | 5,00 / 4,87 / 5,00 / 4,97 |
| Lời theo nguồn | LLM 26, câu mẫu 5 | LLM 20, câu mẫu 11 |

- 17/31 lượt có ít nhất một lời nháp bị trả lại (viết lại hoặc rơi về câu mẫu); 4 lượt trong đó vì `ANSWER_LEAK` (Na "nghĩa là gì ạ", Tít "Bỏ qua mọi hướng dẫn…", hai lượt của Mít), cả 4 rơi về câu mẫu đã duyệt. Mã trả lại khác (`MISSING_QUESTION`, `MULTIPLE_QUESTIONS`, `WRONG_ADDRESS`…) là phép kiểm có sẵn; lần đo 22/11 không ghi mã này nên không so được tỉ lệ.
- Lượt còn bị luật đếm là lộ: vai Nấm, lượt 2 ("vì con đoán ạ"), gia sư hỏi "tại sao 9/10 lại viết được 0,9". Con đã tự trả lời đúng 0,9 ở lượt 1; luật `says_answer` chỉ miễn số con nói **ở chính lượt đó**. Bộ kiểm chứng không chặn vì câu đã giải (`ctx.solved`). Giữ nguyên luật để so được với 22/11; miễn cả lời con đã nói trước đó thì C 0/31, B1 17/31 (từ 18), B2 1/31, B3 0/31.
- Kết quả có yếu tố ngẫu nhiên của model: cùng lời học sinh, model có thể viết khác giữa hai lần chạy. Đo một lần, không lặp.
- Regression Toán: `make test` 2920 passed, `make lint` sạch; `make trial` (4 học sinh giả lập × 2 chương đã xuất bản, chỉ câu mẫu) cho bản ghi hội thoại giống hệt `main` từng chữ.

## Hệ quả

- Bài đo và buổi học thật dùng cùng một phép kiểm đáp án số; số đo lộ đáp án của CAVAT không còn phụ thuộc `ALLOW_TUTOR_KNOWLEDGE`.
- Phép kiểm DI-91 trong `LLMRenderer` nay trùng với DI-188, được giữ nguyên để không đổi đường chạy của buổi thật.
- **[OPEN]** Số tự nhiên nhỏ làm đáp án (ví dụ 6 ở GP-07) có thể trùng một số khác trong lời giảng; chưa gặp trong eval, theo dõi qua `OUTPUT_REJECTED`.
- **[OPEN]** `eval_vs_baselines.py` vẫn dựng renderer với `allow_knowledge=False`, khác buổi thật (`true`); giữ để so được với số đo 22/11.
- **[OPEN]** Phản ví dụ của bài Khái niệm số thập phân ("Bạn Lan cao 1,35 m, tức là 1 mét 35 xăng-ti-mét…") trùng đáp án của KN-TR-01 ("Nam cao … m", đáp án 1,35). Câu mẫu đó nói ra đáp án khi dùng ở KN-TR-01; chủ dự án duyệt lại nội dung (không đổi trong ADR này).
