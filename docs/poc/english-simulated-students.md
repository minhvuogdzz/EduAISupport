# ENG-9a: học sinh mô phỏng học Unit 11 "Family time" — số liệu và lỗi phát hiện

Ngày: 15/11/2026 · Task ENG-9a (một phần của ENG-9, `docs/tasks/BACKLOG.md`) · Liên quan: ADR-060 §10 (kế hoạch kiểm chứng, DI-116), ADR-063 (bộ chấm, `node-mastery-en/0.1.0`, DI-129/130), ADR-064 (giọng nói), ADR-065 (validator), ADR-066 (buổi học đầu-cuối, DI-140/141), ADR-067 (báo cáo, DI-114/145).

- Script: `services/api/scripts/eval_english_students.py` (chỉ đo; không sửa code chính).
- Số liệu thô: `docs/thesis/data/english-simulated-students.json` (offline), `english-simulated-students-live.json` (model thật, cấu hình triển khai), `english-simulated-students-live-relaxed.json` (model thật, chế độ đo).
- Chạy lại: `cd services/api && .venv/bin/python scripts/eval_english_students.py` (khoảng 3,5 phút; seed 20261115; hai lần chạy cho JSON giống hệt nhau trừ id/giờ).

> **Giới hạn [FACT]:** đây là **học sinh giả**, không phải trẻ thật. Câu trả lời được dựng từ chính dữ liệu của unit (đáp án duyệt, `wrong_answers`, mẫu lỗi) theo một mô hình xác suất do script khai báo. Số liệu cho biết hệ thống có **cư xử đúng thiết kế** trước các hành vi này hay không; không nói gì về cách trẻ thật học, và **không thay** tập vàng chấm tay (DI-115/116) của ENG-9.

## 1. Cách làm

**Đường chạy.** Mỗi học sinh giả mở buổi bằng `POST /v1/sessions {"lesson_id": "eng-g5-u11-family-time"}`, trả lời qua `/responses`, xin gợi ý qua `/hint-requests`, nói qua `/v1/voice/transcribe` (bộ nghe giả lập trả bản chép lời và `q` do hồ sơ quyết định), đúng như web gọi. Database trong bộ nhớ (không ghi gì lên Atlas), template (không model) trừ lượt live ở §5. Sau khi mọi em học xong, script đọc các trang báo cáo giáo viên/học sinh/phụ huynh của unit (ADR-067), rồi chạy lại golden Toán.

**Học sinh giả.** Mỗi hồ sơ có xác suất trả lời đúng ban đầu (`ability`), tăng thêm một chút (`gain`) mỗi lần cô gợi ý hoặc sửa câu sai trên nút đó; có thể có "thói quen" (lỗi lặp lại, nhạt dần 8% mỗi lần bị sửa trên nút đó), xác suất nói "con không biết", xin gợi ý, đòi đáp án, hỏi Toán, trả lời tiếng Việt, số lượt nói và khoảng `q`. Seed cố định nên chạy lại được.

**Hồ sơ.** Tám hồ sơ của đề bài, thêm ba hàng của ADR-060 §10 mà danh sách đề bài không có, và một mốc tham chiếu:

