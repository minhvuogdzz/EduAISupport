"""A source handoff contains committed code and excludes local secrets/runtime files."""

import importlib.util
import subprocess
from pathlib import Path

import pytest
from dotenv import dotenv_values

SCRIPT = Path(__file__).resolve().parents[3] / "deploy" / "prepare_handoff.py"
spec = importlib.util.spec_from_file_location("prepare_handoff", SCRIPT)
handoff = importlib.util.module_from_spec(spec)
spec.loader.exec_module(handoff)


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def test_release_source_is_exact_commit_without_ignored_secrets(tmp_path):
    repo, target = tmp_path / "repo", tmp_path / "release"
    repo.mkdir()
    target.mkdir()
    git(repo, "init", "-q")
    (repo / ".gitignore").write_text(".env\nvar/\n")
    (repo / "Dockerfile").write_text("FROM python:3.11\n")
    git(repo, "add", ".")
    git(repo, "-c", "user.name=CI", "-c", "user.email=ci@example.test", "commit", "-qm", "source")
    (repo / ".env").write_text("PRIVATE_KEY=never-export-working-tree")
    (repo / "var").mkdir()
    (repo / "var" / "private").write_text("learner data")
    revision = handoff.copy_release_source(repo, target)
    assert revision == git(repo, "rev-parse", "HEAD")
    assert (target / "Dockerfile").read_text() == (repo / "Dockerfile").read_text()
    assert not any((target / name).exists() for name in (".env", ".git", "var"))
    (repo / "Dockerfile").write_text("uncommitted version")
    with pytest.raises(ValueError, match="Commit/merge"):
        handoff.copy_release_source(repo, target)


def test_env_quote_preserves_json_and_special_characters(tmp_path):
    values = {"KEY": "fake key$with#quotes'and\\slashes", "MODELS": '["one","two"]'}
    file = tmp_path / ".env"
    file.write_text("".join(f"{key}={handoff.quote(value)}\n" for key, value in values.items()))
    assert dotenv_values(file, interpolate=False) == values
    with pytest.raises(ValueError):
        handoff.quote("bad\nINJECT=value")
