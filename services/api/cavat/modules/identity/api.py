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
from cavat.modules.identity.accounts import (
    FIXED_LOGINS,
    Identity,
    LoginGuard,
    issue_token,
    read_token,
    valid_pin,
    verify_pin,
)
from cavat.modules.identity.repository import UserRepository

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


class LoginBody(BaseModel):
    login_name: str = Field(min_length=1, max_length=40)
    pin: str = Field(min_length=1, max_length=12)


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
            user = await repo.get_by_login(login)
            if user is not None and user.kind == kind and user.status == "ACTIVE":
                found.append({"kind": kind, "login_name": login, "display_name": user.display_name})
        return {"mode": "accounts", "accounts": found}

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

    @auth.get("/me", response_model=IdentityView)
    async def me(authorization: Annotated[str | None, Header()] = None):
        return _view(identity_from(authorization))

    return auth