| Hồ sơ | Mô tả | Hàng ADR-060 §10 |
|---|---|---|
| Giỏi | đúng 93% từ đầu, 3 lượt nói q 0,88–0,97 | học tốt |
| Trung bình | đúng 68%, đôi khi xin gợi ý / "không biết", 2 lượt nói | — |
| Yếu | đúng 38%, xin gợi ý 10%, "không biết" 12% | — |
| Quên did / nguyên mẫu sau We | 85% câu cụm có thể sai ngữ pháp thì sai: "You collect…?", "What your family do…", "We eat seafood" | nguyên mẫu sau We; quên did |
| Hay trả lời tiếng Việt | 45% câu tiếng Anh trả lời bằng tiếng Việt | trả lời tiếng Việt |
| Đòi đáp án | 35% lượt "cô cho con đáp án luôn đi" | — |
| Hỏi lạc sang Toán | 15% lượt hỏi "2 + 3 là mấy", "12,5 + 3,7", "số thập phân 0,5", "diện tích tam giác" | (rò rỉ hai môn) |
| Nói không rõ (q thấp) | 10 lượt nói q 0,22–0,55, một nửa bản chép lời bị nghe sai một từ | nói không rõ |
| Trả lời "Yes, I do" | 90% câu "Yes, I did / No, I didn't" thành "Yes, I do / No, I don't" | "Yes, I do" |
| Nhầm nghĩa cụm từ | 70% chọn phương án mang hiểu lầm M06 | nhầm nghĩa |
| Chỉ nói theo cô | mọi lượt lặp lại câu cuối của cô | chỉ nói theo cô |
| Mốc: đúng hết | mọi câu đúng ngay (tham chiếu, không phải học sinh) | — |

**Nhãn để so bộ chấm.** Mỗi câu trả lời script tạo có nhãn ĐÚNG/SAI và, với câu sai có chủ đích, mã lỗi kỳ vọng (mã hiểu lầm của `wrong_answers`/phương án, hoặc `EN_TENSE`, `EN_STRUCTURE`, `EN_SHORT_ANSWER`, `EN_L1`). Lượt nói bị nghe sai (bản chép lời khác lời con) được tách riêng, không tính vào độ khớp, vì nhãn của chúng phụ thuộc vào việc giáo viên nghe băng (§4.3).

## 2. Kết quả offline theo hồ sơ

| Hồ sơ | Lượt | Xong buổi | Bước đã qua | Qua nút | M TB | Đúng lần 1 | Tự làm | Gợi ý/câu | Khớp chấm (κ) | Mã lỗi đúng | Lộ đáp án | Từ Toán / chunk Toán | Câu Toán đưa về bài |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Giỏi | 79 | có | 1–6 | 5/6 | 82,7 | 0,89 | 0,97 | 0,03 | 38/38 (1,0) | 3/3 | 0 | 0 / 0 | — |
| Trung bình | 113 | có | 1–6 | 5/6 | 81,4 | 0,78 | 0,88 | 0,24 | 49/49 (1,0) | 12/12 | 0 | 0 / 0 | — |
| Yếu | 166 | có | 1–6 | 5/6 | 77,1 | 0,61 | 0,65 | 0,88 | 69/69 (1,0) | 25/26 | 0 | 0 / 0 | — |
| Quên did / nguyên mẫu | 137 | có | 1–6 | **3/6** | 79,7 | 0,55 | 0,68 | 0,66 | 73/73 (1,0) | 30/31 | 0 | 0 / 0 | — |
| Hay trả lời tiếng Việt | 116 | có | 1–6 | 5/6 | 79,4 | 0,87 | 0,79 | 0,32 | 41/41 (1,0) | 4/4 (*) | 0 | 0 / 0 | — |
| Đòi đáp án | 147 | có | 1–6 | 5/6 | 78,0 | 0,73 | 0,51 | 1,12 | 50/50 (1,0) | 8/8 | 0 | 0 / 0 | — |
| Hỏi lạc sang Toán | 88 | có | 1–6 | 5/6 | 83,2 | 0,89 | 0,92 | 0,08 | 40/40 (1,0) | 4/4 | 0 | 0 / 0 | **7/7** |
| Nói không rõ (q thấp) | 97 | có | 1–6 | 5/6 | 83,2 | 0,84 | 0,92 | 0,08 | 36/36 (1,0) | 2/2 | 0 | 0 / 0 | — |
| "Yes, I do" | 111 | có | 1–6 | 6/6 | 80,3 | 0,73 | 0,88 | 0,17 | 47/47 (1,0) | 9/9 | 0 | 0 / 0 | — |
| Nhầm nghĩa | 100 | có | 1–6 | 5/6 | 82,9 | 0,76 | 0,87 | 0,13 | 44/44 (1,0) | 7/7 | 0 | 0 / 0 | — |
| Chỉ nói theo cô | 320 (trần) | **không** | 1–5 | **0/6** | 15,7 | 0,22 | 0,06 | 4,47 | — | — | 0 | 0 / 0 | — |
| Mốc: đúng hết | 74 | có | 1–6 | **5/6** | 82,8 | 1,0 | 1,0 | 0 | 36/36 | — | 0 | 0 / 0 | — |

