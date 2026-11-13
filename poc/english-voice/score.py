"""ENG-POC-voice step 3: score the transcripts (stdlib only, no network).

    python3 poc/english-voice/score.py

Per sentence × audio set × language setting:
  hit     share of the English target words found in the transcript (multiset, order ignored)
  en_wer  WER of the English target against the best-matching span of the transcript
          (semi-global alignment: the Vietnamese around it is not counted), capped at 1
  exact   en_wer == 0 (the whole target phrase heard word for word)
Writes results/score.md (tables) and results/score.json.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sentences import SENTENCES  # noqa: E402

DIGITS = {
    "0": "zero",
    "1": "one",
    "2": "two",
    "3": "three",
    "4": "four",
    "5": "five",
    "6": "six",
    "7": "seven",
    "8": "eight",
    "9": "nine",
    "10": "ten",
}
KIND_VI = {"word": "Từ đơn", "pattern": "Mẫu câu", "teacher": "Câu cô (trộn)", "child": "Câu bé (trộn)"}


def tokens(text: str) -> list[str]:
    text = unicodedata.normalize("NFC", text.lower())
    text = re.sub(r"[^\w\s']", " ", text)
    return [DIGITS.get(t, t) for t in text.split()]


def span_wer(ref: list[str], hyp: list[str]) -> float:
    """Edit distance of ref against the best substring of hyp (free start/end in hyp), / len(ref)."""
    n, m = len(ref), len(hyp)
    prev = [0] * (m + 1)  # free start anywhere in hyp
    for i in range(1, n + 1):
        cur = [i] + [0] * m
        for j in range(1, m + 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ref[i - 1] != hyp[j - 1]))
        prev = cur
    return min(1.0, min(prev) / n)  # free end anywhere in hyp


def hit_rate(ref: list[str], hyp: list[str]) -> float:
    have = Counter(hyp)
    found = 0
    for word, count in Counter(ref).items():
        found += min(count, have[word])
    return found / len(ref)


def main() -> None:
    transcripts = json.loads((HERE / "results/transcripts.json").read_text(encoding="utf-8"))
    synth = json.loads((HERE / "results/synth.json").read_text(encoding="utf-8"))
    rows = []
    for key, value in sorted(transcripts.items()):
        audio_set, sid, lang = key.split("/")
        _, kind, text, target, _ = next(s for s in SENTENCES if s[0] == sid)
        ref, hyp = tokens(target), tokens(value["text"])
        wer = span_wer(ref, hyp)
        rows.append(
            {
                "set": audio_set,
                "id": sid,
                "kind": kind,
                "lang": lang,
                "text": text,
                "target": target,
                "heard": value["text"],
                "detected": value.get("language"),
                "hit": round(hit_rate(ref, hyp), 3),
                "en_wer": round(wer, 3),
                "exact": wer == 0,
            }
        )

    def agg(sel):
        k = len(sel)
        return {
            "n": k,
            "hit": sum(r["hit"] for r in sel) / k,
            "en_wer": sum(r["en_wer"] for r in sel) / k,
            "exact": sum(r["exact"] for r in sel) / k,
        }

    groups = defaultdict(list)
    for r in rows:
        groups[(r["set"], r["lang"], "all")].append(r)
        groups[(r["set"], r["lang"], r["kind"])].append(r)
    summary = {"/".join(k): agg(v) for k, v in groups.items()}

    out = ["# Kết quả đo ENG-POC-voice (tự sinh bởi score.py)", ""]
    out += [
        f"- VieNeu {synth['vieneu_version']} · {synth['model']} · giọng {synth['voice']}",
        f"- Máy: {synth['machine']}",
        f"- Nạp model {synth['load_s']} s; câu khởi động {synth['warmup_s']} s (không tính vào bảng)",
        f"- Giọng tham chiếu tiếng Anh: {synth['en_reference_voice']}",
        "",
    ]
    out += [
        "## 1. Thời gian tổng hợp VieNeu trên CPU",
        "",
        "| Câu | Loại | Văn bản | Tổng hợp (s) | Âm thanh (s) | RTF |",
        "|---|---|---|---:|---:|---:|",
    ]
    for r in synth["rows"]:
        out.append(
            f"| {r['id']} | {KIND_VI[r['kind']]} | {r['text']} | {r['synth_s']:.2f} | {r['audio_s']:.2f} | {r['rtf']:.2f} |"
        )
    tot_s = sum(r["synth_s"] for r in synth["rows"])
    tot_a = sum(r["audio_s"] for r in synth["rows"])
    out += [f"| **Tổng** | | | **{tot_s:.1f}** | **{tot_a:.1f}** | **{tot_s / tot_a:.2f}** |", ""]

    out += [
        "## 2. Tổng hợp độ nhận đúng (trung bình trên các câu)",
        "",
        "Audio `vieneu` = cả câu do VieNeu đọc. Audio `ref` = câu thuần Anh do giọng Anh chuẩn đọc; câu trộn "
        "ghép phần Việt (VieNeu) với phần Anh (giọng Anh chuẩn).",
        "",
        "| Audio | Ngôn ngữ Whisper | Nhóm | n | Tỉ lệ từ đích đúng | WER phần Anh | Cụm đúng nguyên văn |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for audio_set in sorted(
        {r["set"] for r in rows}, key=lambda s: ("vieneu", "ref").index(s) if s in ("vieneu", "ref") else 9
    ):
        for lang in ("vi", "en", "auto"):
            for kind in ("all", "word", "pattern", "teacher", "child"):
                s = summary.get(f"{audio_set}/{lang}/{kind}")
                if not s:
                    continue
                name = "**Tất cả**" if kind == "all" else KIND_VI[kind]
                out.append(
                    f"| {audio_set} | {lang} | {name} | {s['n']} | {s['hit']:.0%} | {s['en_wer']:.0%} | {s['exact']:.0%} |"
                )
    out += [
        "",
        "## 3. Từng câu",
        "",
        "| Audio | Câu | Lang | Phát hiện | Whisper nghe được | Từ đích | WER Anh |",
        "|---|---|---|---|---|---:|---:|",
    ]
    for r in sorted(rows, key=lambda r: (r["set"], [s[0] for s in SENTENCES].index(r["id"]), r["lang"])):
        heard = r["heard"].replace("|", "/")
        out.append(
            f"| {r['set']} | {r['id']} | {r['lang']} | {r['detected'] or ''} | {heard} | {r['hit']:.0%} | {r['en_wer']:.0%} |"
        )
    (HERE / "results/score.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    (HERE / "results/score.json").write_text(
        json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    for k in sorted(summary):
        if k.endswith("/all"):
            s = summary[k]
            print(f"{k:18} hit {s['hit']:.0%}  en_wer {s['en_wer']:.0%}  exact {s['exact']:.0%}")


if __name__ == "__main__":
    main()
