"""ENG-POC-voice step 1: synthesise every sentence with VieNeu (the tutor's voice) and a reference.

Run with the voice venv (it has vieneu, soundfile, soxr):

    services/voice/.venv/bin/python poc/english-voice/synth.py

Writes (gitignored, under var/):
  var/storage/poc/english-voice/vieneu/<id>.wav   VieNeu v3 Turbo, voice "Ngọc Huyền" (as server.py)
  var/storage/poc/english-voice/ref/<id>.wav      English-only items: macOS "Samantha" (en_US);
                                                 mixed items: VieNeu for the Vietnamese parts +
                                                 Samantha for the English part ("hybrid")
and poc/english-voice/results/synth.json with the CPU synthesis time per sentence.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("HF_HUB_CACHE", str(ROOT / "var/storage/voice/hf"))  # same cache as server.py

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402
import soxr  # noqa: E402
from sentences import SENTENCES  # noqa: E402
from vieneu import Vieneu  # noqa: E402

OUT = ROOT / "var/storage/poc/english-voice"
RESULTS = Path(__file__).resolve().parent / "results"
VOICE = os.environ.get("POC_VOICE", "Ngọc Huyền")
EN_VOICE = os.environ.get("POC_EN_VOICE", "Samantha")
GAP_S = 0.15


def say_english(text: str, sr: int) -> np.ndarray:
    with tempfile.TemporaryDirectory() as tmp:
        aiff = Path(tmp) / "en.aiff"
        subprocess.run(["say", "-v", EN_VOICE, "-o", str(aiff), text], check=True)
        audio, rate = sf.read(aiff, dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    return soxr.resample(audio, rate, sr).astype(np.float32)


def main() -> None:
    (OUT / "vieneu").mkdir(parents=True, exist_ok=True)
    (OUT / "ref").mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(exist_ok=True)

    t0 = time.perf_counter()
    engine = Vieneu()
    load_s = time.perf_counter() - t0
    sr = engine.sample_rate
    presets = {voice_id for _, voice_id in engine.list_preset_voices()}
    voice = VOICE if VOICE in presets else None

    t0 = time.perf_counter()
    engine.infer("Xin chào các con.", voice=voice) if voice else engine.infer("Xin chào các con.")
    warmup_s = time.perf_counter() - t0

    def tts(text: str) -> np.ndarray:
        return np.asarray(engine.infer(text, voice=voice) if voice else engine.infer(text), dtype=np.float32)

    rows = []
    for sid, kind, text, _target, parts in SENTENCES:
        t0 = time.perf_counter()
        audio = tts(text)
        synth_s = time.perf_counter() - t0
        sf.write(OUT / "vieneu" / f"{sid}.wav", audio, sr, subtype="PCM_16")
        dur = len(audio) / sr

        if parts is None:
            ref = say_english(text, sr)
        else:
            gap = np.zeros(int(GAP_S * sr), dtype=np.float32)
            pieces = []
            for lang, piece in parts:
                pieces += [tts(piece) if lang == "vi" else say_english(piece, sr), gap]
            ref = np.concatenate(pieces[:-1])
        sf.write(OUT / "ref" / f"{sid}.wav", ref, sr, subtype="PCM_16")

        rows.append(
            {
                "id": sid,
                "kind": kind,
                "text": text,
                "synth_s": round(synth_s, 3),
                "audio_s": round(dur, 3),
                "rtf": round(synth_s / dur, 3) if dur else None,
            }
        )
        print(f"{sid:3} {synth_s:5.2f}s for {dur:4.2f}s audio  {text}", flush=True)

    meta = {
        "vieneu_version": __import__("importlib.metadata").metadata.version("vieneu"),
        "model": "VieNeu-TTS v3 Turbo (SDK default), ONNX Runtime CPU, fp32",
        "voice": voice or "default",
        "en_reference_voice": f"macOS say -v {EN_VOICE}",
        "machine": f"{platform.machine()} {platform.platform()} {platform.processor()}",
        "load_s": round(load_s, 2),
        "warmup_s": round(warmup_s, 2),
        "sample_rate": sr,
        "rows": rows,
    }
    (RESULTS / "synth.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(f"load {load_s:.1f}s, warm-up {warmup_s:.1f}s; wrote {RESULTS / 'synth.json'}")


if __name__ == "__main__":
    main()
