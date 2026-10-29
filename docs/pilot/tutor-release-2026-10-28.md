# Kiểm tra AI Tutor · 28/10/2026 · đã sửa lại phạm vi

[FACT] Theo xác nhận mới nhất của chủ dự án, gia sư chỉ phục vụ Toán lớp 5, hai chương đã cấu hình: **Số thập phân** và **Diện tích hình tam giác, hình thang**. Bài hiện tại và các tiên quyết quyết định phạm vi giảng/tra cứu. Ngoài RAG nghĩa là bổ sung kiến thức phục vụ phạm vi này, không mở sang môn khác hoặc Toán ngoài chương.

## Sửa phạm vi

Đã gỡ nhánh trả lời kiến thức tổng quát, tìm kiếm cập nhật ngoài chương, danh sách nguồn y tế/chính phủ tổng quát và prompt kiểm kiến thức ngoài phạm vi từng thêm ở lượt trước. Khôi phục đường tìm nguồn giáo dục hiện có: chọn khái niệm hợp lệ theo node/tiên quyết → Tavily hoặc nguồn giáo dục dự phòng → đọc trang → chọn đoạn lý thuyết phù hợp → kiểm lời giải thích. Không gửi nguyên hội thoại/tên học sinh vào search.

Lượt thử Sở Y tế ở báo cáo trước xuất phát từ việc áp dụng ví dụ AI y tế trong yêu cầu ban đầu quá rộng. Đó là ca thử kỹ thuật không phù hợp sản phẩm này; không được dùng làm bằng chứng nghiệm thu gia sư Toán. Raw logs cũ vẫn giữ trong thư mục gitignored để truy vết, nhưng nhánh code tương ứng đã gỡ.

## Giữ lại cải thiện hội thoại

- Không buộc EXPLAIN phải kết thúc bằng câu hỏi; học sinh xin ngừng hỏi thì server không tự nối lại câu đang chờ.
- Nhận biết lời chưa hiểu rõ ràng, giảng/làm mẫu, vẫn giữ state của câu đang học; không biến trao đổi thành evidence làm đúng/sai.
- Giữ history qua RAG → Web theo phạm vi → giảng kiến thức nền của bài. Không đổi scoring, mastery, graph, prerequisite, unlock, schema hoặc dữ liệu.
- Giữ kiểm đầu ra Groq và cấu hình reasoning riêng từng model; không đổi chuỗi model mặc định.

## Kiểm chứng hiện tại

[FACT] 128 tests liên quan đạt: hội thoại nhiều lượt, khôi phục phiên rồi trả lời đúng, hỏi lý thuyết, nguồn giáo dục/Tavily, bảo toàn assessment. Thêm kiểm thử xác nhận câu hỏi AI y tế, thủ đô, chuyển vế và câu trộn mẫu số với AI y tế không đi ra Web hoặc được trả lời qua nhánh kiến thức tổng quát. Search service chỉ nhận khái niệm chuẩn đã cho phép.

Lệnh: `services/api/.venv/bin/python -m pytest services/api/tests/test_tutor_supplementary.py services/api/tests/test_search_web.py services/api/tests/test_brain2.py services/api/tests/test_brain4.py services/api/tests/test_brain8.py -q`.

[OPEN] Các số đo 2.162 tests và hội thoại live trong báo cáo trước thuộc bản trước khi thu hẹp lại phạm vi; không coi là kết quả toàn bộ backend của bản hiện tại. GPT-OSS vẫn chưa có phép so sánh đầy đủ vì quota. Không tuyên bố chất lượng LLM đã đạt mọi tiêu chí release.

## Rollback và ghi chép

Raw baseline và các thử nghiệm: `evals/reports/tutor-release/` (gitignored). `task-only.patch` được cập nhật cho bản hiện tại và kiểm bằng `git apply --reverse --check`; rollback bằng `git apply --reverse evals/reports/tutor-release/task-only.patch`, giữ những sửa đã có trước phiên. Kiểm lại nếu có sửa code mới sau đó.

