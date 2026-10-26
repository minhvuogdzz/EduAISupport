"""Check the machine before a trial with students: `make doctor` (REL-1, ADR-034). READ-ONLY.

A table of green, yellow and red marks; the exit code is 1 when any is red, so a script can stop on it. It
reads and pings, it never writes: no database write, no file, no index. What it looks at:

- the keys of services/api/.env (their names only, never a value), and the login mode;
- MongoDB: a ping, the database name (``cavat_dev`` gets a yellow mark: real children's data beside the
  development data), the teacher account, the published teaching plans;
- the model chain of each kind of call (``--live``: one tiny call to each model; without it no call is made,
  so the Groq quota is untouched);
- the tutor's voice, the free port, ``cloudflared`` and ``caffeinate``, the disk of ``var/storage``, and
  whether apps/web/dist is newer than the web sources.

Red: students cannot be taught or can walk in without a login. Yellow: it works, but know what you accept.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import socket
import sys
import urllib.request
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from cavat import db, webbuild
from cavat.config import REPO_ROOT, Settings, get_settings

GB = 1024**3
MIN_KEY_CHARS = 16  # AUTH_SECRET shorter than this is easy to guess
DEFAULT_PORT = 8000


class Level(StrEnum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"


@dataclass(frozen=True)
class Check:
    name: str
    level: Level
    detail: str


@dataclass(frozen=True)
class DatabaseFacts:
    teachers: int
    students: int
    published: tuple[str, ...]  # chapter ids with a published teaching plan


# --- what is outside this process (the tests replace it) -------------------------------------------------


async def facts_from(database: Any) -> DatabaseFacts:
    """The few counts the trial depends on, read from ``database`` (any async PyMongo-like database)."""
    from cavat.modules.identity.repository import UserRepository
    from cavat.modules.ingest.repository import TeachingPlanRepository
    from cavat.modules.session.service import DEMO_SCHOOL_ID

    users = UserRepository(database, DEMO_SCHOOL_ID)
    plans = await TeachingPlanRepository(database, DEMO_SCHOOL_ID).list_published()
    return DatabaseFacts(
        teachers=len(await users.list_by_kind("TEACHER")),
        students=len(await users.list_by_kind("STUDENT")),
        published=tuple(sorted(plan.chapter_id for plan in plans)),
    )


async def read_database(settings: Settings) -> DatabaseFacts:
    """Ping Atlas, then read the facts. Raises when the database is not configured or does not answer."""
    try:
        await db.ping(settings)
        return await facts_from(db.get_db(settings))
    finally:
        await db.close_client()


def http_ok(url: str, timeout: float = 1.5) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 (a local URL)
            return 200 <= response.status < 300
    except Exception:
        return False


def port_busy(port: int) -> bool:
    for family, host in ((socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1")):
        try:
            with socket.socket(family) as sock:
                sock.settimeout(0.5)
                if sock.connect_ex((host, port)) == 0:
                    return True
        except OSError:
            continue
    return False


def cavat_answers(port: int) -> bool:
    """A CAVAT API already answers at this port (so "busy" is the app itself)."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1.5) as response:  # noqa: S310
            return b'"status"' in response.read(300) and response.status == 200
    except Exception:
        return False


def dir_size(path: Path) -> int:
    total = 0
    for root, _, files in os.walk(path):
        for name in files:
            try:
                total += (Path(root) / name).stat().st_size
            except OSError:
                continue
    return total


def free_space(path: Path) -> int:
    while not path.exists() and path != path.parent:
        path = path.parent
    return shutil.disk_usage(path).free


def ping_model(settings: Settings, model: str) -> str | None:
    """One tiny call to one model through the gateway; None when it answered, else why not."""
    from cavat.modules.ai_gateway.base import ChatMessage, ChatRequest, ModelClass
    from cavat.modules.ai_gateway.router import build_router

    schema = {
        "type": "object",
        "properties": {"ok": {"type": "boolean"}},
        "required": ["ok"],
        "additionalProperties": False,
    }
    request = ChatRequest(
        messages=(ChatMessage("system", "Trả lời bằng JSON."), ChatMessage("user", "Trả về ok=true.")),
        json_schema=schema,
        schema_name="doctor_ping",
        max_output_tokens=150,
    )
    router = build_router(settings, chains={ModelClass.LIGHTWEIGHT: (model,)})
    outcome = router.chat(ModelClass.LIGHTWEIGHT, request, calls_used=0)
    if outcome.result is not None:
        return None
    last = outcome.attempts[-1] if outcome.attempts else None
    return (last.error if last and last.error else None) or str(outcome.fallback_reason)


