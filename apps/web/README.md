# apps/web — Web app CAVAT (T09)

Khung web app React + TypeScript + Vite cho hai màn hình của vertical slice: **học sinh** học một buổi với tutor, **giáo viên** xem transcript. Vì session API (T08) chưa có, app đang chạy bằng **mock API trong trình duyệt**.

## Chạy

Yêu cầu: Node ≥ 22.13 (khuyên dùng Node 22 LTS) và pnpm 10. Bật pnpm bằng `corepack enable`.

```bash
make web        # cài dependency theo lockfile, mở dev server ở http://localhost:5173
make web-check  # lint + type-check + test + build, giống job `web` của CI
```

Trong `apps/web` có thể gọi trực tiếp: `pnpm dev`, `pnpm lint`, `pnpm test`, `pnpm build`, `pnpm format`.

Thử trên tablet cùng mạng LAN: `pnpm dev --host`, rồi mở `http://<IP máy>:5173`.

## Màn hình

| Đường dẫn                           | Người dùng | Nội dung                                                                                                                                        |
| ----------------------------------- | ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `/`                                 | —          | Chọn vai trò                                                                                                                                    |
| `/student`                          | Học sinh   | Nhập tên gọi để tạo buổi học demo; nút "Học tiếp" nếu buổi trước trên máy này còn dở                                                            |
| `/student/sessions/:id`             | Học sinh   | Câu hỏi, khung hội thoại, ô trả lời, nút dấu `<` `>` `=` `,`, nút "Xin gợi ý", lựa chọn nhỏ của cô, thẻ hoàn thành                              |
| `/teacher`, `/teacher/sessions/:id` | Giáo viên  | Danh sách buổi học và transcript theo từng câu: move, mức gợi ý H0–H7 và target, rule id, kết quả chấm, misconception, kết quả câu (resolution) |

Quy ước hiển thị:

- Số thập phân viết kiểu Việt Nam (`0,25`). Mỗi số là một khối không ngắt dòng; "0,25 … 0,3" luôn nằm trên một dòng và chỗ trống "…" hiện thành ô gạch đứt.
- Không bao giờ sửa chữ học sinh gõ: transcript phải đúng nguyên văn. Chỉ định dạng những số do app tự in ra (`formatViDecimal`), và giờ theo `Asia/Ho_Chi_Minh`.
- Chữ to cho trẻ 10–11 tuổi: câu hỏi 24–30 px, hội thoại 20 px, nút cao ≥ 56 px. Font Lexend (thiết kế cho đọc dễ, có bộ chữ tiếng Việt, tự host nên không cần CDN).
- Trên tablet: bấm nút dấu không làm bật bàn phím ảo; Enter để gửi, Shift+Enter xuống dòng, không gửi khi bộ gõ (Telex, VNI) đang ghép chữ.
- Ẩn hoặc khóa nút chỉ là UX. Backend (và mock) vẫn từ chối lệnh không hợp lệ bằng 409 (CLAUDE.md, quy tắc 4).

## Cấu trúc

```text
src/
  api/contract.ts    Kiểu dữ liệu của session API (PART 29, 10.3, 24.2), viết tay tới khi T08 có OpenAPI
  api/client.ts      Interface SessionApi: màn hình chỉ nói chuyện với interface này; ApiError
  api/mock/          Mock API chạy trong trình duyệt (xem mục dưới)
  features/student/  Màn hình học sinh; tutorSession.ts là reducer ghép snapshot với stream
  features/teacher/  Màn hình giáo viên
  components/, lib/  MathText, nhãn tiếng Việt, định dạng số và giờ vi-VN, id
vite-plugins/        Plugin đưa lesson.yaml vào mock và niêm phong câu EXIT lúc build
```

Một lượt: màn hình gửi command (header `Idempotency-Key`, body có `expected_state_version`), nhận ack, rồi nhận `tutor.delta`… `tutor.final` và `state` qua stream. Khung hội thoại chỉ hiện những gì server đã xác nhận, cộng dòng "Đang gửi…" của học sinh. Gặp 409 thì đọc lại `GET /state` và giữ nguyên chữ học sinh đã gõ.