Ghi chép luận văn: hoàn thiện hội thoại trong phạm vi hai chương Toán 5; sửa việc mở rộng tìm kiếm ngoài mục tiêu; giữ nền tảng adaptive learning. Chưa cập nhật Google Doc bên ngoài.

## Sửa tiếp theo từ phiên anh thử trên giao diện

[FACT] Phiên được chỉ định cho thấy bản ghi THEORY đầu tiên có `source=TEMPLATE`, chứa lệnh giáo án “Tô 30 ô… Giới thiệu…”. Nguyên nhân: endpoint join gọi vòng dạy không có GroundedSpeaker; các lần trả lời sau mới gắn model. Đây là lỗi ở tích hợp mở buổi, không phải cache hay bản thân RAG.

Đã dùng cùng cấu hình speaker cho join và lượt trả lời; gọi model ngoài event loop, tính vào hạn mức và ghi MODEL_CALLED. Join lại phiên đã bắt đầu không sinh lại lời giảng. Mở bài nói tên bài và phần con sẽ học; khi hết model chỉ dùng văn bản đã viết cho học sinh hoặc quy tắc đã duyệt, không đọc lệnh giáo viên. Tài liệu và dữ liệu học tập không bị sửa.

“mấy là mấy” được hiểu theo từ trong câu hỏi vừa nói. “chưa hiểu” dẫn tới giải thích bằng ví dụ, không tự nối nguyên câu hỏi cũ. Bộ kiểm lời cô nhận thêm lịch sử gần đây để kiểm cách giảng; kiểm Toán dùng EVAL_JUDGE sẵn có, tránh chia sẻ toàn bộ hạn mức với model viết lời. Chỉ lượt dạy lý thuyết được phép giải thích đầy đủ ý đang hỏi; bảo vệ đáp án item đánh giá không đổi.

Bổ sung tests mở buổi qua API, idempotence join, usage/events, fallback khi model vắng, chặn lệnh giáo viên và cách gọi sai mẫu số, nghe đúng câu hỏi từ vựng, giữ node/prompt và không tạo evidence khi chưa hiểu. 151 tests hội thoại/API liên quan và 41 tests tiến trình/mở bài đã đạt trong các lượt kiểm tra; các nhóm có giao nhau, không cộng thành một tổng.

Live replay chỉ đọc cấu hình đúng phiên đã chỉ định, chạy bằng đối tượng synthetic trong bộ nhớ, không tạo/sửa phiên học thật. Lần cuối: mở bài sinh từ model (3,21 giây), giải thích “mấy” (3,35 giây), rồi đổi ví dụ từ mẫu 1000 sang 100 khi chưa hiểu (1,28 giây); không nối câu hỏi cũ ở hai lượt sửa. Model vẫn có thể diễn đạt chưa tối ưu; không coi ba lượt là chứng minh chất lượng mọi hội thoại. Raw results: `evals/reports/tutor-release/observed-opening/`.

Đã khởi động lại backend. Lời mở bài cũ là lịch sử đã lưu, nên cần bắt đầu buổi mới để xem phần mở bài mới; không ghi đè lịch sử phiên hiện tại.

Rollback riêng phần sửa mở bài/phản hồi từ ảnh: `git apply --reverse evals/reports/tutor-release/observed-opening/correction-only.patch`; bản vá giữ nguyên các cải thiện đã có trước lần sửa này.

[FACT] Kiểm tra toàn bộ backend sau lần sửa từ ảnh: **2.157 tests đạt**, một cảnh báo Starlette/httpx có sẵn; lint và kiểm tra bản vá đạt.

## Sửa cách sử dụng cấu hình giáo viên

