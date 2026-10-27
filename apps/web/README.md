# apps/web — Web app CAVAT (T09, T13)

Web app React + TypeScript + Vite cho ba vai trò: **học sinh** học với gia sư và xem tiến bộ của mình, **phụ huynh** theo dõi con, **giáo viên** xem bộ não gia sư và transcript. App chạy được ở hai chế độ: **mock API trong trình duyệt** (mặc định, không cần backend) và **API thật** của `services/api`.

## Chạy

Yêu cầu: Node ≥ 22.13 (khuyên dùng Node 22 LTS) và pnpm 10. Bật pnpm bằng `corepack enable`.

```bash
make run        # bản mới nhất ở MỘT cổng: API phục vụ luôn web đã dựng, http://localhost:8000 (database của .env, cavat_dev)
make run-memory # như trên nhưng database trong bộ nhớ: không lưu gì, Ctrl+C là mất
# (make demo và make demo-memory là tên cũ của hai lệnh này)
make web        # chỉ web, mock API trong trình duyệt, không cần backend
make web-live   # chỉ web, nối API thật; cần `make api` hoặc `make api-memory` đang chạy ở một terminal khác
make web-check  # lint + type-check + test + build, giống job `web` của CI
```

`make run` dựng web (`VITE_API=http pnpm build`, chỉ khi mã mới hơn bản dựng) rồi chạy API, API phục vụ `apps/web/dist` (ADR-035); bấm Ctrl+C là dừng. Buổi học và hội thoại được lưu, tắt rồi bật lại vẫn còn. `make run-memory` dùng database trong bộ nhớ thay vì Atlas. Khi cổng bận, đổi cổng bằng `make run PORT=8010`. Dev server (`make web`, `make web-live`) chỉ để sửa giao diện.

Hai cách chạy backend cho `make web-live`:

- `make api`: database MongoDB Atlas trong `.env` (`cavat_dev`). Buổi học được lưu lại.
- `make api-memory`: database trong bộ nhớ. Không ghi gì lên Atlas, dừng server là mất hết; dùng để thử nhanh.

Muốn Qwen diễn đạt lời gợi ý thì đặt `TUTOR_RENDERER=llm` trong `services/api/.env`; mặc định backend chỉ dùng câu mẫu.

Trong `apps/web` có thể gọi trực tiếp: `pnpm dev`, `pnpm lint`, `pnpm test`, `pnpm build`, `pnpm format`.

Thử trên tablet cùng mạng LAN: `pnpm dev --host`, rồi mở `http://<IP máy>:5173`.

## Đăng nhập (ACC-1)

Hệ thống thử nghiệm dùng đúng 3 tài khoản: 1 học sinh, 1 phụ huynh (gắn với học sinh), 1 giáo viên.

- **Tạo tài khoản:** chủ dự án chạy `make accounts`, nhập tên gọi và mã PIN.
- **Đăng nhập:** web hiện 3 tài khoản để chọn, rồi nhập PIN. Token được giữ trong `localStorage` (`cavat.auth.token`).
- **Sau khi đăng nhập:** mỗi tài khoản chỉ thấy phần của mình và có nút "Đăng xuất". Học sinh không phải nhập tên. Phụ huynh xem thẳng tình hình học của con, không cần mã.
- **Chế độ demo:** mock API và `make run-memory` (`AUTH_MODE=demo`) không có đăng nhập, mọi vai mở như trước.

## Màn hình

