"""One port, end to end (REL-1): start ``make run-memory`` on a free port, ask it, stop it. ``make smoke``.

Builds the web app first when it is out of date (so it takes a minute on a clean checkout), then checks that
ONE address answers the web app, its own paths, the API and the API's JSON 404, with the headers of a public
address. The server runs in its own process group and is killed in ``finally``: nothing is left running, and
the port is a free one the system picks, never 8000. CI runs this after the web build.
"""

from __future__ import annotations

import gzip
import json
import os
import re
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
START_TIMEOUT_S = 300  # the web build comes first


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def fetch(url: str, headers: dict[str, str] | None = None) -> tuple[int, dict[str, str], str]:
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            status, head, raw = response.status, response.headers, response.read()
    except urllib.error.HTTPError as exc:
        status, head, raw = exc.code, exc.headers, exc.read()
    lowered = {k.lower(): v for k, v in head.items()}
    if lowered.get("content-encoding") == "gzip":
        raw = gzip.decompress(raw)
    return status, lowered, raw.decode()


def wait_until_up(base: str, server: subprocess.Popen) -> None:
    deadline = time.monotonic() + START_TIMEOUT_S
    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise RuntimeError(f"make run-memory ended with code {server.returncode} before it answered")
        try:
            if fetch(base + "/health")[0] == 200:
                return
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
            time.sleep(1)
    raise RuntimeError(f"no answer from {base} in {START_TIMEOUT_S} s")


def checks(base: str) -> list[tuple[str, bool]]:
    results: list[tuple[str, bool]] = []

    def check(name: str, ok: bool) -> None:
        results.append((name, bool(ok)))

    status, headers, body = fetch(base + "/health")
    check("/health is the API", status == 200 and json.loads(body)["status"] == "ok")
    status, headers, page = fetch(base + "/")
    check(
        "/ is the web app",
        status == 200 and '<div id="root">' in page and headers["cache-control"] == "no-cache",
    )
    check(
        "security headers",
        headers.get("x-content-type-options") == "nosniff" and "x-frame-options" in headers,
    )
    status, _, deep = fetch(base + "/student/sessions/abc")
    check("/student/... is the web app (index.html fallback)", status == 200 and '<div id="root">' in deep)
    asset = re.search(r'(?:src|href)="(/assets/[^"]+\.js)"', page)
    if asset:
        status, headers, _ = fetch(base + asset.group(1), {"Accept-Encoding": "gzip"})
        check(
            "hashed asset is cached for a year",
            status == 200 and "immutable" in headers.get("cache-control", ""),
        )
    else:
        check("index.html points to a hashed script", False)
    status, headers, body = fetch(base + "/v1/does-not-exist")
    check(
        "/v1/... that does not exist is a JSON 404",
        status == 404 and json.loads(body)["error"]["code"] == "NOT_FOUND",
    )
    status, _, _ = fetch(base + "/openapi.json")
    check("/openapi.json is off", status == 404)
    status, headers, _ = fetch(base + "/health", {"Origin": "https://evil.example"})
    check("no CORS header for another origin", "access-control-allow-origin" not in headers)
    return results


def stop(server: subprocess.Popen) -> None:
    """End the whole process group (make, its shell, uvicorn), then make sure."""
    for sig, wait in ((signal.SIGINT, 10), (signal.SIGTERM, 5), (signal.SIGKILL, 5)):
        try:
            os.killpg(server.pid, sig)
        except ProcessLookupError:
            return
        try:
            server.wait(timeout=wait)
            return
        except subprocess.TimeoutExpired:
            continue


def main() -> int:
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    log = tempfile.NamedTemporaryFile("w+", prefix="cavat-smoke-", suffix=".log", delete=False)
    print(f"make run-memory PORT={port} (log: {log.name})")
    server = subprocess.Popen(
        ["make", "run-memory", f"PORT={port}", "VOICE=off"],
        cwd=ROOT,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    try:
        wait_until_up(base, server)
        results = checks(base)
    except Exception as exc:  # the server did not start, or a check broke: the report says which
        print(f"FAIL {type(exc).__name__}: {exc}")
        results = [("server starts and answers", False)]
    finally:
        stop(server)
    for name, ok in results:
        print(f"  {'ok  ' if ok else 'FAIL'} {name}")
    failed = [name for name, ok in results if not ok]
    if failed:
        log.seek(0)
        print("--- end of the server log ---")
        print("".join(log.readlines()[-30:]))
    else:
        os.unlink(log.name)
    print("stopped" if server.poll() is not None else "STILL RUNNING")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
