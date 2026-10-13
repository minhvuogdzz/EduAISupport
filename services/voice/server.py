"""The tutor's voice server (ADR-030): VieNeu-TTS behind one local HTTP endpoint.

    POST /speech  {"text": "...", "voice": ""}  ->  audio/wav (48 kHz mono)
    GET  /health                                 ->  {"ok": true, "voice": "..."}

Run with `make voice` (127.0.0.1:8010). The API (`cavat/modules/ai_gateway/vieneu.py`) is the only client;
it sends words already written out for reading (`cavat/modules/voice/speech_text.py`). One synthesis at a
time: on a CPU VieNeu serves one stream. The first start downloads VieNeu's model from Hugging Face.
"""

from __future__ import annotations

import io
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from pathlib import Path

# VieNeu's model lives with the project's other files (var/storage, gitignored), in a cache of its own:
# a shared Hugging Face cache written by huggingface_hub 2.x keeps the model's data where ONNX Runtime
# refuses to read it.
os.environ.setdefault("HF_HUB_CACHE", str(Path(__file__).resolve().parents[2] / "var/storage/voice/hf"))

import soundfile as sf  # noqa: E402
from vieneu import Vieneu  # noqa: E402

HOST, PORT = "127.0.0.1", int(os.environ.get("VOICE_PORT", "8010"))
MAX_CHARS = 1200
# The tutor is "cô": a woman's voice among VieNeu's recommended ones, Northern first.
PREFERRED = ("Ngọc Huyền", "Trúc Ly", "Đoan Trang", "Mai Anh", "Ngọc Linh")

engine = Vieneu()
presets = {voice_id for _, voice_id in engine.list_preset_voices()}  # (label shown, id)
default_voice = next((v for v in PREFERRED if v in presets), None)
lock = threading.Lock()


def synthesize(text: str, voice: str) -> bytes:
    chosen = voice if voice in presets else default_voice
    with lock:
        audio = engine.infer(text, voice=chosen) if chosen else engine.infer(text)
    out = io.BytesIO()
    sf.write(out, audio, engine.sample_rate, format="WAV", subtype="PCM_16")
    return out.getvalue()


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: bytes, kind: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._send(200, json.dumps({"ok": True, "voice": default_voice}).encode(), "application/json")
        else:
            self._send(404, b"", "text/plain")

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/speech":
            self._send(404, b"", "text/plain")
            return
        try:
            length = min(int(self.headers.get("Content-Length", "0")), 64_000)
            body = json.loads(self.rfile.read(length) or b"{}")
            text = str(body.get("text", "")).strip()[:MAX_CHARS]
            if not text:
                self._send(422, b"no text", "text/plain")
                return
            self._send(200, synthesize(text, str(body.get("voice") or "")), "audio/wav")
        except Exception as exc:  # one bad request never stops the voice
            self._send(500, type(exc).__name__.encode(), "text/plain")

    def log_message(self, fmt: str, *args) -> None:  # the words a child hears are not logged
        pass


if __name__ == "__main__":
    print(f"VieNeu-TTS voice on http://{HOST}:{PORT} (voice: {default_voice or 'default'})", flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
