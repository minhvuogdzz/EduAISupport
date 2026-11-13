# Kết quả đo ENG-POC-voice (tự sinh bởi score.py)

- VieNeu 3.8.3 · VieNeu-TTS v3 Turbo (SDK default), ONNX Runtime CPU, fp32 · giọng Ngọc Huyền
- Máy: arm64 macOS-27.2.1-arm64-arm-64bit arm
- Nạp model 26.12 s; câu khởi động 1.13 s (không tính vào bảng)
- Giọng tham chiếu tiếng Anh: macOS say -v Samantha

## 1. Thời gian tổng hợp VieNeu trên CPU

| Câu | Loại | Văn bản | Tổng hợp (s) | Âm thanh (s) | RTF |
|---|---|---|---:|---:|---:|
| w1 | Từ đơn | Mother. | 1.16 | 1.44 | 0.80 |
| w2 | Từ đơn | Father. | 1.03 | 0.80 | 1.29 |
| w3 | Từ đơn | Sister. | 0.27 | 0.88 | 0.30 |
| w4 | Từ đơn | Brother. | 1.36 | 1.44 | 0.94 |
| w5 | Từ đơn | Grandmother. | 0.46 | 1.76 | 0.26 |
| w6 | Từ đơn | Grandfather. | 0.31 | 1.12 | 0.28 |
| p1 | Mẫu câu | This is my mother. | 0.44 | 1.52 | 0.29 |
| p2 | Mẫu câu | She is my sister. | 0.43 | 1.52 | 0.28 |
| p3 | Mẫu câu | He is my brother. | 0.41 | 1.44 | 0.28 |
| p4 | Mẫu câu | Who is this? | 0.30 | 1.04 | 0.29 |
| p5 | Mẫu câu | How many people are there in your family? | 0.65 | 2.48 | 0.26 |
| p6 | Mẫu câu | There are four people in my family. | 0.61 | 2.32 | 0.26 |
| t1 | Câu cô (trộn) | Con nói theo cô nhé: This is my father. | 0.71 | 2.72 | 0.26 |
| t2 | Câu cô (trộn) | Từ mother nghĩa là mẹ. | 0.39 | 1.44 | 0.27 |
| t3 | Câu cô (trộn) | Từ grandfather nghĩa là ông. | 0.49 | 1.84 | 0.27 |
| t4 | Câu cô (trộn) | Cô hỏi nhé: Who is this? | 0.62 | 1.92 | 0.32 |
| t5 | Câu cô (trộn) | Giỏi lắm! Con đọc lại nhé: She is my sister. | 0.88 | 3.44 | 0.26 |
| s1 | Câu bé (trộn) | Con nghĩ là mother. | 0.35 | 1.28 | 0.28 |
| s2 | Câu bé (trộn) | Dạ, this is my grandmother. | 0.58 | 2.24 | 0.26 |
| s3 | Câu bé (trộn) | Brother là anh trai ạ. | 0.41 | 1.44 | 0.28 |
| **Tổng** | | | **11.9** | **34.1** | **0.35** |

## 2. Tổng hợp độ nhận đúng (trung bình trên các câu)

Audio `vieneu` = cả câu do VieNeu đọc. Audio `ref` = câu thuần Anh do giọng Anh chuẩn đọc; câu trộn ghép phần Việt (VieNeu) với phần Anh (giọng Anh chuẩn).

