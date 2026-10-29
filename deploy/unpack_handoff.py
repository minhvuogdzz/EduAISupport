#!/usr/bin/env python3
"""Prepare a handoff without overwriting an existing server configuration or data."""

import filecmp
import os
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path

NAMES = (".env", "db-dump/cavat-db.tar.gz", "db-dump/cavat-storage.tar.gz", "db-dump/SHA256SUMS")


def prepare(source: Path, destination: Path) -> None:
    with tempfile.TemporaryDirectory() as temp:
        temporary = Path(temp)
        if source.is_dir():
            for name in NAMES:
                file = source / name
                if not file.is_file() or file.is_symlink():
                    raise ValueError(f"Missing or unsafe file: {name}")
                (temporary / name).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(file, temporary / name)
        else:
            with tarfile.open(source, "r:gz") as archive:
                members = archive.getmembers()
                if len(members) != len(NAMES) or {m.name for m in members} != set(NAMES):
                    raise ValueError("Invalid handoff members")
                for member in members:
                    if not member.isfile():
                        raise ValueError(f"Unsafe handoff member: {member.name}")
                    target = temporary / member.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.extractfile(member) as inp, target.open("wb") as out:
                        shutil.copyfileobj(inp, out)
        # Check all targets before writing, including the initialized Mongo password.
        if (destination / "db-dump").is_symlink():
            raise ValueError("Unsafe destination: db-dump")
        for name in NAMES:
            target = destination / name
            if target.is_symlink() or (target.exists() and not target.is_file()):
                raise ValueError(f"Unsafe destination: {name}")
            if target.exists() and not filecmp.cmp(target, temporary / name, shallow=False):
                raise ValueError(f"Existing file differs; refusing to overwrite: {name}")
        for name in NAMES:
            target = destination / name
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as out, (temporary / name).open("rb") as inp:
                    shutil.copyfileobj(inp, out)


if __name__ == "__main__":
    try:
        prepare(Path(sys.argv[1]), Path.cwd())
    except (OSError, ValueError, tarfile.TarError, IndexError) as exc:
        print(f"Không thể chuẩn bị gói bàn giao: {exc}", file=sys.stderr)
        sys.exit(1)
