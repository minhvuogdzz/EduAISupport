# ADR-055: Sửa lỗi thật ở lượt nói lại, chặn tràn prompt và thử lại theo khả năng provider

29/10/2026 · Tiếp phản hồi “liên tục lỗi” sau ADR-054.

## Dấu vết thực tế

[FACT] Phiên trong ảnh đang ở RETELL. State vẫn giữ câu hỏi nói lại phương pháp chung, còn lời gia sư đã chuyển sang câu nhỏ đổi 5/10. Vì vậy chốt câu đang chờ nhìn sai mục tiêu. Nhánh hội thoại RETELL còn truyền `may_reveal=True`; các chốt thêm ở author lý thuyết không bao phủ nhánh này.

[FACT] Trong các lượt chờ, model có trả lời được nhưng yêu cầu reviewer đạt 3.068–3.077 token, mentor có lượt 3.181 token, vượt trần 3.000. Retry lại nguyên cấu trúc không sửa được lỗi này. Đồng thời có Gemini RPD, Gemini 504 và Groq TPM/ITPM/TPD; không thể quy mọi lỗi cho quota hoặc mọi lỗi cho kiểm duyệt.

[FACT] “5/10 chia cho 10 cho kết quả 0,5” lọt chốt Toán vì phép toán viết bằng lời chưa được chuẩn hóa thành biểu thức. Cổng nghĩa cũng đã duyệt câu cho đáp án rồi yêu cầu học sinh viết lại. Mỗi lần recovery lại phát cùng một thông báo.

## Thay đổi

- Rút gọn prompt có version (`constitution.v18`, `mentor.v4`, `curriculum-check.v12`), giữ ràng buộc sư phạm/Toán/safety và luật server. Tính cả system mentor và schema trước khi giảm lịch sử/nguồn. Reviewer giảm ngữ cảnh phụ khi cần nhưng giữ nguyên toàn bộ lời Toán đang kiểm, câu đang làm, input và hợp đồng hỗ trợ; không cắt phần cuối lời giảng để vừa ngân sách.
- RETELL dùng câu hỏi thực tế gần nhất học sinh nghe để gợi mở và kiểm lộ đáp án; lời chào/thông báo vận hành không thay mục tiêu. Giữ nguyên rubric nói lại và mastery. Hội thoại không được tự mở quyền giải đáp số. Cùng chốt tất định cho lời giảng, câu hỏi xác nhận và lời mời chép kết quả; cho phép ví dụ khác.
- Chuẩn hóa phép toán viết bằng lời như “chia cho”, “nhân với”, “cho kết quả” để kiểm phân số chính xác. Khi có lời cô cũ sai chưa được sửa, yêu cầu lời tiếp theo nhận và sửa trước câu hỏi mới. Dấu hiệu nhận lỗi không thay cho kiểm Toán/kiểm nghĩa.
- Với lỗi Toán cũ đã nhận diện, yêu cầu model viết phần `correction` riêng theo schema rồi mới đến hướng dẫn/câu hỏi; kiểm toàn bộ hai phần trước khi ghép lời nói. Đây vẫn là lời do model viết, không thêm câu Toán mẫu cố định. Sau khi cô đã sửa hợp lệ, không buộc lặp lời nhận lỗi ở mọi lượt sau.
- Lịch sử cô có phép tính sai hoặc đã cho sẵn đáp số được đánh dấu không hợp lệ trong ngữ cảnh gửi model; giữ nguyên input con, câu thực tế và event gốc. Với lỗi chia cả phân số thêm một lần, bổ sung chẩn đoán đúng: chuyển bằng tử số chia mẫu số là hợp lệ, không phải chia tiếp cả phân số. Tránh model tiếp tục học theo lời cô sai hoặc reviewer bác nhầm phép chuyển đúng. [DI] Chốt độ dài cho phép thêm tối đa 25 từ khi phải nhận và sửa lỗi cũ; không bỏ các chốt Toán, lộ đáp án, câu hỏi hay kiểm nghĩa.
- Giữ các mã lỗi đã bác trong trạng thái khôi phục nội bộ và chuyển vào lượt viết tiếp theo, kể cả mentor; không công khai lệnh/input nội bộ qua state view. Reviewer không hoạt động thì không đốt thêm bản nháp chỉ để kiểm lại bằng chính reviewer đang lỗi; không gán thất bại dịch vụ thành thiếu hiểu biết của học sinh.
- Trong cùng một lượt lỗi, chỉ hiện một thông báo chờ; các lần thử tiếp vẫn ghi event/cost để chẩn đoán, nhưng không phát thêm bubble/TTS trùng. Thông báo hết lượt thử vẫn được hiển thị. Transcript cũ cũng gộp các thông báo chờ liền nhau khi trình bày, không sửa event lịch sử.
- [DI vận hành] Khi mọi model đều đang bị chặn và provider có mốc hồi phục, chờ tới mốc gần nhất cộng một giây thay vì retry dồn 2/4/8 giây. Nếu mốc đó trên 60 giây thì báo chưa thể tiếp tục và dừng thử tự động; không hứa chờ ngắn khi phải đợi hạn mức ngày. Còn một fallback khả dụng thì không dừng theo quota của model khác. Giữ trần ba lần recovery và ngân sách phiên.

