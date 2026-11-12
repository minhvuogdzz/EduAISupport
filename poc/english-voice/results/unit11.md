# Unit 11 "Family time": kết quả đo bổ sung (tự sinh bởi unit11.py)

VieNeu: 16.8 s tổng hợp cho 28.0 s âm thanh (RTF 0.60).

| Audio | Lang | Từ đích đúng | WER phần Anh | Cụm đúng nguyên văn | Động từ quá khứ đúng dạng |
|---|---|---:|---:|---:|---:|
| vieneu | vi | 75% | 25% | 40% | 6/9 |
| vieneu | en | 82% | 18% | 60% | 6/9 |
| ref | en | 100% | 0% | 100% | 9/9 |

| Câu | Audio | Lang | Whisper nghe được | WER Anh | Động từ |
|---|---|---|---|---:|---|
| u1 | vieneu | vi | Diesel collect seashells Yes, I did Yippee | 29% |  |
| u1 | vieneu | en | Diesel collects seashells. Yes, I did. Yep. | 43% |  |
| u1 | ref | en | Did you collect seashells? Yes, I did. | 0% |  |
| u2 | vieneu | vi | What did your family do in Ha Long Bay? We took a boat trip around the bay. | 0% | took: past |
| u2 | vieneu | en | What did your family do in Ha Long Bay? We took a boat trip around the bay. | 0% | took: past |
| u2 | ref | en | What did your family do in Ha Long Bay? We took a boat trip around the bay. | 0% | took: past |
| u3 | vieneu | vi | Con nói theo cô nhé, We are seafood. | 33% | ate: missing |
| u3 | vieneu | en | Con nói theo cô nhé. We are seafood. | 33% | ate: missing |
| u3 | ref | en | Con nói theo cô nhé. We ate seafood. | 0% | ate: past |
| u4 | vieneu | vi | Quay went to the beach | 20% | went: past |
| u4 | vieneu | en | We went to the beach. | 0% | went: past |
| u4 | ref | en | We went to the beach. | 0% | went: past |
| u5 | vieneu | vi | My mother bought some souvenirs | 0% | bought: past |
| u5 | vieneu | en | My mother bought some souvenirs | 0% | bought: past |
| u5 | ref | en | My mother bought some souvenirs. | 0% | bought: past |
| u6 | vieneu | vi | Bị đâu xui mình the sea? No, I didn't. | 44% |  |
| u6 | vieneu | en | Did you swim in the sea? No, I didn't. | 0% |  |
| u6 | ref | en | Did you swim in the sea? No, I didn't. | 0% |  |
| u7 | vieneu | vi | Where did you go last summer? I went to Ha Long Bay. | 0% | went: past |
| u7 | vieneu | en | Where did you go last summer? I went to Ha Long Bay. | 0% | went: past |
| u7 | ref | en | Where did you go last summer? I went to Ha Long Bay. | 0% | went: past |
| u8 | vieneu | vi | Con nói theo cô nhé. My father took a lot of photos. | 0% | took: past |
| u8 | vieneu | en | Con nói theo cô nhé. My father took a lot of photos. | 0% | took: past |
| u8 | ref | en | Con nói theo cô nhé. My father took a lot of photos. | 0% | took: past |
| u9 | vieneu | vi | Con nhớ nhé, ngu quên. Ít, ít. | 100% | went: missing, ate: missing |
| u9 | vieneu | en | Con nhớ nhé, nguồn quên. Eat, eat. | 75% | went: missing, ate: base |
| u9 | ref | en | Con nhớ nha. Go, went, eat, ate. | 0% | went: past, ate: past |
| u10 | vieneu | vi | Con nghĩ là we bought some souvenir. | 25% | bought: past |
| u10 | vieneu | en | Con nghĩ là we bought some souvenir. | 25% | bought: past |
| u10 | ref | en | Con nghĩ là... We bought some souvenirs. | 0% | bought: past |
