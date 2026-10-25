"""Login for the three fixed accounts (ACC-1) and the identity every other endpoint reads.

``AUTH_MODE=accounts`` (default): a request carries ``Authorization: Bearer <token>`` from
``POST /v1/auth/login``; the identity comes from the signed token only. ``AUTH_MODE=demo`` keeps the old
``X-Demo-*`` headers for the offline tests and the in-memory demo, where no account exists.
"""

from __future__ import annotations

import secrets
from functools import lru_cache
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from cavat.config import get_settings
from cavat.core.repository import AlreadyExists
from cavat.modules.identity.accounts import (
    FIXED_LOGINS,
    STUDENT_PREFIX,
    Identity,
    LoginGuard,
    clean_name,
    issue_token,
    name_slug,
    read_token,
    valid_pin,
    verify_pin,
)
from cavat.modules.identity.repository import User, UserRepository

auth = APIRouter(prefix="/v1/auth", tags=["auth"])
_guard = LoginGuard()


class AuthError(Exception):
    """Mapped to the API error body by the session API's handler (same ``{"error": ...}`` shape)."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


@lru_cache
def _process_secret() -> bytes:
    return secrets.token_bytes(32)


def signing_secret() -> bytes:
    configured = get_settings().auth_secret
    if configured is not None and configured.get_secret_value():
        return configured.get_secret_value().encode()
    return _process_secret()


def demo_mode() -> bool:
    return get_settings().auth_mode == "demo"


def identity_from(authorization: str | None) -> Identity:
    """The caller of an accounts-mode request; 401 without a valid, unexpired token."""
    scheme, _, token = (authorization or "").partition(" ")
    identity = read_token(token, signing_secret()) if scheme.lower() == "bearer" and token else None
    if identity is None:
        raise AuthError(401, "NOT_SESSION_OWNER", "please log in")
    return identity


def require(identity: Identity, kind: Literal["STUDENT", "PARENT", "TEACHER"]) -> Identity:
    if identity.kind != kind:
        raise AuthError(403, "NOT_SESSION_OWNER", f"this page is for the {kind.lower()} account")
    return identity


class AccountView(BaseModel):
    kind: Literal["STUDENT", "PARENT", "TEACHER"]
    login_name: str
    display_name: str


class AuthConfig(BaseModel):
    mode: Literal["accounts", "demo"]
    accounts: list[AccountView]
    student_signup: bool = False  # students come in by typing their name: no fixed student card


class LoginBody(BaseModel):
    login_name: str = Field(min_length=1, max_length=40)
    pin: str = Field(min_length=1, max_length=12)


class StudentBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class IdentityView(BaseModel):
    user_id: str
    kind: Literal["STUDENT", "PARENT", "TEACHER"]
    display_name: str
    child_id: str | None = None


class LoginResult(BaseModel):
    token: str
    user: IdentityView


def _view(identity: Identity) -> dict[str, Any]:
    return {
        "user_id": identity.user_id,
        "kind": identity.kind,
        "display_name": identity.display_name,
        "child_id": identity.child_id,
    }


async def _create_student(repo: UserRepository, name: str) -> User:
    """A new student account. The full typed name only forms the login key; the display name, the only one
    ever sent to an AI (CLAUDE.md rule 8), is the given name (the last word, as `make accounts` does)."""
    user = User(
        school_id=repo.school_id,
        kind="STUDENT",
        login_name=STUDENT_PREFIX + name_slug(name),
        display_name=name.split()[-1],
        grade=5,
    )
    try:
        return await repo.create(user)
    except AlreadyExists:  # two first visits at once: the other one won
        found = await repo.get_by_login(user.login_name)
        if found is None:
            raise
        return found


def register_auth(router_database_dependency: Any, school_id: str) -> APIRouter:
    """The auth routes, on the same database dependency and school as the session API."""
    database_dependency = Depends(router_database_dependency)

    @auth.get("/config", response_model=AuthConfig)
    async def config(database: Any = database_dependency):
        """Which login the web shows: the three accounts, or none in the demo mode."""
        if demo_mode():
            return {"mode": "demo", "accounts": []}
        repo = UserRepository(database, school_id)
        found = []
        for kind, login in FIXED_LOGINS.items():
            if kind == "STUDENT":  # students sign in by name below
                continue
            user = await repo.get_by_login(login)
            if user is not None and user.kind == kind and user.status == "ACTIVE":
                found.append({"kind": kind, "login_name": login, "display_name": user.display_name})
        return {"mode": "accounts", "accounts": found, "student_signup": True}

    @auth.post("/login", response_model=LoginResult)
    async def login(body: LoginBody, database: Any = database_dependency):
        if demo_mode():
            raise AuthError(409, "INVALID_STATE", "the demo mode has no accounts")
        login_name = body.login_name.strip().lower()
        if _guard.locked_for(login_name) > 0:
            raise AuthError(429, "INVALID_STATE", "too many wrong PINs: wait five minutes")
        user = await UserRepository(database, school_id).get_by_login(login_name)
        ok = (
            user is not None
            and user.status == "ACTIVE"
            and user.kind in FIXED_LOGINS
            and valid_pin(body.pin)
            and verify_pin(body.pin, user.pin_hash)
        )
        if not ok or user is None:
            _guard.failed(login_name)
            raise AuthError(401, "NOT_SESSION_OWNER", "wrong account or PIN")
        _guard.succeeded(login_name)
        identity = Identity(user.id, user.kind, user.display_name, user.child_id)  # type: ignore[arg-type]
        return {"token": issue_token(identity, signing_secret()), "user": _view(identity)}

    @auth.post("/student", response_model=LoginResult)
    async def student(body: StudentBody, database: Any = database_dependency):
        """A student comes in by name: the first time the name makes the account, later it finds it again.

        There is no PIN (the trial's children are given a link, not a secret): the same name on any
        device is the same student and the same history. Only the STUDENT kind can be made or found here,
        so a name can never open the parent or the teacher."""
        if demo_mode():
            raise AuthError(409, "INVALID_STATE", "the demo mode has no accounts")
        name = clean_name(body.name)
        if name is None:
            raise AuthError(422, "VALIDATION_ERROR", "please type the name of the student")
        repo = UserRepository(database, school_id)
        user = await repo.get_by_login(STUDENT_PREFIX + name_slug(name))
        if user is None:  # the fixed trial student (`make accounts`) keeps its history under its name
            fixed = await repo.get_by_login(FIXED_LOGINS["STUDENT"])
            if (
                fixed is not None
                and fixed.kind == "STUDENT"
                and name_slug(fixed.display_name) == name_slug(name)
            ):
                user = fixed
        if user is None:
            user = await _create_student(repo, name)
        if user.kind != "STUDENT" or user.status != "ACTIVE":
            raise AuthError(403, "NOT_SESSION_OWNER", "this student cannot come in")
        identity = Identity(user.id, "STUDENT", user.display_name, None)
        return {"token": issue_token(identity, signing_secret()), "user": _view(identity)}

    @auth.get("/me", response_model=IdentityView)
    async def me(authorization: Annotated[str | None, Header()] = None):
        return _view(identity_from(authorization))

    return auth
