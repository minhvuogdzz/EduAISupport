"""DEPLOY-1: ``python -m cavat.restore`` loads an export into a database and checks it. Offline: the in-memory
database stands in for Atlas (the source) and for the Mongo of the server (the target)."""

import io
import json
import stat
import tarfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from cavat import backup, restore
from cavat.core.memory_db import InMemoryDatabase

WHEN = datetime(2026, 10, 26, 14, 30, 5, tzinfo=UTC)
USERS = [
    {"_id": "u1", "school_id": "s", "login_name": "hs-an", "pin_hash": "scrypt$x", "created_at": WHEN},
    {"_id": "u2", "school_id": "s", "login_name": "giaovien", "display_name": "Cô Hà — Toán 5"},
]
SESSION = {
    "_id": "ls1",
    "school_id": "s",
    "student_id": "u1",
    "state_version": 7,
    "events": [{"type": "TUTOR_SAID", "text": "0,25 < 0,3", "at": WHEN}],
}


async def exported(tmp_path: Path) -> Path:
    """The export folder of a small database, as ``make backup`` writes it."""
    source = InMemoryDatabase(name="cavat_source")
    await source["users"].insert_many(USERS)
    await source["learning_sessions"].insert_one(SESSION)
    folder = tmp_path / "export"
    await backup.export_database(source, folder)
    return folder


async def archived(tmp_path: Path) -> Path:
    archive = tmp_path / "cavat-db.tar.gz"
    backup.pack_archive(await exported(tmp_path), archive)
    return archive


def tar_of(path: Path, members: dict[str, bytes], **extra: tarfile.TarInfo) -> Path:
    """A ``.tar.gz`` with exactly these members (and the given special ones: a link, a folder)."""
    with tarfile.open(path, "w:gz") as tar:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        for info in extra.values():
            tar.addfile(info)
    return path


def manifest(**counts: int) -> bytes:
    return json.dumps({"database": "x", "documents": counts}).encode()


def line(doc: dict) -> bytes:
    return json.dumps(doc).encode() + b"\n"


async def rows(database: InMemoryDatabase, name: str) -> list[dict]:
    return await database[name].find({}).to_list()


async def test_an_archive_loads_every_document_into_an_empty_database_and_creates_the_indexes(tmp_path):
    target = InMemoryDatabase(name="cavat_target")
    with restore.open_archive(await archived(tmp_path)) as archive:
        counts = await restore.restore(target, archive)

    assert counts == {"learning_sessions": 1, "users": 2}
    assert sorted(await rows(target, "users"), key=lambda d: d["_id"]) == USERS
    assert await rows(target, "learning_sessions") == [SESSION]
    assert len(await target["users"].index_information()) > 1  # the repositories' indexes, not only _id


async def test_a_folder_loads_like_an_archive(tmp_path):
    target = InMemoryDatabase()
    with restore.open_archive(await exported(tmp_path)) as archive:
        assert await restore.restore(target, archive) == {"learning_sessions": 1, "users": 2}
    assert await rows(target, "learning_sessions") == [SESSION]


async def test_a_database_that_holds_documents_is_refused_and_left_as_it_was(tmp_path):
    target = InMemoryDatabase(name="cavat_target")
    await target["users"].insert_one({"_id": "keep"})
    with restore.open_archive(await archived(tmp_path)) as archive:
        with pytest.raises(restore.TargetNotEmpty, match="cavat_target"):
            await restore.restore(target, archive)
    assert await rows(target, "users") == [{"_id": "keep"}]
    assert await rows(target, "learning_sessions") == []


async def test_replace_drops_only_the_collections_of_the_archive(tmp_path):
    target = InMemoryDatabase()
    await target["users"].insert_one({"_id": "old"})
    await target["unrelated"].insert_one({"_id": "stays"})
    with restore.open_archive(await archived(tmp_path)) as archive:
        await restore.restore(target, archive, replace=True)
    assert sorted(d["_id"] for d in await rows(target, "users")) == ["u1", "u2"]
    assert await rows(target, "unrelated") == [{"_id": "stays"}]


async def test_a_dry_run_checks_the_archive_and_writes_nothing(tmp_path):
    target = InMemoryDatabase()
    with restore.open_archive(await archived(tmp_path)) as archive:
        counts = await restore.restore(target, archive, dry_run=True)
    assert counts == {"learning_sessions": 1, "users": 2}
    assert await target.list_collection_names() == []


def test_an_archive_without_a_manifest_is_refused(tmp_path):
    path = tar_of(tmp_path / "a.tar.gz", {"users.jsonl": line({"_id": 1})})
    with pytest.raises(restore.ArchiveError, match="manifest"):
        with restore.open_archive(path):
            pass