Artifact: `brain/1.11.0`, `grounded-speech/0.12.0`, `teaching-templates/0.19.0`. Không đổi API key, billing, chấm assessment, công thức mastery hoặc dữ liệu của phiên thật.

## Kiểm chứng và giới hạn

Hồi quy lấy các phát biểu/luồng trong ảnh, thay tên bằng dữ liệu tổng hợp: phép chia sai/đúng; lộ đáp án trong lời giảng lẫn câu hỏi; mục tiêu RETELL thực tế; sửa lời cô sai; ngân sách mentor/reviewer; bảo toàn đầy đủ lời đang kiểm; chuyển mã bác giữa các lần thử; không lặp bubble; chờ quota hợp lý khi mọi model bận và tiếp tục khi còn fallback.

Thử riêng bằng bản sao phiên và đúng version giáo án: chỉ đọc database gốc, các lượt mới chạy trong repository bộ nhớ. Lượt “88” đã có lời gợi mở hợp lệ với model thật; các lần khác vẫn có draft bị bác hoặc provider hết hạn mức. Kết quả chốt và giới hạn ghi trong PR. Không suy ra chất lượng cả buổi từ kiểm thử giả hoặc một lượt model thật.

[FACT] Vòng đầy đủ trước chốt độ dài phần sửa lỗi đạt **2.267 kiểm thử backend**, 37 Atlas tách khỏi vòng offline; Ruff, format và diff check xanh. 19 kiểm thử frontend liên quan state/HTTP/recovery xanh. Một lượt replay model thật cho “??” có lời nhận lỗi phép tính rồi câu hỏi nhỏ, không nêu đáp số 0,5; prompt lớn nhất 2.451 token. Replay toàn bộ nhật ký mới nhất vẫn có draft bị bác và quota, dù prompt dưới 3.000 token; không coi đó là nghiệm thu cả buổi. Các báo cáo cục bộ `retell-recovery-live-v2.json` đến `retell-recovery-live-v5.json` giữ cả lần chưa đạt/quota và lần sửa được; không chỉ chọn kết quả tốt. Số liệu CI bản chốt ghi ở PR.

## Ghi chép luận văn

29/10/2026 · TUTOR-LIVE-RECOVERY: hồi quy từ lỗi RETELL thực tế sau bản vá trước. Phân biệt lỗi lắp prompt (vượt 3.000 token), quyền giải đáp số sai và quota provider; sửa bộ biên dịch prompt, bảo vệ câu thật đã hỏi, kiểm phép toán diễn đạt bằng lời và sửa lỗi cô trước. Khôi phục giữ mã bác, chống thông báo trùng và chờ theo hạn mức đã biết. Kết quả kiểm thử cụ thể ở PR. Không có connector Google Docs, chuẩn bị mục này để cập nhật Phụ lục E.
