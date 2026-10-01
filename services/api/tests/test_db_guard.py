"""Offline tests for the Atlas safety guard (CLAUDE.md rules 12-14, 20).

Names of real (non-test) databases are built from parts below on purpose: the rules forbid test code
from hard-coding them, and these are only ever inputs that must be refused.
"""

from types import SimpleNamespace

import pytest
from cavat.core.db_guard import (
    UnsafeDatabaseError,
    assert_test_database,
    drop_test_database,
    is_test_database,
    new_test_database_name,
)

HEX12 = "0123456789ab"
REAL_DATABASES = [f"cavat_{env}" for env in ("dev", "prod")]


@pytest.mark.parametrize("name", ["cavat_test", f"cavat_test_{HEX12}", "cavat_test_ffffffffffff"])
def test_accepts_test_family(name):
    assert is_test_database(name)
    assert assert_test_database(name) == name


@pytest.mark.parametrize(
    "name",
    [
        *REAL_DATABASES,
        "",
        "admin",
        "local",
        "cavat",
        "cavat_",
        "cavat_test_",
        "cavat_testing",
        "xcavat_test",
        "cavat_test_xyz",
        f"cavat_test_{HEX12}0",  # 13 hex chars
        f"cavat_test_{HEX12[:-1]}",  # 11 hex chars
        f"cavat_test_{HEX12.upper()}",
        "cavat_test\n",
        f"cavat_test_{HEX12}\n",
        "cavat_test ",
        f"{REAL_DATABASES[0]}_cavat_test",
    ],
)
def test_rejects_everything_else(name):
    assert not is_test_database(name)
    with pytest.raises(UnsafeDatabaseError):
        assert_test_database(name)


def test_accepts_objects_with_a_name_attribute():
    assert assert_test_database(SimpleNamespace(name=f"cavat_test_{HEX12}")) == f"cavat_test_{HEX12}"


@pytest.mark.parametrize(
    "bad", [SimpleNamespace(), SimpleNamespace(name=None), SimpleNamespace(name=7), None, 7]
)
def test_rejects_objects_without_a_valid_name(bad):
    with pytest.raises(UnsafeDatabaseError):
        assert_test_database(bad)


def test_error_message_names_the_refused_database():
    with pytest.raises(UnsafeDatabaseError, match=REAL_DATABASES[0]):
        assert_test_database(REAL_DATABASES[0])


def test_generated_names_pass_the_guard_and_are_unique():
    names = {new_test_database_name() for _ in range(200)}
    assert len(names) == 200
    assert all(is_test_database(n) for n in names)


class _FakeClient:
    def __init__(self):
        self.dropped: list[str] = []

    async def drop_database(self, name):
        self.dropped.append(name)


async def test_drop_runs_for_a_test_database():
    client = _FakeClient()
    await drop_test_database(client, SimpleNamespace(name=f"cavat_test_{HEX12}"))
    assert client.dropped == [f"cavat_test_{HEX12}"]


@pytest.mark.parametrize("name", REAL_DATABASES + ["admin", ""])
async def test_drop_is_refused_before_touching_the_client(name):
    client = _FakeClient()
    with pytest.raises(UnsafeDatabaseError):
        await drop_test_database(client, name)
    assert client.dropped == []
