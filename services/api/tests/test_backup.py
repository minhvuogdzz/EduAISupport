"""REL-1: ``make backup`` writes every collection to JSONL and writes nothing to the database. Offline: the
in-memory database stands in for Atlas."""

import json
import stat
from datetime import UTC, datetime

import pytest
from bson import json_util
from cavat import backup, db
from cavat.config import Settings
from cavat.core.memory_db import InMemoryDatabase

WHEN = datetime(2026, 10, 26, 14, 30, 5, tzinfo=UTC)


async def filled() -> InMemoryDatabase:
    database = InMemoryDatabase(name="cavat_memory")
    await database["users"].insert_many(
        [
            {
                "_id": "u1",
                "school_id": "s",
                "login_name": "hs-an",
                "pin_hash": "scrypt$x",
                "created_at": WHEN,
            },
            {"_id": "u2", "school_id": "s", "login_name": "giaovien", "display_name": "Cô Hà — Toán 5"},
        ]
    )
    await database["learning_sessions"].insert_one(
        {
            "_id": "ls1",
            "school_id": "s",
            "student_id": "u1",
            "events": [{"type": "TUTOR_SAID", "text": "0,25 < 0,3"}],
        }
    )
    await database["empty"].insert_one({"_id": "e"})
    await database["empty"].delete_one({"_id": "e"})
    return database


AWARE = json_util.RELAXED_JSON_OPTIONS.with_options(tz_aware=True)  # as the app's client reads dates


def read(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json_util.loads(line, json_options=AWARE) for line in lines]


async def test_every_collection_goes_to_its_own_jsonl_with_the_count(tmp_path):
    database = await filled()
    counts = await backup.export_database(database, tmp_path / "b")
    assert counts == {"empty": 0, "learning_sessions": 1, "users": 2}
    assert sorted(p.name for p in (tmp_path / "b").iterdir()) == [
        "empty.jsonl",
        "learning_sessions.jsonl",
        "manifest.json",
        "users.jsonl",
    ]
    assert (tmp_path / "b" / "empty.jsonl").read_text() == ""
    manifest = json.loads((tmp_path / "b" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["documents"] == counts
    assert manifest["database"] == "cavat_memory"


async def test_what_is_written_reads_back_the_same_with_dates_and_vietnamese(tmp_path):
    database = await filled()
    await backup.export_database(database, tmp_path / "b")
    again = read(tmp_path / "b" / "users.jsonl")
    assert again == [
        await database["users"].find_one({"_id": "u1"}),
        await database["users"].find_one({"_id": "u2"}),
    ]
    assert again[0]["created_at"] == WHEN
    assert "Cô Hà — Toán 5" in (tmp_path / "b" / "users.jsonl").read_text(encoding="utf-8")  # not \u escapes


async def test_the_database_is_not_touched(tmp_path):
    database = await filled()
    before = {
        name: await database[name].find({}).to_list() for name in await database.list_collection_names()
    }
    await backup.export_database(database, tmp_path / "b")
    after = {name: await database[name].find({}).to_list() for name in await database.list_collection_names()}
    assert after == before


async def test_files_are_for_the_owner_only_and_a_backup_is_never_overwritten(tmp_path):
    database = await filled()
    await backup.export_database(database, tmp_path / "b")
    assert stat.S_IMODE((tmp_path / "b").stat().st_mode) == 0o700
    assert stat.S_IMODE((tmp_path / "b" / "users.jsonl").stat().st_mode) == 0o600
    with pytest.raises(FileExistsError):
        await backup.export_database(database, tmp_path / "b")


def test_the_folder_is_named_by_the_time_under_var_storage(tmp_path):
    settings = Settings(_env_file=None, storage_dir=tmp_path)
    assert backup.backup_dir(settings, WHEN) == tmp_path / "backups" / "20261026T143005Z"


async def test_the_command_backs_up_the_database_of_the_settings(tmp_path, monkeypatch, capsys):
    database = await filled()
    settings = Settings(
        _env_file=None, storage_dir=tmp_path, mongodb_uri="mongodb://never-used", mongodb_db="cavat_x"
    )
    monkeypatch.setattr(backup, "get_settings", lambda: settings)
    monkeypatch.setattr(db, "get_db", lambda s=None: database)
    monkeypatch.setattr("sys.argv", ["backup"])
    assert await backup.main() == 0
    out = capsys.readouterr().out
    assert "Database: cavat_x" in out
    assert "Đã sao lưu 3 bản ghi của 3 bộ sưu tập" in out
    [folder] = (tmp_path / "backups").iterdir()
    assert (folder / "users.jsonl").is_file()


async def test_the_command_says_so_without_a_database(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        backup, "get_settings", lambda: Settings(_env_file=None, storage_dir=tmp_path, mongodb_uri=None)
    )
    assert await backup.main() == 1
    assert "MONGODB_URI" in capsys.readouterr().out
    assert not (tmp_path / "backups").exists()