[FACT] Cấu hình lý thuyết đang có ba ràng buộc gây cứng: nối nguyên văn câu hỏi được duyệt; ưu tiên khớp danh sách cách nói; chỉ kiểm nghĩa cho câu đủ dài và chưa khớp mẫu. Đã sửa ở tầng sử dụng cấu hình, không sửa dữ liệu đã xuất bản: khi chế độ AI hiện hành khả dụng, câu hỏi có thể diễn đạt tương đương cùng ý/dữ kiện; câu thực tế được lưu và khôi phục từ event. Đáp án tham khảo và quy tắc được dùng để đối chiếu ý nghĩa; khớp từ không được ghi đè kết luận kiểm nghĩa âm, câu ngắn khác mẫu cũng được kiểm. Retell/mastery, bài đánh giá và chế độ strict-source cũ giữ hợp đồng hiện tại.

Màn hình duyệt bài và thư viện bài phân biệt nội dung kiến thức, câu hỏi tham khảo, ý giải thích và ví dụ học sinh diễn đạt đúng. Prompt tạo nháp mới cũng dùng cách phân biệt này; không tự tạo lại/xuất bản giáo án hay graph hiện có.

[FACT] 2.159 tests backend đạt; 10 tests giao diện liên quan, lint, kiểm kiểu và build đạt. Tests API xác nhận câu hỏi khác câu mẫu được lưu đúng và giữ nguyên sau restore/rejoin; tests phản ví dụ xác nhận có từ khóa đúng nhưng nghĩa sai không bỏ qua kiểm nghĩa. Live đã sinh câu hỏi khác câu cấu hình. Lượt live sau có fallback khi không dùng được model: chưa coi đây là bằng chứng chất lượng hội thoại đã hoàn toàn đạt. Raw log `teacher-references-live.txt`, kết quả regression `teacher-references-final-tests.txt` trong thư mục reports gitignored.

Đã dựng lại web và khởi động backend. Tải lại trang giáo viên để thấy giao diện mới. Rollback lượt sửa cấu hình: `git apply --reverse evals/reports/tutor-release/teacher-references-only.patch`; rollback toàn bộ thay đổi của công việc: `task-only.patch` cùng thư mục. Các patch đã được kiểm tra trên working tree sau sửa.

## RAG tổng hợp và Gemini hỗ trợ sư phạm

Theo yêu cầu mới, đã thêm đường hỗ trợ Gemini có giới hạn và đổi cách trả lời từ RAG trong chế độ AI: lấy ý nguồn để giải thích, không dùng trích xuất nguyên đoạn làm giả đầu ra model. Cho phép suy luận Toán đúng để giải thích ý trong nguồn, giữ kiểm chứng toàn bộ khẳng định và nguồn. Chi tiết: `docs/adr/ADR-045-bounded-gemini-teaching-support.md`.

Gemini viết lời giảng tốt hơn kèm góp ý, model chính thử diễn đạt lại một lần; nếu không đạt thì dùng lời Gemini đã kiểm. Không huấn luyện trọng số. Tối đa một lượt hỗ trợ trong một command, giữ session cap và grading guard. Tắt bằng `TUTOR_MENTOR_MODEL=`. Model mạnh cấu hình là `gemini-4-argon`, không thay API key.

Live hiện bị chặn ở Gemini: Argon và Pro trả 429, Flash trả 504; không đánh dấu nghiệm thu chất lượng mentor thật. Live RAG sau sửa trả lời diễn giải 1,27 giây, RAG grounded=true, có source verification. Logs `mentor-rag-reasoning-live.json`; các mẫu trả lời trước bị lỗi cũng được giữ để truy vết, không dùng làm bằng chứng thành công. Kiểm tra regression cuối ghi ở `mentor-verified-tests.txt` (reports gitignored).

[FACT] Regression sau tích hợp: **2.168 tests backend đạt**, một cảnh báo Starlette/httpx có sẵn; lint đạt. Bản sửa đã được khởi động, HTTP 200. Rollback lượt này: `git apply --reverse evals/reports/tutor-release/mentor-only.patch`.

## Teencode, hiểu ý theo ngữ cảnh và chuyển model khi hết hạn mức