"M TB": trung bình mastery cuối của sáu nút (nút chưa có số tính 0). "Đúng lần 1": tỉ lệ `attempt_no = 1` đúng. "Tự làm": tỉ lệ `ITEM_RESOLVED.resolution = INDEPENDENT`. (*) Hồ sơ tiếng Việt: 21 câu tiếng Việt **không** vào bộ chấm (lỗi L-2, §4).

Mastery và mức của từng nút (M / level, "qua" = `passed_at` có giá trị):

| Hồ sơ | VOCAB | PAST | DIDYOU | WHATDID | STRESS | TRIP |
|---|---|---|---|---|---|---|
| Giỏi | 72,7 / 3 | 80,9 / 3 qua | 87,6 / 4 qua | 81,1 / 4 qua | 89,2 / 3 qua | 84,6 / 4 qua |
| Trung bình | 72,0 / 3 | 77,8 / 3 qua | 85,6 / 4 qua | 82,1 / 4 qua | 88,7 / 3 qua | 82,3 / 4 qua |
| Yếu | 62,6 / 3 | 78,9 / 3 qua | 79,3 / 4 qua | 79,9 / 4 qua | 75,3 / 3 qua | 86,4 / 4 qua |
| Quên did / nguyên mẫu | 70,0 / 3 | 76,8 / 3 (M04 còn mở) | 81,8 / 4 qua | 78,6 / 4 qua | 88,3 / 3 qua | 82,6 / 4 (M11 đang sửa) |
| Chỉ nói theo cô | 32,3 / 1 | 31,7 / 1 | 30,1 / 1 | — | — | — |
| Mốc: đúng hết | 72,7 / 3 | 80,9 / 3 qua | 88,4 / 4 qua | 81,1 / 4 qua | 89,2 / 3 qua | 84,8 / 4 qua |

## 3. Đối chiếu với ADR-060 §10, DI-116 và yêu cầu của task

