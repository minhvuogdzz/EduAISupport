# Lỗi sai gia sư nhận ra được trên hai chương đã phát hành (2026-10-13)

`misconception-rules/0.1.0` (DI-54). Lệnh: `make misconception-coverage` (chỉ đọc database).

## Diện tích hình tam giác, hình thang

| Tiết | Câu số/chọn | Câu nhận ra lỗi sai | Lỗi sai nhận ra |
|---|---|---|---|
| Đáy và đường cao của tam giác | 0 | 0 | — |
| Khám phá công thức diện tích tam giác | 14 | 13 | DTTGHT-T02-M1 |
| Luyện tập tính diện tích tam giác | 20 | 10 | DTTGHT-T02-M1 |
| Luyện tập chung, công thức ngược | 26 | 7 | DTTGHT-L1, DTTGHT-T04-M1 |
| Nhận biết hình thang, đường cao | 1 | 0 | — |
| Khám phá công thức diện tích hình thang | 14 | 12 | DTTGHT-T06-M1, DTTGHT-T06-M2 |
| Luyện tập tính diện tích hình thang | 18 | 12 | DTTGHT-T06-M1, DTTGHT-T06-M2, DTTGHT-T07-M1 |
| Hình ghép, công thức ngược | 28 | 2 | DTTGHT-T06-M1, DTTGHT-T06-M2 |

Lỗi sai trong tài liệu:

- DTTGHT-T01-M1 (NORMAL) «Bé lấy cạnh nghiêng làm đường cao»: SLANT_AS_HEIGHT; **chưa nhận ra**
- DTTGHT-T01-M2 (NORMAL) «Bé không vẽ được đường cao tam giác tù»: chưa có họ lỗi; **chưa nhận ra**
- DTTGHT-T02-M1 (NORMAL) «Bé quên chia 2»: FORGOT_HALF; nhận ra
- DTTGHT-T02-M2 (NORMAL) «Bé viết đơn vị là cm thay vì cm²»: chưa có họ lỗi; **chưa nhận ra**
- DTTGHT-T03-M1 (NORMAL) «Bé nhân số thập phân sai»: chưa có họ lỗi; **chưa nhận ra**
- DTTGHT-T03-M2 (NORMAL) «Bé quên đổi đơn vị»: chưa có họ lỗi; **chưa nhận ra**
- DTTGHT-T04-M1 (NORMAL) «Bé quên nhân 2»: FORGOT_DOUBLE; nhận ra
- DTTGHT-T04-M2 (NORMAL) «Bé tính S tam giác ABC bằng cách nhân sai đáy»: chưa có họ lỗi; **chưa nhận ra**
- DTTGHT-L1 (CRITICAL) «Quên chia 2 khi tính diện tích tam giác»: FORGOT_HALF; nhận ra
- DTTGHT-L2 (CRITICAL) «Lấy cạnh nghiêng làm đường cao»: SLANT_AS_HEIGHT; **chưa nhận ra**
- DTTGHT-L4 (CRITICAL) «Quên ngoặc, tính sai thứ tự phép tính»: MISSING_PARENS; cùng họ, câu sai được ghi vào DTTGHT-T07-M1
- DTTGHT-L5 (CRITICAL) «Không đổi về cùng đơn vị trước khi tính»: chưa có họ lỗi; **chưa nhận ra**
- DTTGHT-L6 (CRITICAL) «Ghi sai hoặc thiếu đơn vị diện tích»: chưa có họ lỗi; **chưa nhận ra**
- DTTGHT-L7 (CRITICAL) «Công thức ngược: quên nhân 2»: FORGOT_DOUBLE; cùng họ, câu sai được ghi vào DTTGHT-T04-M1
- DTTGHT-L8 (CRITICAL) «Tam giác vuông: lấy cạnh huyền làm đáy với cạnh góc vuông làm»: SLANT_AS_HEIGHT; **chưa nhận ra**
- DTTGHT-T05-M1 (NORMAL) «Bé nhầm cạnh bên là đáy»: chưa có họ lỗi; **chưa nhận ra**
- DTTGHT-T05-M2 (NORMAL) «Bé coi cạnh nghiêng là chiều cao»: SLANT_AS_HEIGHT; **chưa nhận ra**
- DTTGHT-T06-M1 (NORMAL) «Bé nhân hai đáy với nhau»: BASES_MULTIPLIED; nhận ra
- DTTGHT-T06-M2 (NORMAL) «Bé quên chia 2»: FORGOT_HALF; nhận ra
- DTTGHT-T07-M1 (NORMAL) «Bé viết a + b × h»: MISSING_PARENS; nhận ra
- DTTGHT-T07-M2 (NORMAL) «Bé quên đơn vị diện tích»: chưa có họ lỗi; **chưa nhận ra**
- DTTGHT-T08-M1 (NORMAL) «Bé chia hình thiếu phần»: chưa có họ lỗi; **chưa nhận ra**
- DTTGHT-T08-M2 (NORMAL) «Bé tìm đáy lớn mà quên trừ đáy bé»: chưa có họ lỗi; **chưa nhận ra**
- DTTGHT-L3 (CRITICAL) «Hình thang: nhân hai đáy thay vì cộng»: BASES_MULTIPLIED; cùng họ, câu sai được ghi vào DTTGHT-T06-M1

