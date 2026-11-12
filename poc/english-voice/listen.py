"""ENG-POC-voice step 2: let Groq Whisper listen to every synthesised sentence, three language settings.

    GROQ_API_KEY=... services/voice/.venv/bin/python poc/english-voice/listen.py

For each audio set (vieneu, ref) and each setting (vi, en, auto = no `language` field) it sends the
WAV to /audio/transcriptions exactly like the API adapter does (whisper-large-v3, verbose_json,
temperature 0) and caches the raw text and detected language in results/transcripts.json. Cached
entries are not sent again, so a rerun only fills what is missing. Calls are paced (PACE_S) because
Whisper's free tier is limited per minute; a 429 waits for retry-after.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from sentences import SENTENCES  # noqa: E402

AUDIO = ROOT / "var/storage/poc/english-voice"
CACHE = HERE / "results/transcripts.json"
MODEL = os.environ.get("POC_STT_MODEL", "whisper-large-v3")
PACE_S = float(os.environ.get("PACE_S", "3.5"))
SETS = ("vieneu", "ref")
LANGS = ("vi", "en", "auto")
URL = "https://api.groq.com/openai/v1/audio/transcriptions"


def transcribe(session: requests.Session, wav: Path, lang: str) -> dict:
    data = {"model": MODEL, "response_format": "verbose_json", "temperature": "0"}
    if lang != "auto":
        data["language"] = lang
    for _attempt in range(6):
        with wav.open("rb") as fh:
            resp = session.post(URL, data=data, files={"file": (wav.name, fh, "audio/wav")}, timeout=60)
        if resp.status_code == 429:
            wait = float(resp.headers.get("retry-after") or 20)
            print(f"  429, waiting {wait:.0f}s", flush=True)
            time.sleep(wait + 1)
            continue
        resp.raise_for_status()
        body = resp.json()
        return {"text": body.get("text", "").strip(), "language": body.get("language")}
    raise RuntimeError("Whisper kept answering 429")


def main() -> None:
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        sys.exit("GROQ_API_KEY is not set")
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {key}"
    for audio_set in SETS:
        for sid, *_ in SENTENCES:
            for lang in LANGS:
                k = f"{audio_set}/{sid}/{lang}"
                if k in cache:
                    continue
                cache[k] = transcribe(session, AUDIO / audio_set / f"{sid}.wav", lang)
                print(f"{k:18} [{cache[k]['language']}] {cache[k]['text']}", flush=True)
                CACHE.write_text(
                    json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8"
                )
                time.sleep(PACE_S)
    print(f"{len(cache)} transcripts in {CACHE}")


if __name__ == "__main__":
    main()