[FACT] Log chỉ đọc của phiên được chủ dự án chỉ định: ở “hahaha”, GPT-OSS-120B đã trả nhãn CONTINUE, khiến server lặp nguyên câu hỏi. Đây là đọc sai ý, không phải model vắng ở chính lượt ấy. Các lượt sau có 429 thật ở GPT-OSS, Qwen và Gemini. Không sửa lịch sử phiên hay tạo dữ liệu học sinh để thử.

Lời gốc, bản hỗ trợ chuẩn hóa tiếng Việt và hội thoại gần đây cùng được chuyển cho bộ đọc ý. Ngôn ngữ không có đáp án số được đọc trước heuristic coi chữ ngắn là gõ linh tinh/đáp án sai. Nhãn REACTION tách biểu cảm khỏi đồng ý/đã hiểu; câu trộn tiếng cười với đáp án vẫn qua bộ chấm hiện có. REPAIR theo ngữ nghĩa gọi mentor cả với “khum hỉu”, không đợi khớp nguyên chuỗi. Bỏ tự nối câu hỏi cũ vào lời giảng ở lượt sửa hiểu; giữ nguyên câu đang chờ trong state. Không thay scoring, mastery, graph, assessment hay dữ liệu xuất bản.

Gateway mở dự phòng chéo Groq/Gemini cho cả đọc ý, viết lời và kiểm lời, bỏ qua model đang được ghi nhận hết quota/lỗi tạm thời. Chuỗi Gemini ưu tiên Argon, sau đó 2.5 Flash và 3.8 Flash; tắt mentor vẫn tắt nhánh bổ sung Gemini. Không bật billing hoặc thay secret. Các request lỗi vẫn được tính vào cap hiện có.

[FACT] Thử API thật riêng bộ đọc ý: 7/7 câu gồm “kkk”, “khum hỉu cô ui”, “ok nhưng e vẫn ko bít lm”, “ảo ma z cô”, “cô nói ngắn lại đc hong”, câu trộn tiếng cười với 31/10 và lời xin nghỉ được phân loại đúng. Raw: `teencode-listener-live.json`. Gemini 2.5 Flash đã thực sự hỗ trợ, kiểm lời và chuyển lời đã kiểm về model chính (`reactions-final-live.json`).

[OPEN] Thử chuỗi hội thoại trung gian (`teencode-conversation-live.json`) phát hiện lời ví dụ sai đơn vị vẫn bị bộ kiểm yếu chấp nhận, rồi hết toàn bộ chuỗi model; không coi đó là lượt đạt chất lượng. Sau phát hiện đã đưa REPAIR sang mentor ngay, bổ sung kiểm tính nhất quán tỉ lệ/đơn vị, bỏ lặp câu hỏi bắt buộc và dùng hỏi rõ khi không đọc được ý. Không tuyên bố hệ thống hiểu mọi tiếng lóng hoặc không bao giờ sai. Lượt thử cuối và regression được ghi bên dưới khi hoàn tất.

[FACT] Thử lại chuỗi sau sửa (`teencode-final-conversation-live.json`): cả 4 lượt trả lời source=LLM, giữ nguyên pending prompt/phase. “khum hỉu” có một ví dụ hình 100 ô (5,94 giây); yêu cầu nói ngắn được rút gọn (4,34 giây); “ảo ma” đáp theo lịch sử đang khó hiểu (5,33 giây); xin nghỉ được tôn trọng (2,79 giây). Ba lượt đầu có gọi Gemini mentor, sau đó model chính trả lời; riêng lượt “ảo ma” có đủ đường kiểm lời mentor → model chính viết lại → kiểm lời mới. Hai lượt đầu không được dùng làm bằng chứng lời mentor đã vượt kiểm. Lời xin nghỉ dùng model chính. Không lặp câu hỏi cũ ở các lượt sửa hiểu. Bộ đọc ý 7/7 là kiểm riêng, không cộng thành số lượt kiểm chất lượng toàn bộ hội thoại.

