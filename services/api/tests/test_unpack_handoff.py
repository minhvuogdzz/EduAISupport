"""Private handoffs must not overwrite credentials or escape their destination."""

import io
import subprocess
import sys
import tarfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / "deploy" / "unpack_handoff.py"
FILES = {
    ".env": b"MONGO_PASSWORD=original\n",
    "db-dump/cavat-db.tar.gz": b"database",
    "db-dump/cavat-storage.tar.gz": b"storage",
    "db-dump/SHA256SUMS": b"checksums",
}


def bundle(path, files):
    with tarfile.open(path, "w:gz") as tar:
        for name, data in files.items():
            member = tarfile.TarInfo(name)
            member.size = len(data)
            tar.addfile(member, io.BytesIO(data))


def run(source, destination):
    return subprocess.run([sys.executable, str(SCRIPT), str(source)], cwd=destination, capture_output=True)


def test_unpack_is_idempotent_but_refuses_changed_credentials(tmp_path):
    source = tmp_path / "bundle.tar.gz"
    dest = tmp_path / "dest"
    dest.mkdir()
    bundle(source, FILES)
    assert run(source, dest).returncode == 0
    assert run(source, dest).returncode == 0
    (dest / ".env").write_text("existing server password")
    assert run(source, dest).returncode != 0
    assert (dest / ".env").read_text() == "existing server password"


def test_unpack_rejects_unexpected_archive_paths_before_writing(tmp_path):
    source = tmp_path / "bundle.tar.gz"
    dest = tmp_path / "dest"
    dest.mkdir()
    bundle(source, {**FILES, "../escape": b"bad"})
    assert run(source, dest).returncode != 0
    assert not (dest / ".env").exists()
