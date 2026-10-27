# BRAIN-2 · Kiểm tra trực tiếp 27/10/2026

[FACT] Câu hỏi tổng hợp, index trong bộ nhớ, tắt embedding để thử đường dự phòng. Không truy cập hoặc ghi database. Đây là bốn ca kiểm tra, không phải ước lượng tỷ lệ thành công trên học sinh thật.

Bản: brain/1.1.0 / grounded-speech/0.5.0.

| Ca | Nguồn trả lời | Call | Giây | Kết quả |
|---|---|---:|---:|---|
| denominator | LLM | 2 | 3.92 | đạt |
| same_value | LLM | 2 | 3.55 | đạt |
| fresh_example | LLM | 2 | 2.77 | đạt |
| official_gap | WEB | 3 | 7.2 | đạt |

Model quan sát: openai/gpt-oss-120b.

## Mẫu lời trả lời quan sát được

- **mẫu số là gì cô** → Mẫu số là số ở dưới của phân số, cho biết chia thành bao nhiêu phần bằng nhau. Ví dụ 5/10, 10 là mẫu số.
- **Sao 0,30 và 0,3 lại bằng nhau?** → Cô giải thích: 0,30 và 0,3 bằng nhau vì chữ 0 ở cuối phần thập phân có thể bỏ đi, giá trị không đổi. Ví dụ 1,250 = 1,25.
- **Cho con một ví dụ khác về số thập phân bằng nhau** → Ví dụ: 3,450 = 3,45 vì chỉ bỏ số 0 ở cuối phần thập phân. Hoặc 0,700 = 0,7 vì bỏ các 0 cuối cùng cũng không thay đổi giá trị.
- **phân số thập phân là gì** → Sách Toán 5 giải thích thế này: Cô giải thích: phân số thập phân là phân số có mẫu số là 10, 100, 1000… ví dụ 0,75 = 75/100 là một phân số thập phân.

## Điều tìm thấy khi sửa

- Hai lượt đo trước chỉ đạt 3/4 ca theo tiêu chí nguồn mong đợi: từ khóa kéo câu 0,30/0,3 về bài phân số, và câu hỏi mẫu số không có định nghĩa tường minh nhưng fallback lại đọc câu về phân số thập phân. Đã kèm quy tắc của bài hiện tại, cho phép nhắc số con hỏi, và không dùng một câu vụn để thay định nghĩa còn thiếu.
- Một lần kiểm nghĩa tạo trích dẫn không có trong nguồn: bị kiểm trích dẫn thật bác. Không tính lời bị chặn là lời học sinh nhận.
- Bộ kiểm vẫn có thể từ chối lời đúng hoặc nhận lời chưa hay; kiểm nghĩa không phải chứng minh hình thức. Ví dụ nguồn chính thức cuối phải thử lại vì quá dài/thuật ngữ thiếu căn cứ. Chưa có nghiên cứu người dùng để khẳng định giọng nói đã tốt cho mọi tình huống.
- Nguồn trực tiếp: SGV Toán 5 của NXB Giáo dục; bài Dương Hữu Tòng (2016) trên Tạp chí Khoa học ĐH Cần Thơ có các định nghĩa tử số/mẫu số trích SGK, lấy từ PDF gốc. Danh mục nhỏ, không có tìm kiếm web mở.

Tái lập: `services/api/.venv/bin/python services/api/scripts/eval_brain2.py --live` (cần key riêng trong môi trường, không commit key). Test offline: `MONGODB_URI='' make test`.

Kiểm tra riêng nguồn nền bị thiếu trong RAG: câu tổng hợp “mẫu số là gì” được trả lời từ PDF gốc ĐH Cần Thơ, 2 call, không bị từ chối ở lượt cuối: “Mẫu số là số dưới dấu gạch ngang của phân số, cho biết hình được chia thành bao nhiêu phần bằng nhau, ví dụ 3/6 thì mẫu số là 6.” Đã sửa việc bộ kiểm coi một phân số minh hoạ mới là số liệu tự bịa dù nguồn đã định nghĩa ký hiệu đó.