[FACT] Regression cuối: **2.189 tests backend đạt**, một cảnh báo Starlette/httpx có sẵn (`reactions-final-tests.txt`); lint và `git diff --check` đạt. Đã khởi động lại backend bản mới, HTTP 200 ở trang chính, trang học sinh và đường dẫn phiên đang thử. Có thể gửi tiếp trong phiên hiện tại; không cần xóa cache hoặc tạo lại buổi để áp dụng lời đáp mới. Lời đã lưu trong lịch sử giữ nguyên.

Rollback riêng lượt phản ứng/teencode và dự phòng: `git apply --reverse evals/reports/tutor-release/reactions-only.patch`. Rollback toàn bộ công việc: `git apply --reverse evals/reports/tutor-release/task-only.patch`. Giữ nguyên các chỉnh sửa ban đầu của chủ dự án; không thay API key, không bật billing, không deploy production.

## Bỏ kịch bản câu mẫu ở lượt giảng lý thuyết

[FACT] Chủ dự án chỉ rõ vấn đề là lời hỏi vô nghĩa và pipeline ép câu dữ liệu, không chỉ sai đếm số 0. Đã xác nhận từ log phiên mới: câu mẫu vẫn quay lại trong CONTINUE; Gemini bị bác do trộn luật hỏi/che đáp án với hội thoại giảng. Bản “cho paraphrase câu mẫu” trước đó chưa xử lý đúng yêu cầu này.

Đã thay bằng luồng author/reviewer cho lý thuyết không chấm, đầu vào chỉ mục tiêu + kiến thức thô + ngữ cảnh, không ask/reply/accept. AI tự thiết kế ví dụ/câu hỏi, reviewer không buộc tương đương câu cũ. Câu trả lời được đọc theo câu thực tế, không so với ví dụ đáp án cũ. Master đã kiểm có thể nói trực tiếp, không bắt model nhỏ viết lại. Chi tiết và giới hạn: ADR-046.

[FACT] Lượt live mới (`teaching-author-live.json`) đã soạn được lời mở bài từ ví dụ 3/10 = 0,3 rồi hỏi cách viết 7/10, không đưa câu “mẫu số có mấy chữ số 0…” trở lại. Hai lượt sau bị chặn bởi quota/lỗi nhà cung cấp ở toàn chuỗi kiểm lời; hệ thống báo chưa thể giảng tiếp, không giả thành công bằng đoạn dữ liệu. Không coi hai lượt đó là đạt chất lượng hội thoại. Raw các lượt trung gian chưa đạt vẫn giữ.

[FACT] Replay lại đúng lịch sử phiên được chỉ định bằng đối tượng trong bộ nhớ (`teaching-author-final-replay-live.json`): Gemini 2.5 Flash soạn lời ví dụ 3/10, Gemini 2.5 Flash kiểm lời, source=LLM, 6,49 giây. Không dùng model yếu viết lại hoặc nối câu mẫu. Không ghi ngược lời thử vào phiên thật. Câu hỏi kết quả là câu quan sát mối liên hệ từ ví dụ, vẫn cần đánh giá sư phạm nhiều tình huống; không lấy một lượt này chứng minh mọi lời đều có chất lượng.

[FACT] Regression cuối bản này: **2.200 tests backend đạt**, một cảnh báo Starlette/httpx có sẵn (`teaching-author-release-tests.txt`); lint và `git diff --check` đạt. Đã khởi động lại backend và kiểm HTTP 200 ở trang phiên hiện tại. Không dựng lại giáo án, không sửa dữ liệu xuất bản hoặc lịch sử học sinh.

Rollback riêng luồng mục tiêu: `git apply --reverse evals/reports/tutor-release/goal-driven-only.patch`; rollback toàn bộ công việc: `task-only.patch` cùng thư mục. Bản vá giữ những sửa có trước công việc, được kiểm reverse trước khi giao.

