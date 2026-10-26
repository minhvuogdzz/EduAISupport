"""A public HTTPS address for the app on this machine: `make tunnel` (REL-1, ADR-034).

Students on other computers cannot reach ``localhost``, and a browser lets a page use the microphone only over
HTTPS. A Cloudflare *quick tunnel* gives both for free, with no account: ``cloudflared tunnel --url
http://localhost:PORT`` prints a random ``https://<words>.trycloudflare.com`` that forwards to the one port
``make run`` serves. The address changes at every start; stop the tunnel and it is gone.

This runs ``cloudflared`` in the foreground, shows its log, picks the address out of it and prints it with the
few things to remember. ``caffeinate -i -w <pid>`` rides along (macOS): the machine does not idle-sleep while
the tunnel runs, and it ends by itself with it. Ctrl+C stops everything. Nothing is left behind.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Callable

from cavat import doctor

PUBLIC_URL = re.compile(r"https://[a-z0-9][a-z0-9-]*\.trycloudflare\.com")
SLOW_START_S = 45

REMEMBER = """\
 Ai có địa chỉ này và PIN đều vào được, và ai có địa chỉ cũng tự tạo được tài khoản học sinh:
   chỉ gửi cho các em tham gia buổi thử. Địa chỉ ngẫu nhiên, mất khi tắt đường hầm.
 Sau buổi thử: Ctrl+C ở đây, đổi PIN (make accounts), make backup.
 Máy phải bật và có mạng suốt buổi{awake}"""


def find_public_url(line: str) -> str | None:
    match = PUBLIC_URL.search(line)
    return match.group(0) if match else None


def banner(url: str, *, caffeinated: bool) -> str:
    awake = (
        ": caffeinate -i đang giữ máy không ngủ."
        if caffeinated
        else ": không có caffeinate, tự giữ máy không ngủ."
    )
    rule = "=" * 78
    return f"\n{rule}\n Địa chỉ công khai:  {url}\n{rule}\n{REMEMBER.format(awake=awake)}\n{rule}\n"


def stop(process: subprocess.Popen) -> None:
    for sig, wait in ((signal.SIGINT, 8), (signal.SIGTERM, 4), (signal.SIGKILL, 4)):
        if process.poll() is not None:
            return
        try:
            process.send_signal(sig)
            process.wait(timeout=wait)
        except subprocess.TimeoutExpired:
            continue
        except ProcessLookupError:
            return


def main(
    argv: list[str] | None = None,
    *,
    cavat_answers: Callable[[int], bool] = doctor.cavat_answers,
    which: Callable[[str], str | None] = shutil.which,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", doctor.DEFAULT_PORT)))
    parser.add_argument(
        "--cloudflared", default="cloudflared", help="the cloudflared program (tests use a stub)"
    )
    args = parser.parse_args(argv)
    tool = which(args.cloudflared)
    if tool is None:
        print("Không thấy cloudflared. Cài: brew install cloudflared")
        return 1
    if not cavat_answers(args.port):
        print(
            f"Chưa có CAVAT ở cổng {args.port}: chạy make run (hoặc make run-memory) trước, rồi make tunnel."
        )
        return 1
    process = subprocess.Popen(
        [tool, "tunnel", "--url", f"http://localhost:{args.port}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    awake = which("caffeinate")
    keeper = subprocess.Popen([awake, "-i", "-w", str(process.pid)]) if awake else None
    started, shown = time.monotonic(), False
    try:
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="", flush=True)
            url = find_public_url(line)
            if url and not shown:
                shown = True
                print(banner(url, caffeinated=keeper is not None), flush=True)
            elif not shown and time.monotonic() - started > SLOW_START_S:
                started = time.monotonic()
                print("(Chưa thấy địa chỉ công khai sau 45 giây: xem log ở trên, kiểm tra mạng.)", flush=True)
    except KeyboardInterrupt:
        print("\nĐang tắt đường hầm...")
    finally:
        stop(process)
        if keeper is not None:
            stop(keeper)
    print("Đường hầm đã tắt: địa chỉ công khai không còn dùng được.")
    return 0 if process.returncode in (0, -signal.SIGINT, -signal.SIGTERM) else process.returncode


if __name__ == "__main__":
    sys.exit(main())
