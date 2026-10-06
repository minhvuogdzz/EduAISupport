# apps/web — Web app CAVAT (T09, T13)

Web app React + TypeScript + Vite cho ba vai trò: **học sinh** học với gia sư và xem tiến bộ của mình, **phụ huynh** theo dõi con, **giáo viên** xem bộ não gia sư và transcript. App chạy được ở hai chế độ: **mock API trong trình duyệt** (mặc định, không cần backend) và **API thật** của `services/api`.

## Chạy

Yêu cầu: Node ≥ 22.13 (khuyên dùng Node 22 LTS) và pnpm 10. Bật pnpm bằng `corepack enable`.

```bash
make demo        # một lệnh cho cả bản demo: API (lưu vào database của .env, cavat_dev) + web ở http://localhost:5173
make demo-memory # như trên nhưng database trong bộ nhớ: không lưu gì, Ctrl+C là mất
make web        # chỉ web, mock API trong trình duyệt, không cần backend
make web-live   # chỉ web, nối API thật; cần `make api` hoặc `make api-memory` đang chạy ở một terminal khác
make web-check  # lint + type-check + test + build, giống job `web` của CI
```

`make demo` chạy API (database của `services/api/.env`, tức `cavat_dev`) và `make web-live` trong cùng một terminal; bấm Ctrl+C là dừng cả hai. Buổi học và hội thoại được lưu, tắt rồi bật lại vẫn còn. `make demo-memory` dùng database trong bộ nhớ thay vì Atlas. Mỗi lệnh chạy server chiếm một terminal cho tới khi dừng, nên `make api` và `make web-live` phải nằm ở hai tab khác nhau. Khi cổng bận, đổi cổng bằng `make demo API_PORT=8010 WEB_PORT=5183`.

Hai cách chạy backend cho `make web-live`:

- `make api`: database MongoDB Atlas trong `.env` (`cavat_dev`). Buổi học được lưu lại.
- `make api-memory`: database trong bộ nhớ. Không ghi gì lên Atlas, dừng server là mất hết; dùng để thử nhanh.

Muốn Qwen diễn đạt lời gợi ý thì đặt `TUTOR_RENDERER=llm` trong `services/api/.env`; mặc định backend chỉ dùng câu mẫu.

Trong `apps/web` có thể gọi trực tiếp: `pnpm dev`, `pnpm lint`, `pnpm test`, `pnpm build`, `pnpm format`.

Thử trên tablet cùng mạng LAN: `pnpm dev --host`, rồi mở `http://<IP máy>:5173`.

## Màn hình

| Đường dẫn                           | Người dùng | Nội dung                                                                                                                                                                                                                                   |
| ----------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `/`                                 | —          | Trang giới thiệu: vòng dạy 7 bước, khác gì chatbot, cây tri thức của chương, góc nhìn của ba vai trò                                                                                                                                       |
| `/student`                          | Học sinh   | Lời chào, "Học tiếp" buổi còn dở, bắt đầu buổi mới; tiến bộ của chương (API thật): chuỗi ngày học, bài đã qua, bản đồ chương với "Đã nắm chắc / Cần luyện thêm", tuần này, mã cho bố mẹ, "Lịch sử học"                                     |
| `/student/sessions/:id`             | Học sinh   | Câu hỏi, khung hội thoại, ô trả lời, nút dấu `<` `>` `=` `,`, nút "Xin gợi ý", lựa chọn nhỏ của cô, thẻ hoàn thành. Buổi học theo chương có thêm bản đồ bài học, thanh 7 bước, thẻ "Cô giảng bài", "Cô làm mẫu" và ô "con nói lại"         |
| `/parent`, `/parent/:code`          | Phụ huynh  | Nhập mã của con; xem số buổi, thời gian học, bài đã vững, chuỗi ngày học, mức hiểu từng bài bằng chữ (DI-14), việc con làm tốt và cần luyện thêm, gợi ý giúp con ở nhà, tiến bộ 4 tuần, các buổi học. Không có điểm số, không có hội thoại |
| `/teacher`, `/teacher/sessions/:id` | Giáo viên  | Danh sách buổi học và transcript theo từng câu: move, mức gợi ý H0–H7 và target, rule id, kết quả chấm, misconception, kết quả câu (resolution). Buổi học theo chương mở tab "Bộ não gia sư" (xem dưới)                                    |