def model_chains(settings: Settings) -> dict[str, tuple[str, ...]]:
    """The models each kind of call tries, in order, as the gateway wires them (the tutor's Qwen first)."""
    from cavat.modules.ai_gateway.base import CHAT_MODEL_CLASSES, ModelClass
    from cavat.modules.ai_gateway.router import build_router

    router = build_router(settings)
    kinds = sorted(CHAT_MODEL_CLASSES - {ModelClass.EVAL_JUDGE})  # the judge belongs to the evaluations
    return {str(kind): router.chain(kind) for kind in kinds}


@dataclass
class Probes:
    read_database: Callable[[Settings], Awaitable[DatabaseFacts]] = read_database
    http_ok: Callable[[str], bool] = http_ok
    port_busy: Callable[[int], bool] = port_busy
    cavat_answers: Callable[[int], bool] = cavat_answers
    which: Callable[[str], str | None] = shutil.which
    dir_size: Callable[[Path], int] = dir_size
    free_space: Callable[[Path], int] = free_space
    ping_model: Callable[[Settings, str], str | None] = ping_model
    web_state: Callable[[], webbuild.BuildState] = webbuild.check
    voice_installed: Callable[[], bool] = lambda: (REPO_ROOT / "services/voice/.venv/bin/python").exists()
    chains: Callable[[Settings], dict[str, tuple[str, ...]]] = model_chains


# --- the checks ---------------------------------------------------------------------------------------------


def _set(secret: Any) -> bool:
    value = secret.get_secret_value() if hasattr(secret, "get_secret_value") else secret
    return bool(value and str(value).strip())


def check_keys(settings: Settings) -> list[Check]:
    required = {
        "MONGODB_URI": settings.mongodb_uri,
        "GROQ_API_KEY": settings.groq_api_key,
        "AUTH_SECRET": settings.auth_secret,
    }
    optional = {"GEMINI_API_KEY": settings.gemini_api_key}
    missing = [name for name, value in required.items() if not _set(value)]
    absent = [name for name, value in optional.items() if not _set(value)]
    out = []
    if missing:
        out.append(Check("Khóa trong .env", Level.FAIL, f"thiếu {', '.join(missing)} (services/api/.env)"))
    elif absent:
        out.append(
            Check(
                "Khóa trong .env",
                Level.WARN,
                f"{', '.join(absent)} chưa đặt: vector của RAG chạy offline, ảnh hình học không đọc được",
            )
        )
    else:
        names = ", ".join([*required, *optional])
        out.append(Check("Khóa trong .env", Level.OK, f"{names} đã đặt (giá trị không in)"))
    secret = settings.auth_secret.get_secret_value().strip() if _set(settings.auth_secret) else ""
    if secret and len(secret) < MIN_KEY_CHARS:
        out.append(
            Check("AUTH_SECRET", Level.WARN, f"ngắn hơn {MIN_KEY_CHARS} ký tự: dễ đoán, đặt chuỗi dài hơn")
        )
    if settings.auth_mode != "accounts":
        out.append(
            Check(
                "Đăng nhập",
                Level.FAIL,
                f"AUTH_MODE={settings.auth_mode}: không đăng nhập, ai mở địa chỉ cũng vào được",
            )
        )
    else:
        out.append(Check("Đăng nhập", Level.OK, "AUTH_MODE=accounts: PIN, khóa 5 phút khi sai 5 lần"))
    if settings.api_docs:
        out.append(
            Check(
                "API_DOCS",
                Level.WARN,
                "API_DOCS=1: /docs và /openapi.json công khai, tắt trước khi mở đường hầm",
            )
        )
    return out


