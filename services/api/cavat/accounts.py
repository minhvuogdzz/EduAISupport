"""Create or update the three trial accounts (ACC-1): `make accounts`.

The owner trials the system with one student, one parent and one teacher. This command writes them to
the database of services/api/.env (cavat_dev) and links the parent to the student. It is the only way
accounts are created: never at startup, never by a test, never by a migration (CLAUDE.md rule 16).
Running it again updates the names and PINs of the same three accounts; their sessions stay theirs.

Names and PINs come from the environment (ACCOUNT_STUDENT_NAME, ACCOUNT_STUDENT_PIN, and the same with
PARENT and TEACHER), else they are asked for. Only the given name of the child is stored and ever sent to
an AI (rule 8). PINs are kept as scrypt hashes and are never printed.
"""

from __future__ import annotations

import asyncio
import getpass
import os
import sys

from cavat import db
from cavat.config import get_settings
from cavat.modules.identity.accounts import FIXED_LOGINS, PIN_MAX, PIN_MIN, hash_pin, valid_pin
from cavat.modules.identity.repository import User, UserRepository
from cavat.modules.session.service import DEMO_SCHOOL_ID

DEFAULT_NAMES = {"STUDENT": "Minh", "PARENT": "Phụ huynh của Minh", "TEACHER": "Giáo viên"}
LABEL = {"STUDENT": "học sinh", "PARENT": "phụ huynh", "TEACHER": "giáo viên"}


def _ask(kind: str) -> tuple[str, str]:
    name = (
        os.environ.get(f"ACCOUNT_{kind}_NAME")
        or input(f"Tên gọi của {LABEL[kind]} [{DEFAULT_NAMES[kind]}]: ").strip()
        or DEFAULT_NAMES[kind]
    )
    pin = os.environ.get(f"ACCOUNT_{kind}_PIN") or ""
    while not valid_pin(pin):
        pin = getpass.getpass(f"Mã PIN của {LABEL[kind]} ({PIN_MIN}-{PIN_MAX} chữ số): ").strip()
        if valid_pin(pin) and getpass.getpass("Nhập lại mã PIN: ").strip() != pin:
            print("Hai lần nhập không khớp.")
            pin = ""
    return name, pin


async def main() -> None:
    settings = get_settings()
    if settings.mongodb_uri is None:
        sys.exit("MONGODB_URI chưa có trong services/api/.env.")
    repo = UserRepository(db.get_db(settings), DEMO_SCHOOL_ID)
    student_name, student_pin = _ask("STUDENT")
    student = await repo.save(
        User(
            school_id=DEMO_SCHOOL_ID,
            kind="STUDENT",
            login_name=FIXED_LOGINS["STUDENT"],
            display_name=student_name.split()[-1],  # the given name only (rule 8)
            grade=5,
            pin_hash=hash_pin(student_pin),
        )
    )
    for kind in ("PARENT", "TEACHER"):
        name, pin = _ask(kind)
        await repo.save(
            User(
                school_id=DEMO_SCHOOL_ID,
                kind=kind,  # type: ignore[arg-type]
                login_name=FIXED_LOGINS[kind],  # type: ignore[index]
                display_name=name,
                pin_hash=hash_pin(pin),
                child_id=student.id if kind == "PARENT" else None,
            )
        )
    print(f"Database: {settings.mongodb_db}. Tài khoản (tên đăng nhập: tên gọi):")
    for kind, login in FIXED_LOGINS.items():
        user = await repo.get_by_login(login)
        print(f"  {LABEL[kind]:<10} {login}: {user.display_name if user else '?'}")
    await db.close_client()


if __name__ == "__main__":
    asyncio.run(main())
