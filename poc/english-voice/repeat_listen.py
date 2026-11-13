"""ENG-POC-voice: Whisper listens to the lone-word takes of word_repeat.py (bare word vs. Vietnamese carrier).

    GROQ_API_KEY=... services/voice/.venv/bin/python poc/english-voice/repeat_listen.py

Takes runs 0-1 of the spellings "Word." and "Con nói: word." (6 words × 2 runs × 2 spellings), language
`vi` and `en` = 48 calls. Per take: was the target word heard, and how many times (a word heard twice =
VieNeu repeated it). -> results/repeat_transcripts.json (cached), results/repeat_score.json.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from listen import PACE_S, transcribe  # noqa: E402
from score import tokens  # noqa: E402

ROOT = HERE.parents[1]
AUDIO = ROOT / "var/storage/poc/english-voice/repeat"
CACHE = HERE / "results/repeat_transcripts.json"
SPELLINGS = ("Word.", "Con nói: word.")
RUNS = (0, 1)
LANGS = ("vi", "en")


def main() -> None:
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        sys.exit("GROQ_API_KEY is not set")
    takes = json.loads((HERE / "results/word_repeat.json").read_text(encoding="utf-8"))["rows"]
    takes = [t for t in takes if t["spelling"] in SPELLINGS and t["run"] in RUNS]
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {key}"
    for take in takes:
        for lang in LANGS:
            k = f"{take['file']}/{lang}"
            if k in cache:
                continue
            cache[k] = transcribe(session, AUDIO / take["file"], lang)
            print(f"{k:45} {cache[k]['text']}", flush=True)
            CACHE.write_text(
                json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8"
            )
            time.sleep(PACE_S)

    summary: dict[str, dict] = {}
    rows = []
    for take in takes:
        for lang in LANGS:
            heard = cache[f"{take['file']}/{lang}"]["text"]
            count = tokens(heard).count(take["word"])
            rows.append({**take, "lang": lang, "heard": heard, "times_heard": count})
            s = summary.setdefault(f"{take['spelling']}/{lang}", {"n": 0, "heard": 0, "heard_twice": 0})
            s["n"] += 1
            s["heard"] += count >= 1
            s["heard_twice"] += count >= 2
    out = {"summary": summary, "rows": rows}
    (HERE / "results/repeat_score.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    for k, s in summary.items():
        print(f"{k:22} heard {s['heard']}/{s['n']}  heard twice {s['heard_twice']}/{s['n']}")


if __name__ == "__main__":
    main()