Test (`pnpm test`, Vitest + Testing Library): enum của contract khớp `services/api/cavat/core/pedagogy.py`, câu EXIT bị niêm phong, bộ chấm và vòng item của mock, các kiểm tra 409 và idempotency, reducer, màn hình học sinh và giáo viên.

## Mock API

- Đóng đúng vai server: kiểm tra SessionContext (lifecycle, item hiện tại, `state_version`, `allowed_commands`), idempotency key, ghi state và event của một buổi học thành một khối (CLAUDE.md, quy tắc 10), stream lời tutor từng chữ.
- Kế hoạch buổi học tối giản của T08 trên 8 câu của bài 1: CONCEPT_CHECK (CC-01, CC-02) → GUIDED_PRACTICE (GP-01, GP-02, GP-08, GP-09) → EXIT_ASSESSMENT (EX-01, EX-03) → SUMMARY.
- **Không phải tutor thật.** Bộ chấm (`checker.ts`) và vòng item (`engine.ts`) chỉ là bản rút gọn để màn hình chạy được. Câu chữ riêng của mock (`phrases.ts`) là câu mẫu, chưa phải nội dung sư phạm đã duyệt. Rule id bắt đầu bằng `MOCK-` là hành vi chỉ có trong mock. Policy (T02), renderer (T03) và item loop (T04) thật nằm ở backend.
- **Bundle không chứa đáp án câu EXIT:** plugin `vite-plugins/mockLesson.ts` chỉ giữ loại câu trả lời và nhãn lựa chọn của câu EXIT; mock ghi nhận câu trả lời EXIT mà không chấm. Câu luyện tập vẫn có đáp án trong bundle vì mock cần để chấm, nên **bản build hiện tại chỉ dùng để thử nghiệm**.
- Dữ liệu nằm trong `localStorage` của trình duyệt: tab học sinh và tab giáo viên trên cùng máy thấy cùng dữ liệu, tải lại trang thì buổi học tiếp tục đúng chỗ. Lần đầu mở có sẵn 2 buổi mẫu (Minh đã xong, Lan đang học). Nút "Tạo lại dữ liệu demo" ở trang giáo viên xóa và tạo lại.

## Nối API thật (sau T08)

1. Sinh kiểu TypeScript từ OpenAPI của FastAPI (ví dụ `openapi-typescript`) và thay dần `src/api/contract.ts`.
2. Viết `HttpSessionApi` implement `SessionApi`: `fetch` cho command, `EventSource` cho `/stream`, lỗi `{ "error": { "code", "message", "details" } }` thành `ApiError`. Chọn giữa mock và HTTP bằng biến môi trường trong `src/api/index.ts`; thêm `server.proxy` cho `/v1` trong `vite.config.ts`.
3. Chỉ import mock khi dùng mock (dynamic import), để bản build thật không mang theo đáp án câu luyện tập.

Những điểm web app đang giả định, cần T08 xác nhận hoặc đổi:

- Mọi command đổi state, kể cả `/hint-requests` và `/choices`, đều mang `expected_state_version` (PART 29.1). PART 29.2 mới ghi trường này cho `/responses`.
- `SessionState` có `allowed_commands`, `pending_choice`, `item.expecting` (ANSWER hoặc EXPLANATION), `item.answer_format` và `item.options` (không kèm đúng/sai).
- Lựa chọn SMALL/EXAMPLE sau OFFER_CHOICE đi qua `POST /choices`.
- `Idempotency-Key` được kiểm tra trước các kiểm tra khác, để lệnh gửi lại nhận đúng kết quả cũ thay vì 409.
- Giáo viên cần endpoint danh sách buổi học (chưa có trong PART 29), ví dụ `GET /v1/sessions?class_id=…`.
- Micro choice cần một event type: PART 24.3 nói lựa chọn được ghi event nhưng PART 10.4 chưa có; mock tạm dùng `CHOICE_MADE`.