| Kiểm chứng | Kết quả | Đạt? |
|---|---|---|
| Đi hết vòng 6 bước | 10/10 hồ sơ học thật (trừ "chỉ nói theo cô") đi đủ bước 1–6 và kết thúc buổi | Đạt |
| Chỉ-nói-theo-cô không qua nút nào | 0/6 nút; nhưng buổi không kết thúc, lặp tới trần 320 lượt (lỗi L-4) | Đạt (kèm lỗi) |
| q thấp sai không bao giờ làm M giảm (DI-109/130) | 3 câu nói q < 0,6 bị chấm không đúng; 0 lần M giảm. Lượt nói q thấp đúng chỉ được tính × 0,3 | Đạt |
| "Yes, I do" không qua DIDYOU khi hiểu lầm còn mở | DIDYOU qua khi không còn hiểu lầm ACTIVE (M03 đã RESOLVED). Bộ chấm gán "Yes, I do" vào **M03**, không phải M01 như câu chữ ADR-060 §10 | Đạt (ghi chú L-8) |
| Nguyên mẫu không qua WHATDID khi M02 còn mở; quên did không qua DIDYOU khi M01 còn mở | lúc qua không còn hiểu lầm ACTIVE; PAST và TRIP **không qua** vì M04/M11 còn mở; hồ sơ này qua 3/6, ít nhất trong các hồ sơ học thật | Đạt |
| Học tốt qua cả unit trong trần lượt | **Không đạt**: giỏi 5/6, ngay cả mốc "đúng hết" cũng 5/6: nút VOCAB không thể qua (lỗi L-1) | **Không đạt** |
| Xếp được giỏi > trung bình > yếu | M TB 82,7 > 81,4 > 77,1; đúng lần 1 0,89 > 0,78 > 0,61; tự làm 0,97 > 0,88 > 0,65; lượt 79 < 113 < 166 | Đạt, nhưng khoảng cách M cuối nhỏ (L-5) |
| Độ khớp đúng/sai của bộ chấm ≥ 95%, κ ≥ 0,8 (DI-116) | 523/523 câu trả lời có nhãn khớp (100%, κ = 1,0 trên mọi hồ sơ có câu sai) | Đạt trên dữ liệu giả (**không thay tập vàng**) |
| Độ khớp mã lỗi ≥ 80% (DI-116) | 104/106 (98%); 2 lệch ở §4 (L-7) | Đạt trên dữ liệu giả |
| Lộ đáp án = 0 | 0 câu cô nói đáp án cụm của item đang mở trước khi con trả lời đúng, dưới H7, ngoài item cùng làm (31 lượt đòi đáp án đều bị từ chối: "Cô chưa nói đáp án ngay đâu…") | Đạt |
| Lời cô chứa thuật ngữ Toán = 0 | 0 (offline, cả live) | Đạt |
| Chunk Toán lọt vào buổi Tiếng Anh = 0 (DI-116) | 0 trên mọi `RAG_RETRIEVED` | Đạt |
| Câu hỏi Toán được đưa về bài | 7/7 offline + 2/2 live: `OFF_TOPIC`, không chấm, không gợi ý, không RAG, hỏi lại đúng câu đang chờ | Đạt (lời hỏi lại đôi khi cụt, L-6) |
| Báo cáo giáo viên/phụ huynh | nhóm kết quả (độc lập / có hỗ trợ / xem lời giải / chưa xong) khớp event ở 12/12 em; `ASR_LOW` chỉ có ở em "nói không rõ" (10 lượt, 10 q thấp); "chỉ nói theo cô" bị gắn STOPPED/WEAK/MISCONCEPTION; trang phụ huynh không lộ lượt nói, bản chép lời, q hay điểm; trang học sinh không có số mastery | Đạt (L-9 về nhãn chất lượng VOCAB) |
| Buổi Toán chạy cùng lúc vẫn y hệt golden | golden `math-session-before-eng5b.json` chạy sau các buổi Tiếng Anh trong cùng tiến trình: giống hệt (83 view, mọi event); buổi Toán xen kẽ từng lượt với một buổi Tiếng Anh của cùng em = buổi Toán chạy riêng (436 event) | Đạt |
| Buổi Tiếng Anh với model thật (cấu hình triển khai) | **Kẹt ở lời giảng đầu**, 0 lần gọi model (lỗi L-0) | **Không đạt** |

## 4. Lỗi phát hiện (không sửa trong PR này)