**Mỗi vai trò thấy gì về mức hiểu bài (blueprint PART 27.1):** học sinh thấy hai cụm "Đã nắm chắc / Cần luyện thêm"; phụ huynh thấy 6 mức nhận xét bằng chữ của DI-14 (Chưa học, Chưa đủ dữ liệu, Đang làm quen, Làm được khi có hỗ trợ, Tự làm được, Vững và vận dụng) và xu hướng 4 tuần; chỉ giáo viên thấy điểm M, độ tin cậy và 7 chiều đánh giá.

Quy ước hiển thị:

- Số thập phân viết kiểu Việt Nam (`0,25`). Mỗi số là một khối không ngắt dòng; "0,25 … 0,3" luôn nằm trên một dòng và chỗ trống "…" hiện thành ô gạch đứt.
- Không bao giờ sửa chữ học sinh gõ: transcript phải đúng nguyên văn. Chỉ định dạng những số do app tự in ra (`formatViDecimal`), và giờ theo `Asia/Ho_Chi_Minh`.
- Chữ to cho trẻ 10–11 tuổi: câu hỏi 24–30 px, hội thoại 20 px, nút cao ≥ 56 px. Font Be Vietnam Pro (vẽ riêng cho dấu tiếng Việt, giấy phép OFL, tự host qua `@fontsource` nên không cần CDN).
- Giao diện (UI-1): màu thương hiệu xanh ngọc (`brand-*`) và vàng ấm (`gold`, `gold-soft`) khai báo trong `@theme` của `src/index.css`; thẻ `.card` bo tròn, viền vàng nhạt; nền `.brand-gradient` cho phần đầu trang. Linh vật là con cò quàng khăn xanh tự vẽ (`components/Mascot.tsx`), có 5 tâm trạng. Mọi trang trừ màn học dùng chung `components/AppShell.tsx` (thanh vai trò, chân trang).
- Biểu đồ tự vẽ bằng SVG, không dùng thư viện: chiều rộng đo bằng `lib/useElementWidth.ts` nên chữ không bị kéo giãn; mỗi biểu đồ có tên cho trình đọc màn hình và một danh sách ẩn nói cùng nội dung.
- Trên tablet: bấm nút dấu không làm bật bàn phím ảo; Enter để gửi, Shift+Enter xuống dòng, không gửi khi bộ gõ (Telex, VNI) đang ghép chữ.
- Ẩn hoặc khóa nút chỉ là UX. Backend (và mock) vẫn từ chối lệnh không hợp lệ bằng 409 (CLAUDE.md, quy tắc 4).

## Cấu trúc

```text
src/
  api/contract.ts    Kiểu dữ liệu của session API (PART 29, 10.3, 24.2), viết tay tới khi T08 có OpenAPI
  api/client.ts      Interface SessionApi: màn hình chỉ nói chuyện với interface này; ApiError
  api/http/          SessionApi qua HTTP tới services/api (xem mục "API thật")
  api/index.ts       Chọn mock hay HTTP lúc build theo biến VITE_API
  api/mock/          Mock API chạy trong trình duyệt (xem mục dưới)
  features/student/  Màn hình học sinh; tutorSession.ts là reducer ghép snapshot với stream
  features/parent/   Trang phụ huynh và biểu đồ tiến bộ 4 tuần
  features/teacher/  Màn hình giáo viên
  features/teaching/ Bản đồ bài học (cây tri thức) và thanh 7 bước, dùng chung
  pages/             Trang giới thiệu, trang 404
  components/, lib/  AppShell, Mascot, MathText, nhãn tiếng Việt, định dạng số và giờ vi-VN, id
vite-plugins/        Plugin đưa lesson.yaml vào mock và niêm phong câu EXIT lúc build
```

Một lượt: màn hình gửi command (header `Idempotency-Key`, body có `expected_state_version`), nhận ack, rồi nhận `tutor.delta`… `tutor.final` và `state` qua stream. Khung hội thoại chỉ hiện những gì server đã xác nhận, cộng dòng "Đang gửi…" của học sinh. Gặp 409 thì đọc lại `GET /state` và giữ nguyên chữ học sinh đã gõ.

Test (`pnpm test`, Vitest + Testing Library): enum của contract khớp `services/api/cavat/core/pedagogy.py`, câu EXIT bị niêm phong, bộ chấm và vòng item của mock, các kiểm tra 409 và idempotency, reducer, màn hình học sinh, phụ huynh và giáo viên.

## Buổi học theo chương (M1-7)

Với API thật, buổi học mặc định là **buổi học theo chương** Số thập phân: gia sư dạy theo vòng 7 bước trên cây tri thức của chương (kế hoạch v1, `docs/plan/plan-v1-teaching-knowledge-graph.md`). Mock API trong trình duyệt vẫn chỉ chạy bài 1 cũ, nên muốn xem phần này thì chạy `make demo`.