## Nếp vào buổi, nhắc lý thuyết sau sai và giữ giờ học

[FACT] Chủ dự án yêu cầu chào/nhắc kiến thức/định hướng ôn trước ví dụ, nhắc ý lý thuyết liên quan khi trả lời sai, và không biến tiếng cười thành lời mời tán gẫu. Ảnh phiên đang học cho thấy cô vừa gán con vui vừa tiếp tục mời chia sẻ sau khi bị phủ nhận. Đây là lỗi mục tiêu hội thoại và ràng buộc prompt, không coi do học sinh hoặc cache.

Đã sửa đồng bộ author/reviewer, mentor/constitution, listener và fallback; thêm đầu ra có cấu trúc cho hai phần đầu buổi để không coi tên chủ đề là nhắc lý thuyết. Thay đổi theo ADR-047. Dữ liệu giáo án và lịch sử không sửa. Kiểm thử rehearsal đều trong bộ nhớ; lịch sử phiên chỉ được đọc. Các lượt thử trung gian chưa đủ recap và bị giới hạn quota được giữ trong `routine-focus-live.json`, không coi là nghiệm thu yêu cầu đầu buổi. Kết quả cuối ghi tiếp khi kiểm xong.

[FACT] Kiểm tra tổng thể sau thay đổi: 2.206 tests đạt; một assertion metadata còn mong templates/0.13.0 đã cập nhật thành 0.14.0. Không đổi mã production sau lượt tổng thể đó; chạy lại nhóm 51 tests API/nếp dạy/hội thoại liên quan đều đạt (`routine-focus-verified-tests.txt`). Trước đó 147 tests Toán/lời giảng liên quan đã đạt. Không cộng các nhóm có giao nhau thành một tổng mới. Lint và `git diff --check` đạt.

[FACT] Các lượt live `routine-focus-final-live.json` và `routine-focus-release-opening-live.json` là dữ liệu kiểm tra trung gian: đã có lời chào và phần nhắc/định hướng theo cấu trúc, nhưng phát hiện một phát biểu sai về số phần mười bị reviewer yếu lọt. Đã bổ sung kiểm số phần bằng phân số chính xác và dữ kiện đối chiếu cho reviewer; ca sai cụ thể bị chặn bởi test hồi quy. Lượt live cuối không có lời giảng được duyệt vì các model kiểm lời đều báo quota/lỗi; không gọi đây là nghiệm thu chất lượng lời giảng thật. Nhánh quay về bài trả lời ngắn và nhận lỗi, không mời tán gẫu. Phiên thật chỉ dùng 35/160 lượt gọi ở lúc đọc, nên không nhầm lỗi provider với hết budget của buổi.

[FACT] Đã khởi động lại backend và xác nhận HTTP 200 tại trang phiên. Không đổi API key, billing, dữ liệu giáo án/học sinh, policy mastery hoặc công thức chấm. Rollback riêng: `git apply --reverse evals/reports/tutor-release/routine-focus-only.patch`; rollback toàn bộ công việc: `task-only.patch` cùng thư mục. Các patch giữ những sửa có trước công việc.

## Kiểm lại trạng thái theo yêu cầu chủ dự án

[FACT] Đã kiểm backend vẫn chạy, trang học sinh HTTP 200. Lượt thử thật mới (`routine-acceptance-recheck.json`, đối tượng trong bộ nhớ, không ghi DB) có thứ tự chào/nhắc kiến thức/định hướng/ví dụ. Tuy nhiên lời nhắc còn khái quát cách đặt dấu phẩy chưa đủ điều kiện, không coi là nghiệm thu chất lượng sư phạm. Lượt đáp án sai tiếp theo không tạo được lời nhắc vì toàn chuỗi đọc ý/kiểm nghĩa/viết lời trả quota hoặc unavailable, rồi dùng thông báo chưa thể giảng tiếp. Trạng thái: đã triển khai, chưa nghiệm thu trọn vẹn hai hành vi bằng model thật; không báo hoàn thành toàn bộ dựa vào tests mock.

