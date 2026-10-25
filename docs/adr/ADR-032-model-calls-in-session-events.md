# ADR-032: Ghi mỗi lần gọi model vào sự kiện của buổi học (CFG-2)

**Trạng thái:** Đã làm, 2026-10-25.
- Chủ dự án yêu cầu (2026-10-25):
  - phát `MODEL_FALLBACK` khi chuỗi chuyển sang gpt-oss;
  - lưu số token thật của mỗi lần gọi;
  - đo lại ước lượng 3 ký tự/token trên prompt thật của gia sư.
- Code:
  - ghi lần gọi: `ai_gateway/router.py` (`RecordingRouter`, `ChatCall`);
  - sự kiện: `core/events.py` (`ModelCalled`, `ModelFallback`), `session/model_calls.py`;
  - nối vào buổi học: `session/api.py`;
  - bản nháp của giáo viên: `ingest/drafting.py`;
  - đo: `scripts/simulate_learner.py --measure`.
- Liên quan: ADR-017 (vai trò model, chuỗi dự phòng), quy tắc 3 và 10 của CLAUDE.md, blueprint PART 11 và 12.6.

## Bối cảnh

- Trước CFG-2, buổi học không ghi lại model nào đã viết lời gia sư, cũng không ghi Groq tính bao nhiêu token.
- Sự kiện `MODEL_FALLBACK` đã có trong danh sách sự kiện (blueprint PART 12.6: "chuyển sang model kế tiếp và ghi `MODEL_FALLBACK`"), nhưng chưa code nào phát ra. Lần đo EVAL-4 (2026-10-24) còn cho thấy nhãn model trong báo cáo có thể sai mà không ai biết (đã sửa ở CFG-1).
- Vì vậy các con số sau chỉ dựa trên ước lượng 3 ký tự/token [ASSUME], chưa được đo:
  - trần 3.000 token mỗi lần gọi;
  - hạn mức 8.000 token/phút;
  - "6–7 buổi dùng LLM mỗi ngày".
- Blueprint PART 11 định ghi lần gọi vào một bảng `ai_request_log`. Atlas M0 không có transaction nhiều document, nên trạng thái và sự kiện của một buổi học nằm trong một document (quy tắc 10). Một bảng riêng sẽ phải ghi tách khỏi buổi học, và có thể lệch với nó.

## Quyết định

1. **Bọc router theo từng lệnh.** Mỗi lệnh của học sinh dùng một `RecordingRouter` bọc router dùng chung. Router dùng chung vẫn nhớ model nào hết hạn mức. `RecordingRouter` giữ lại mọi lần `chat` của lệnh: kết quả, ước lượng của gateway, số ký tự của lời nhắn và của schema.
2. **Ghi hai loại sự kiện.** Sau các sự kiện khác của lệnh, buổi học ghi thêm:
   - **`MODEL_CALLED`** cho mỗi lần gọi đã vào chuỗi model. Sự kiện ghi:
     - mục đích, tức tên schema: `tutor_turn`, `reading`, `move_choice`, `grounded_turn`;
     - model đã trả lời, hoặc lý do không model nào trả lời;
     - từng lần thử;
     - số token Groq tính (prompt và completion);
     - ước lượng của gateway;
     - số ký tự.
   - **`MODEL_FALLBACK`** cho mỗi bước xuống chuỗi, ví dụ Qwen → gpt-oss. Lý do là `QUOTA`, `UNAVAILABLE` hoặc `INVALID_OUTPUT`.
   - Lần gọi chưa tới model nào thì không để lại sự kiện, ví dụ khi trần 15 lần gọi của buổi đã hết.
   - Lời nhắn bị từ chối trước khi gửi vì quá dài vẫn có `MODEL_CALLED` (`prompt_too_long`), nhưng không có `MODEL_FALLBACK`.
3. **Cùng document, không phát lại.** Hai sự kiện này nằm trong document của buổi học và được ghi cùng lần với các sự kiện khác (atomic). Chúng không bao giờ được phát lại (replay). Màn hình học sinh và giáo viên bỏ qua chúng.
4. **Bản nháp của giáo viên** (INGEST-3b, ngoài buổi học) ghi số token vào bộ đệm của từng bản nháp.

## Hệ quả

- Từ sự kiện của buổi học biết được:
  - lượt nào gpt-oss viết thay Qwen, và vì sao;
  - chi phí token thật của mỗi buổi.
- Ước lượng token đo lại được trên prompt thật. Kết quả nằm ở `docs/poc/free-tier-quota.md`, mục "Token thật của prompt gia sư".
- Sự kiện chỉ chứa tên model, số đếm và nhãn lý do. Không có prompt, không có lời của con.
- Các lời gọi ngoài buổi học chưa được ghi theo cách này: đọc ảnh, tạo vector, bài đo.