| Mã | Mức | Lỗi | Bằng chứng | Đề xuất task |
|---|---|---|---|---|
| **L-0** | **Nghiêm trọng** | Với model thật, buổi Tiếng Anh **không qua được lời giảng đầu**. DI-140 cho `GroundedSpeaker` của buổi Tiếng Anh chạy không router, nên lời giảng/lời nối là template; nhưng router thật (`build_router`, luôn `model_only_speech=True`, cũng là đường của `AUTH_MODE=accounts` khi triển khai) cấm mọi lời không do model nói → mỗi lượt chỉ trả "Con chờ cô một chút nhé…" (`MODEL_WAIT`, `rejected: MODEL_ONLY_SPEECH`), `tutor_recovery.status = retrying`, 0 `MODEL_CALLED`. Test ENG-5b không bắt được vì router giả không bật `model_only_speech`. | `english-simulated-students-live.json`: 2 hồ sơ × 6 lượt, đều đứng ở VOCAB bước 1, 0 lần gọi model | **ENG-5c**: cho phép lời đã duyệt của unit (đoạn lý thuyết/ví dụ từ gói, `source=TEMPLATE` có `sources`) đi qua cổng `model_only_speech` ở buổi Tiếng Anh, hoặc viết đường model cho `GroundedSpeaker` Tiếng Anh (việc [OPEN] của DI-140); thêm test với router `model_only_speech=True`. Chỉ chạm nhánh `subject == "english"`; regression Toán + golden. |
| **L-1** | Cao | Nút **VOCAB không thể qua**, kể cả khi mọi câu đúng ngay: M tối đa 72,7 < ngưỡng; vòng dạy dừng nút vì hết item (`STOP_NODE`, `N-BUDGET`, `NO_ITEMS_LEFT`) rồi đi tiếp. VOCAB chỉ có 6 item (1 kiểm tra hiểu, 1 nói theo cô độc lập ≤ 0,20, 4 luyện tập), không có item ở mức A/T nên các chiều A, T, S đứng ở prior 0,5. Hệ quả: báo cáo luôn hiện VOCAB "chưa qua"; 11/12 em có VOCAB trong `nodes_out_of_items`; hồ sơ yếu còn hết item cả ở STRESS. | bảng §2 (mốc "đúng hết" 5/6); NODE_DECISION của VOCAB | **ENG-3c** (nội dung, chủ dự án duyệt): thêm 2–3 item VOCAB mức vận dụng/chuyển giao (nhìn tranh nói câu, chọn cụm cho tình huống mới), hoặc DI cho pass rule của nút từ vựng. Không đổi công thức chung của Toán. |
| **L-2** | Trung bình | Câu trả lời **tiếng Việt** cho câu tiếng Anh không vào bộ chấm: vòng dạy đọc là `UNREADABLE` → `REDIRECT` ("Mình quay lại câu đang làm nhé…"), không có `ANSWER_SUBMITTED`, không có lớp `L1`, không bao giờ `final_error_class = L1`. ADR-063 §5 đã ghi việc này cho ENG-5 nhưng chưa làm. Giáo viên không thấy em hay trả lời tiếng Việt; lời cô không mời nói bằng tiếng Anh rõ ràng; lặp lại thì vòng dạy tự leo gợi ý. | 21/21 câu tiếng Việt: `outcome = None`, 0 lần L1 | **ENG-5d**: trước intent "không đọc được", với item `response_language = en` gọi bộ chấm Tiếng Anh để nhận `EN_L1` (DI-129 điểm 4), lời cô "Con nói bằng tiếng Anh nhé: We …", đóng item bằng L1 khi hết lượt. |
| **L-3** | Trung bình | `ANSWER_SUBMITTED.modality` của câu **nói** ghi `TEXT` (8/8 lượt nói của em "nói không rõ", 3/3 của em giỏi); chỉ `STUDENT_MESSAGE` và `ITEM_RESOLVED` mang `VOICE`. Projector đọc `ITEM_RESOLVED` nên mastery đúng, nhưng phân tích theo từng lần thử (báo cáo, xuất dữ liệu luận văn) sẽ sai. | `spoken_answer_submitted_as_text` trong JSON | Task nhỏ: điền `modality` thật vào `ANSWER_SUBMITTED` (kiểm tra cả Toán, ADR-030; thêm trường không đổi golden thì giữ nguyên hành vi Toán). |
| **L-4** | Trung bình | Học sinh **chỉ lặp lại lời cô** làm buổi lặp vô hạn: cô trả "Đó chính là câu cô đang hỏi con đấy! Con thử nghĩ xem nhé: …", con lặp lại, … tới trần 320 lượt; buổi không dừng, không chuyển sang hỏi khác hay báo cô giáo trong buổi (chỉ báo cáo sau mới có STOPPED/WEAK). | trích đoạn §6.5 | Luật vòng dạy: sau N lần lời con trùng lời cô, chuyển sang câu chọn/nói theo cô ngắn, rồi dừng buổi có lời nhắn (chung cho cả Toán: cần chủ dự án quyết). |
| **L-5** | Thấp (thiết kế) | Mastery **cuối** gần trần với mọi em học tới cùng (M TB 77–83; yếu chỉ thấp hơn giỏi 5,6 điểm; mốc "đúng hết" 82,8 ≈ giỏi 82,7) vì vòng dạy cho thêm item tới khi qua. Phân biệt rõ nằm ở quá trình (đúng lần 1, tự làm, số gợi ý, số lượt). Trang học sinh còn hiện yếu là INDEPENDENT ở mọi nút. | §2 | Đưa "đúng lần 1/tự làm/gợi ý" vào báo cáo giáo viên Tiếng Anh nếu chủ dự án muốn; không đổi công thức mastery. |
| **L-6** | Thấp | Khi đưa câu hỏi Toán về bài ở item nhiều câu, cô chỉ hỏi lại **câu cuối** của đề ("Bây giờ con trả lời giúp cô câu này nhé: Nếu chưa, con sửa giúp bạn nhé?") nên mất ngữ cảnh. | trích đoạn §6.3 | Hỏi lại cả đề (hoặc câu hỏi chính) khi `OFF_SUBJECT`. |
| **L-7** | Thấp | Hai lệch mã lỗi: (a) phương án C của `U11-DY-PR-04` mang hai hiểu lầm (M01, M02) → bộ chấm không ghi hiểu lầm nào; (b) điền chỗ trống "(2) swim" thay "swam" (`U11-WD-PR-03`) → PARTIAL không mã, trong khi đây đúng là lỗi thì. Thêm: `U11-PA-PR-04` chỉ có `required: [["bought"]]` nên "his the bought some souvenirs" (bản chép lời nghe sai) vẫn CORRECT. | `codes.misses`, `garbled` trong JSON | **ENG-3c** (nội dung): mỗi phương án một hiểu lầm chính; thêm `wrong_answers` cho dạng nguyên mẫu ở chỗ trống; siết `required` của PA-PR-04 (thêm "parents"). |
| **L-8** | Thấp (tài liệu) | ADR-060 §10 ghi "Yes, I do" gắn M01, nội dung unit và bộ chấm gắn M03 (`EN_SHORT_ANSWER`). | `yes_i_do` misconceptions = M03 | Sửa câu chữ ADR-060 §10 (Revision) cho khớp nội dung. |
| **L-9** | Thấp | Sư phạm của bước "nói theo cô": sau câu nhắc lại sai, nước đầu là `PROBE` kiểu Toán "Con nói cho cô nghe con đã làm thế nào để ra câu trả lời đó?" và sau câu đúng là `VERIFY` "vì sao con chọn cách nói đó?"; với câu nhắc lại thì nên chỉ ngay từ bị đổi (took/take). Cũng gặp với model thật. | trích đoạn §6.1 | Bảng nước đi theo `kind = say_after_me` (thay PROBE/VERIFY bằng nhắc từ khác biệt), chỉ trong nhánh Tiếng Anh. |
| L-10 | Thấp | Bản chép lời có tiếng đệm ("uh A") làm câu chọn không đọc được (không chấm, cô hỏi lại). | `garbled` | Bỏ tiếng đệm tiếng Anh (uh, um, er) khi chuẩn hóa câu chọn — cần chủ dự án duyệt vì DI-110 cấm tự thêm biến thể. |

