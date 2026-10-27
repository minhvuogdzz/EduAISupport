"""Is the web build in apps/web/dist newer than the web sources? (REL-1)

``make run`` serves apps/web/dist from the API. The dist is built with ``VITE_API=http`` (the real API); the
dist of ``make web-check`` is built for the mock API and must not be served. So ``make web-build`` marks its
own build with ``dist/.cavat-build`` (written after the build; vite empties the folder at the next build, so
any other build removes the mark) and rebuilds when a source is newer than the mark.

    python -m cavat.webbuild          exit 0: fresh, 1: missing or older than the sources (says why)
    python -m cavat.webbuild --mark   write the mark (``make web-build`` after ``pnpm build``)
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from cavat.config import REPO_ROOT

WEB = REPO_ROOT / "apps" / "web"
MARK = ".cavat-build"
# What the build reads: sources, static files, the lockfile and the configs. Paths relative to apps/web.
INPUTS = (
    "src",
    "public",
    "vite-plugins",
    "index.html",
    "package.json",
    "pnpm-lock.yaml",
    "vite.config.ts",
    "tsconfig.json",
    "tsconfig.app.json",
    "tsconfig.node.json",
)


@dataclass(frozen=True)
class BuildState:
    fresh: bool
    reason: str  # one sentence, for the person at the terminal
    built_at: datetime | None = None


def _files(web: Path):
    for name in INPUTS:
        path = web / name
        if path.is_file():
            yield path
        elif path.is_dir():
            yield from (p for p in path.rglob("*") if p.is_file())


def check(web: Path = WEB) -> BuildState:
    mark = web / "dist" / MARK
    if not (web / "dist" / "index.html").is_file():
        return BuildState(False, "chưa dựng web (apps/web/dist chưa có)")
    if not mark.is_file():
        return BuildState(
            False, "dist không do make web-build dựng (có thể là bản mock API của make web-check)"
        )
    built = mark.stat().st_mtime
    newer = next((p for p in _files(web) if p.stat().st_mtime > built), None)
    at = datetime.fromtimestamp(built, UTC)
    if newer is not None:
        return BuildState(False, f"mã web mới hơn bản dựng ({newer.relative_to(web)})", at)
    return BuildState(True, "bản dựng mới hơn mã nguồn", at)


def mark(web: Path = WEB) -> None:
    body = {"api": "http", "built_at": datetime.now(UTC).isoformat(timespec="seconds")}
    (web / "dist" / MARK).write_text(json.dumps(body) + "\n", encoding="utf-8")


def main(argv: list[str], web: Path = WEB) -> int:
    if "--mark" in argv:
        mark(web)
        return 0
    state = check(web)
    print(("Web đã dựng: " if state.fresh else "Cần dựng web: ") + state.reason)
    return 0 if state.fresh else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