- **Lịch sử hội thoại:** mỗi buổi học là một document trên database, giữ toàn bộ hội thoại. Trang học sinh có mục "Lịch sử học" (`GET /v1/sessions/mine`): mở lại buổi đã xong để xem lại, buổi chưa xong thì học tiếp đúng chỗ cũ. Giáo viên xem mọi buổi ở trang giáo viên.
- **Học tiếp qua nhiều buổi:** buổi mới của cùng học sinh đọc lại sự kiện các buổi trước của chương. Bài đã qua vẫn là đã qua, điểm được cộng dồn, và gia sư vào bài tiếp theo bằng một câu ôn bài nền. Báo cáo giáo viên ghi số buổi trước và đánh dấu bằng chứng "buổi trước".

- **Học sinh:** `state.teaching` (contract.ts, `TeachingView`) mang bản đồ node (trạng thái và mức hiểu bằng chữ, không có điểm số), bước hiện tại của vòng dạy và câu hỏi cô đang chờ trả lời. Lời trả lời gửi qua `POST /responses` với `item_attempt_id` = `teaching.input_id`. Lời giảng và bài cô làm mẫu là `ChatTurn.kind` (`THEORY`, `EXAMPLE`...) và hiện thành thẻ riêng.
- **Giáo viên:** tab "Bộ não gia sư" đọc `GET /v1/sessions/{id}/report` (`TeachingReport`), tự cập nhật 3 giây một lần khi buổi học đang diễn ra. Nội dung:
  - cây tri thức có điểm M từng bài (bấm vào một bài để xem chi tiết);
  - điểm M qua từng lượt so với ngưỡng qua bài;
  - 7 chiều đánh giá và lượng bằng chứng của từng chiều;
  - điều kiện qua bài (DI-15) và phần còn thiếu;
  - bảng bằng chứng cộng/trừ điểm kèm lý do;
  - mọi quyết định của chính sách dạy kèm mã luật `N-*`.

  Tất cả được tính lại từ sự kiện của buổi học.

## Tiến bộ của học sinh và trang phụ huynh (UI-1)

Hai endpoint đọc mọi buổi học theo chương của một học sinh và trả lời bằng chữ, không có điểm số (`services/api/cavat/modules/session/progress.py`):

- `GET /v1/students/me/overview` (header `X-Demo-Student`): bài đã qua, mức hiểu từng bài, số buổi, thời gian học, ngày học, chuỗi ngày học, tuần này, việc làm tốt và cần luyện thêm, mã cho bố mẹ.
- `GET /v1/parents/children/{code}` (header `X-Demo-Parent`): như trên, thêm xu hướng 28 ngày, gợi ý giúp con ở nhà (`home_tip` của từng bài trong `chapter.yaml`, bản nháp chờ duyệt) và danh sách buổi học. Mã sai trả 404.

Các quy ước có tính diễn giải (DI):

- **Mã cho bố mẹ** là 6 ký tự đầu của SHA-256 mã học sinh. Đây là liên kết phụ huynh tạm cho demo, chưa phải đăng nhập (chờ T12).
- **Thời gian học** cộng khoảng cách giữa hai sự kiện liên tiếp trong buổi học, mỗi khoảng tính tối đa 5 phút, nên lúc nghỉ lâu không bị tính thêm.
- **Ngày học** tính theo giờ Việt Nam, là ngày có ít nhất một lượt học sinh trả lời.
- Bài đang học nhưng chưa có bằng chứng hiện "Đang học", không hiện "Chưa học".

Mock API trong trình duyệt không có hai endpoint này: trang chủ học sinh chỉ hiện phần bắt đầu học, trang phụ huynh báo cần chạy `make demo`.

## Mock API

