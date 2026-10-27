"""Deployment copies file payloads as well as Mongo documents; invalid transfers write nothing."""

import io
import stat
import tarfile

import pytest
from cavat import storage_transfer as transfer


def test_runtime_files_round_trip_but_trial_outputs_and_backups_stay_local(tmp_path):
    source = tmp_path / "source"
    for folder in ["documents", "voice", "rag", "backups", "figures-preview", "voice/hf"]:
        (source / folder).mkdir(parents=True)
        (source / folder / "file.bin").write_bytes(b"\x00\xff" * 30)
    archive, target = tmp_path / "files.tar.gz", tmp_path / "target"
    assert transfer.pack(source, archive) == 3
    assert stat.S_IMODE(archive.stat().st_mode) == 0o600
    assert transfer.restore(archive, target, dry_run=True) == 3
    assert not target.exists()
    assert transfer.restore(archive, target) == 3
    for folder in ["documents", "voice", "rag"]:
        assert (target / folder / "file.bin").read_bytes() == b"\x00\xff" * 30
    assert not (target / "backups").exists()
    assert not (target / "figures-preview").exists()
    assert not (target / "voice" / "hf").exists()
    with pytest.raises(transfer.StorageError, match="không trống"):
        transfer.restore(archive, target)
    with pytest.raises(FileExistsError):
        transfer.pack(source, archive)


@pytest.mark.parametrize(
    "name", ["../outside", "/documents/outside", "documents/../../outside", "unknown/file", "documents"]
)
def test_invalid_members_fail_before_even_a_valid_member_is_written(tmp_path, name):
    archive = tmp_path / "files.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for path in ["documents/valid", name]:
            info = tarfile.TarInfo(path)
            info.size = 1
            tar.addfile(info, io.BytesIO(b"x"))
    target = tmp_path / "target"
    with pytest.raises(transfer.StorageError):
        transfer.restore(archive, target)
    assert not target.exists()


def test_links_in_the_archive_or_source_are_refused(tmp_path):
    source = tmp_path / "source"
    (source / "documents").mkdir(parents=True)
    (source / "documents" / "link").symlink_to(tmp_path / "outside")
    with pytest.raises(transfer.StorageError, match="liên kết"):
        transfer.pack(source, tmp_path / "out.tar.gz")
    archive = tmp_path / "link.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        info = tarfile.TarInfo("documents/link")
        info.type, info.linkname = tarfile.SYMTYPE, "/etc/passwd"
        tar.addfile(info)
    with pytest.raises(transfer.StorageError):
        transfer.restore(archive, tmp_path / "target")


@pytest.mark.parametrize("names", [["documents/x", "documents/x"], ["documents/x", "documents/x/y"]])
def test_duplicate_or_conflicting_file_paths_are_rejected_before_writing(tmp_path, names):
    archive = tmp_path / "files.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for name in names:
            tar.addfile(tarfile.TarInfo(name), io.BytesIO(b""))
    with pytest.raises(transfer.StorageError):
        transfer.restore(archive, tmp_path / "target")
    assert not (tmp_path / "target").exists()
