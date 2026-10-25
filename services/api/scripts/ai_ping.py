"""Call Groq (Qwen) and Gemini (vision) once with the keys in services/api/.env. Local only.

Usage: ``make ai-ping``. Prints model, token usage and remaining quota; never prints keys.
"""

from __future__ import annotations

import struct
import sys
import zlib

from cavat.config import get_settings
from cavat.modules.ai_gateway.base import AIGatewayError, ChatMessage, ChatRequest, ModelClass
from cavat.modules.ai_gateway.router import build_router, groq_key

PING_SCHEMA = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}, "reply": {"type": "string"}},
    "required": ["ok", "reply"],
    "additionalProperties": False,
}


def _tiny_png(size: int = 16) -> bytes:
    """A white square with a black diagonal, built without extra dependencies."""
    rows = b"".join(
        b"\x00" + b"".join(b"\x00\x00\x00" if x == y else b"\xff\xff\xff" for x in range(size))
        for y in range(size)
    )

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


def ping_groq(router) -> bool:
    request = ChatRequest(
        messages=(
            ChatMessage("system", "Trả lời bằng JSON."),
            ChatMessage("user", "Kiểm tra kết nối: trả về ok=true và một câu chào ngắn bằng tiếng Việt."),
        ),
        json_schema=PING_SCHEMA,
        schema_name="ping",
        max_output_tokens=60,
    )
    outcome = router.chat(ModelClass.TUTOR_REASONING, request, calls_used=0)
    for attempt in outcome.attempts:
        print(f"  attempt {attempt.model}: sent={attempt.sent} error={attempt.error}")
    if outcome.result is None:
        print(f"Groq: FAIL, caller would use templates ({outcome.fallback_reason})")
        return False
    result = outcome.result
    print(f"Groq: OK model={result.model} data={result.data} usage={result.usage}")
    snap = router.quota.snapshot(result.model)
    if snap is not None:
        print(
            f"  quota: requests {snap.remaining_requests}/{snap.limit_requests}, "
            f"tokens {snap.remaining_tokens}/{snap.limit_tokens}"
        )
    return True


def ping_gemini(router) -> bool:
    try:
        result = router.describe_image(_tiny_png(), "Mô tả ngắn gọn hình này trong một câu.")
    except AIGatewayError as exc:
        print(f"Gemini: FAIL {type(exc).__name__}: {exc}")
        return False
    print(f"Gemini: OK model={result.model} usage={result.usage}")
    print(f"  text: {result.text[:200]}")
    return True


def main() -> int:
    settings = get_settings()
    router = build_router(settings)
    ok = True
    if settings.groq_api_key is None or not settings.groq_api_key.get_secret_value():
        print("Groq: SKIP (GROQ_API_KEY chưa đặt trong services/api/.env)")
    else:
        ok = ping_groq(router) and ok
        if groq_key(settings, for_eval=True) != settings.groq_api_key:  # CFG-3: a key of its own for evals
            print("Groq (khóa của bài đo, GROQ_API_KEY_EVAL):")
            ok = ping_groq(build_router(settings, for_eval=True)) and ok
    if settings.gemini_api_key is None or not settings.gemini_api_key.get_secret_value():
        print("Gemini: SKIP (GEMINI_API_KEY chưa đặt trong services/api/.env)")
    else:
        ok = ping_gemini(router) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
