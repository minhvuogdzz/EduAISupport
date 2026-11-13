"""ENG-POC-voice, bổ sung: 10 câu theo Unit 11 "Family time" (Tiếng Anh 5 Global Success, tập hai).

    GROQ_API_KEY=... services/voice/.venv/bin/python poc/english-voice/unit11.py

One script, small quota: VieNeu synthesises each sentence once (timed); the reference (macOS
"Samantha", mixed sentences spliced as in synth.py) is made too. Whisper listens to VieNeu with `vi`
and `en`, and to the reference with `en` only: 10 × 3 = 30 calls, cached in
results/unit11_transcripts.json. Auto-detect is not measured again (the first run showed it unusable).

Besides the target-phrase scores of score.py it checks the past-tense verbs (took, ate, went,
bought...): is the exact past form in the transcript, or did Whisper write the base form / another
word? -> results/unit11.json, results/unit11.md. Audio: var/storage/poc/english-voice/u11_{vieneu,ref}/.

The sentences follow the unit's topic and the patterns the project owner named; except the two the
owner quoted, they are not checked word for word against the textbook.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
os.environ.setdefault("HF_HUB_CACHE", str(ROOT / "var/storage/voice/hf"))

import numpy as np  # noqa: E402
import requests  # noqa: E402
import soundfile as sf  # noqa: E402
from listen import PACE_S, transcribe  # noqa: E402
from score import hit_rate, span_wer, tokens  # noqa: E402
from synth import GAP_S, say_english  # noqa: E402
from vieneu import Vieneu  # noqa: E402

# (id, kind, text, english_target, past_verbs, parts)
UNIT11: list[tuple[str, str, str, str, list[str], list[tuple[str, str]] | None]] = [
    (
        "u1",
        "pattern",
        "Did you collect seashells? Yes, I did.",
        "did you collect seashells yes i did",
        [],
        None,
    ),
    (
        "u2",
        "pattern",
        "What did your family do in Ha Long Bay? We took a boat trip around the bay.",
        "what did your family do in ha long bay we took a boat trip around the bay",
        ["took"],
        None,
    ),
    (
        "u3",
        "teacher",
        "Con nói theo cô nhé: We ate seafood.",
        "we ate seafood",
        ["ate"],
        [("vi", "Con nói theo cô nhé:"), ("en", "We ate seafood.")],
    ),
    ("u4", "pattern", "We went to the beach.", "we went to the beach", ["went"], None),
    (
        "u5",
        "pattern",
        "My mother bought some souvenirs.",
        "my mother bought some souvenirs",
        ["bought"],
        None,
    ),
    (
        "u6",
        "pattern",
        "Did you swim in the sea? No, I didn't.",
        "did you swim in the sea no i didn't",
        [],
        None,
    ),
    (
        "u7",
        "pattern",
        "Where did you go last summer? I went to Ha Long Bay.",
        "where did you go last summer i went to ha long bay",
        ["went"],
        None,
    ),
    (
        "u8",
        "teacher",
        "Con nói theo cô nhé: My father took a lot of photos.",
        "my father took a lot of photos",
        ["took"],
        [("vi", "Con nói theo cô nhé:"), ("en", "My father took a lot of photos.")],
    ),
    (
        "u9",
        "teacher",
        "Con nhớ nhé: go, went. Eat, ate.",
        "go went eat ate",
        ["went", "ate"],
        [("vi", "Con nhớ nhé:"), ("en", "go, went. Eat, ate.")],
    ),
    (
        "u10",
        "child",
        "Con nghĩ là we bought some souvenirs.",
        "we bought some souvenirs",
        ["bought"],
        [("vi", "Con nghĩ là"), ("en", "we bought some souvenirs.")],
    ),
]
BASE = {"took": "take", "ate": "eat", "went": "go", "bought": "buy"}
RUNS = (("vieneu", "vi"), ("vieneu", "en"), ("ref", "en"))
OUT = ROOT / "var/storage/poc/english-voice"
CACHE = HERE / "results/unit11_transcripts.json"


def norm(text: str) -> list[str]:
    toks = tokens(text.replace("’", "'"))
    out: list[str] = []
    for t in toks:
        out += ["ha", "long"] if t == "halong" else [t]
    return out


def synthesise() -> list[dict]:
    (OUT / "u11_vieneu").mkdir(parents=True, exist_ok=True)
    (OUT / "u11_ref").mkdir(parents=True, exist_ok=True)
    engine = Vieneu()
    sr, voice = engine.sample_rate, "Ngọc Huyền"
    engine.infer("Xin chào các con.", voice=voice)  # warm-up, not timed

    def tts(text: str) -> np.ndarray:
        return np.asarray(engine.infer(text, voice=voice), dtype=np.float32)

    rows = []
    for sid, _, text, _, _, parts in UNIT11:
        t0 = time.perf_counter()
        audio = tts(text)
        took = time.perf_counter() - t0
        sf.write(OUT / "u11_vieneu" / f"{sid}.wav", audio, sr, subtype="PCM_16")
        if parts is None:
            ref = say_english(text, sr)
        else:
            gap = np.zeros(int(GAP_S * sr), dtype=np.float32)
            pieces = []
            for lang, piece in parts:
                pieces += [tts(piece) if lang == "vi" else say_english(piece, sr), gap]
            ref = np.concatenate(pieces[:-1])
        sf.write(OUT / "u11_ref" / f"{sid}.wav", ref, sr, subtype="PCM_16")
        rows.append({"id": sid, "synth_s": round(took, 3), "audio_s": round(len(audio) / sr, 3)})
        print(f"{sid:4} {took:5.2f}s for {len(audio) / sr:4.2f}s  {text}", flush=True)
    return rows


def main() -> None:
    synth_path = HERE / "results/unit11_synth.json"
    if synth_path.exists():
        synth = json.loads(synth_path.read_text(encoding="utf-8"))
    else:
        synth = synthesise()
        synth_path.write_text(json.dumps(synth, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    missing = [(s, a, lang) for s, *_ in UNIT11 for a, lang in RUNS if f"{a}/{s}/{lang}" not in cache]
    if missing:
        key = os.environ.get("GROQ_API_KEY") or sys.exit("GROQ_API_KEY is not set")
        session = requests.Session()
        session.headers["Authorization"] = f"Bearer {key}"
        for sid, audio_set, lang in missing:
            k = f"{audio_set}/{sid}/{lang}"
            cache[k] = transcribe(session, OUT / f"u11_{audio_set}" / f"{sid}.wav", lang)
            print(f"{k:16} {cache[k]['text']}", flush=True)
            CACHE.write_text(
                json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8"
            )
            time.sleep(PACE_S)

    rows = []
    for sid, kind, text, target, past, _ in UNIT11:
        for audio_set, lang in RUNS:
            heard = cache[f"{audio_set}/{sid}/{lang}"]["text"]
            ref, hyp = norm(target), norm(heard)
            wer = span_wer(ref, hyp)
            verbs = {v: ("past" if v in hyp else "base" if BASE[v] in hyp else "missing") for v in past}
            rows.append(
                {"id": sid, "kind": kind, "set": audio_set, "lang": lang, "text": text, "heard": heard,
                 "hit": round(hit_rate(ref, hyp), 3), "en_wer": round(wer, 3), "exact": wer == 0, "verbs": verbs}
            )  # fmt: skip

    lines = ['# Unit 11 "Family time": kết quả đo bổ sung (tự sinh bởi unit11.py)', ""]
    tot_s = sum(r["synth_s"] for r in synth)
    tot_a = sum(r["audio_s"] for r in synth)
    lines += [f"VieNeu: {tot_s:.1f} s tổng hợp cho {tot_a:.1f} s âm thanh (RTF {tot_s / tot_a:.2f}).", ""]
    lines += ["| Audio | Lang | Từ đích đúng | WER phần Anh | Cụm đúng nguyên văn | Động từ quá khứ đúng dạng |",
              "|---|---|---:|---:|---:|---:|"]  # fmt: skip
    summary = {}
    for audio_set, lang in RUNS:
        sel = [r for r in rows if r["set"] == audio_set and r["lang"] == lang]
        verbs = [v for r in sel for v in r["verbs"].values()]
        s = {
            "n": len(sel),
            "hit": sum(r["hit"] for r in sel) / len(sel),
            "en_wer": sum(r["en_wer"] for r in sel) / len(sel),
            "exact": sum(r["exact"] for r in sel) / len(sel),
            "past_ok": verbs.count("past"),
            "past_n": len(verbs),
        }
        summary[f"{audio_set}/{lang}"] = s
        lines.append(
            f"| {audio_set} | {lang} | {s['hit']:.0%} | {s['en_wer']:.0%} | {s['exact']:.0%} "
            f"| {s['past_ok']}/{s['past_n']} |"
        )
    lines += [
        "",
        "| Câu | Audio | Lang | Whisper nghe được | WER Anh | Động từ |",
        "|---|---|---|---|---:|---|",
    ]
    for r in rows:
        verbs = ", ".join(f"{v}: {state}" for v, state in r["verbs"].items())
        lines.append(f"| {r['id']} | {r['set']} | {r['lang']} | {r['heard']} | {r['en_wer']:.0%} | {verbs} |")
    (HERE / "results/unit11.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (HERE / "results/unit11.json").write_text(
        json.dumps({"summary": summary, "synth": synth, "rows": rows}, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    for k, s in summary.items():
        print(
            f"{k:12} hit {s['hit']:.0%} wer {s['en_wer']:.0%} exact {s['exact']:.0%} past {s['past_ok']}/{s['past_n']}"
        )


if __name__ == "__main__":
    main()
