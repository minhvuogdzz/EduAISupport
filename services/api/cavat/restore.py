"""Load a database export into a database: ``python -m cavat.restore ARCHIVE`` (DEPLOY-1, ADR-036).

ARCHIVE is what ``make db-pack`` (``cavat.backup --archive``) writes: a ``.tar.gz``, or the folder
``make backup`` writes. It holds one ``<collection>.jsonl`` per collection (MongoDB extended JSON, one
document a line) and a ``manifest.json`` that says how many documents each collection had. The
documents go into the database of MONGODB_URI / MONGODB_DB (``--db`` names another), the indexes the
repositories declare are created, and every count is checked against the manifest. It is what the
person who deploys runs on the server, once:

    docker compose run --rm app python -m cavat.restore /dump/cavat-db-....tar.gz

Safe by default:

- an archive is read and checked completely (names, counts, JSON) before the first write;
- a database that already holds a document is refused (exit 2); ``--replace`` drops only the collections the
  archive has, the others stay;
- ``--dry-run`` stops after the check and writes nothing;
- the archive is read in memory, never extracted to disk, and a member that is not a plain file at the top
  level (a path, a link) refuses the whole archive.

Exit 0 loaded and counted, 1 a bad archive or a count that does not match, 2 refused because the database is
not empty.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import tarfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from bson import json_util

from cavat import db
from cavat.backup import MANIFEST
from cavat.config import get_settings

BATCH = 500
# the collections of this app are snake_case words; a name with a dot or a slash is never one of them
COLLECTION = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
READ = json_util.RELAXED_JSON_OPTIONS.with_options(tz_aware=True)  # as the app's client reads dates


class ArchiveError(ValueError):
    """The archive is not one this tool wrote, or it is damaged."""


class TargetNotEmpty(RuntimeError):
    """The database already holds documents and ``--replace`` was not given."""


class Archive:
    """The manifest and the lines of each collection of an export, a folder or a ``.tar.gz``."""

    def __init__(self, manifest: dict[str, Any], opener: Any) -> None:
        self.manifest = manifest
        self._open = opener

    @property
    def counts(self) -> dict[str, int]:
        return self.manifest["documents"]

    def lines(self, collection: str) -> Iterator[str]:
        with self._open(collection) as handle:
            for raw in handle:
                line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
                if line.strip():
                    yield line


def _check_manifest(manifest: Any, collections: set[str]) -> dict[str, Any]:
    documents = manifest.get("documents") if isinstance(manifest, dict) else None
    if not isinstance(documents, dict) or not all(type(n) is int and n >= 0 for n in documents.values()):
        raise ArchiveError(f"{MANIFEST} không có mục 'documents' (tên bộ sưu tập → số bản ghi).")
    bad = [name for name in documents if not COLLECTION.match(name)]
    if bad:
        raise ArchiveError(f"Tên bộ sưu tập không hợp lệ trong {MANIFEST}: {bad[0]!r}.")
    if set(documents) != collections:
        extra, missing = sorted(collections - set(documents)), sorted(set(documents) - collections)
        raise ArchiveError(f"Tệp và {MANIFEST} không khớp nhau (thừa tệp: {extra}; thiếu tệp: {missing}).")
    return manifest


@contextmanager
def open_archive(path: Path) -> Iterator[Archive]:
    """Open ``path`` (a folder or a ``.tar.gz``) and check its shape; nothing is extracted to disk."""
    if path.is_dir():
        files = {p.name: p for p in path.iterdir()}
        if any(p.is_symlink() or not p.is_file() for p in files.values()):
            raise ArchiveError("Thư mục xuất chỉ được chứa tệp thường, không có liên kết.")
        if MANIFEST not in files:
            raise ArchiveError(f"Thư mục {path} không có {MANIFEST}.")
        collections = {n.removesuffix(".jsonl") for n in files if n.endswith(".jsonl")}
        manifest = _check_manifest(json.loads(files[MANIFEST].read_text(encoding="utf-8")), collections)
        yield Archive(manifest, lambda name: files[f"{name}.jsonl"].open("r", encoding="utf-8"))
        return
    try:
        tar = tarfile.open(path, "r:gz")
    except (tarfile.TarError, OSError) as exc:
        raise ArchiveError(f"{path} không phải tệp .tar.gz đọc được ({exc}).") from exc
    with tar:
        members: dict[str, tarfile.TarInfo] = {}
        for member in tar.getmembers():
            if not member.isreg() or "/" in member.name or member.name.startswith("."):
                raise ArchiveError(
                    f"Thành viên không hợp lệ trong tệp nén: {member.name!r} (chỉ nhận tệp thường ở gốc)."
                )
            if member.name in members:
                raise ArchiveError(f"Tệp lặp trong tệp nén: {member.name!r}.")
            members[member.name] = member
        if MANIFEST not in members:
            raise ArchiveError(f"Tệp nén không có {MANIFEST}.")
        collections = {n.removesuffix(".jsonl") for n in members if n.endswith(".jsonl")}
        stray = sorted(n for n in members if n != MANIFEST and not n.endswith(".jsonl"))
        if stray:
            raise ArchiveError(f"Tệp lạ trong tệp nén: {stray[0]!r}.")
        manifest_file = tar.extractfile(members[MANIFEST])
        assert manifest_file is not None
        manifest = _check_manifest(json.loads(manifest_file.read().decode("utf-8")), collections)

        def opener(name: str):
            handle = tar.extractfile(members[f"{name}.jsonl"])
            assert handle is not None
            return handle

        yield Archive(manifest, opener)


def check_counts(archive: Archive) -> dict[str, int]:
    """Read every line (valid JSON, an object with an ``_id``) and compare with the manifest; no database."""
    counts: dict[str, int] = {}
    for name, expected in archive.counts.items():
        count = 0
        seen_ids: set[str] = set()
        for line in archive.lines(name):
            try:
                doc = json_util.loads(line, json_options=READ)
            except ValueError as exc:
                raise ArchiveError(f"{name}.jsonl dòng {count + 1} không đọc được: {exc}") from exc
            if not isinstance(doc, dict) or "_id" not in doc:
                raise ArchiveError(f"{name}.jsonl dòng {count + 1} không phải bản ghi có _id.")
            key = json_util.dumps(doc["_id"], json_options=json_util.CANONICAL_JSON_OPTIONS)
            if key in seen_ids:
                raise ArchiveError(f"{name}.jsonl dòng {count + 1} có _id bị lặp.")
            seen_ids.add(key)
            count += 1
        if count != expected:
            raise ArchiveError(f"{name}: tệp có {count} bản ghi nhưng {MANIFEST} ghi {expected}.")
        counts[name] = count
    return counts


async def holds_documents(database: Any) -> list[str]:
    """The collections of ``database`` that hold at least one document."""
    busy = []
    for name in await database.list_collection_names():
        if not name.startswith("system.") and await database[name].count_documents({}) > 0:
            busy.append(name)
    return busy


async def load_collection(collection: Any, lines: Iterator[str], batch: int = BATCH) -> int:
    loaded, buffer = 0, []
    for line in lines:
        buffer.append(json_util.loads(line, json_options=READ))
        if len(buffer) >= batch:
            await collection.insert_many(buffer)
            loaded, buffer = loaded + len(buffer), []
    if buffer:
        await collection.insert_many(buffer)
        loaded += len(buffer)
    return loaded


async def restore(
    database: Any, archive: Archive, *, replace: bool = False, dry_run: bool = False
) -> dict[str, int]:
    """Check ``archive``, then load it into ``database``; the counts the database holds afterwards."""
    expected = check_counts(archive)
    if dry_run:
        return expected
    busy = await holds_documents(database)
    if busy and not replace:
        raise TargetNotEmpty(f"Database {database.name!r} đã có dữ liệu ở: {', '.join(busy)}.")
    for name in archive.counts:
        if replace:
            await database.drop_collection(name)
        await load_collection(database[name], archive.lines(name))
    await db.ensure_indexes(database)
    found = {name: await database[name].count_documents({}) for name in expected}
    if found != expected:
        wrong = [f"{n}: {found[n]} thay vì {expected[n]}" for n in expected if found[n] != expected[n]]
        raise ArchiveError("Số bản ghi sau khi nạp không khớp: " + "; ".join(wrong))
    return found


def host_of(uri: str) -> str:
    try:
        return urlsplit(uri).hostname or "?"
    except ValueError:
        return "?"


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m cavat.restore", description=__doc__.split("\n")[0])
    parser.add_argument(
        "archive", type=Path, help="tệp .tar.gz hoặc thư mục do make db-pack / make backup tạo"
    )
    parser.add_argument("--db", help="tên database đích (mặc định MONGODB_DB trong cấu hình)")
    parser.add_argument("--replace", action="store_true", help="xóa rồi nạp lại các bộ sưu tập có trong tệp")
    parser.add_argument("--dry-run", action="store_true", help="chỉ kiểm tra tệp, không ghi gì")
    args = parser.parse_args(argv)

    settings = get_settings()
    try:
        with open_archive(args.archive) as archive:
            total = sum(archive.counts.values())
            source = archive.manifest.get("database") or "?"
            if args.dry_run:
                counts = await restore(None, archive, dry_run=True)
                print(f"Tệp hợp lệ: {total} bản ghi của {len(counts)} bộ sưu tập (nguồn: {source}).")
                print("Chưa ghi gì.")
                return 0
            try:
                client = db.get_client(settings)
            except db.DatabaseNotConfiguredError:
                print("MONGODB_URI chưa được đặt.")
                return 1
            name = args.db or settings.mongodb_db
            host = host_of(settings.mongodb_uri.get_secret_value())
            print(f"Nạp {total} bản ghi của {len(archive.counts)} bộ sưu tập (nguồn: {source})")
            print(f"vào database {name!r} ở {host}.")
            counts = await restore(client[name], archive, replace=args.replace)
    except TargetNotEmpty as exc:
        print(f"{exc}\nKhông ghi gì. Muốn nạp đè đúng các bộ sưu tập trong tệp: thêm --replace.")
        return 2
    except (ArchiveError, ValueError, OSError, tarfile.TarError, EOFError) as exc:
        print(f"Lỗi: {exc}")
        return 1
    finally:
        await db.close_client()
    width = max((len(n) for n in counts), default=0)
    for collection, count in counts.items():
        print(f"  {collection:<{width}}  {count:>7}")
    print(f"Đã nạp và đếm lại khớp: {sum(counts.values())} bản ghi, chỉ mục đã tạo.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