def check_database(settings: Settings, facts: DatabaseFacts | None, error: str | None) -> list[Check]:
    name = settings.mongodb_db
    out = []
    if error is not None:
        out.append(Check("MongoDB", Level.FAIL, error))
    else:
        out.append(Check("MongoDB", Level.OK, f"ping ok, database `{name}`"))
    if name.startswith("cavat_test"):
        out.append(
            Check("Tên database", Level.FAIL, f"`{name}` là database của test: đặt MONGODB_DB cho buổi thử")
        )
    elif name == "cavat_dev":
        out.append(
            Check(
                "Tên database",
                Level.WARN,
                "`cavat_dev`: bài làm của học sinh nằm cạnh dữ liệu phát triển (chấp nhận cho buổi thử), "
                "make backup trước và sau buổi",
            )
        )
    else:
        out.append(Check("Tên database", Level.OK, f"`{name}`"))
    if facts is None:
        return out
    if facts.teachers < 1:
        out.append(
            Check(
                "Tài khoản giáo viên", Level.FAIL, "chưa có: không ai mở được trang giáo viên (make accounts)"
            )
        )
    else:
        out.append(
            Check(
                "Tài khoản giáo viên",
                Level.OK,
                f"{facts.teachers} tài khoản; {facts.students} học sinh đã tạo",
            )
        )
    if not facts.published:
        out.append(
            Check(
                "Kế hoạch dạy",
                Level.WARN,
                "chưa chương nào được duyệt xuất bản: gia sư dạy bản dựng sẵn trong mã",
            )
        )
    else:
        out.append(Check("Kế hoạch dạy", Level.OK, f"đã duyệt xuất bản: {', '.join(facts.published)}"))
    return out


def check_models(settings: Settings, probes: Probes, live: bool) -> list[Check]:
    chains = probes.chains(settings)
    keyed = _set(settings.groq_api_key)
    if not keyed:
        return [Check("Model của gia sư", Level.FAIL, "không có GROQ_API_KEY: gia sư chỉ nói bằng câu mẫu")]
    out = []
    if settings.tutor_renderer == "template":
        out.append(
            Check(
                "Lời gia sư", Level.WARN, "TUTOR_RENDERER=template: chỉ dùng câu mẫu đã duyệt, Qwen không nói"
            )
        )
    called: dict[str, str | None] = {}
    for kind, chain in chains.items():
        text = " → ".join(chain)
        if not live:
            out.append(Check(f"Model {kind}", Level.OK, f"{text} (chưa gọi thử: make doctor LIVE=1)"))
            continue
        for model in chain:
            if model not in called:
                called[model] = probes.ping_model(settings, model)
        marks = [f"{m} {'✔' if called[m] is None else '✘ ' + str(called[m])}" for m in chain]
        alive = [m for m in chain if called[m] is None]
        level = Level.OK if len(alive) == len(chain) else Level.WARN if alive else Level.FAIL
        out.append(Check(f"Model {kind}", level, " → ".join(marks)))
    return out


def check_voice(settings: Settings, probes: Probes) -> Check:
    if settings.tts == "off":
        return Check("Giọng gia sư", Level.OK, "TTS=off: trình duyệt tự đọc bằng giọng của máy")
    if probes.http_ok(f"{settings.vieneu_url.rstrip('/')}/health"):
        return Check(
            "Giọng gia sư", Level.OK, f"VieNeu đang chạy ở {settings.vieneu_url}; nghe bằng Groq Whisper"
        )
    if probes.voice_installed():
        return Check("Giọng gia sư", Level.OK, "VieNeu đã cài, chưa chạy: make run sẽ bật nội bộ")
    return Check(
        "Giọng gia sư",
        Level.WARN,
        "chưa cài VieNeu (make voice-setup): trình duyệt tự đọc bằng giọng của máy",
    )


def check_port(port: int, probes: Probes) -> Check:
    if not probes.port_busy(port):
        return Check("Cổng", Level.OK, f"{port} trống")
    if probes.cavat_answers(port):
        return Check("Cổng", Level.OK, f"{port} đang có một bản CAVAT chạy (đúng cổng duy nhất)")
    return Check("Cổng", Level.FAIL, f"{port} đang bận bởi chương trình khác: đổi PORT=... hoặc tắt nó")


