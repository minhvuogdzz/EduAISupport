# ADR-059: Vòng dạy 6 bước, gộp "ôn bài nền" và "giảng bài" (CYCLE-1)

Ngày: 09/11/2026 · DI-105
Chủ dự án (giáo viên kiểm soát đặc tả sư phạm) yêu cầu gộp bước 1 "Ôn bài nền" và bước 2 "Giảng bài" của vòng dạy 7 bước (ADR-018, kế hoạch v1 mục 5.2) thành một bước "Ôn và giảng bài nền", để vòng còn 6 bước, và sửa cả hệ thống lẫn giao diện.

## Quyết định

Vòng dạy có 6 bước:

| Bước | Tên cho học sinh | Hành động của chính sách |
|---|---|---|
| 1 | Ôn và giảng bài nền | `WARMUP_ITEM`, `RECALL_PRIOR`, `TEACH_THEORY` |
| 2 | Kiểm tra hiểu | `CHECK_ITEM`, `ASK_RETELL` |
| 3 | Học cách làm | `SHOW_WORKED_EXAMPLE`, `COMPLETION_ITEM` |
| 4 | Luyện tập | `PRACTICE_ITEM` |
| 5 | Vận dụng | `TRANSFER_ITEM` |
| 6 | Qua bài | `REVIEW_ITEM`, `PASS_NODE`, `STOP_NODE` |

**DI-105 (cách đếm bước):** "ôn nền và giảng" là một bước vì với học sinh đó là một mạch: nhắc điều đã biết rồi nối sang điều mới. Hai khung đánh giá không quy định số bước của vòng dạy, nên đây là một diễn giải khai báo.

## Cái đổi

- **Backend:** `STEP_OF` (`session/chapter_service.py`) đánh số lại theo bảng trên; hợp đồng `teaching.step` nay là 1–6. Chú thích `TeachAction` và docstring nhắc "bước 3" của phần con nói lại đổi theo.
- **Phiên đã lưu:** activity của phiên lưu `step_scheme` (hiện là 2). Phiên lưu trước đó không có trường này, nên khi dựng view `current_step` chuyển số cũ sang số mới (1→1, 2→1, 3→2, 4→3, 5→4, 6→5, 7→6). Một phiên đang dở qua ngày đổi vẫn hiện đúng bước. Không migration, không ghi vào database.
- **Web:** `TEACHING_STEPS` còn 6 tên, nhãn thẻ câu hỏi theo bước (`ITEM_STEP_LABEL`), thanh bước, trang chủ (vòng 6 bước), README.
- **Tài liệu:** kế hoạch v1 mục 5.2, ADR-018, blueprint `00-START-HERE`, `CLAUDE.md`, bài báo `05-socratic.tex`. Các ADR trước (039, 040, 041, 044) nói "giữ vòng 7 bước" là bản ghi đúng thời điểm của chúng, không sửa.

## Giữ nguyên

Luật `N-*` và thứ tự quyết định của chính sách dạy, đồ thị, giáo án xuất bản, prompt (`constitution`, `listener`), công thức và ngưỡng mastery, nhãn `activity` của sự kiện, các `TeachAction` và event đã ghi. Vì không đổi prompt, chính sách hay mastery nên không cần chạy lại eval regression của quy tắc 7. `activity_id` của câu hỏi trong sự kiện mới mang số bước theo cách đếm mới (`node:step`); đó chỉ là nhãn, không có phép chiếu nào đọc nó.

## Kiểm chứng

`tests/test_teaching_steps.py`: mọi hành động dạy thuộc một trong 6 bước, ba hành động ghi chép (`ENTER_NODE`, `SWITCH_TO_PREREQUISITE`, `FINISH`) không có bước; ôn nền, giảng và nhắc lại cùng bước 1; bảng chuyển phiên cũ; phiên mới giữ nguyên. Test API buổi học theo chương và test web (thanh bước, trang chủ) cập nhật theo số bước mới.