- Đóng đúng vai server: kiểm tra SessionContext (lifecycle, item hiện tại, `state_version`, `allowed_commands`), idempotency key, ghi state và event của một buổi học thành một khối (CLAUDE.md, quy tắc 10), stream lời tutor từng chữ.
- Kế hoạch buổi học tối giản của T08 trên 8 câu của bài 1: CONCEPT_CHECK (CC-01, CC-02) → GUIDED_PRACTICE (GP-01, GP-02, GP-08, GP-09) → EXIT_ASSESSMENT (EX-01, EX-03) → SUMMARY.
- **Không phải tutor thật.** Bộ chấm (`checker.ts`) và vòng item (`engine.ts`) chỉ là bản rút gọn để màn hình chạy được. Câu chữ riêng của mock (`phrases.ts`) là câu mẫu, chưa phải nội dung sư phạm đã duyệt. Rule id bắt đầu bằng `MOCK-` là hành vi chỉ có trong mock. Policy (T02), renderer (T03) và item loop (T04) thật nằm ở backend.
- **Bundle không chứa đáp án câu EXIT:** plugin `vite-plugins/mockLesson.ts` chỉ giữ loại câu trả lời và nhãn lựa chọn của câu EXIT; mock ghi nhận câu trả lời EXIT mà không chấm. Câu luyện tập vẫn có đáp án trong bundle vì mock cần để chấm, nên **bản build hiện tại chỉ dùng để thử nghiệm**.
- Dữ liệu nằm trong `localStorage` của trình duyệt: tab học sinh và tab giáo viên trên cùng máy thấy cùng dữ liệu, tải lại trang thì buổi học tiếp tục đúng chỗ. Lần đầu mở có sẵn 2 buổi mẫu (Minh đã xong, Lan đang học). Nút "Tạo lại dữ liệu demo" ở trang giáo viên xóa và tạo lại.

## API thật (T13)

`make web-live` đặt `VITE_API=http` lúc build, khi đó `src/api/index.ts` dùng `createHttpApi` (`src/api/http/httpApi.ts`) thay cho mock. Dev server chuyển tiếp `/v1` tới `http://127.0.0.1:8000` (`vite.config.ts`; đổi cổng bằng biến `CAVAT_API_PORT`); nếu API ở địa chỉ khác thì đặt `VITE_API_URL`.

- **Danh tính tạm (chờ T12):** mỗi trình duyệt tự sinh một mã học sinh, lưu ở `localStorage` (`cavat.demo.student-id`) và gửi qua header `X-Demo-Student`. Màn hình giáo viên gửi `X-Demo-Teacher`. Đây chưa phải đăng nhập.
- **Chưa có SSE:** backend chưa có `GET /v1/sessions/{id}/stream`. Sau mỗi lệnh, client đọc `GET /state` rồi tự phát `tutor.delta` … `tutor.final` và `state` cho màn hình, đúng thứ tự mà stream thật sẽ dùng. Khi có SSE chỉ cần đổi trong `httpApi.ts`.
- **Lỗi:** body `{ "error": { "code", "message", "details" } }` thành `ApiError`; lỗi khác (API chưa chạy, proxy trả 502) thành lỗi thường và màn hình báo "Chưa gửi được".
- **Bản build cho API thật không chứa mock và đáp án:** mock chỉ được import động khi dùng mock. Đã kiểm tra bundle của `VITE_API=http pnpm build` không có chuỗi nào của mock.
- **Transcript của giáo viên** có thêm nhãn "AI diễn đạt" ở lượt do LLM viết lời (nước đi vẫn do policy chọn) và "Câu dự phòng" khi cả LLM lẫn câu mẫu không qua bộ kiểm tra.

Đã chạy tay (2026-10-01): một buổi học 8 câu từ trình duyệt tới API với Qwen thật, gồm trả lời sai, xin gợi ý và chọn "Cho con gợi ý", câu hỏi tách nguyên nhân ở GP-08, hỏi "vì sao", tổng kết, rồi xem danh sách và transcript ở màn hình giáo viên.

Còn thiếu:

- `src/api/contract.ts` vẫn viết tay, chưa sinh từ OpenAPI của FastAPI.
- SSE, đăng nhập thật, ghi audit khi giáo viên xem transcript, lọc danh sách buổi học theo lớp.

Các giả định trước đây của web app, nay backend đã làm theo:

- Mọi command đổi state, kể cả `/hint-requests` và `/choices`, đều mang `expected_state_version`.
- `SessionState` có `allowed_commands`, `pending_choice`, `item.expecting`, `item.answer_format` và `item.options` (không kèm đúng/sai).
- Lựa chọn sau OFFER_CHOICE đi qua `POST /choices`. Backend dùng hai lựa chọn `HINT` ("Cho con gợi ý") và `RETRY` ("Con tự thử lại"); mock vẫn dùng SMALL/EXAMPLE.
- `Idempotency-Key` được kiểm tra trước các kiểm tra khác, để lệnh gửi lại nhận đúng kết quả cũ thay vì 409.
- Giáo viên có `GET /v1/sessions` và `GET /v1/sessions/{id}/transcript`.
- Lựa chọn của học sinh được ghi bằng event `CHOICE_MADE`.
