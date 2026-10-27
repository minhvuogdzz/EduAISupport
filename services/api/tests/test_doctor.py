"""REL-1: ``make doctor`` reads, reports, and is red when a trial would fail. Offline: fake probes and the
in-memory database; nothing here reaches Atlas, a model, a port or the disk of the trial."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from cavat import doctor, webbuild
from cavat.config import Settings
from cavat.core.memory_db import InMemoryDatabase
from cavat.doctor import Check, DatabaseFacts, Level, Probes

CHAINS = {
    "tutor_reasoning": ("qwen/qwen3.8-27b", "openai/gpt-oss-120b"),
    "intent_agent": ("openai/gpt-oss-120b", "qwen/qwen3.8-27b"),
}
FRESH = webbuild.BuildState(True, "bản dựng mới hơn mã nguồn", datetime(2026, 10, 26, 9, 0, tzinfo=UTC))
FACTS = DatabaseFacts(teachers=1, students=2, published=("math-g5-decimals", "math-g5-triangle"))


def settings(tmp_path, **env) -> Settings:
    base = {
        "mongodb_uri": "mongodb://never-used",
        "mongodb_db": "cavat_prod",
        "groq_api_key": "gsk_secret_value",
        "gemini_api_key": "gem_secret_value",
        "auth_secret": "a-long-random-signing-key",
        "auth_mode": "accounts",
        "tutor_renderer": "llm",
        "storage_dir": tmp_path / "storage",
        "web_dist": Path(webbuild.WEB) / "dist",
    }
    return Settings(_env_file=None, **{**base, **env})


async def good_database(_: Settings) -> DatabaseFacts:
    return FACTS


def probes(**fakes) -> Probes:
    base = dict(
        read_database=good_database,
        http_ok=lambda url: False,
        port_busy=lambda port: False,
        cavat_answers=lambda port: False,
        which=lambda tool: f"/usr/bin/{tool}",
        dir_size=lambda path: 10 * 1024**2,
        free_space=lambda path: 50 * doctor.GB,
        ping_model=lambda s, model: None,
        web_state=lambda: FRESH,
        voice_installed=lambda: True,
        chains=lambda s: CHAINS,
    )
    return Probes(**{**base, **fakes})


def by_name(checks: list[Check]) -> dict[str, Check]:
    return {c.name: c for c in checks}


async def run(tmp_path, *, port=18080, live=False, fakes=None, **env) -> dict[str, Check]:
    return by_name(
        await doctor.run_checks(settings(tmp_path, **env), probes(**(fakes or {})), port=port, live=live)
    )


async def test_a_ready_machine_has_no_red(tmp_path):
    checks = await run(tmp_path)
    assert not [c for c in checks.values() if c.level == Level.FAIL]
    assert checks["MongoDB"].level == Level.OK
    assert checks["Tên database"].level == Level.OK
    assert checks["Cổng"].detail == "18080 trống"


async def test_no_secret_is_ever_printed(tmp_path):
    checks = await doctor.run_checks(settings(tmp_path), probes(), port=18080)
    text = doctor.render(checks, color=False)
    for secret in ("gsk_secret_value", "gem_secret_value", "a-long-random-signing-key", "never-used"):
        assert secret not in text
    assert "MONGODB_URI, GROQ_API_KEY, AUTH_SECRET, GEMINI_API_KEY đã đặt" in text


async def test_missing_keys_are_red_and_named(tmp_path):
    checks = await run(tmp_path, groq_api_key=None, auth_secret=None, mongodb_uri=None)
    keys = checks["Khóa trong .env"]
    assert keys.level == Level.FAIL
    assert all(name in keys.detail for name in ("MONGODB_URI", "GROQ_API_KEY", "AUTH_SECRET"))
    assert checks["MongoDB"].level == Level.FAIL
    assert checks["Model của gia sư"].level == Level.FAIL


async def test_no_gemini_key_is_only_yellow(tmp_path):
    checks = await run(tmp_path, gemini_api_key=None)
    assert checks["Khóa trong .env"].level == Level.WARN
    assert "GEMINI_API_KEY" in checks["Khóa trong .env"].detail


async def test_a_short_signing_key_is_yellow(tmp_path):
    assert (await run(tmp_path, auth_secret="short"))["AUTH_SECRET"].level == Level.WARN


async def test_demo_login_is_red_because_the_address_is_public(tmp_path):
    checks = await run(tmp_path, auth_mode="demo")
    assert checks["Đăng nhập"].level == Level.FAIL


async def test_the_dev_database_is_yellow_the_test_database_red(tmp_path):
    dev = await run(tmp_path, mongodb_db="cavat_dev")
    assert dev["Tên database"].level == Level.WARN
    assert "make backup" in dev["Tên database"].detail
    assert dev["MongoDB"].level == Level.OK
    assert (await run(tmp_path, mongodb_db="cavat_test_0123456789ab"))["Tên database"].level == Level.FAIL
    assert (await run(tmp_path, mongodb_db="cavat_prod"))["Tên database"].level == Level.OK


async def test_an_unreachable_database_is_red_without_the_message(tmp_path):
    class ServerSelectionTimeoutError(Exception):
        pass

    async def down(_: Settings) -> DatabaseFacts:
        raise ServerSelectionTimeoutError("cluster0-shard-00-00.abc.mongodb.net:27017 secret-host")

    checks = await run(tmp_path, fakes={"read_database": down})
    assert checks["MongoDB"].level == Level.FAIL
    assert "ServerSelectionTimeoutError" in checks["MongoDB"].detail
    assert "secret-host" not in checks["MongoDB"].detail
    assert "Tài khoản giáo viên" not in checks


async def test_no_teacher_account_is_red_and_no_published_plan_yellow(tmp_path):
    async def bare(_: Settings) -> DatabaseFacts:
        return DatabaseFacts(teachers=0, students=0, published=())

    checks = await run(tmp_path, fakes={"read_database": bare})
    assert checks["Tài khoản giáo viên"].level == Level.FAIL
    assert "make accounts" in checks["Tài khoản giáo viên"].detail
    assert checks["Kế hoạch dạy"].level == Level.WARN
    assert (await run(tmp_path))["Kế hoạch dạy"].level == Level.OK


async def test_facts_are_read_from_the_database_with_reads_only():
    from cavat.modules.identity.repository import User, UserRepository
    from cavat.modules.session.service import DEMO_SCHOOL_ID

    database = InMemoryDatabase()
    users = UserRepository(database, DEMO_SCHOOL_ID)
    await users.create(
        User(school_id=DEMO_SCHOOL_ID, kind="TEACHER", login_name="giaovien", display_name="Cô")
    )
    await users.create(User(school_id=DEMO_SCHOOL_ID, kind="STUDENT", login_name="hs-an", display_name="An"))
    before = await database["users"].find({}).to_list()
    facts = await doctor.facts_from(database)
    assert (facts.teachers, facts.students, facts.published) == (1, 1, ())
    assert await database["users"].find({}).to_list() == before
    assert await database["teaching_plans"].find({}).to_list() == []  # looked at, nothing written


async def test_models_are_listed_but_not_called_unless_live(tmp_path):
    called = []
    fakes = {"ping_model": lambda s, model: called.append(model)}
    checks = await run(tmp_path, fakes=fakes)
    assert called == []
    assert "qwen/qwen3.8-27b → openai/gpt-oss-120b" in checks["Model tutor_reasoning"].detail
    live = await run(tmp_path, live=True, fakes=fakes)
    assert sorted(called) == ["openai/gpt-oss-120b", "qwen/qwen3.8-27b"]  # one call per model, not per kind
    assert live["Model tutor_reasoning"].level == Level.OK


async def test_live_one_model_down_is_yellow_all_down_is_red(tmp_path):
    def one_down(s, model):
        return "RateLimitError" if model.startswith("qwen") else None

    checks = await run(tmp_path, live=True, fakes={"ping_model": one_down})
    assert checks["Model tutor_reasoning"].level == Level.WARN
    assert "qwen/qwen3.8-27b ✘ RateLimitError" in checks["Model tutor_reasoning"].detail
    all_down = await run(tmp_path, live=True, fakes={"ping_model": lambda s, m: "RateLimitError"})
    assert all_down["Model intent_agent"].level == Level.FAIL


async def test_template_only_tutor_is_yellow(tmp_path):
    assert (await run(tmp_path, tutor_renderer="template"))["Lời gia sư"].level == Level.WARN


@pytest.mark.parametrize(
    ("fakes", "tts", "level", "word"),
    [
        ({"http_ok": lambda url: True}, "vieneu", Level.OK, "đang chạy"),
        ({}, "vieneu", Level.OK, "make run sẽ bật"),
        ({"voice_installed": lambda: False}, "vieneu", Level.WARN, "make voice-setup"),
        ({"voice_installed": lambda: False}, "off", Level.OK, "TTS=off"),
    ],
)
async def test_the_voice_server(tmp_path, fakes, tts, level, word):
    check = (await run(tmp_path, fakes=fakes, tts=tts))["Giọng gia sư"]
    assert check.level == level
    assert word in check.detail


async def test_the_port(tmp_path):
    busy = await run(tmp_path, fakes={"port_busy": lambda p: True})
    assert busy["Cổng"].level == Level.FAIL
    ours = await run(tmp_path, fakes={"port_busy": lambda p: True, "cavat_answers": lambda p: True})
    assert ours["Cổng"].level == Level.OK
    assert "CAVAT" in ours["Cổng"].detail


async def test_missing_tunnel_tools_are_yellow_not_red(tmp_path):
    checks = await run(tmp_path, fakes={"which": lambda tool: None})
    assert checks["cloudflared"].level == Level.WARN
    assert checks["caffeinate"].level == Level.WARN
    assert "brew install cloudflared" in checks["cloudflared"].detail


async def test_the_disk(tmp_path):
    low = await run(tmp_path, fakes={"free_space": lambda p: doctor.GB // 2})
    assert low["Đĩa"].level == Level.FAIL
    tight = await run(tmp_path, fakes={"free_space": lambda p: 3 * doctor.GB})
    assert tight["Đĩa"].level == Level.WARN
    ok = await run(tmp_path)
    assert ok["Đĩa"].level == Level.OK
    assert "50.0 GB trống; var/storage đang dùng 0 MB" in ok["Đĩa"].detail  # the folder is not there yet


async def test_a_stale_build_is_yellow_because_make_run_builds_it(tmp_path):
    stale = webbuild.BuildState(False, "mã web mới hơn bản dựng (src/App.tsx)")
    check = (await run(tmp_path, fakes={"web_state": lambda: stale}))["Giao diện web"]
    assert check.level == Level.WARN
    assert "make run tự dựng" in check.detail


async def test_a_web_dist_setting_that_points_nowhere_is_red(tmp_path):
    assert (await run(tmp_path, web_dist=tmp_path / "nowhere"))["Giao diện web"].level == Level.FAIL


async def test_api_docs_on_is_yellow(tmp_path):
    assert (await run(tmp_path, api_docs=True))["API_DOCS"].level == Level.WARN


def test_the_table_and_the_exit_code(tmp_path, monkeypatch, capsys):
    checks = [Check("A", Level.OK, "fine"), Check("Bb", Level.WARN, "mind"), Check("C", Level.FAIL, "broken")]
    plain = doctor.render(checks, color=False)
    assert " ✔ A   fine" in plain
    assert " ! Bb  mind" in plain
    assert " ✘ C   broken" in plain
    assert "1 xanh · 1 vàng · 1 đỏ: chưa sẵn sàng" in plain
    assert "\033[" in doctor.render(checks, color=True)

    async def fake_run(settings, probes=None, *, port, live):
        return checks

    monkeypatch.setattr(doctor, "run_checks", fake_run)
    monkeypatch.setattr(doctor, "get_settings", lambda: settings(tmp_path))
    assert doctor.main(["--port", "18080"]) == 1
    assert "cổng 18080" in capsys.readouterr().out

    async def all_good(settings, probes=None, *, port, live):
        return checks[:2]

    monkeypatch.setattr(doctor, "run_checks", all_good)
    assert doctor.main([]) == 0
