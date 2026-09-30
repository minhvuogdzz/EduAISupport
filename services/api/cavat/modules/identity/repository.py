"""Identity module storage: user accounts (blueprint PART 28.3).

Only the name the child is called by (``display_name``) is stored here, which is also the only
name ever sent to AI (CLAUDE.md rule 8). Credentials and profiles come with the auth task.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from cavat.core.repository import (
    ASCENDING,
    AlreadyExists,
    IndexSpec,
    TenantDocument,
    TenantScopedRepository,
    utc_now,
)

UserKind = Literal["STUDENT", "TEACHER", "PARENT", "SCHOOL_ADMIN"]


class User(TenantDocument):
    kind: UserKind
    login_name: str = Field(min_length=1)
    display_name: str
    grade: int | None = None
    status: Literal["ACTIVE", "DISABLED"] = "ACTIVE"
    created_at: datetime = Field(default_factory=utc_now)


class UserRepository(TenantScopedRepository):
    collection_name = "users"
    indexes = (
        IndexSpec((("school_id", ASCENDING), ("login_name", ASCENDING)), "login_unique", unique=True),
        IndexSpec((("school_id", ASCENDING), ("kind", ASCENDING)), "kind"),
    )

    async def create(self, user: User) -> User:
        try:
            await self._insert(user.to_doc())
        except AlreadyExists as exc:
            raise AlreadyExists(f"login name already used: {user.login_name}") from exc
        return user

    async def get(self, user_id: str) -> User | None:
        doc = await self._find_one({"_id": user_id})
        return User.from_doc(doc) if doc else None

    async def get_by_login(self, login_name: str) -> User | None:
        doc = await self._find_one({"login_name": login_name})
        return User.from_doc(doc) if doc else None

    async def list_by_kind(self, kind: UserKind) -> list[User]:
        docs = await self._find({"kind": kind}, sort=[("login_name", ASCENDING)])
        return [User.from_doc(d) for d in docs]
