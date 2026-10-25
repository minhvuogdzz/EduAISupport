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
    PIN_MAX,
    PIN_MIN,
    STUDENT_PREFIX,
    Identity,
    LoginGuard,
    clean_name,
    hash_pin,
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
    login_name: str = Field(min_length=1, max_length=120)
    pin: str = Field(min_length=1, max_length=12)
    # A child's account also opens the parent's view of that child (one account for both). None: the
    # account's own kind.
    role: Literal["STUDENT", "PARENT"] | None = None


class RegisterBody(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    passcode: str = Field(min_length=1, max_length=12)


class IdentityView(BaseModel):
    user_id: str
    kind: Literal["STUDENT", "PARENT", "TEACHER"]
    display_name: str
    child_id: str | None = None


class LoginResult(BaseModel):
    token: str
    user: IdentityView
    # A student's login also gives the parent's token for the same child: switching role asks nothing.
    parent_token: str | None = None


def _view(identity: Identity) -> dict[str, Any]:
    return {
        "user_id": identity.user_id,
        "kind": identity.kind,
        "display_name": identity.display_name,
        "child_id": identity.child_id,
    }


def _given_name(typed: str) -> str:
    """The name shown and sent to an AI (CLAUDE.md rule 8): the last word of the username, capitalised."""
    word = typed.split()[-1]
    return word[:1].upper() + word[1:] if word.islower() else word


async def _find_user(repo: UserRepository, typed: str) -> User | None:
    """The account a typed username means: its own login name (``giaovien``, ``hocsinh``), the key made from
    the typed name, or the fixed student of `make accounts` by its name ("Vuong" finds its old history)."""
    literal = typed.strip().lower()
    user = await repo.get_by_login(literal) or await repo.get_by_login(STUDENT_PREFIX + name_slug(typed))
    if user is None:
        fixed = await repo.get_by_login(FIXED_LOGINS["STUDENT"])
        if fixed is not None and name_slug(fixed.display_name) == name_slug(typed):
            user = fixed
    return user


def _result(user: User, role: str | None) -> dict[str, Any]:
    """The token of the requested role; a child's login adds the parent's token for the same child."""
    secret = signing_secret()
    if user.kind == "STUDENT":
        student = Identity(user.id, "STUDENT", user.display_name, None)
        parent = Identity(user.id, "PARENT", f"Phụ huynh của {user.display_name}", user.id)
        shown = parent if role == "PARENT" else student
        return {
            "token": issue_token(shown, secret),
            "user": _view(shown),
            "parent_token": issue_token(parent, secret),
        }
    identity = Identity(user.id, user.kind, user.display_name, user.child_id)  # type: ignore[arg-type]
    return {"token": issue_token(identity, secret), "user": _view(identity)}


def register_auth(router_database_dependency: Any, school_id: str) -> APIRouter:
    """The auth routes, on the same database dependency and school as the session API."""
    database_dependency = Depends(router_database_dependency)

    @auth.get("/config", response_model=AuthConfig)
    async def config(database: Any = database_dependency):
        """Which login the web shows: the fixed parent and teacher, and that children make their own."""
        if demo_mode():
            return {"mode": "demo", "accounts": []}
        repo = UserRepository(database, school_id)
        found = []
        for kind, login in FIXED_LOGINS.items():
            user = await repo.get_by_login(login)
            if user is not None and user.kind == kind and user.status == "ACTIVE":
                found.append({"kind": kind, "login_name": login, "display_name": user.display_name})
        return {"mode": "accounts", "accounts": found, "student_signup": True}

    @auth.post("/login", response_model=LoginResult)
    async def login(body: LoginBody, database: Any = database_dependency):
        if demo_mode():
            raise AuthError(409, "INVALID_STATE", "the demo mode has no accounts")
        typed = body.login_name.strip().lower()
        if _guard.locked_for(typed) > 0:
            raise AuthError(429, "INVALID_STATE", "too many wrong passcodes: wait five minutes")
        user = await _find_user(UserRepository(database, school_id), body.login_name)
        ok = (
            user is not None
            and user.status == "ACTIVE"
            and user.kind in FIXED_LOGINS
            and valid_pin(body.pin)
            and verify_pin(body.pin, user.pin_hash)
        )
        if not ok or user is None:
            _guard.failed(typed)
            raise AuthError(401, "NOT_SESSION_OWNER", "wrong username or passcode")
        # Only a child's account has two roles; the parent and the teacher open their own kind.
        if body.role is not None and user.kind != "STUDENT" and body.role != user.kind:
            raise AuthError(403, "NOT_SESSION_OWNER", "this account is not a child's")
        _guard.succeeded(typed)
        return _result(user, body.role)

    @auth.post("/student/register", response_model=LoginResult)
    async def register(body: RegisterBody, database: Any = database_dependency):
        """A child makes an account: a username and a passcode. The same pair then opens the lessons and the
        parent's view of the child, on any device, with the history kept in the database. The trial's fixed
        logins and the old student's name are taken, a name already used asks for another."""
        if demo_mode():
            raise AuthError(409, "INVALID_STATE", "the demo mode has no accounts")
        username = clean_name(body.username)
        if username is None:
            raise AuthError(422, "VALIDATION_ERROR", "please type a username")
        if not valid_pin(body.passcode):
            raise AuthError(422, "VALIDATION_ERROR", f"the passcode is {PIN_MIN} to {PIN_MAX} digits")
        repo = UserRepository(database, school_id)
        slug = name_slug(username)
        if slug in FIXED_LOGINS.values() or await _find_user(repo, username) is not None:
            raise AuthError(409, "INVALID_STATE", "this username is taken")
        user = User(
            school_id=school_id,
            kind="STUDENT",
            login_name=STUDENT_PREFIX + slug,
            display_name=_given_name(username),
            grade=5,
            pin_hash=hash_pin(body.passcode),
        )
        try:
            await repo.create(user)
        except AlreadyExists:  # two children making the same name at once: the other one won
            raise AuthError(409, "INVALID_STATE", "this username is taken") from None
        return _result(user, None)

    @auth.get("/me", response_model=IdentityView)
    async def me(authorization: Annotated[str | None, Header()] = None):
        return _view(identity_from(authorization))

    return auth
