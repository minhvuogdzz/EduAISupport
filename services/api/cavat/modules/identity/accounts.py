"""The three fixed accounts of the trial and their login (ACC-1).

The owner trials the system with exactly one student, one parent and one teacher, so that every session,
every score and every document belongs to a known person. They are created once with `make accounts`
(never at startup, never by a test) and log in with a PIN.

- PINs are stored as scrypt hashes (standard library, salt per account), never in clear.
- A login gives a token: the claims (user id, kind, display name, child) and an HMAC-SHA256 signature
  with ``AUTH_SECRET``. The server trusts only signed claims; the client never chooses who it is
  (CLAUDE.md rule 4).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import time
import unicodedata
from dataclasses import dataclass
from typing import Literal

Kind = Literal["STUDENT", "PARENT", "TEACHER"]

# The login names of the trial accounts. Display names and PINs come from the owner (`make accounts`).
STUDENT_LOGIN = "hocsinh"
PARENT_LOGIN = "phuhuynh"
TEACHER_LOGIN = "giaovien"
FIXED_LOGINS: dict[Kind, str] = {"STUDENT": STUDENT_LOGIN, "PARENT": PARENT_LOGIN, "TEACHER": TEACHER_LOGIN}

STUDENT_PREFIX = "hs-"  # login names of the students who signed up by name; the fixed logins never start so
NAME_MAX = 40  # characters of a typed name

TOKEN_TTL_S = 7 * 24 * 3600  # DI: a week, the trial runs on one family computer
PIN_MIN, PIN_MAX = 4, 8  # digits
MAX_FAILURES = 5  # wrong PINs in a row before a pause
LOCK_S = 300.0  # DI: five minutes

_SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}


def name_slug(name: str) -> str:
    """The key of a typed name: no accents, lower case, words joined by "-" ("Bảo An" -> "bao-an").

    The same child typing the name with other capitals, accents or spaces is the same student."""
    plain = unicodedata.normalize("NFD", name.replace("đ", "d").replace("Đ", "D"))
    plain = "".join(c for c in plain if unicodedata.category(c) != "Mn")
    return "-".join(re.findall(r"[a-z0-9]+", plain.lower()))


def clean_name(name: str) -> str | None:
    """The typed name with single spaces, or None when it is empty, too long or has no letter."""
    cleaned = " ".join(name.split())
    if not cleaned or len(cleaned) > NAME_MAX or not name_slug(cleaned):
        return None
    return cleaned


def valid_pin(pin: str) -> bool:
    return pin.isdigit() and PIN_MIN <= len(pin) <= PIN_MAX


def hash_pin(pin: str) -> str:
    if not valid_pin(pin):
        raise ValueError(f"a PIN is {PIN_MIN} to {PIN_MAX} digits")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(pin.encode(), salt=salt, **_SCRYPT)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_pin(pin: str, stored: str | None) -> bool:
    if not stored or not stored.startswith("scrypt$"):
        return False
    _, salt_hex, digest_hex = stored.split("$")
    digest = hashlib.scrypt(pin.encode(), salt=bytes.fromhex(salt_hex), **_SCRYPT)
    return hmac.compare_digest(digest.hex(), digest_hex)


@dataclass(frozen=True)
class Identity:
    """Who is calling, from a verified token."""

    user_id: str
    kind: Kind
    display_name: str
    child_id: str | None = None


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def issue_token(identity: Identity, secret: bytes, now: float | None = None) -> str:
    claims = {
        "sub": identity.user_id,
        "kind": identity.kind,
        "name": identity.display_name,
        "child": identity.child_id,
        "exp": int((now if now is not None else time.time()) + TOKEN_TTL_S),
    }
    body = _b64(json.dumps(claims, separators=(",", ":"), ensure_ascii=False).encode())
    signature = _b64(hmac.new(secret, body.encode(), hashlib.sha256).digest())
    return f"{body}.{signature}"


def read_token(token: str, secret: bytes, now: float | None = None) -> Identity | None:
    """The identity in a token signed with ``secret`` and not expired, else None."""
    try:
        body, signature = token.split(".")
        expected = _b64(hmac.new(secret, body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            return None
        claims = json.loads(_unb64(body))
    except (ValueError, json.JSONDecodeError):
        return None
    if claims.get("exp", 0) < (now if now is not None else time.time()):
        return None
    if claims.get("kind") not in FIXED_LOGINS:
        return None
    return Identity(claims["sub"], claims["kind"], claims.get("name", ""), claims.get("child"))


class LoginGuard:
    """Pause a login name after MAX_FAILURES wrong PINs in a row (in memory: one API process)."""

    def __init__(self) -> None:
        self._failures: dict[str, tuple[int, float]] = {}

    def locked_for(self, login: str, now: float | None = None) -> float:
        count, since = self._failures.get(login, (0, 0.0))
        left = since + LOCK_S - (now if now is not None else time.time())
        return left if count >= MAX_FAILURES and left > 0 else 0.0

    def failed(self, login: str, now: float | None = None) -> None:
        count, _ = self._failures.get(login, (0, 0.0))
        self._failures[login] = (count + 1, now if now is not None else time.time())

    def succeeded(self, login: str) -> None:
        self._failures.pop(login, None)