## Số thập phân

| Tiết | Câu số/chọn | Câu nhận ra lỗi sai | Lỗi sai nhận ra |
|---|---|---|---|
| Từ phân số thập phân đến số thập phân | 26 | 9 | STP-T01-M1, STP-T01-M2 |
| Cấu tạo số thập phân – đọc, viết số | 16 | 8 | STP-L1, STP-T01-M2 |
| Tính chất; số thập phân ↔ phân số | 17 | 12 | STP-L3, STP-T01-M2 |
| So sánh hai số thập phân | 1 | 0 | — |
| Sắp xếp thứ tự, tìm x, bài toán thực tế | 3 | 0 | — |
| Viết số đo độ dài dưới dạng số thập phân | 22 | 1 | STP-L4 |
| Viết số đo khối lượng dưới dạng số thập phân | 16 | 6 | STP-T07-M2 |
| Viết số đo diện tích – luyện tập | 12 | 4 | STP-L5 |
| Làm tròn đến hàng đơn vị và phần mười | 27 | 11 | STP-L6, STP-T09-M1 |
| Làm tròn đến hàng phần trăm và ứng dụng | 14 | 6 | STP-T09-M1, STP-T10-M1 |
| Luyện tập chung | 5 | 1 | STP-T11-M1 |

Lỗi sai trong tài liệu:

- STP-T01-M1 (NORMAL) «Bé viết 8/1000 = 0,8»: ZERO_PLACEHOLDER; nhận ra
- STP-T01-M2 (NORMAL) «Bé quên dấu phẩy»: MISSING_COMMA; nhận ra
- STP-T02-M1 (NORMAL) «Bé đọc 3,05 thành “ba phẩy năm”»: ZERO_PLACEHOLDER; cùng họ, câu sai được ghi vào STP-L1, STP-L3, STP-L4, STP-T01-M1
- STP-T02-M2 (NORMAL) «Bé nhầm “phần mười” với “mười”»: chưa có họ lỗi; **chưa nhận ra**
- STP-T03-M1 (NORMAL) «Bé bỏ số 0 ở giữa (4,05 → 4,5)»: ZERO_PLACEHOLDER; cùng họ, câu sai được ghi vào STP-L1, STP-L3, STP-L4, STP-T01-M1
- STP-T03-M2 (NORMAL) «Bé viết 2,15 = 2/15»: chưa có họ lỗi; **chưa nhận ra**
- STP-L1 (CRITICAL) «Đọc/viết sai chữ số 0 ngay sau dấu phẩy»: ZERO_PLACEHOLDER; nhận ra
- STP-L3 (CRITICAL) «Bỏ/thêm chữ số 0 sai chỗ»: ZERO_PLACEHOLDER; nhận ra
- STP-L8 (CRITICAL) «Nhầm tên hàng và giá trị của chữ số»: chưa có họ lỗi; **chưa nhận ra**
- STP-T04-M1 (NORMAL) «Bé nói “0,125 > 0,5 vì 125 > 5”»: LONGER_IS_LARGER; nhận ra (câu so sánh)
- STP-T04-M2 (NORMAL) «Bé so sánh sai phần nguyên»: INTEGER_PART; nhận ra (câu so sánh)
- STP-T05-M1 (NORMAL) «Bé quên rằng x phải là số tự nhiên»: chưa có họ lỗi; **chưa nhận ra**
- STP-T05-M2 (NORMAL) «Bé xếp ngược chiều (bé → lớn)»: chưa có họ lỗi; **chưa nhận ra**
- STP-T06-M1 (NORMAL) «Bé viết 3 m 5 cm = 3,5 m»: chưa có họ lỗi; **chưa nhận ra**
- STP-T06-M2 (NORMAL) «Bé viết 1 km 85 m = 1,85 km»: chưa có họ lỗi; **chưa nhận ra**
- STP-T07-M1 (NORMAL) «Bé nhầm 1 tạ = 10 kg»: chưa có họ lỗi; **chưa nhận ra**
- STP-T07-M2 (NORMAL) «Bé viết 750 g = 7,5 kg»: UNIT_STEP; nhận ra
- STP-T08-M1 (NORMAL) «Bé coi 1 m² = 10 dm²»: AREA_AS_LENGTH; cùng họ, câu sai được ghi vào STP-L5
- STP-T08-M2 (NORMAL) «Bé thiếu số 0 giữ chỗ (3,5 thay vì 3,05)»: ZERO_PLACEHOLDER; cùng họ, câu sai được ghi vào STP-L1, STP-L3, STP-L4, STP-T01-M1
- STP-L2 (CRITICAL) «Cho rằng “dài hơn thì lớn hơn”»: LONGER_IS_LARGER; cùng họ, câu sai được ghi vào STP-T04-M1
- STP-L4 (CRITICAL) «Nhầm số bước khi đổi đơn vị (thiếu số 0 giữ chỗ)»: UNIT_STEP, ZERO_PLACEHOLDER; nhận ra
- STP-L5 (CRITICAL) «Đổi đơn vị diện tích như độ dài»: AREA_AS_LENGTH; nhận ra
- STP-T09-M1 (NORMAL) «Bé nhìn sai chữ số (nhìn chính hàng cần làm tròn)»: ROUND_LOOK; nhận ra
- STP-T09-M2 (NORMAL) «Bé làm tròn “dây chuyền” (3,449 → 3,45 → 3,5)»: ROUND_CHAIN; cùng họ, câu sai được ghi vào STP-L6
- STP-T10-M1 (NORMAL) «Bé viết 9,96 ≈ 9,10»: ROUND_CARRY; nhận ra
- STP-T10-M2 (NORMAL) «Bé bỏ mất số 0 cuối (1,00 thành 1,0)»: chưa có họ lỗi; **chưa nhận ra**
- STP-L6 (CRITICAL) «Làm tròn “dây chuyền”»: ROUND_CHAIN; nhận ra
- STP-L7 (CRITICAL) «Làm tròn mà quên “nhớ” sang hàng bên trái»: ROUND_CARRY; cùng họ, câu sai được ghi vào STP-T10-M1
- STP-T11-M1 (NORMAL) «Bé đổi nhầm đơn vị»: UNIT_STEP; nhận ra
- STP-T11-M2 (NORMAL) «Bé làm dài dòng»: chưa có họ lỗi; **chưa nhận ra**