### 4.3. Lượt nói nghe sai (q thấp)

7 lượt bản chép lời khác lời con (q 0,26–0,43): 2 bị chấm WRONG ("we ate the", "I look photos there"), 3 CORRECT vì phần sai không thuộc nhóm bắt buộc, 2 không đọc được ("uh A"). Theo DI-130 cả 7 không làm giảm M (đúng thì × 0,3, sai thì không evidence). Đây là lý do tập vàng phải có băng thật: chỉ giáo viên nghe băng mới biết lượt nào "nghe là đúng".

## 5. Lượt nhỏ với model thật

Chuỗi model lấy từ `services/api/.env` (Groq, `TUTOR_MODELS` để trống nên dùng thứ tự mặc định, kèm `GEMINI_TUTOR_FALLBACKS` chủ dự án đã đặt); khóa đọc qua biến môi trường, database trong bộ nhớ, MONGODB_URI bỏ.

| Chế độ | Hồ sơ × lượt | Lần gọi model | Model trả lời | Chuyển model (lý do) | Lời bị validator loại | Kết quả |
|---|---|---|---|---|---|---|
| Triển khai (`model_only_speech=True`) | giỏi, hỏi Toán × 6 | **0** | — | — | — | đứng ở VOCAB bước 1 (L-0) |
| Đo (`--relaxed`: cho lời đã duyệt đi qua) | quên did, hỏi Toán × 14 | 28 (25 `tutor_turn_en`, 3 `dialogue_listen_en_v1`) | qwen3.8-27b 6, gpt-oss-20b 5, gpt-oss-120b 7, gemini-2.5-flash 10 | 104 (QUOTA 82, UNAVAILABLE 22) | 4 (MISSING_QUESTION, MULTIPLE_QUESTIONS, OUT_OF_UNIT_ENGLISH → template dự phòng) | đi bước 1–4; 0 lộ đáp án; 0 từ Toán; 2/2 câu Toán đưa về bài; 9/9 câu có nhãn chấm khớp |

