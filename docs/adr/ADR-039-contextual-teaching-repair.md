# ADR-039: Sửa đọc câu trả lời và nhịp hội thoại gia sư

Ngày: 28/10/2026 · BRAIN-3 · DI-88, DI-89, DI-90

## Bối cảnh

[FACT] Chủ dự án yêu cầu hoàn thiện công việc bị gián đoạn do quota, giữ thiết kế của Claude và kế hoạch dạy hiện hành. Đã đọc hội thoại đang mở trong trình duyệt và đối chiếu bản giáo án xuất bản chỉ đọc. Không sửa hội thoại hoặc giáo án đó.

Các lỗi tại DTTGHT-BT-01 và DTTGHT-PH01-2: chấm toàn câu nhiều phần khi cô chỉ hỏi một phần; không đọc được phản ví dụ bằng lời nếu con chưa gõ “Sai”; dùng nhận định cần xét đúng/sai như kiến thức; tiếp tục yêu cầu giải thích điều con đã giải thích; dùng mục tiêu giáo viên thay cho lời giảng. Phiên cả chương đã hết trần 40 cuộc gọi nên mất tiếng nói model từ bài đầu.

## Quyết định

- **DI-88 — Đọc đúng bước đang hỏi.** `dialogue_version=2` thêm bộ đọc tất định cho phản ví dụ vị trí đường cao, câu nhiều phần và một số quan hệ nền của cả hai chương. Câu đúng một phần được công nhận, chỉ hỏi phần thiếu, không cộng lượt sai hay nâng mức gợi ý. Các phần được tích luỹ trong cùng item; lời sửa phủ nhận một phần trước đó không được ghép thành đáp án đúng. Số học, điều kiện khác, câu hỏi, phủ định/không chắc chắn ngoài khả năng đọc vẫn chuyển đường đọc cũ. Đây không phải bộ hiểu mọi cách diễn đạt. Đáp án vẫn qua MathChecker; không giao quyền chấm cho model.
- **DI-89 — Giảng và công nhận thay vì hỏi lặp.** `constitution.v8`, `brain/1.2.0`, `hint-policy/0.13.0`, `llm-renderer.v10`, `teaching-templates/0.10.0`: giảng ngắn trước khi hỏi con thử, công nhận ý đúng, nhận và sửa lời cô sai; không đọc true/false hay lời máy chấm ra cho học sinh. Mỗi lượt model tối đa 45 từ thông thường, 60 từ khi giảng/gợi ý. Tái dùng lý do đã nói ngay trong đáp án; giữa hai câu cùng KC chỉ bỏ câu “vì sao” liền kề khi cùng dạng, cùng mức nhận thức, trong cùng lượt dạy và không phải vận dụng. Câu bắt buộc giải thích vẫn giữ. Không bỏ kiểm tra nói lại quy tắc của node, không thay công thức mastery hoặc tự cộng bằng chứng giả. Khi cần nhắc lại, dùng quy tắc toán thay vì mục tiêu giáo viên; khi còn thiếu một ý, tìm cả đáp lời các cách giảng để không giảng lại đúng ý con vừa nêu.
- **Kiểm nghĩa lời giảng.** Câu đúng/sai luôn được đối chiếu với nguồn và khoá luyện tập trong cuộc gọi kiểm chứng riêng; các lượt giảng có tri thức node cũng được kiểm nghĩa. Chỉ verifier của luyện tập nhận khoá, không đưa khoá assessment vào prompt. Mã kiểm nguồn yêu cầu trích nguyên đoạn thực sự có trong nguồn; kiểm phép tính và một số mệnh đề hình học vẫn là code. Bổ sung căn cứ hình học chính xác: trong tam giác tù, đường cao từ đỉnh góc tù ở trong; hai đường cao còn lại ở ngoài. Có kiểm chứng bằng tọa độ trong regression. Kiểm nghĩa bằng model không phải chứng minh Toán và không bảo đảm bắt mọi lỗi.
- **DI-90 — Trần cho cả chương.** Một bài giữ 40 cuộc gọi; cả chương mặc định 160 (`MAX_LLM_CALLS_PER_CHAPTER`), thay đổi được bằng cấu hình, hữu hạn và vẫn chịu quota nhà cung cấp. RecordingRouter tính tổng cuộc gọi giữa các thành phần trong một command, tránh hai thành phần cùng tiêu phần quota còn lại. Không mua dịch vụ hoặc đổi chuỗi model.
- **Replay.** StudentMessage/input bổ sung phiên bản mặc định 1; dữ liệu cũ giữ cách đọc cũ. Dữ liệu mới có phiên bản 2. Không migration dữ liệu, không seed, không sửa lịch sử.

## Phạm vi giữ nguyên

Kế hoạch vòng dạy 7 bước, hai chương lớp 5, các cách giảng và bài xuất bản, chính sách node, công thức và ngưỡng mastery, Socratic, RAG và tra cứu nguồn chính thống của ADR-038 đều giữ nguyên. Không thiết kế lại agent hoặc mở tìm kiếm web tự do.

## Kiểm chứng

Xem `evals/reports/BRAIN-3-teaching-flow.md` và `services/api/tests/test_brain3.py`. Test offline/in-memory; phép thử live dùng snapshot giáo án chỉ đọc và trạng thái Python trong bộ nhớ, không ghi vào database học sinh. File snapshot và hội thoại riêng ở `var/storage/`, không commit.
