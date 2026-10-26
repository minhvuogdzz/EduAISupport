"""REL-1: when does ``make run`` build the web app again? (cavat.webbuild)"""

import os

import pytest
from cavat import webbuild


@pytest.fixture
def web(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "App.tsx").write_text("export {}", encoding="utf-8")
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    return tmp_path


def build(web, *, mark=True):
    (web / "dist").mkdir(exist_ok=True)
    (web / "dist" / "index.html").write_text("<html></html>", encoding="utf-8")
    if mark:
        webbuild.mark(web)


def touch(path, seconds):
    stat = path.stat()
    os.utime(path, (stat.st_atime, stat.st_mtime + seconds))


def test_no_dist_means_build(web):
    state = webbuild.check(web)
    assert not state.fresh
    assert "chưa dựng" in state.reason


def test_a_dist_the_build_did_not_mark_is_not_served(web):
    """`make web-check` builds for the mock API: that dist must not pass for the real one."""
    build(web, mark=False)
    state = webbuild.check(web)
    assert not state.fresh
    assert "mock" in state.reason


def test_a_marked_build_newer_than_the_sources_is_fresh(web):
    for source in (web / "src" / "App.tsx", web / "package.json"):
        touch(source, -10)
    build(web)
    state = webbuild.check(web)
    assert state.fresh
    assert state.built_at is not None


@pytest.mark.parametrize("changed", ["src/App.tsx", "package.json"])
def test_a_newer_source_means_build(web, changed):
    build(web)
    touch(web / changed, +10)
    state = webbuild.check(web)
    assert not state.fresh
    assert changed in state.reason


def test_a_new_file_in_src_means_build(web):
    build(web)
    new = web / "src" / "pages" / "New.tsx"
    new.parent.mkdir()
    new.write_text("export {}", encoding="utf-8")
    touch(new, +10)
    assert not webbuild.check(web).fresh


def test_the_command_exits_0_only_when_fresh(web, capsys):
    assert webbuild.main([], web) == 1
    (web / "dist").mkdir()
    (web / "dist" / "index.html").write_text("<html></html>", encoding="utf-8")
    assert webbuild.main(["--mark"], web) == 0  # `make web-build` after pnpm build
    for source in (web / "src" / "App.tsx", web / "package.json"):
        touch(source, -10)
    assert webbuild.main([], web) == 0
    assert "Web đã dựng" in capsys.readouterr().out
