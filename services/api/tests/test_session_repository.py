"""learning_sessions: one document per session, optimistic concurrency, idempotency, event ledger copy."""

import asyncio

import pytest
from cavat.core.repository import NotFound, TenantViolation
from cavat.modules.session.repository import (
    Actor,
    DuplicateCommand,
    EventRepository,
    LearningSession,
    LearningSessionRepository,
    LifecycleState,
    NewEvent,
    SessionState,
    StateVersionConflict,
)

SCHOOL = "sch-A"


def _session(**kw) -> LearningSession:
    return LearningSession(
        school_id=SCHOOL, student_id="stu-1", lesson_id="math-g5-dec-compare", lesson_version="0.1.0", **kw
    )


def _event(event_type: str, **payload) -> NewEvent:
    return NewEvent(event_type=event_type, payload=payload, actor=Actor(type="student", id="stu-1"))


@pytest.fixture
def repo(db):
    return LearningSessionRepository(db, SCHOOL)


@pytest.fixture
def ledger(db):
    return EventRepository(db, SCHOOL)


async def _started(repo: LearningSessionRepository) -> LearningSession:
    return await repo.create(_session(), [NewEvent(event_type="SESSION_SCHEDULED")])


# --- create and read ----------------------------------------------------------------------------


async def test_create_stores_state_and_initial_events(repo):
    created = await _started(repo)
    loaded = await repo.get(created.id)
    assert loaded == created
    assert loaded.state_version == 0
    assert loaded.state.lifecycle == LifecycleState.SCHEDULED
    assert loaded.next_sequence_no == 2
    [event] = loaded.events
    assert event.sequence_no == 1
    assert (event.school_id, event.student_id, event.session_id) == (SCHOOL, "stu-1", created.id)
    assert event.schema_version == 1
    assert event.actor.type == "system"


async def test_create_rejects_non_fresh_session(repo):
    with pytest.raises(ValueError):
        await repo.create(_session(state_version=3))


async def test_create_rejects_session_of_other_school(repo):
    with pytest.raises(TenantViolation):
        await repo.create(_session().model_copy(update={"school_id": "sch-B"}))


async def test_events_carry_contract_bound_in_same_commit(repo):
    session = await _started(repo)
    after = await repo.commit(
        session, state=session.state, events=[_event("CONTRACT_BOUND")], contract_id="contract-1"
    )
    assert after.contract_id == "contract-1"
    assert after.events[0].contract_id is None
    assert after.events[1].contract_id == "contract-1"


async def test_session_is_invisible_to_other_school(db, repo):
    created = await _started(repo)
    other = LearningSessionRepository(db, "sch-B")
    assert await other.get(created.id) is None
    assert await other.list_for_student("stu-1") == []
    with pytest.raises(NotFound):
        await other.commit(created, state=SessionState(lifecycle=LifecycleState.CANCELLED))
    assert (await repo.get(created.id)).state_version == 0


async def test_list_for_student_filters_lifecycle(repo):
    first = await _started(repo)
    await repo.create(_session())
    await repo.commit(
        first, state=SessionState(lifecycle=LifecycleState.READY), events=[_event("SESSION_READY")]
    )
    ready = await repo.list_for_student("stu-1", [LifecycleState.READY, LifecycleState.ACTIVE])
    assert [s.id for s in ready] == [first.id]
    assert len(await repo.list_for_student("stu-1")) == 2


# --- commit -------------------------------------------------------------------------------------


async def test_commit_updates_state_and_appends_events_atomically(repo):
    session = await _started(repo)
    state = SessionState(
        lifecycle=LifecycleState.ACTIVE,
        activity={"type": "CONCEPT_CHECK", "index": 0},
        item={"item_id": "CC-01", "phase": "AWAITING", "hint_level": 0},
    )
    after = await repo.commit(
        session,
        state=state,
        events=[_event("SESSION_STARTED"), _event("QUESTION_SHOWN", item_id="CC-01")],
        started_at=session.created_at,
    )
    assert after.state_version == 1
    assert after.state == state
    assert after.started_at == session.created_at
    assert [e.sequence_no for e in after.events] == [1, 2, 3]
    assert after.next_sequence_no == 4
    assert after.events[2].payload == {"item_id": "CC-01"}
    assert await repo.get(session.id) == after


async def test_commit_without_events_still_bumps_version(repo):
    session = await _started(repo)
    after = await repo.commit(session, state=SessionState(lifecycle=LifecycleState.READY))
    assert after.state_version == 1
    assert len(after.events) == 1


async def test_stale_state_version_conflicts_and_writes_nothing(repo):
    session = await _started(repo)
    writer_a = session  # both writers read version 0
    writer_b = session
    await repo.commit(
        writer_a, state=SessionState(lifecycle=LifecycleState.READY), events=[_event("SESSION_READY")]
    )

    with pytest.raises(StateVersionConflict) as info:
        await repo.commit(
            writer_b,
            state=SessionState(lifecycle=LifecycleState.CANCELLED),
            events=[_event("SESSION_CANCELLED")],
        )
    assert (info.value.expected, info.value.current) == (0, 1)

    current = await repo.get(session.id)
    assert current.state_version == 1
    assert current.state.lifecycle == LifecycleState.READY
    assert [e.event_type for e in current.events] == ["SESSION_SCHEDULED", "SESSION_READY"]