def test_files_and_manifest_must_name_the_same_collections(tmp_path):
    path = tar_of(
        tmp_path / "a.tar.gz",
        {
            "manifest.json": manifest(users=1),
            "users.jsonl": line({"_id": 1}),
            "extra.jsonl": line({"_id": 2}),
        },
    )
    with pytest.raises(restore.ArchiveError, match="không khớp"):
        with restore.open_archive(path):
            pass


@pytest.mark.parametrize("name", ["../evil.jsonl", "sub/users.jsonl", "/abs.jsonl", ".hidden.jsonl"])
def test_a_member_that_is_not_a_plain_top_level_file_refuses_the_whole_archive(tmp_path, name):
    path = tar_of(tmp_path / "a.tar.gz", {"manifest.json": manifest(users=0), name: b""})
    with pytest.raises(restore.ArchiveError, match="không hợp lệ"):
        with restore.open_archive(path):
            pass


def test_a_link_member_refuses_the_whole_archive(tmp_path):
    link = tarfile.TarInfo("users.jsonl")
    link.type, link.linkname = tarfile.SYMTYPE, "/etc/passwd"
    path = tar_of(tmp_path / "a.tar.gz", {"manifest.json": manifest(users=0)}, link=link)
    with pytest.raises(restore.ArchiveError, match="không hợp lệ"):
        with restore.open_archive(path):
            pass


def test_a_file_that_is_not_an_archive_is_said_so(tmp_path):
    path = tmp_path / "x.tar.gz"
    path.write_bytes(b"this is not gzip")
    with pytest.raises(restore.ArchiveError, match="không phải tệp .tar.gz"):
        with restore.open_archive(path):
            pass


@pytest.mark.parametrize("name", ["system.users", "users.old", "a/b", "1abc"])
def test_a_collection_name_that_is_not_one_of_the_apps_is_refused(tmp_path, name):
    path = tar_of(tmp_path / "a.tar.gz", {"manifest.json": manifest(**{name: 0}), f"{name}.jsonl": b""})
    with pytest.raises(restore.ArchiveError):
        with restore.open_archive(path):
            pass


async def test_a_count_that_differs_from_the_manifest_is_refused_before_any_write(tmp_path):
    path = tar_of(
        tmp_path / "a.tar.gz",
        {"manifest.json": manifest(users=3), "users.jsonl": line({"_id": 1}) + line({"_id": 2})},
    )
    target = InMemoryDatabase()
    with restore.open_archive(path) as archive:
        with pytest.raises(restore.ArchiveError, match="users: tệp có 2 bản ghi nhưng manifest.json ghi 3"):
            await restore.restore(target, archive)
    assert await target.list_collection_names() == []


async def test_duplicate_ids_are_refused_before_any_collection_is_written(tmp_path):
    path = tar_of(
        tmp_path / "duplicate.tar.gz",
        {"manifest.json": manifest(users=2), "users.jsonl": line({"_id": 1}) * 2},
    )
    target = InMemoryDatabase()
    with restore.open_archive(path) as archive:
        with pytest.raises(restore.ArchiveError, match="_id bị lặp"):
            await restore.restore(target, archive)
    assert await target.list_collection_names() == []


async def test_a_line_that_is_not_a_document_with_an_id_is_refused_before_any_write(tmp_path):
    for bad in (b"not json\n", b'{"no_id": 1}\n', b"[1, 2]\n"):
        path = tar_of(tmp_path / "a.tar.gz", {"manifest.json": manifest(users=1), "users.jsonl": bad})
        target = InMemoryDatabase()
        with restore.open_archive(path) as archive:
            with pytest.raises(restore.ArchiveError, match=r"users\.jsonl dòng 1"):
                await restore.restore(target, archive)
        assert await target.list_collection_names() == []
        path.unlink()


async def test_a_collection_is_loaded_in_batches(tmp_path):
    docs = b"".join(line({"_id": i}) for i in range(1203))
    path = tar_of(tmp_path / "a.tar.gz", {"manifest.json": manifest(big=1203), "big.jsonl": docs})
    target = InMemoryDatabase()
    with restore.open_archive(path) as archive:
        assert await restore.restore(target, archive) == {"big": 1203}
    assert await target["big"].count_documents({}) == 1203


async def test_pack_archive_puts_the_manifest_first_keeps_it_private_and_never_overwrites(tmp_path):
    folder = await exported(tmp_path)
    archive = tmp_path / "out" / "cavat-db.tar.gz"
    digest = backup.pack_archive(folder, archive)

    assert len(digest) == 64
    assert stat.S_IMODE(archive.stat().st_mode) == 0o600
    with tarfile.open(archive, "r:gz") as tar:
        assert tar.getnames() == ["manifest.json", "learning_sessions.jsonl", "users.jsonl"]
        assert {m.mode for m in tar.getmembers()} == {0o600}
    with pytest.raises(FileExistsError):
        backup.pack_archive(folder, archive)
