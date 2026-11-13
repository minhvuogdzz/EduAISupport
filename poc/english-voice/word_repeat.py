"""ENG-POC-voice: does VieNeu say a lone English word twice? How often, and which spelling avoids it?

    services/voice/.venv/bin/python poc/english-voice/word_repeat.py

Counts the bursts of speech in each WAV (50 ms RMS frames, a burst = speech separated by >= 250 ms of
quiet). A single word read once is one burst ("grandmother" may be two when the speaker pauses).
Each word × spelling is synthesised RUNS times (sampling is random). -> results/word_repeat.json,
WAVs under var/storage/poc/english-voice/repeat/.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
os.environ.setdefault("HF_HUB_CACHE", str(ROOT / "var/storage/voice/hf"))

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402
from vieneu import Vieneu  # noqa: E402

WORDS = ["mother", "father", "sister", "brother", "grandmother", "grandfather"]
SPELLINGS = {
    "Word.": lambda w: f"{w.capitalize()}.",
    "word": lambda w: w,
    "Word, word.": lambda w: f"{w.capitalize()}, {w}.",  # the teacher says it twice on purpose
    "Từ: word.": lambda w: f"Từ: {w}.",  # a Vietnamese carrier word in front
    "Con nói: word.": lambda w: f"Con nói theo cô: {w}.",
}
EXPECTED = {"Word.": 1, "word": 1, "Word, word.": 2, "Từ: word.": 2, "Con nói: word.": 2}
RUNS = int(os.environ.get("RUNS", "4"))
OUT = ROOT / "var/storage/poc/english-voice/repeat"


def bursts(audio: np.ndarray, sr: int) -> int:
    frame = int(sr * 0.05)
    loud = [
        float(np.sqrt(np.mean(audio[i : i + frame] ** 2))) > 0.02 for i in range(0, len(audio) - frame, frame)
    ]
    count, quiet, inside = 0, 99, False
    for is_loud in loud:
        if is_loud:
            if not inside and quiet >= 5:
                count += 1
            inside, quiet = True, 0
        else:
            quiet += 1
            if quiet >= 5:
                inside = False
    return count


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    engine = Vieneu()
    voice = "Ngọc Huyền"
    rows = []
    for label, make in SPELLINGS.items():
        for word in WORDS:
            text = make(word)
            for run in range(RUNS):
                audio = np.asarray(engine.infer(text, voice=voice), dtype=np.float32)
                n = bursts(audio, engine.sample_rate)
                name = f"{label.replace(' ', '_').replace(':', '').replace(',', '').replace('.', '')}_{word}_{run}.wav"
                sf.write(OUT / name, audio, engine.sample_rate, subtype="PCM_16")
                rows.append(
                    {
                        "spelling": label,
                        "word": word,
                        "text": text,
                        "run": run,
                        "bursts": n,
                        "audio_s": round(len(audio) / engine.sample_rate, 2),
                        "file": name,
                    }
                )
                print(
                    f"{label:15} {text:32} run {run}: {n} bursts, {len(audio) / engine.sample_rate:.2f}s",
                    flush=True,
                )
    summary = {}
    for label in SPELLINGS:
        sel = [r for r in rows if r["spelling"] == label]
        extra = [r for r in sel if r["bursts"] > EXPECTED[label]]
        summary[label] = {
            "n": len(sel),
            "more_bursts_than_expected": len(extra),
            "expected_bursts": EXPECTED[label],
        }
    (HERE / "results/word_repeat.json").write_text(
        json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    for label, s in summary.items():
        print(
            f"{label:15} {s['more_bursts_than_expected']}/{s['n']} with more bursts than {s['expected_bursts']}"
        )


if __name__ == "__main__":
    main()