## Xác định quota thực tế và hướng nguồn API ổn định

[FACT] Probe ngắn không có dữ liệu học sinh xác nhận Gemini 2.5 Flash hết mức 20 request/ngày, API yêu cầu chờ khoảng 17 giờ; Gemini 4 cũng bị giới hạn free tier. Raw metadata đã lược bỏ định danh ở `quota-diagnosis.json`. Đã đối chiếu tài liệu Google: quota theo project, RPD reset lúc nửa đêm Pacific. Thêm key cùng project không tăng quota.

Chủ dự án chấp nhận phí để ưu tiên ổn định, sau đó hỏi có thể tạo API khác. Đã kiểm read-only AI Studio: key app là EduAI trong project AIdevhouse, Free level. Chưa tạo key, đổi secret hoặc bật billing; ngân sách và ý nghĩa “API khác” chưa được chốt.

Đã sửa adapter nhận RetryInfo và loại quota, giữ đúng thời điểm hồi giữa các vai trò thay vì thử lại mỗi 10 phút (ADR-048). 77 tests liên quan đạt; lint/diff check đạt; khởi động lại local, trang học sinh HTTP 200. Rollback riêng phần này: `quota-retry-only.patch` trong thư mục reports gitignored.

## Sự cố không có lời giảng: phân biệt quota với lời học sinh

[FACT] Đọc đúng session hình học trong ảnh: các lượt mới đều fallback sau Groq TPD (cả 3 model), Gemini 4/2.5 RPD và Gemini 3.8 HTTP503. Session chỉ dùng 9 lượt, không phải hết cap. Probe ngắn mới trả được ở 3 Groq nhưng lượt mở bài đầy đủ trên giáo án đã xuất bản, đối tượng synthetic trong bộ nhớ, vẫn thất bại: 120B/20B TPD, Qwen soạn một bản bị kiểm copy, lần kế Qwen cũng TPD. Báo cáo `outage-recovery-live.json`; chưa xác nhận khôi phục lời giảng thật.

[DI] Không đánh đồng model unavailable với học sinh diễn đạt không rõ. Ghi SERVICE_UNAVAILABLE trong dấu vết từ chối lời giảng; báo kết nối AI gián đoạn và giữ bài. Reviewer không hoạt động thì dừng, không đốt thêm bản nháp. Lời mở chưa được tạo không được hiện câu hỏi mẫu để chờ/chấm học sinh. Lượt kế tiếp thử lại lời mở trước khi đọc/chấm câu trả lời; restore lấy lời mở mới nhất, giữ thứ tự nhắc kiến thức và định hướng; không chào lại. templates/0.15.0. Không đổi API key/billing; không ghi database thật. Kiểm thử liên quan 106 đạt trước bump version; kết quả toàn bộ lưu `outage-recovery-tests.txt`.

## Quy chế chờ khi không có model (29/10/2026)

Chủ dự án yêu cầu khi AI không hoạt động chỉ nói “Con chờ cô một chút nhé.”, tuyệt đối không lấy câu mẫu liên quan bài học để thay lời model. Dùng chung một thông báo ngắn, không nói chuyện quota/kết nối với học sinh. API chặn lượt không có lời LLM hợp lệ khi nguồn gọi cuối báo không khả dụng: giữ state trước lượt (ngoại trừ bộ đếm chi phí gọi model), bỏ sự kiện chấm/gợi ý/chuyển bước phát sinh từ lượt lỗi, ghi lời học sinh ngoài luồng chấm và giữ log model. Đầu buổi chỉ có lời chờ, không hiện câu hỏi mẫu; thử lại phần mở bài khi nguồn AI hồi. Không biến lời chờ thành lượt trả lời sai sau replay. Luồng chăm sóc an toàn hiện hữu vẫn ưu tiên. templates/0.16.0.