| Audio | Ngôn ngữ Whisper | Nhóm | n | Tỉ lệ từ đích đúng | WER phần Anh | Cụm đúng nguyên văn |
|---|---|---|---:|---:|---:|---:|
| vieneu | vi | **Tất cả** | 20 | 75% | 25% | 75% |
| vieneu | vi | Từ đơn | 6 | 50% | 50% | 50% |
| vieneu | vi | Mẫu câu | 6 | 100% | 0% | 100% |
| vieneu | vi | Câu cô (trộn) | 5 | 80% | 20% | 80% |
| vieneu | vi | Câu bé (trộn) | 3 | 67% | 33% | 67% |
| vieneu | en | **Tất cả** | 20 | 95% | 5% | 95% |
| vieneu | en | Từ đơn | 6 | 83% | 17% | 83% |
| vieneu | en | Mẫu câu | 6 | 100% | 0% | 100% |
| vieneu | en | Câu cô (trộn) | 5 | 100% | 0% | 100% |
| vieneu | en | Câu bé (trộn) | 3 | 100% | 0% | 100% |
| vieneu | auto | **Tất cả** | 20 | 50% | 50% | 50% |
| vieneu | auto | Từ đơn | 6 | 33% | 67% | 33% |
| vieneu | auto | Mẫu câu | 6 | 33% | 67% | 33% |
| vieneu | auto | Câu cô (trộn) | 5 | 80% | 20% | 80% |
| vieneu | auto | Câu bé (trộn) | 3 | 67% | 33% | 67% |
| ref | vi | **Tất cả** | 20 | 95% | 5% | 95% |
| ref | vi | Từ đơn | 6 | 83% | 17% | 83% |
| ref | vi | Mẫu câu | 6 | 100% | 0% | 100% |
| ref | vi | Câu cô (trộn) | 5 | 100% | 0% | 100% |
| ref | vi | Câu bé (trộn) | 3 | 100% | 0% | 100% |
| ref | en | **Tất cả** | 20 | 100% | 0% | 100% |
| ref | en | Từ đơn | 6 | 100% | 0% | 100% |
| ref | en | Mẫu câu | 6 | 100% | 0% | 100% |
| ref | en | Câu cô (trộn) | 5 | 100% | 0% | 100% |
| ref | en | Câu bé (trộn) | 3 | 100% | 0% | 100% |
| ref | auto | **Tất cả** | 20 | 100% | 0% | 100% |
| ref | auto | Từ đơn | 6 | 100% | 0% | 100% |
| ref | auto | Mẫu câu | 6 | 100% | 0% | 100% |
| ref | auto | Câu cô (trộn) | 5 | 100% | 0% | 100% |
| ref | auto | Câu bé (trộn) | 3 | 100% | 0% | 100% |

## 3. Từng câu