async def test_concurrent_commits_from_same_snapshot_only_one_wins(repo):
    session = await _started(repo)

    async def write(tag: str):
        state = SessionState(lifecycle=LifecycleState.ACTIVE, item={"writer": tag})
        return await repo.commit(session, state=state, events=[_event("ANSWER_SUBMITTED", writer=tag)])

    results = await asyncio.gather(*(write(t) for t in "abcde"), return_exceptions=True)
    winners = [r for r in results if isinstance(r, LearningSession)]
    losers = [r for r in results if isinstance(r, StateVersionConflict)]
    assert len(winners) == 1 and len(losers) == 4
    current = await repo.get(session.id)
    assert current.state_version == 1
    assert len(current.events) == 2
    assert current.events[1].payload["writer"] == current.state.item["writer"]


async def test_retry_after_conflict_with_fresh_snapshot_succeeds(repo):
    session = await _started(repo)
    await repo.commit(session, state=SessionState(lifecycle=LifecycleState.READY))
    with pytest.raises(StateVersionConflict):
        await repo.commit(session, state=SessionState(lifecycle=LifecycleState.ACTIVE))
    fresh = await repo.get(session.id)
    after = await repo.commit(
        fresh, state=SessionState(lifecycle=LifecycleState.ACTIVE), events=[_event("X")]
    )
    assert after.state_version == 2
    assert after.events[-1].sequence_no == 2


async def test_duplicate_idempotency_key_writes_no_duplicate_events(repo):
    session = await _started(repo)
    events = [_event("ANSWER_SUBMITTED", text="0,3"), _event("POLICY_DECISION", move="PROBE")]
    state = SessionState(lifecycle=LifecycleState.ACTIVE)
    after = await repo.commit(session, state=state, events=events, idempotency_key="key-1")
    assert all(e.idempotency_key == "key-1" for e in after.events[1:])

    # Client retries with the snapshot it had (stale) and with a fresh one: both are duplicates.
    for snapshot in (session, after):
        with pytest.raises(DuplicateCommand) as info:
            await repo.commit(snapshot, state=state, events=events, idempotency_key="key-1")
        assert info.value.session.state_version == 1

    current = await repo.get(session.id)
    assert current.state_version == 1
    assert len(current.events) == 3

    again = await repo.commit(current, state=state, events=events, idempotency_key="key-2")
    assert again.state_version == 2 and len(again.events) == 5


async def test_commit_guards(repo):
    session = await _started(repo)
    state = SessionState(lifecycle=LifecycleState.ACTIVE)
    with pytest.raises(ValueError):
        await repo.commit(session, state=state, student_id="someone-else")
    with pytest.raises(ValueError):
        await repo.commit(session, state=state, state_version=99)
    with pytest.raises(ValueError):
        await repo.commit(session, state=state, idempotency_key="k")  # no event to carry the key
    missing = _session()
    with pytest.raises(NotFound):
        await repo.commit(missing, state=state)
    assert (await repo.get(session.id)).state_version == 0


# --- event ledger copy --------------------------------------------------------------------------


async def test_copy_events_to_ledger_is_incremental_and_idempotent(repo, ledger):
    session = await _started(repo)
    session = await repo.commit(
        session, state=SessionState(lifecycle=LifecycleState.READY), events=[_event("A")]
    )

    assert await repo.copy_events_to_ledger(session.id, ledger) == 2
    assert await repo.copy_events_to_ledger(session.id, ledger) == 0
    assert (await repo.get(session.id)).events_copied_upto == 2
    assert (await repo.get(session.id)).state_version == 1  # bookkeeping does not bump the state

    session = await repo.get(session.id)
    await repo.commit(session, state=session.state, events=[_event("B"), _event("C")])
    assert await repo.copy_events_to_ledger(session.id, ledger) == 2

    copied = await ledger.list_for_session(session.id)
    assert [e.sequence_no for e in copied] == [1, 2, 3, 4]
    assert [e.event_type for e in copied] == ["SESSION_SCHEDULED", "A", "B", "C"]
    assert copied == (await repo.get(session.id)).events
    assert [e.sequence_no for e in await ledger.list_for_session(session.id, after_sequence_no=2)] == [3, 4]


async def test_copy_recovers_after_crash_between_insert_and_marker(repo, ledger):
    session = await _started(repo)
    session = await repo.commit(session, state=session.state, events=[_event("A"), _event("B")])
    # Simulate a copier that inserted two events and died before moving the marker.
    assert await ledger.append_copies(session.events[:2]) == 2
    assert await repo.copy_events_to_ledger(session.id, ledger) == 1
    assert [e.sequence_no for e in await ledger.list_for_session(session.id)] == [1, 2, 3]


async def test_ledger_rejects_duplicate_session_sequence(repo, ledger):
    session = await _started(repo)
    [event] = session.events
    assert await ledger.append_copies([event]) == 1
    clone = event.model_copy(update={"event_id": "another-id"})  # same (session_id, sequence_no)
    assert await ledger.append_copies([clone]) == 0
    assert len(await ledger.list_for_session(session.id)) == 1


async def test_ledger_queries_by_student_and_is_tenant_scoped(db, repo, ledger):
    first = await _started(repo)
    second = await _started(repo)
    for s in (first, second):
        await repo.copy_events_to_ledger(s.id, ledger)
    events = await ledger.list_for_student("stu-1")
    assert {e.session_id for e in events} == {first.id, second.id}
    assert await ledger.list_for_student("stu-1", since=events[-1].occurred_at) != []

    other = EventRepository(db, "sch-B")
    assert await other.list_for_student("stu-1") == []
    assert await other.list_for_session(first.id) == []
    with pytest.raises(ValueError):
        await repo.copy_events_to_ledger(first.id, other)


def test_ledger_has_no_update_or_delete():
    public = {name for name in dir(EventRepository) if not name.startswith("_")}
    assert not {n for n in public if n.startswith(("update", "delete", "remove", "replace"))}
