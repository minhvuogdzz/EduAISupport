# Hồi quy chính sách dạy sau DI-52 (hỏi lại bài đã học), 2026-10-13

- **Phiên bản:** `node-policy/0.3.0` và `teaching-templates/0.4.0`.
- **Lệnh:** `make trial`. Bốn học sinh mẫu học hai chương đã phát hành, chạy offline trong bộ nhớ, chỉ đọc database.
- **Mốc so sánh:** `2026-10-12-trial-sessions.md` (`node-policy/0.2.0`).

## Kết quả

| Chương | Học sinh | Lượt trước → sau | Tiết qua | Kết quả chấm | Gợi ý |
|---|---|---|---|---|---|
| Số thập phân | gioi | 104 → 114 | 11/11 | 60 đúng (như cũ) | 0 |
| | hay-sai | 227 → 237 | 11/11 | 61 đúng, 50 sai, 11 không đọc được (như cũ) | 58 |
| | sai-dang | 137 → 147 | 11/11 | 60 đúng, 11 sai (như cũ) | 11 |
| | bi | 164 → 174 | 11/11 | 60 đúng, 60 xin giúp (như cũ) | 0 |
| Diện tích tam giác, hình thang | gioi | 83 → 90 | 8/8 | 51 đúng (như cũ) | 0 |
| | hay-sai | 193 → 200 | 8/8 | 53 đúng, 40 sai, 13 không đọc được (như cũ) | 51 |
| | sai-dang | 91 → 98 | 8/8 | 51 đúng (như cũ) | 0 |
| | bi | 134 → 141 | 8/8 | 51 đúng, 51 xin giúp (như cũ) | 0 |

- Số lượt tăng đúng bằng số tiết có tiết tiên quyết: 10 tiết ở chương Số thập phân, 7 tiết ở chương Diện tích. Mỗi tiết có thêm một câu hỏi lại lúc vào bài.
- Kết quả chấm, số gợi ý và số tiết qua không đổi.
- Các học sinh mẫu đều làm đúng phần kiểm tra hiểu, nên lần hỏi lại thứ hai (khi kiểm tra hiểu sai) không xuất hiện ở đây. Trường hợp này có test riêng: `tests/test_node_policy.py`.

## Ví dụ hội thoại (chương Diện tích, học sinh `gioi`)

> **Gia sư:** Bài Khám phá công thức diện tích tam giác dùng tới bài Đáy và đường cao của tam giác mình đã học. Con nhớ lại giúp cô nhé: bài Đáy và đường cao của tam giác cho con biết những điều gì?
>
> **Bé:** vuông góc với đáy. ba đường cao. nằm ngoài
>
> **Gia sư:** Đúng rồi, con nhớ bài cũ tốt lắm! Mình dùng điều đó cho bài Khám phá công thức diện tích tam giác nhé.

Khi bé trả lời "con ko nhớ ạ", gia sư nhắc lại ý chính của bài cũ, nối sang bài mới, rồi giảng. Điểm của bài cũ giảm nhưng bài đó vẫn giữ dấu đã qua (`tests/test_teaching_loop.py`).

## Giới hạn

- **Tên bài làm câu nối dài.** Tên tiết của chương phát hành vừa dài vừa có ký hiệu, nên câu nối hơi nặng, ví dụ "bài Tính chất; số thập phân ↔ phân số". Muốn gọn hơn, giáo viên cần đặt tên tiết ngắn hơn khi duyệt.
- **Học sinh mẫu nhớ lại bằng đúng ý chính của giáo viên.** Số liệu này chỉ kiểm luồng dạy, chưa đo được việc trẻ thật nhớ lại thế nào.
