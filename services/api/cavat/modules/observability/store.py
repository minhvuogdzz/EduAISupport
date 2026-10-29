"""Bounded JSONL journal. No prompts, responses, credentials or audio are recorded.

All records carry a school id. A request context is copied into the existing thread pool, so nested
RAG, embedding, web and model work shares a request id and parent span. Logging never changes teaching.
"""

from __future__ import annotations

import json
import logging
import threading
from collections import OrderedDict
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

MAX_RECORDS = 3000
MAX_BYTES = 5_000_000
_logger = logging.getLogger(__name__)


class OperationalLog:
    def __init__(self, path: Path | None = None, capacity: int = MAX_RECORDS) -> None:
        self.path, self.capacity = path, capacity
        self._rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()
        self.persistence_error = False
        if path:
            for source in (path.with_suffix(".previous.jsonl"), path):
                if not source.is_file():
                    continue
                try:
                    with source.open(encoding="utf-8") as stream:
                        for line in stream:
                            try:
                                row = json.loads(line)
                                if isinstance(row, dict) and row.get("id") and row.get("school_id"):
                                    self._put(row)
                            except (ValueError, TypeError):
                                continue
                except OSError:
                    self.persistence_error = True
            # A process that ended mid-request cannot still be running.
            for row in self._rows.values():
                if row.get("status") == "running":
                    row["status"] = "interrupted"

    def _put(self, row: dict[str, Any]) -> None:
        self._rows[row["id"]] = row
        if len(self._rows) > self.capacity:
            self._rows.popitem(last=False)

    def write(self, row: dict[str, Any]) -> None:
        with self._lock:
            self._put(dict(row))
            if self.path is None:
                return
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                if self.path.exists() and self.path.stat().st_size >= MAX_BYTES:
                    self.path.replace(self.path.with_suffix(".previous.jsonl"))
                with self.path.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            except (OSError, ValueError, TypeError):
                self.persistence_error = True
                _logger.warning("Operational journal unavailable; keeping bounded in-memory logs")

    def snapshot(self, school_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(row) for row in reversed(self._rows.values()) if row["school_id"] == school_id]


@dataclass(frozen=True)
class TraceContext:
    store: OperationalLog
    school_id: str
    request_id: str
    session_id: str | None
    path: str
    parent_id: str | None = None


context: ContextVar[TraceContext | None] = ContextVar("operational_trace", default=None)


def new_row(ctx: TraceContext, kind: str, operation: str) -> dict[str, Any]:
    return {
        "id": uuid4().hex,
        "school_id": ctx.school_id,
        "request_id": ctx.request_id,
        "session_id": ctx.session_id,
        "parent_id": ctx.parent_id,
        "path": ctx.path,
        "started_at": datetime.now(UTC).isoformat(),
        "kind": kind,
        "operation": operation,
        "status": "running",
        "duration_ms": None,
        "model": None,
        "model_class": None,
        "purpose": operation,
        "prompt_tokens": None,
        "completion_tokens": None,
        "calls_sent": 0,
        "details": {},
    }
