"""The commit of the code this process runs (ENG-5i, DI-184), for ``/health``.

From a git checkout (``make run``, ``make run-memory``) it is the checkout's HEAD, read once when the app
is built: a ``CAVAT_REVISION`` left in ``services/api/.env`` by an earlier release told the wrong commit
(the third live run: 35d15a6 on main 79404e4). In the Docker image there is no ``.git``; there
``CAVAT_REVISION`` (a build argument, ``deploy/start.sh``) is the truth. Neither: "development".
"""

from __future__ import annotations

import os
import subprocess
from functools import lru_cache
from pathlib import Path

SOURCE = Path(__file__).resolve().parent


def _git_head(where: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=where, capture_output=True, text=True, timeout=3, check=True
        )
    except (OSError, subprocess.SubprocessError):
        return None
    head = out.stdout.strip()
    return head if len(head) >= 7 and all(c in "0123456789abcdef" for c in head) else None


@lru_cache(maxsize=1)
def revision(where: Path = SOURCE) -> str:
    return _git_head(where) or os.environ.get("CAVAT_REVISION") or "development"
