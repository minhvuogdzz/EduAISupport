"""Admin-only model usage, configured chains and source traces. No learner or policy mutations."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import time
from collections import Counter
from dataclasses import replace
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated, Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, FastAPI, Header, Query, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from cavat.config import get_settings
from cavat.modules.ai_gateway.base import CHAT_MODEL_CLASSES
from cavat.modules.identity.accounts import LoginGuard
from cavat.modules.identity.api import AuthError, signing_secret

from .store import OperationalLog, TraceContext, context, new_row

TTL_SECONDS = 8 * 3600
_guard = LoginGuard()


@lru_cache
def journal() -> OperationalLog:
    return OperationalLog(get_settings().storage_dir / "observability" / "operations.jsonl")


def _signature(body: str) -> str:
    return hmac.new(signing_secret(), ("admin-observability:" + body).encode(), hashlib.sha256).hexdigest()


def issue_admin_token(school_id: str) -> str:
    password = get_settings().admin_password.get_secret_value()
    payload = {
        "scope": "observability",
        "school_id": school_id,
        "exp": time.time() + TTL_SECONDS,
        "credential": hmac.new(signing_secret(), password.encode(), hashlib.sha256).hexdigest(),
    }
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    return body + "." + _signature(body)


def check_admin(authorization: str | None, school_id: str) -> None:
    try:
        scheme, raw = (authorization or "").split(" ", 1)
        body, signature = raw.split(".")
        if scheme.lower() != "bearer" or not hmac.compare_digest(signature, _signature(body)):
            raise ValueError
        data = json.loads(base64.urlsafe_b64decode(body))
        expected = hmac.new(
            signing_secret(), get_settings().admin_password.get_secret_value().encode(), hashlib.sha256
        ).hexdigest()
        if (
            data.get("scope") != "observability"
            or data.get("school_id") != school_id
            or data.get("exp", 0) <= time.time()
            or data.get("credential") != expected
        ):
            raise ValueError
    except (ValueError, TypeError, KeyError, AttributeError):
        raise AuthError(401, "NOT_SESSION_OWNER", "Vui lòng đăng nhập Admin.") from None


class LoginBody(BaseModel):
    password: str = Field(min_length=1, max_length=128)


def totals(rows: list[dict]) -> dict:
    models = [r for r in rows if r["kind"] == "model"]
    usage_by_model: dict[str, dict] = {}
    for row in models:
        # Count provider attempts, including errors, separately from answered token usage.
        attempts = row.get("details", {}).get("attempts", [])
        for attempt in attempts:
            if attempt.get("sent"):
                model = attempt["model"]
                usage_by_model.setdefault(
                    model, {"sent": 0, "answered": 0, "prompt_tokens": 0, "completion_tokens": 0}
                )["sent"] += 1
        if row.get("model"):
            entry = usage_by_model.setdefault(
                row["model"], {"sent": 0, "answered": 0, "prompt_tokens": 0, "completion_tokens": 0}
            )
            if not attempts:
                entry["sent"] += row.get("calls_sent", 0)
            entry["answered"] += 1
            entry["prompt_tokens"] += row.get("prompt_tokens") or 0
            entry["completion_tokens"] += row.get("completion_tokens") or 0
    return {
        "usage_by_model": usage_by_model,
        "operations": len(rows),
        "model_operations": len(models),
        "calls_sent": sum(r.get("calls_sent", 0) for r in models),
        "prompt_tokens": sum(r.get("prompt_tokens") or 0 for r in models),
        "completion_tokens": sum(r.get("completion_tokens") or 0 for r in models),
        "unknown_usage": sum(r.get("prompt_tokens") is None for r in models),
        "rag": sum(r["kind"] == "rag" for r in rows),
        "web": sum(r["kind"] == "web" for r in rows),
        "network": sum(r["kind"] == "network" for r in rows),
        "network_errors": sum(r["kind"] == "network" and r["status"] == "error" for r in rows),
        "cache": sum(r["kind"] == "cache" for r in rows),
        "rag_hits": sum(r["kind"] == "rag" and r["status"] == "success" for r in rows),
        "web_hits": sum(r["kind"] == "web" and r["status"] == "success" for r in rows),
        "decisions": dict(Counter(r["purpose"] for r in rows if r["kind"] == "decision")),
        "commands": sum(r["kind"] == "command" for r in rows),
        "errors": sum(r["status"] in ("error", "fallback", "interrupted") for r in rows),
        "by_model": dict(Counter(r["model"] for r in models if r.get("model"))),
    }


def historical_rows(doc: dict) -> list[dict]:
    out = []
    for event in doc.get("events", []):
        event_type, payload = event.get("event_type"), event.get("payload", {})
        kind = {"MODEL_CALLED": "model", "RAG_RETRIEVED": "rag", "WEB_LOOKED": "web"}.get(event_type)
        if not kind:
            continue
        status = "success"
        details = {}
        if kind == "model":
            status = "success" if payload.get("model") else "fallback"
            details = {
                "attempts": [
                    {k: a.get(k) for k in ("model", "sent", "error", "limit", "retry_after_s")}
                    for a in payload.get("attempts", [])
                ],
                "fallback_reason": payload.get("fallback_reason"),
            }
        elif kind == "rag":
            status = "success" if payload.get("grounded") else "miss"
            details = {k: payload.get(k) for k in ("node_id", "grounded", "grounding", "semantic")}
            details["chunks"] = [
                {"id": c.get("chunk_id"), "title": c.get("title")} for c in payload.get("chunks", [])
            ]
        else:
            status = "success" if payload.get("answered") else "miss"
            details = {k: payload.get(k) for k in ("title", "url", "retrieval", "search_engine", "answered")}
        known = bool(payload.get("prompt_tokens") or payload.get("completion_tokens"))
        out.append(
            {
                "id": event.get("event_id") or f"{doc['_id']}:{event.get('sequence_no')}",
                "kind": kind,
                "operation": event_type,
                "status": status,
                "started_at": event.get("occurred_at"),
                "session_id": str(doc["_id"]),
                "request_id": None,
                "parent_id": None,
                "path": None,
                "duration_ms": None,
                "model": payload.get("model"),
                "model_class": payload.get("model_class"),
                "purpose": payload.get("purpose") or payload.get("source") or event_type,
                "prompt_tokens": payload.get("prompt_tokens", 0) if known else None,
                "completion_tokens": payload.get("completion_tokens", 0) if known else None,
                "calls_sent": max(
                    sum(bool(a.get("sent")) for a in payload.get("attempts", [])),
                    int(bool(payload.get("model"))),
                ),
                "details": details,
            }
        )
    return out


def model_status(router) -> list[dict]:
    if router is None:
        return []
    now = datetime.now(UTC)
    rows = []
    for model_class in sorted(CHAT_MODEL_CLASSES):
        for priority, model in enumerate(router.chain(model_class), 1):
            reset = router.quota.reset_at(model)
            rows.append(
                {
                    "model_class": model_class.value,
                    "model": model,
                    "priority": priority,
                    "quota_exhausted": router.quota.is_exhausted(model, now),
                    "reset_at": reset,
                    "provider_configured": router._chat is not None,
                }
            )
    return rows


def register(app: FastAPI, database_dependency, router_factory, school_id: str) -> None:
    root = APIRouter(prefix="/v1/admin", tags=["admin"])
    database_dep = Depends(database_dependency)

    def authorized(authorization: Annotated[str | None, Header()] = None):
        check_admin(authorization, school_id)

    @app.middleware("http")
    async def observe(request: Request, call_next):
        # Polls and credentials are not telemetry. Commands carry no request body into the log.
        if request.url.path.startswith("/v1/admin"):
            response = await call_next(request)
            response.headers["Cache-Control"] = "no-store"
            return response
        if (
            not get_settings().observability_enabled
            or not request.url.path.startswith("/v1/")
            or request.url.path.startswith("/v1/admin")
        ):
            return await call_next(request)
        match = re.search(r"/sessions/([^/]+)", request.url.path)
        log = journal()
        ctx = TraceContext(log, school_id, uuid4().hex, match.group(1) if match else None, request.url.path)
        command = (
            new_row(ctx, "command", f"{request.method} {request.url.path}")
            if (request.method == "POST" and request.url.path.startswith("/v1/sessions"))
            else None
        )
        if command is not None:
            log.write(command)
            ctx = replace(ctx, parent_id=command["id"])
        token = context.set(ctx)
        start = time.perf_counter()
        try:
            response = await call_next(request)
            if command is not None:
                command["status"] = "success" if response.status_code < 400 else "error"
                command["details"]["http_status"] = response.status_code
            return response
        except Exception:
            if command is not None:
                command["status"] = "error"
            raise
        finally:
            if command is not None:
                rows = [r for r in log.snapshot(school_id) if r["request_id"] == ctx.request_id]
                command["details"].update(
                    model_calls=sum(r.get("calls_sent", 0) for r in rows if r["kind"] == "model"),
                    rag_calls=sum(r["kind"] == "rag" for r in rows),
                    web_calls=sum(r["kind"] == "web" for r in rows),
                    network_calls=sum(r["kind"] == "network" for r in rows),
                    cache_calls=sum(r["kind"] == "cache" for r in rows),
                )
                command["duration_ms"] = round((time.perf_counter() - start) * 1000, 1)
                log.write(command)
            context.reset(token)

    @root.post("/login")
    async def login(body: LoginBody, request: Request):
        key = "admin:" + (request.client.host if request.client else "local")
        if _guard.locked_for(key) > 0:
            raise AuthError(429, "INVALID_STATE", "Sai mật khẩu nhiều lần. Thử lại sau 5 phút.")
        if not hmac.compare_digest(
            body.password.encode(), get_settings().admin_password.get_secret_value().encode()
        ):
            _guard.failed(key)
            raise AuthError(401, "NOT_SESSION_OWNER", "Mật khẩu Admin chưa đúng.")
        _guard.succeeded(key)
        return {"token": issue_admin_token(school_id), "expires_in": TTL_SECONDS}

    @root.get("/overview", dependencies=[Depends(authorized)])
    async def overview(
        limit: Annotated[int, Query(ge=1, le=1000)] = 25,
        offset: Annotated[int, Query(ge=0, le=1000000)] = 0,
        session_id: Annotated[str | None, Query(max_length=120)] = None,
        kind: Literal["model", "rag", "web", "command", "network", "cache", "decision"] | None = None,
        search: Annotated[str, Query(max_length=200)] = "",
        database: Any = database_dep,
    ):
        log = journal()
        runtime = await run_in_threadpool(log.snapshot, school_id)
        flt = {"school_id": school_id}
        if session_id:
            flt["_id"] = session_id
            runtime = [row for row in runtime if row.get("session_id") == session_id]
        docs = (
            await database["learning_sessions"]
            .find(
                flt,
                {"events": 1, "lesson_id": 1, "created_at": 1, "updated_at": 1},
                sort=[("updated_at", -1)],
                limit=50,
            )
            .to_list(50)
        )
        history = [row for doc in docs for row in historical_rows(doc)]
        history.sort(key=lambda row: str(row["started_at"]), reverse=True)

        def matching(rows):
            term = search.casefold()
            return [
                row
                for row in rows
                if (kind is None or row["kind"] == kind)
                and (
                    not term
                    or term
                    in " ".join(
                        str(row.get(key) or "")
                        for key in ("model", "purpose", "session_id", "request_id", "status", "operation")
                    ).casefold()
                )
            ]

        runtime_matches, history_matches = matching(runtime), matching(history)
        return {
            "generated_at": datetime.now(UTC),
            "runtime": {
                "totals": totals(runtime),
                "logs": runtime_matches[offset : offset + limit],
                "coverage": {"network_tracked": True, "from": runtime[-1]["started_at"] if runtime else None},
                "filtered_total": len(runtime_matches),
                "retained": len(runtime),
                "capacity": log.capacity,
                "persistence_error": log.persistence_error,
            },
            "history": {
                "totals": totals(history),
                "logs": history_matches[offset : offset + limit],
                "coverage": {
                    "network_tracked": False,
                    "from": history[-1]["started_at"] if history else None,
                },
                "filtered_total": len(history_matches),
                "sessions": [
                    {"id": str(d["_id"]), "chapter": d.get("lesson_id"), "updated_at": d.get("updated_at")}
                    for d in docs
                ],
                "session_limit": 50,
            },
            "models": model_status(router_factory()),
            "web_mode": get_settings().web_lookup,
        }

    app.include_router(root)
