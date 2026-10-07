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
    pin_hash: str | None = None  # scrypt, never the PIN itself (ACC-1)
    child_id: str | None = None  # a parent's child (guardian link, ACC-1)


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

    async def save(self, user: User) -> User:
        """Create the account, or replace it when its login name exists (``make accounts`` is idempotent)."""
        existing = await self.get_by_login(user.login_name)
        if existing is None:
            return await self.create(user)
        updated = user.model_copy(update={"id": existing.id, "created_at": existing.created_at})
        doc = updated.to_doc()
        doc.pop("_id", None)
        doc.pop("school_id", None)
        await self._update_one({"_id": existing.id}, {"$set": doc})
        return updated

    async def list_by_kind(self, kind: UserKind) -> list[User]:
        docs = await self._find({"kind": kind}, sort=[("login_name", ASCENDING)])
        return [User.from_doc(d) for d in docs]