| Audio | Câu | Lang | Phát hiện | Whisper nghe được | Từ đích | WER Anh |
|---|---|---|---|---|---:|---:|
| ref | w1 | auto | English | Mother. | 100% | 0% |
| ref | w1 | en | English | Mother. | 100% | 0% |
| ref | w1 | vi | Vietnamese | Mother | 100% | 0% |
| ref | w2 | auto | English | Father. | 100% | 0% |
| ref | w2 | en | English | Father. | 100% | 0% |
| ref | w2 | vi | Vietnamese | Cha | 0% | 100% |
| ref | w3 | auto | English | Sister | 100% | 0% |
| ref | w3 | en | English | Sister | 100% | 0% |
| ref | w3 | vi | Vietnamese | Sister | 100% | 0% |
| ref | w4 | auto | English | brother. | 100% | 0% |
| ref | w4 | en | English | brother. | 100% | 0% |
| ref | w4 | vi | Vietnamese | Brother. | 100% | 0% |
| ref | w5 | auto | English | Grandmother. | 100% | 0% |
| ref | w5 | en | English | Grandmother. | 100% | 0% |
| ref | w5 | vi | Vietnamese | Grandmother | 100% | 0% |
| ref | w6 | auto | English | grandfather. | 100% | 0% |
| ref | w6 | en | English | grandfather. | 100% | 0% |
| ref | w6 | vi | Vietnamese | Grandfather | 100% | 0% |
| ref | p1 | auto | English | This is my mother. | 100% | 0% |
| ref | p1 | en | English | This is my mother. | 100% | 0% |
| ref | p1 | vi | Vietnamese | This is my mother. | 100% | 0% |
| ref | p2 | auto | English | She is my sister. | 100% | 0% |
| ref | p2 | en | English | She is my sister. | 100% | 0% |
| ref | p2 | vi | Vietnamese | She is my sister. | 100% | 0% |
| ref | p3 | auto | English | He is my brother. | 100% | 0% |
| ref | p3 | en | English | He is my brother. | 100% | 0% |
| ref | p3 | vi | Vietnamese | He is my brother. | 100% | 0% |
| ref | p4 | auto | English | Who is this? | 100% | 0% |
| ref | p4 | en | English | Who is this? | 100% | 0% |
| ref | p4 | vi | Vietnamese | Who is this? | 100% | 0% |
| ref | p5 | auto | English | How many people are there in your family? | 100% | 0% |
| ref | p5 | en | English | How many people are there in your family? | 100% | 0% |
| ref | p5 | vi | Vietnamese | How many people are there in your family? | 100% | 0% |
| ref | p6 | auto | English | There are four people in my family. | 100% | 0% |
| ref | p6 | en | English | There are four people in my family. | 100% | 0% |
| ref | p6 | vi | Vietnamese | There are four people in my family. | 100% | 0% |
| ref | t1 | auto | Vietnamese | Con nói theo cô nhé. This is my father. | 100% | 0% |
| ref | t1 | en | English | Con nói theo cô nhé. This is my father. | 100% | 0% |
| ref | t1 | vi | Vietnamese | Con nói theo cô nhé. This is my father. | 100% | 0% |
| ref | t2 | auto | Vietnamese | Tu. Mother. Nghĩa là mẹ. | 100% | 0% |
| ref | t2 | en | English | Tu. Mother. Nghĩa là mẹ. | 100% | 0% |
| ref | t2 | vi | Vietnamese | Tu. Mother. Nghĩa là mẹ. | 100% | 0% |
| ref | t3 | auto | Vietnamese | Từ grandfather nghĩa là ông. | 100% | 0% |
| ref | t3 | en | English | Từ grandfather nghĩa là ông. Ông bố. | 100% | 0% |
| ref | t3 | vi | Vietnamese | Từ grandfather nghĩa là ông. | 100% | 0% |
| ref | t4 | auto | Japanese | 後輩ね。Who is this? | 100% | 0% |
| ref | t4 | en | English | 後輩ね。 Who is this? | 100% | 0% |
| ref | t4 | vi | Vietnamese | Cô hai nhé. Who is this? | 100% | 0% |
| ref | t5 | auto | Vietnamese | Giỏi lắm, con đọc lại nhé. She is my sister. | 100% | 0% |
| ref | t5 | en | English | Giỏi lắm. Con đọc lại nhé. She is my sister. | 100% | 0% |
| ref | t5 | vi | Vietnamese | Giỏi lắm, con đọc lại nhé. She is my sister. | 100% | 0% |
| ref | s1 | auto | Vietnamese | Con nghĩ là... Mother. | 100% | 0% |
| ref | s1 | en | English | Con nghĩ là... Mother. | 100% | 0% |
| ref | s1 | vi | Vietnamese | Con nghĩ là... Mother. | 100% | 0% |
| ref | s2 | auto | English | Za. This is my grandmother. | 100% | 0% |
| ref | s2 | en | English | Za. This is my grandmother. | 100% | 0% |
| ref | s2 | vi | Vietnamese | Dạ This is my grandmother | 100% | 0% |
| ref | s3 | auto | Vietnamese | Brother. Là anh trai ạ. | 100% | 0% |
| ref | s3 | en | English | Brother. Là anh trai ạ? | 100% | 0% |
| ref | s3 | vi | Vietnamese | Brother. Là anh trai ạ. | 100% | 0% |
| vieneu | w1 | auto | Vietnamese | Mà tự... mà tự... | 0% | 100% |
| vieneu | w1 | en | English | Mother, mother... | 100% | 0% |
| vieneu | w1 | vi | Vietnamese | Mà tự... mà tự... | 0% | 100% |
| vieneu | w2 | auto | German | Vater | 0% | 100% |
| vieneu | w2 | en | English | Father | 100% | 0% |
| vieneu | w2 | vi | Vietnamese | Phá đơ | 0% | 100% |
| vieneu | w3 | auto | Japanese | シート | 0% | 100% |
| vieneu | w3 | en | English | See To. | 0% | 100% |
| vieneu | w3 | vi | Vietnamese | Xí tự. | 0% | 100% |
| vieneu | w4 | auto | Korean | 브래더 브라더 | 0% | 100% |
| vieneu | w4 | en | English | Brother Brother | 100% | 0% |
| vieneu | w4 | vi | Vietnamese | Brother, Brother | 100% | 0% |
| vieneu | w5 | auto | English | Grandmother, come and move. | 100% | 0% |
| vieneu | w5 | en | English | Grandmother, come and move. | 100% | 0% |
| vieneu | w5 | vi | Vietnamese | Grandmother Cơ bản mụn | 100% | 0% |
| vieneu | w6 | auto | Vietnamese | Grandfather | 100% | 0% |
| vieneu | w6 | en | English | grandfather | 100% | 0% |
| vieneu | w6 | vi | Vietnamese | Grandfather | 100% | 0% |
| vieneu | p1 | auto | Malay (macrolanguage) | Ini ialah ibu saya | 0% | 100% |
| vieneu | p1 | en | English | This is my mother | 100% | 0% |
| vieneu | p1 | vi | Vietnamese | This is my mother. | 100% | 0% |
| vieneu | p2 | auto | English | She is my sister. | 100% | 0% |
| vieneu | p2 | en | English | She is my sister. | 100% | 0% |
| vieneu | p2 | vi | Vietnamese | She is my sister. | 100% | 0% |
| vieneu | p3 | auto | Malay (macrolanguage) | Dia adik saya. | 0% | 100% |
| vieneu | p3 | en | English | He is my brother. | 100% | 0% |
| vieneu | p3 | vi | Vietnamese | He is my brother. | 100% | 0% |
| vieneu | p4 | auto | English | Who is this? | 100% | 0% |
| vieneu | p4 | en | English | Who is this? | 100% | 0% |
| vieneu | p4 | vi | Vietnamese | Who is this? | 100% | 0% |
| vieneu | p5 | auto | Malay (macrolanguage) | Berapa ramai orang ada di dalam keluarga anda? | 0% | 100% |
| vieneu | p5 | en | English | How many people are there in your family? | 100% | 0% |
| vieneu | p5 | vi | Vietnamese | How many people are there in your family? | 100% | 0% |
| vieneu | p6 | auto | Malay (macrolanguage) | Ada empat orang dalam keluarga saya. | 0% | 100% |
| vieneu | p6 | en | English | There are four people in my family. | 100% | 0% |
| vieneu | p6 | vi | Vietnamese | There are four people in my family. | 100% | 0% |
| vieneu | t1 | auto | Vietnamese | Con nói theo cô nhé. This is my father. | 100% | 0% |
| vieneu | t1 | en | English | Con nói theo cô nhé. This is my father. | 100% | 0% |
| vieneu | t1 | vi | Vietnamese | Con nói theo cô nhé. This is my father. | 100% | 0% |
| vieneu | t2 | auto | Vietnamese | Từ mơ từ nghĩa là mẹ. | 0% | 100% |
| vieneu | t2 | en | English | The mother nghĩa là mẹ. | 100% | 0% |
| vieneu | t2 | vi | Vietnamese | Từ mơ từ nghĩa là mẹ. | 0% | 100% |
| vieneu | t3 | auto | Vietnamese | Từ grandfather nghĩa là ông. | 100% | 0% |
| vieneu | t3 | en | English | Thư grandfather nghĩa là ông. | 100% | 0% |
| vieneu | t3 | vi | Vietnamese | Từ grandfather nghĩa là ông. | 100% | 0% |
| vieneu | t4 | auto | Vietnamese | Cô hỏi nhé, who is this? | 100% | 0% |
| vieneu | t4 | en | English | Cô hỏi nhé, who is this? | 100% | 0% |
| vieneu | t4 | vi | Vietnamese | Cô hỏi nhé, who is this? | 100% | 0% |
| vieneu | t5 | auto | Vietnamese | Giỏi lắm. Con đọc lại nhé. She is my sister. | 100% | 0% |
| vieneu | t5 | en | English | Giỏi lắm. Con đọc lại nhé. She is my sister. | 100% | 0% |
| vieneu | t5 | vi | Vietnamese | Giỏi lắm. Con đọc lại nhé. She is my sister. | 100% | 0% |
| vieneu | s1 | auto | Vietnamese | Con nghĩ là Mother. | 100% | 0% |
| vieneu | s1 | en | English | Con nghĩ là Mother. | 100% | 0% |
| vieneu | s1 | vi | Vietnamese | Con nghĩ là Mother. | 100% | 0% |
| vieneu | s2 | auto | Vietnamese | Dạ, this is my grandmother. | 100% | 0% |
| vieneu | s2 | en | English | That this is my grandmother. | 100% | 0% |
| vieneu | s2 | vi | Vietnamese | Dạ, this is my grandmother. | 100% | 0% |
| vieneu | s3 | auto | Vietnamese | Bluto là anh trai ạ. | 0% | 100% |
| vieneu | s3 | en | English | Bluto is my brother. | 100% | 0% |
| vieneu | s3 | vi | Vietnamese | Bluto là anh trai ạ. | 0% | 100% |