def check_tools(probes: Probes) -> list[Check]:
    out = []
    for tool, why in (
        ("cloudflared", "đường hầm HTTPS cho máy khác (brew install cloudflared)"),
        ("caffeinate", "giữ máy không ngủ trong buổi thử"),
    ):
        path = probes.which(tool)
        if path:
            out.append(Check(tool, Level.OK, path))
        else:
            out.append(Check(tool, Level.WARN, f"không thấy: cần cho {why}"))
    return out


def check_disk(settings: Settings, probes: Probes) -> Check:
    folder = settings.storage_dir
    free = probes.free_space(folder)
    used = probes.dir_size(folder) if folder.exists() else 0
    text = f"{free / GB:.1f} GB trống; var/storage đang dùng {used / 1024**2:.0f} MB"
    if free < 1 * GB:
        return Check("Đĩa", Level.FAIL, f"{text}: dưới 1 GB, âm thanh và tài liệu sẽ không ghi được")
    if free < 5 * GB:
        return Check("Đĩa", Level.WARN, f"{text}: dưới 5 GB")
    return Check("Đĩa", Level.OK, text)


def check_web(settings: Settings, probes: Probes) -> Check:
    if (
        settings.web_dist != REPO_ROOT / "apps" / "web" / "dist"
        and not (settings.web_dist / "index.html").is_file()
    ):
        return Check("Giao diện web", Level.FAIL, f"WEB_DIST={settings.web_dist} không có index.html")
    state = probes.web_state()
    if state.fresh:
        return Check(
            "Giao diện web", Level.OK, f"{state.reason} (dựng lúc {state.built_at:%Y-%m-%d %H:%M} UTC)"
        )
    return Check("Giao diện web", Level.WARN, f"{state.reason}: make run tự dựng lại (khoảng 10 giây)")


async def run_checks(
    settings: Settings, probes: Probes | None = None, *, port: int = DEFAULT_PORT, live: bool = False
) -> list[Check]:
    probes = probes or Probes()
    checks = check_keys(settings)
    facts, error = None, None
    if not _set(settings.mongodb_uri):
        error = "MONGODB_URI chưa đặt"
    else:
        try:
            facts = await probes.read_database(settings)
        except (
            Exception
        ) as exc:  # network, auth, allow-list: the class says which, the message may hold a host
            error = (
                f"không kết nối được ({type(exc).__name__}): xem MONGODB_URI, mạng, IP allow-list của Atlas"
            )
    checks += check_database(settings, facts, error)
    checks += check_models(settings, probes, live)
    checks += [check_voice(settings, probes), check_port(port, probes), *check_tools(probes)]
    checks += [check_disk(settings, probes), check_web(settings, probes)]
    return checks


# --- the table ----------------------------------------------------------------------------------------------

MARKS = {Level.OK: ("✔", "32"), Level.WARN: ("!", "33"), Level.FAIL: ("✘", "31")}


def render(checks: list[Check], *, color: bool) -> str:
    width = max(len(c.name) for c in checks)
    lines = []
    for check in checks:
        mark, code = MARKS[check.level]
        mark = f"\033[{code}m{mark}\033[0m" if color else mark
        lines.append(f" {mark} {check.name:<{width}}  {check.detail}")
    count = {level: sum(c.level == level for c in checks) for level in Level}
    ready = "sẵn sàng cho buổi thử." if not count[Level.FAIL] else "chưa sẵn sàng: sửa các mục đỏ (✘)."
    lines.append(f"\n{count[Level.OK]} xanh · {count[Level.WARN]} vàng · {count[Level.FAIL]} đỏ: {ready}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true", help="call each model once (uses a little Groq quota)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", DEFAULT_PORT)))
    args = parser.parse_args(argv)
    settings = get_settings()
    print(f"CAVAT doctor · chỉ đọc · cổng {args.port}{' · gọi thử từng model' if args.live else ''}\n")
    checks = asyncio.run(run_checks(settings, port=args.port, live=args.live))
    color = sys.stdout.isatty() and "NO_COLOR" not in os.environ
    print(render(checks, color=color))
    return 1 if any(c.level == Level.FAIL for c in checks) else 0


if __name__ == "__main__":
    sys.exit(main())