Nhận xét: prompt Tiếng Anh đi đúng đường (chỉ `tutor_turn_en`, `dialogue_listen_en_v1`), validator Tiếng Anh loại 4/25 lời model và rơi về template như thiết kế. Free tier hết hạn mức nhanh (82 lần QUOTA cho 28 lời gọi) nên một buổi thật trên web sẽ chậm và đổi model nhiều; đây là số đo của một lần chạy, chưa phải đánh giá chất lượng lời giảng. Ví dụ lời model: "Đúng rồi, con đã trả lời rất chính xác! Con có thể nói cho cô biết vì sao mình lại chọn cụm từ đó để trả lời không?" (đúng một câu hỏi, không lộ đáp án).

## 6. Trích đoạn hội thoại (offline trừ khi ghi khác; "Con" là học sinh giả)

**6.1. Quên did / nguyên mẫu (bước "nói theo cô", L-9):**
> Cô: Cô đọc trước, con nói theo cô cả câu nhé: We took a boat trip around the bay.
> Con: We take a boat trip around the bay.
> Cô: Con nói cho cô nghe con đã làm thế nào để ra câu trả lời đó được không?
> Con: Vì con thấy vậy ạ.
> Cô (H1): Con nghe cô đọc chậm lại nhé: We took a boat trip around the bay. Con nói theo được không?

**6.2. Trả lời tiếng Việt (L-2):**
> Cô: Trong tranh, cả nhà đang ngồi quanh bàn có tôm, cua, cá ở Nha Trang. Con nói câu kể việc cả nhà làm, bắt đầu bằng: We ate …
> Con: Nhà con đi ăn hải sản ạ.
> Cô: Mình quay lại câu đang làm nhé. Trong tranh, cả nhà đang ngồi quanh bàn có tôm, cua, cá ở Nha Trang. Con nói câu kể việc cả nhà làm, bắt đầu bằng: We ate …. Con làm thử giúp cô được không?
> Con: We ate seafood.

