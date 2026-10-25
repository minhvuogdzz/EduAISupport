"""CFG-2: the model calls of one session command, written down after the command's other events.

``MODEL_CALLED`` for every call that reached the chain: the model that answered, the tokens the provider
counted and the gateway's estimate before sending. ``MODEL_FALLBACK`` for every step down the chain, when a
model did not answer and the next one was tried (ADR-017: Qwen, then gpt-oss; blueprint PART 12.6). A call
that reached no model (the session's cap was already used up) leaves nothing. None of them is replayed.
"""

from __future__ import annotations

from collections.abc import Iterable
from itertools import pairwise

from pydantic import BaseModel

from cavat.core.events import EventType, ModelAttempt, ModelCalled, ModelFallback
from cavat.modules.ai_gateway.router import ChatCall
from cavat.modules.session.repository import NewEvent

# The errors after which the router tries the next model of the chain.
_FALLBACK_REASON = {
    "QuotaExceeded": "QUOTA",
    "ModelUnavailable": "UNAVAILABLE",
    "InvalidModelOutput": "INVALID_OUTPUT",
}


def model_call_events(calls: Iterable[ChatCall], item_attempt_id: str | None = None) -> list[NewEvent]:
    events: list[NewEvent] = []
    for call in calls:
        attempts = call.outcome.attempts
        if not attempts:
            continue
        for tried, after in pairwise(attempts):
            if tried.error in _FALLBACK_REASON:
                moved = ModelFallback(
                    model_class=call.model_class.value,
                    from_model=tried.model,
                    to_model=after.model,
                    reason=_FALLBACK_REASON[tried.error],
                    purpose=call.purpose,
                )
                events.append(_event(EventType.MODEL_FALLBACK, moved, item_attempt_id))
        result, reason = call.outcome.result, call.outcome.fallback_reason
        called = ModelCalled(
            model_class=call.model_class.value,
            purpose=call.purpose,
            model=result.model if result is not None else None,
            fallback_reason=reason.value if reason is not None else None,
            attempts=[
                ModelAttempt(
                    model=a.model,
                    sent=a.sent,
                    error=a.error,
                    detail=a.detail,
                    limit=a.limit,
                    retry_after_s=a.retry_after_s,
                )
                for a in attempts
            ],
            prompt_tokens=result.usage.prompt_tokens if result is not None else 0,
            completion_tokens=result.usage.completion_tokens if result is not None else 0,
            estimated_tokens=call.estimated_tokens,
            prompt_chars=call.prompt_chars,
            schema_chars=call.schema_chars,
            messages=call.messages,
        )
        events.append(_event(EventType.MODEL_CALLED, called, item_attempt_id))
    return events


def _event(event_type: EventType, payload: BaseModel, item_attempt_id: str | None) -> NewEvent:
    return NewEvent(
        event_type=event_type.value, payload=payload.model_dump(mode="json"), item_attempt_id=item_attempt_id
    )
