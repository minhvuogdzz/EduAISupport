"""Transfer the library, voice files and runtime caches alongside the database (ADR-036).

No model weights or source code are installed. A restore refuses a nonempty target and validates
every archive member before writing; it never follows links or extracts outside STORAGE_DIR.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tarfile
from pathlib import Path, PurePosixPath

from cavat.config import get_settings

RUNTIME_DIRS = {"documents", "voice", "rag", "web", "cache", "figures", "observability"}


class StorageError(ValueError):
    pass


def pack(source: Path, archive: Path) -> int:
    """Pack runtime files only, without backups, trial reports or unapproved figure previews."""
    if not source.is_dir():
        raise StorageError(f"Không có thư mục storage: {source}")
    files = []
    for folder in sorted(RUNTIME_DIRS):
        root = source / folder
        if root.is_symlink():
            raise StorageError(f"Không đóng gói liên kết: {root}")
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if path.relative_to(source).parts[:2] == ("voice", "hf"):
                continue  # VieNeu/Hugging Face weights are not part of the brain-only deployment.
            if path.is_symlink():
                raise StorageError(f"Không đóng gói liên kết: {path}")
            if path.is_file():
                files.append(path)
    archive.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(archive, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as raw, tarfile.open(fileobj=raw, mode="w:gz") as tar:
        for path in files:
            info = tar.gettarinfo(path, arcname=path.relative_to(source).as_posix())
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mode = 0o600
            with path.open("rb") as handle:
                tar.addfile(info, handle)
    return len(files)


def restore(archive: Path, target: Path, *, dry_run: bool = False) -> int:
    """Validate and load into an empty storage directory; a dry run also checks the target."""
    if target.is_symlink() or (target.exists() and (not target.is_dir() or any(target.iterdir()))):
        raise StorageError(f"Storage đích {target} không trống: không ghi đè tệp hiện có.")
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        seen: set[str] = set()
        for member in members:
            path = PurePosixPath(member.name)
            if (
                not member.isfile()
                or path.is_absolute()
                or len(path.parts) < 2
                or path.parts[0] not in RUNTIME_DIRS
                or any(p in {"", ".", ".."} for p in member.name.split("/"))
                or "\\" in member.name
                or member.name in seen
            ):
                raise StorageError(f"Thành viên storage không hợp lệ: {member.name!r}")
            seen.add(member.name)
            # Read the payload now too, so a truncated archive fails before any file is written.
            with tar.extractfile(member) as handle:
                while handle.read(1 << 20):
                    pass
        # A file cannot also be the parent directory of another member.
        if any(str(parent) in seen for name in seen for parent in PurePosixPath(name).parents):
            raise StorageError("Tệp storage bị trùng với đường dẫn thư mục.")
        if not dry_run:
            target.mkdir(parents=True, exist_ok=True)
            for member in members:
                destination = target / member.name
                destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as out, tar.extractfile(member) as source:
                    shutil.copyfileobj(source, out)
        return len(members)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    packing = sub.add_parser("pack")
    packing.add_argument("archive", type=Path)
    packing.add_argument("--source", type=Path)
    loading = sub.add_parser("restore")
    loading.add_argument("archive", type=Path)
    loading.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    settings = get_settings()
    try:
        if args.command == "pack":
            count = pack(args.source or settings.storage_dir, args.archive)
            print(f"Đã đóng gói {count} tệp storage: {args.archive}")
        else:
            count = restore(args.archive, settings.storage_dir, dry_run=args.dry_run)
            print(f"{'Đã kiểm tra' if args.dry_run else 'Đã nạp'} {count} tệp storage.")
    except (StorageError, OSError, tarfile.TarError, EOFError) as exc:
        print(f"Lỗi storage: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
