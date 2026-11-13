"""ENG-POC-voice: show how VieNeu's phonemizer (sea-g2p, lang="vi") reads each sentence.

English words that come out as English IPA (e.g. "mother" -> mˈʌðɚ) are routed to the English engine;
English words spelled as Vietnamese syllables would mean code-switching failed before synthesis.

    services/voice/.venv/bin/python poc/english-voice/g2p_check.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from sea_g2p import G2P  # noqa: E402
from sentences import SENTENCES  # noqa: E402

g2p = G2P(lang="vi")
rows = [{"id": sid, "text": text, "phonemes": g2p.convert(text)} for sid, _, text, _, _ in SENTENCES]
for row in rows:
    print(f"{row['id']:3} {row['text']}  =>  {row['phonemes']}")
(HERE / "results").mkdir(exist_ok=True)
(HERE / "results/g2p.json").write_text(
    json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
)