**6.3. Hỏi lạc sang Toán (đưa về bài; câu thứ hai cho thấy L-6):**
> Cô: Bạn Ben kể: 'I walked on the beach at Co To Island with my family.' Ben đã làm gì cùng gia đình?
> Con: Số thập phân 0,5 đọc là gì ạ?
> Cô: Cô nghe rồi, nhưng câu đó không thuộc bài «Unit 11: Family time» mình đang học, mình để lúc khác nhé. Bây giờ con trả lời giúp cô câu này nhé: Bạn Ben kể: 'I walked on the beach at Co To Island with my family.' Ben đã làm gì cùng gia đình?
>
> Cô: Bạn Nam nhìn tranh hai bạn đang cúi xuống cát nhặt vỏ sò, rồi nói: 'They bought souvenirs.' Bạn Nam nói đúng chưa? Nếu chưa, con sửa giúp bạn nhé?
> Con: Diện tích hình tam giác tính thế nào ạ?
> Cô: Cô nghe rồi, nhưng câu đó không thuộc bài «Unit 11: Family time» mình đang học, mình để lúc khác nhé. Bây giờ con trả lời giúp cô câu này nhé: Nếu chưa, con sửa giúp bạn nhé?

**6.4. Đòi đáp án (không lộ):**
> Cô: Bạn Lan kể: 'I collected seashells with my brother.' Bạn ấy đã làm gì cùng anh trai?
> Con: Cô cho con đáp án luôn đi ạ.
> Cô: Cô chưa nói đáp án ngay đâu, vì con tự tìm ra sẽ nhớ lâu hơn. Con nghe lại câu của Lan: I collected seashells with my brother. Từ seashells nói về thứ gì ở bãi biển?

**6.5. Chỉ nói theo cô (L-4):**
> Cô: … Trong tranh hai bạn cúi xuống cát nhặt vỏ sò, cô nói câu nào trong bốn câu vừa rồi?
> Con: Trong tranh hai bạn cúi xuống cát nhặt vỏ sò, cô nói câu nào trong bốn câu vừa rồi?
> Cô: Đó chính là câu cô đang hỏi con đấy! Con thử nghĩ xem nhé: Trong tranh hai bạn cúi xuống cát nhặt vỏ sò, cô nói câu nào trong bốn câu vừa rồi?
> Con: Con thử nghĩ xem nhé: Trong tranh hai bạn cúi xuống cát nhặt vỏ sò, cô nói câu nào trong bốn câu vừa rồi?
> Cô: Đó chính là câu cô đang hỏi con đấy! … (lặp lại)

## 7. Kết luận

- **Đạt [FACT, trên dữ liệu giả]:** vòng 6 bước chạy hết với mọi hồ sơ học thật; bộ chấm khớp 100% đúng/sai và 98% mã lỗi trên câu trả lời dựng từ unit; mastery xếp đúng giỏi > trung bình > yếu và giữ nút có hiểu lầm còn mở; q thấp không làm giảm M; 0 lộ đáp án, 0 từ Toán, 0 chunk Toán; câu hỏi Toán được gác như ngoài bài; báo cáo hiện đúng nhóm kết quả và `ASR_LOW`; luồng Toán y hệt golden khi chạy cùng/xen kẽ với Tiếng Anh.
- **Chưa đạt:** buổi Tiếng Anh với router thật bị kẹt (L-0, nghiêm trọng: chặn mọi buổi Tiếng Anh khi triển khai với tài khoản); nút VOCAB không thể qua (L-1); câu tiếng Việt không được ghi L1 (L-2).
- **[OPEN]** DI-116 vẫn cần tập vàng chấm tay (≥ 200 câu, ≥ 60 lượt nói có băng thật) của ENG-9: độ khớp 100% ở đây là trên câu do chính dữ liệu unit sinh ra, nên chỉ chứng minh bộ chấm nhất quán với đáp án đã duyệt, chưa chứng minh nó khớp giáo viên trên câu trẻ thật nói.