| Đường dẫn                                         | Người dùng | Nội dung                                                                                                                                                                                                                                                                                      |
| ------------------------------------------------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/`                                               | —          | Trang giới thiệu: vòng dạy 7 bước, khác gì chatbot, cây tri thức của chương, góc nhìn của ba vai trò                                                                                                                                                                                          |
| `/student`                                        | Học sinh   | Lời chào, "Học tiếp" buổi còn dở, bắt đầu buổi mới; khi gia sư dạy nhiều chương thì có nút chọn chương (`?chapter=`, mặc định chương đầu); tiến bộ của chương (API thật): chuỗi ngày học, bài đã qua, bản đồ chương với "Đã nắm chắc / Cần luyện thêm", tuần này, mã cho bố mẹ, "Lịch sử học" |
| `/student/sessions/:id`                           | Học sinh   | Câu hỏi, khung hội thoại, ô trả lời, nút dấu `<` `>` `=` `,`, nút "Xin gợi ý", lựa chọn nhỏ của cô, thẻ hoàn thành. Buổi học theo chương có thêm bản đồ bài học, thanh 7 bước, thẻ "Cô giảng bài", "Cô làm mẫu" và ô "con nói lại"                                                            |
| `/parent`, `/parent/:code`                        | Phụ huynh  | Nhập mã của con; xem số buổi, thời gian học, bài đã vững, chuỗi ngày học, mức hiểu từng bài bằng chữ (DI-14), việc con làm tốt và cần luyện thêm, gợi ý giúp con ở nhà, tiến bộ 4 tuần, các buổi học. Không có điểm số, không có hội thoại                                                    |
| `/teacher`                                        | Giáo viên  | Bảng theo dõi lớp: chỉ số tổng, bản đồ nhiệt học sinh × bài, lỗi sai phổ biến, học sinh cần chú ý, cả lớp theo từng bài (xem dưới)                                                                                                                                                            |
| `/teacher/students/:id`                           | Giáo viên  | Báo cáo một học sinh: đồng hồ điểm và độ tin cậy, radar, nhận định, cây tri thức, chi tiết từng bài, tiến bộ theo ngày, hoạt động học, các buổi học                                                                                                                                           |
| `/teacher/sessions`, `/teacher/sessions/:id`      | Giáo viên  | Danh sách buổi học và transcript theo từng câu: move, mức gợi ý H0–H7 và target, rule id, kết quả chấm, misconception, kết quả câu (resolution). Buổi học theo chương mở tab "Bộ não gia sư" (xem dưới)                                                                                       |
| `/teacher/lessons`, `/teacher/lessons/:chapterId` | Giáo viên  | Nội dung gia sư dạy, từng bài: lý thuyết và câu hỏi cuối (đáp án chấp nhận, lời cô đáp), phương pháp, cô làm mẫu, ý chính phần nói lại, câu hỏi theo bước với đáp án, thang gợi ý, lời giải, lỗi sai dự đoán; trạng thái duyệt và file nguồn                                                  |
| `/teacher/documents`, `/teacher/documents/:id`    | Giáo viên  | Thư viện tài liệu: tải lên (PDF, DOCX, TXT, MD, ảnh), loại và chương, danh sách, chữ đọc được (nguồn cho RAG), mở file gốc, xóa                                                                                                                                                               |

**Mỗi vai trò thấy gì về mức hiểu bài (blueprint PART 27.1):** học sinh thấy hai cụm "Đã nắm chắc / Cần luyện thêm"; phụ huynh thấy 6 mức nhận xét bằng chữ của DI-14 (Chưa học, Chưa đủ dữ liệu, Đang làm quen, Làm được khi có hỗ trợ, Tự làm được, Vững và vận dụng) và xu hướng 4 tuần; chỉ giáo viên thấy điểm M, độ tin cậy và 7 chiều đánh giá.

Quy ước hiển thị:

- Số thập phân viết kiểu Việt Nam (`0,25`). Mỗi số là một khối không ngắt dòng; "0,25 … 0,3" luôn nằm trên một dòng và chỗ trống "…" hiện thành ô gạch đứt.
- Không bao giờ sửa chữ học sinh gõ: transcript phải đúng nguyên văn. Chỉ định dạng những số do app tự in ra (`formatViDecimal`), và giờ theo `Asia/Ho_Chi_Minh`.
- Chữ vừa phải, dễ đọc trên máy tính bảng (chủ dự án góp ý 2026-10-06: chữ cũ quá to): câu hỏi 18–20 px, hội thoại 16–18 px, nút cao ≥ 44 px (cỡ chạm tối thiểu). Font Be Vietnam Pro (vẽ riêng cho dấu tiếng Việt, giấy phép OFL, tự host qua `@fontsource` nên không cần CDN).
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

Với API thật, buổi học mặc định là **buổi học theo chương** Số thập phân: gia sư dạy theo vòng 7 bước trên cây tri thức của chương (kế hoạch v1, `docs/plan/plan-v1-teaching-knowledge-graph.md`). Mock API trong trình duyệt vẫn chỉ chạy bài 1 cũ, nên muốn xem phần này thì chạy `make run`.

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

Cả hai endpoint này và `GET /v1/parents/me/child` nhận `?chapter=<chapter_id>`: không có thì trả chương đầu, chương không tồn tại thì 404. Câu trả lời có `chapter` (chương đang xem) và `chapters` (mọi chương gia sư đang dạy, chương đầu đứng đầu) để web vẽ nút chọn chương (`features/teaching/ChapterPicker.tsx`, nút cao ≥ 44 px, chỉ hiện khi có từ hai chương). Lựa chọn nằm trong URL nên tải lại trang hay gửi đường dẫn vẫn giữ nguyên. Bắt đầu buổi mới thì web gửi `lesson_id` là chương đang chọn; máy chủ từ chối chương nó không dạy, và client vẫn không bao giờ chọn model hay hoạt động (quy tắc 4). Trang giáo viên cũng giữ `?chapter=` khi đi từ bản đồ nhiệt hay danh sách cần chú ý sang báo cáo một học sinh.

Các quy ước có tính diễn giải (DI):

- **Mã cho bố mẹ** là 6 ký tự đầu của SHA-256 mã học sinh. Đây là liên kết phụ huynh tạm cho demo, chưa phải đăng nhập (chờ T12).
- **Thời gian học** (DI-29) cộng khoảng cách giữa hai sự kiện liên tiếp trong buổi học, mỗi khoảng tính tối đa 5 phút, nên lúc nghỉ lâu không bị tính thêm.
- **Ngày học** (DI-30) tính theo giờ Việt Nam, là ngày có ít nhất một lượt học sinh trả lời.
- Bài đang học nhưng chưa có bằng chứng hiện "Đang học", không hiện "Chưa học" (DI-31).

Mock API trong trình duyệt không có hai endpoint này: trang chủ học sinh chỉ hiện phần bắt đầu học, trang phụ huynh báo cần chạy `make run`.

## Bảng theo dõi của giáo viên (UI-2)

Hai endpoint chỉ đọc (`services/api/cavat/modules/session/teacher_view.py`, header `X-Demo-Teacher`). Mọi con số được tính lại từ sự kiện qua projector điểm từng bài (quy tắc 3).

- `GET /v1/teachers/class` trả về:
  - bản đồ nhiệt học sinh × bài;
  - cả lớp theo từng bài;
  - lỗi sai phổ biến;
  - chỉ số tổng;
  - lý do cần chú ý của từng em.
- `GET /v1/teachers/students/{id}` trả về:
  - điểm tổng, phủ kiến thức và các chiều;
  - từng bài chi tiết;
  - dòng thời gian, tốc độ học, hoạt động theo ngày;
  - danh sách buổi học.

Mỗi biểu đồ bám một mục của khung đánh giá Toán:

| Biểu đồ                                                                                                   | Khung Toán | Ở đâu            |
| --------------------------------------------------------------------------------------------------------- | ---------- | ---------------- |
| Bản đồ nhiệt học sinh × bài, 5 vùng màu (90–100 xanh đậm, 75–89 xanh, 60–74 vàng, 40–59 cam, 0–39 đỏ)     | §46, §25   | Lớp học          |
| Cả lớp theo từng bài (hàng cuối bản đồ nhiệt và biểu đồ thanh)                                            | §45        | Lớp học          |
| Lỗi sai phổ biến: tỉ lệ, số lần, lỗi tái diễn nhiều nhất trong 14 ngày, mức độ                            | §28        | Lớp học          |
| Đồng hồ điểm M kèm thanh độ tin cậy                                                                       | §56.1, §21 | Báo cáo học sinh |
| Radar 6 trục: Kiến thức (C), Lập luận, Vận dụng, Chuyển giao, Tự làm, Ghi nhớ                             | §24        | Báo cáo học sinh |
| Nhận định: điểm mạnh, điểm yếu, rủi ro, nhóm ✓ ⚠ ✕                                                        | §23, §43   | Báo cáo học sinh |
| Cây tri thức có vạch màu vùng điểm                                                                        | §26        | Báo cáo học sinh |
| Chi tiết một bài: M, độ tin cậy, mức, các chiều, số câu, gợi ý, thời gian, lỗi sai, xu hướng, khuyến nghị | §57, DI-8  | Báo cáo học sinh |
| Tiến bộ theo ngày và tốc độ học                                                                           | §27, §39   | Báo cáo học sinh |
| Hoạt động học theo ngày: câu tự làm, nhờ gợi ý, cần làm mẫu, chưa giải quyết                              | §56        | Báo cáo học sinh |

Quy ước hiển thị:

- **Độ tin cậy thấp:** ô có độ tin cậy dưới 30 vẫn hiện số cho giáo viên nhưng có gạch chéo và dấu "?" (DI-7, PART 27.3).
- **Số trong ô:** số trong ô bản đồ nhiệt được làm tròn xuống, nên luôn nằm trong khoảng của vùng màu; số chính xác có trong chú thích của ô.
- **Không dùng màu một mình:** mỗi màu luôn đi kèm số hoặc chữ.
- **Các ngưỡng tự đặt:** những ngưỡng không có trong khung là DI-20 đến DI-28, ghi trong mục 9 của `docs/plan/plan-v1-teaching-knowledge-graph.md`.

Mock API không có hai endpoint này: trang "Lớp học" báo cần chạy `make run` và dẫn sang "Buổi học".

## Tài liệu của giáo viên (DOC-1)

Giáo viên là nguồn của nội dung (ADR-020). Tài liệu tải lên được xử lý như sau:

- **Lưu:** file gốc ghi vào `var/storage/documents/<id>/` (gitignore); thông tin và chữ đọc được lưu ở collection `documents`.
- **Đọc chữ:** ngay khi tải lên (`services/api/cavat/modules/library/extract.py`):
  - PDF có lớp chữ: dùng pypdf;
  - DOCX: đọc XML bằng thư viện chuẩn;
  - TXT, MD: đọc trực tiếp;
  - ảnh và PDF dạng scan: OCR bằng Gemini nếu có khóa, nếu không thì đánh dấu "Cần đọc ảnh (OCR)".
- **Đánh trang:** mỗi trang mở đầu bằng "[Trang n]" để đoạn truy xuất sau này ghi được nguồn.
- **Giới hạn:** tối đa 25 MB một file.
- **Dùng cho RAG:** chữ đọc được là nguồn của Hybrid RAG (RAG-1).

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


## Hình minh họa (FIG-1, ADR-037)

Màn học hiển thị ảnh đã trích từ tài liệu, gồm cả hình chung cho các câu nhỏ. Ảnh dùng API cùng cổng, có đăng nhập. Chưa có ảnh hoặc tải ảnh lỗi thì giữ mô tả để học sinh không mất dữ kiện; có thể thử tải lại. Trang nội dung bài và trang duyệt phương án có mục Hình minh họa để giáo viên duyệt/bỏ/thay, độc lập với duyệt chữ.

Công cụ nội dung: `make figures DRY=1` tạo gallery chỉ đọc; `make figures` nhập các hình đã kiểm. Không chạy tự động khi ứng dụng khởi động. Gói chuyển DB/storage của ADR-036 mang theo cả hình; không cần xuất bản lại kế hoạch.
