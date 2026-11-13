# ENG-POC-voice: giọng cô và bộ nghe cho Tiếng Anh lớp 5, Unit 11 "Family time"

Unit chủ dự án chốt là Unit 11 "Family time" (SGK Tiếng Anh 5 Global Success, tập hai). Bộ 20 câu đo chính (`sentences.py`) là câu thuộc chủ đề gia đình chung, **chưa phải câu của Unit 11**; `unit11.py` đo bổ sung 10 câu theo Unit 11.

POC đo hai việc cho module Tiếng Anh lớp 5 (kết quả và đề xuất: `docs/poc/english-voice-decision.md`):

1. VieNeu-TTS v3 Turbo (giọng cô "Ngọc Huyền", như `services/voice/server.py`) đọc câu tiếng Anh và câu Việt xen Anh có rõ không, và nhanh không trên CPU.
2. Groq Whisper (`whisper-large-v3`) nghe cụm tiếng Anh ra sao với ba cách đặt ngôn ngữ: `vi`, `en`, tự nhận dạng.

Code ở đây không được import vào `services/` hay `apps/`.

## Tệp

| Tệp | Việc |
|---|---|
| `sentences.py` | 20 câu: 6 từ đơn, 6 mẫu câu, 5 câu cô nói (trộn Việt–Anh), 3 câu bé trả lời (trộn) |
| `g2p_check.py` | In cách bộ phiên âm của VieNeu (`sea-g2p`) đọc từng câu → `results/g2p.json` |
| `synth.py` | Tổng hợp bằng VieNeu, đo thời gian; tạo audio tham chiếu → `results/synth.json` |
| `listen.py` | Gửi Groq Whisper, 2 bộ audio × 20 câu × 3 cách đặt ngôn ngữ = 120 lượt → `results/transcripts.json` (có cache) |
| `score.py` | Chấm, không gọi mạng → `results/score.md`, `results/score.json` |
| `unit11.py` | Bổ sung 10 câu theo Unit 11: tổng hợp, Whisper nghe (VieNeu với `vi`, `en`; tham chiếu với `en`; 30 lượt, có cache), kiểm dạng quá khứ của động từ → `results/unit11.md` |

Audio tham chiếu (`ref`): câu thuần Anh do giọng hệ thống macOS "Samantha" (en_US) đọc; câu trộn ghép phần Việt do VieNeu đọc với phần Anh do Samantha đọc, cách nhau 150 ms. Đây cũng là bản thử của phương án dự phòng "VieNeu cho tiếng Việt + giọng Anh của máy/trình duyệt cho cụm tiếng Anh".

## Chạy lại (macOS, từ gốc repo)

```bash
make voice-setup
```

```bash
services/voice/.venv/bin/python poc/english-voice/g2p_check.py
```

```bash
services/voice/.venv/bin/python poc/english-voice/synth.py
```

`listen.py` cần khóa Groq trong biến môi trường. Không chép `.env` vào đây; đọc từ `services/api/.env` khi chạy:

```bash
GROQ_API_KEY="$(grep '^GROQ_API_KEY=' services/api/.env | cut -d= -f2- | tr -d "'\"")" services/voice/.venv/bin/python poc/english-voice/listen.py
```

```bash
python3 poc/english-voice/score.py
```

Đo bổ sung Unit 11 (cần khóa Groq như trên):

```bash
GROQ_API_KEY="$(grep '^GROQ_API_KEY=' services/api/.env | cut -d= -f2- | tr -d "'\"")" services/voice/.venv/bin/python poc/english-voice/unit11.py
```

- Lần đầu `synth.py` tải model VieNeu (~580 MB) về `var/storage/voice/hf`.
- `listen.py` nghỉ `PACE_S` giây (mặc định 3,5) giữa hai lượt vì hạn mức Whisper free tier theo phút; gặp 429 thì chờ theo `retry-after`. Xóa `results/transcripts.json` nếu muốn nghe lại từ đầu (sau khi đổi audio).
- Audio nằm ở `var/storage/poc/english-voice/{vieneu,ref}/<id>.wav` (gitignore, không commit).

## Đo thêm khi có giọng học sinh thật

Đặt bản ghi vào `var/storage/poc/english-voice/child/<id>.wav` theo đúng `id` trong `sentences.py` (hoặc thêm câu mới vào `sentences.py`), thêm `"child"` vào `SETS` của `listen.py`, rồi chạy `listen.py` và `score.py`. Bản ghi giọng các em là dữ liệu thật: chỉ để trong `var/`, không commit.
