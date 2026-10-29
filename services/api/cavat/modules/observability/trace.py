"""Passive synchronous tracing at the gateway and retrieval boundaries."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from functools import wraps
from time import perf_counter
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .store import context, new_row


def source_event(reason: str, *, kind: str = "decision", url: str = "") -> None:
    """Record a bounded routing/cache fact without the learner's question."""
    ctx = context.get()
    if ctx is None:
        return
    row = new_row(ctx, kind, reason)
    row.update(status="success", purpose=reason, duration_ms=0)
    if url:
        row["details"]["url"] = _public_url(url)
    ctx.store.write(row)


def _public_url(url: str) -> str:
    parsed = urlsplit(str(url))
    return urlunsplit((parsed.scheme, parsed.hostname or "", parsed.path, "", ""))


@contextmanager
def network_request(url: str, method: str = "GET"):
    """One actual outbound source HTTP request; exclude query strings, headers and bodies."""
    ctx = context.get()
    meta: dict[str, Any] = {}
    if ctx is None:
        yield meta
        return
    row = new_row(ctx, "network", method)
    row.update(purpose=urlsplit(str(url)).hostname or "source_http")
    row["details"] = {"url": _public_url(url), "method": method}
    ctx.store.write(row)
    start = perf_counter()
    try:
        yield meta
        row["status"] = "success" if 200 <= meta.get("http_status", 200) < 400 else "error"
    except Exception as exc:
        row["status"] = "error"
        meta["error"] = type(exc).__name__
        raise
    finally:
        row["details"].update(meta)
        row["duration_ms"] = round((perf_counter() - start) * 1000, 1)
        ctx.store.write(row)


def traced(kind: str):
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            ctx = context.get()
            if ctx is None:
                return function(*args, **kwargs)
            row = new_row(ctx, kind, function.__name__)
            if kind == "model" and function.__name__ == "chat":
                row["model_class"] = str(args[1] if len(args) > 1 else kwargs.get("model_class", ""))
                request = args[2] if len(args) > 2 else kwargs.get("request")
                row["purpose"] = getattr(request, "schema_name", "chat")
            ctx.store.write(row)
            token = context.set(replace(ctx, parent_id=row["id"]))
            start = perf_counter()
            try:
                result = function(*args, **kwargs)
                try:
                    row.update(_result(kind, function.__name__, result, args, kwargs))
                except Exception:  # noqa: BLE001 - diagnostics must not change a successful teaching call
                    row.update(status="success", details={"telemetry": "metadata_unavailable"})
                return result
            except Exception as exc:
                row["status"] = "error"
                row["details"] = {"error": type(exc).__name__}
                raise
            finally:
                row["duration_ms"] = round((perf_counter() - start) * 1000, 1)
                ctx.store.write(row)
                context.reset(token)

        return wrapped

    return decorate


def _result(kind: str, operation: str, result: Any, args: tuple, kwargs: dict) -> dict[str, Any]:
    if kind == "rag":
        return {
            "status": "success" if result.grounded else "miss",
            "purpose": result.mode,
            "details": {
                "node_id": result.node_id,
                "grounded": result.grounded,
                "grounding": result.grounding,
                "semantic": result.semantic,
                "candidates": result.candidates,
                "chunks": [{"id": s.chunk.chunk_id, "title": s.chunk.title} for s in result.results],
            },
        }
    if kind == "web":
        return {
            "status": "success" if result else "miss",
            "purpose": getattr(args[0], "name", "web_lookup"),
            "details": {
                "title": getattr(result, "title", None),
                "url": getattr(result, "url", None),
                "retrieval": getattr(result, "retrieval", None),
                "search_engine": getattr(result, "search_engine", None),
                "cache_possible": True,
            },
        }
    if operation == "chat":
        answered = result.result
        usage = getattr(answered, "usage", None)
        known = usage is not None and usage.prompt_tokens + usage.completion_tokens > 0
        return {
            "status": "success" if answered else "fallback" if result.calls_made else "skipped",
            "model": getattr(answered, "model", None),
            "calls_sent": result.calls_made,
            "prompt_tokens": usage.prompt_tokens if known else None,
            "completion_tokens": usage.completion_tokens if known else None,
            "details": {
                "fallback_reason": result.fallback_reason,
                "attempts": [
                    {
                        "model": a.model,
                        "sent": a.sent,
                        "error": a.error,
                        "limit": a.limit,
                        "retry_after_s": a.retry_after_s,
                    }
                    for a in result.attempts
                ],
            },
        }
    usage = getattr(result, "usage", None)
    return {
        "status": "success",
        "model": getattr(result, "model", None)
        or (args[0].embedding_model if operation == "embed" else None),
        "calls_sent": 1,
        "prompt_tokens": usage.prompt_tokens if usage and usage.total_tokens else None,
        "completion_tokens": usage.completion_tokens if usage and usage.total_tokens else None,
        "purpose": kwargs.get("task", operation),
        "details": {"usage_reported": usage is not None},
    }