Kiểm thử tích hợp bộ nhớ bao gồm: mất model lúc vào buổi; mất model giữa lý thuyết; xin gợi ý khi model mất; state, prompt, input_id và tiến độ giữ nguyên, câu mới từ tutor chỉ là lời chờ. Không thử bằng database học sinh, không thay key/billing. Các kiểm thử trước sửa lời chờ: toàn bộ 2.215 đạt (outage-recovery-tests.txt); đó là kết quả bản trước, không dùng làm nghiệm thu bản mới. Kết quả bản mới nằm ở model-wait-tests.txt.

[FACT] Bản cuối: 2.182 tests API offline đạt, bỏ chọn 37 Atlas tests (`model-wait-final-tests.txt`). Đã sửa giữ modality VOICE trong lượt chờ; test chooser dùng scaffold legacy riêng để chỉ kiểm báo cáo chọn move, quy chế mất model được kiểm ở API integration. Lint phần sửa và diff-check services/api đạt. Khởi động lại backend với bản này, không thay nguồn API; tính sẵn sàng model thật chưa được xác nhận hồi phục. Rollback riêng lời chờ: `model-wait-only.patch`; toàn task: `task-only.patch`. Không đưa các sửa giao diện đồng thời không thuộc task vào patch mới.

## 29/10/2026 · Giữ mạch giảng, bằng chứng KC và ổn định model

Chủ dự án báo gia sư thường xuyên xin chờ dù có model trả lời, hoặc giải thích xong không hỏi tiếp. Log chỉ ra quota RPD/TPM/ITPM, prompt mentor vượt 3.000 token và lượt trộn lời AI với lời mẫu bị chặn bởi quy chế model-only. Điều kiện cũ còn cho phép chuyển sau một lần dạy lại dù chưa trả lời đúng.

Đã sửa các nhánh giảng lý thuyết và luyện tập để giải thích rồi hỏi một bước thuộc nội dung đang học; lời sai cần nhắc lý thuyết liên quan; lời nói lại chưa đạt không chuyển vì đã được giúp một lần. Giữ công thức mastery, KC graph và chấm assessment. Prompt có version mới; bớt lời chuyển dư thừa, bỏ lượt viết lại mentor đã kiểm, giới hạn độ dài yêu cầu trước khi gọi. Router hồi phục một lần với cooldown ngắn tối đa 6 giây; quota ngày vẫn trả thông báo chờ, không phát Toán mẫu. Chốt xuất lời lưu được mã bác thực tế để giáo viên chẩn đoán.

Thử API thật trên giáo án đã xuất bản, dữ liệu hội thoại tổng hợp: lần thử nhanh có giới hạn phút; lần có khoảng cách 15 giây đạt 8/8 lượt có AI trên hai chương, thời gian trả từng lượt 1,34–5,14 giây và prompt lớn nhất 1.975 token. Không dùng con số này làm bảo đảm SLA hoặc chất lượng tuyệt đối. Thêm chốt chặn kết luận đã hiểu sau lời tiếp nhận; có báo cáo kiểm riêng sau chốt. Không ghi DB học sinh, đổi API key hoặc bật billing.

Kiểm hồi quy và các giới hạn được ghi trong ADR-052. Sửa phép kiểm gzip cũ để đo byte nén thực thay vì bắt buộc header Content-Length, vì luồng trả streaming có thể không có header này; không đổi hành vi nén của ứng dụng.

Kết quả chốt: **2.223 kiểm thử API offline đạt**, 37 kiểm thử Atlas được tách khỏi lần chạy, một cảnh báo thư viện TestClient. Ruff và kiểm tra khoảng trắng của mã API đạt. Kiểm API thật riêng sau chốt không suy ra đã hiểu: cả hai chương có lời hợp lệ kèm câu hỏi, không khen đã nắm ý từ “à ra vậy” (`continuity-ack-verified-live.json`). Ứng dụng đã được khởi động lại để nạp thay đổi; kiểm `/health` và `/student` sau khi khởi động.
