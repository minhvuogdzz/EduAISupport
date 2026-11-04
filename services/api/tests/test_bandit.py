"""BANDIT-1 (ADR-058, DI-101 to DI-104): a contextual bandit picks one of the moves the policy allows and
learns from the answer that follows. The policy still owns the menu; the bandit never writes mastery; its
state is a replayable fold of BANDIT_REWARD events. Offline: scripted situations, no model."""

from __future__ import annotations

import random
from typing import Any

import numpy as np
import pytest
from cavat.core.events import EventType, MoveChosen
from cavat.core.memory_db import InMemoryDatabase
from cavat.core.pedagogy import ActivityType, HintLevel, Move, Outcome
from cavat.modules.content.lesson_package import Item
from cavat.modules.session import chapter_service
from cavat.modules.tutor.bandit import (
    BANDIT_VERSION,
    DIM,
    HELP_COST,
    BanditChooser,
    LinUCB,
    arm_of,
    context_vector,
    fold,
    increments,
    pick_probabilities,
    reward_of,
)
from cavat.modules.tutor.bandit_store import BanditRepository
from cavat.modules.tutor.chooser import Choice, recorded_choices
from cavat.modules.tutor.contracts import PolicyDecision
from cavat.modules.tutor.item_loop import HINT_REQUEST_TEXT, ItemTutor
from cavat.modules.tutor.policy import MoveOption
from cavat.modules.tutor.renderer import TemplateRenderer
from cavat.modules.tutor.validator import validate_message

CHAPTER = chapter_service.chapters()["math-g5-decimals"]
ITEM: Item = CHAPTER.item("TP-PR-01")  # "Viết phân số 9/10 dưới dạng số thập phân." (answer 0,9)


def probe() -> PolicyDecision:
    return PolicyDecision(move=Move.PROBE)


def hint(level: HintLevel = HintLevel.H1) -> PolicyDecision:
    return PolicyDecision(move=Move.HINT, level=level)


def menu_of(*decisions: PolicyDecision) -> tuple[MoveOption, ...]:
    return tuple(MoveOption("ABC"[i], d) for i, d in enumerate(decisions))


FRESH = {"so_lan_tra_loi": 1}
STUCK = {"so_lan_tra_loi": 4, "so_goi_y_da_nhan": 2, "luot_chua_tien_bo": 3, "co_da_hoi_cach_lam": True}


def pick(chooser: BanditChooser, menu, situation=None, turn: int = 1):
    return chooser.choose(menu=menu, stem="đề", last_tutor="", said="0,5", turn=turn, situation=situation)


# --- the pieces ---------------------------------------------------------------------------------------


def test_the_context_is_nine_numbers_in_the_unit_interval_made_of_counts():
    x = context_vector({**STUCK, "so_lan_tra_loi": 99, "dau_hieu_nan": 99, "bac_goi_y_cao_nhat": 99})
    assert len(x) == DIM == 9 and x[0] == 1.0
    assert all(0.0 <= v <= 1.0 for v in x)
    assert context_vector(None) == (1.0, 0, 0, 0, 0, 0, 0, 0, 0)
    assert context_vector(STUCK) == context_vector(dict(STUCK))  # a pure function of the situation


def test_an_arm_is_the_kind_of_move_and_its_rung_and_a_closing_move_has_none():
    assert arm_of(probe()) == "PROBE"
    assert arm_of(hint(HintLevel.H2)) == "HINT:2"
    assert arm_of(PolicyDecision(move=Move.COGNITIVE_CONFLICT, level=HintLevel.H2)) == "COGNITIVE_CONFLICT"
    assert arm_of(PolicyDecision(move=Move.OFFER_CHOICE)) == "OFFER_CHOICE"
    assert arm_of(PolicyDecision(move=Move.VERIFY)) is None
    assert arm_of(PolicyDecision(move=Move.CONFIRM_ADVANCE)) is None


def test_the_reward_pays_the_answer_and_charges_the_help():
    assert reward_of(Outcome.CORRECT, 0) == 1.0
    assert reward_of(Outcome.PARTIAL, 0) == 0.5
    assert reward_of(Outcome.WRONG, 0) == 0.0
    assert reward_of(Outcome.CORRECT, 7) == pytest.approx(1 - HELP_COST)
    assert reward_of("CORRECT", 1) > reward_of("CORRECT", 3)  # the smaller help that works is worth more
    assert reward_of(Outcome.WRONG, 99) == pytest.approx(-HELP_COST)  # the help is capped at 7


def _train(model: LinUCB, rounds: int, seed: int = 0) -> None:
    """PROBE works for a child on a first attempt, HINT:1 works for a child who is stuck."""
    rng = random.Random(seed)
    for _ in range(rounds):
        stuck = rng.random() < 0.5
        x = context_vector(STUCK if stuck else FRESH)
        arm = rng.choice(["PROBE", "HINT:1"])
        good = (arm == "HINT:1") == stuck
        model.update(arm, x, 1.0 if rng.random() < (0.85 if good else 0.2) else 0.0)


def test_the_model_learns_which_move_suits_which_child():
    model = LinUCB(alpha=0.1)
    _train(model, 600)
    fresh, stuck = context_vector(FRESH), context_vector(STUCK)
    assert model.ucb("PROBE", fresh) > model.ucb("HINT:1", fresh)
    assert model.ucb("HINT:1", stuck) > model.ucb("PROBE", stuck)


def test_the_order_of_the_rewards_does_not_change_the_state():
    rows = [
        (a, context_vector(s), r)
        for a, s, r in [("PROBE", FRESH, 1.0), ("HINT:1", STUCK, 0.5), ("PROBE", STUCK, 0.0)]
    ]
    forward, backward = LinUCB(), LinUCB()
    for row in rows:
        forward.update(*row)
    for row in reversed(rows):
        backward.update(*row)
    for arm in ("PROBE", "HINT:1"):
        assert forward.stats(arm) == pytest.approx(backward.stats(arm))


def test_the_state_is_a_fold_of_the_reward_events_and_of_the_increments():
    events = [
        {"arm": "PROBE", "context": list(context_vector(FRESH)), "reward": 1.0},
        {"arm": "PROBE", "context": list(context_vector(STUCK)), "reward": 0.0},
        {"arm": "HINT:1", "context": list(context_vector(STUCK)), "reward": 0.8},
    ]
    folded = fold(events)
    summed: dict[str, dict[str, float]] = {}
    for e in events:
        acc = summed.setdefault(e["arm"], {})
        for key, value in increments(e["context"], e["reward"]).items():
            acc[key] = acc.get(key, 0.0) + value
    rebuilt = LinUCB.from_stats(summed)
    x = context_vector(STUCK)
    for arm in ("PROBE", "HINT:1"):
        assert folded.count(arm) == rebuilt.count(arm)
        assert folded.score(arm, x) == pytest.approx(rebuilt.score(arm, x))


def test_the_probability_of_a_pick_is_epsilon_spread_and_the_rest_on_the_greedy_move():
    p = pick_probabilities(1, 3, 0.15)
    assert sum(p) == pytest.approx(1.0)
    assert p == pytest.approx([0.05, 0.9, 0.05])


# --- the chooser ----------------------------------------------------------------------------------------


def test_a_bandit_that_learned_nothing_plays_the_policys_own_move():
    chooser = BanditChooser(LinUCB(), epsilon=0.0)
    got = pick(chooser, menu_of(probe(), hint()), FRESH)
    assert got is not None and got.option_id == "A" and got.arm == "PROBE" and got.source == "BANDIT"
    assert got.propensity == 1.0


def test_the_pick_follows_what_was_learned_and_is_always_on_the_menu():
    model = LinUCB(alpha=0.1)
    _train(model, 600)
    chooser = BanditChooser(model, epsilon=0.0)
    menu = menu_of(probe(), hint())
    assert pick(chooser, menu, FRESH).option_id == "A"
    assert pick(chooser, menu, STUCK).option_id == "B"
    for situation in (FRESH, STUCK, None):
        assert pick(BanditChooser(model, seed_key="s", epsilon=0.5), menu, situation).option_id in {"A", "B"}


def test_one_session_one_turn_one_menu_always_give_the_same_pick():
    model = LinUCB()
    menu = menu_of(probe(), hint(), hint(HintLevel.H2))
    a = pick(BanditChooser(model, seed_key="S1", epsilon=0.6), menu, STUCK, turn=3)
    b = pick(BanditChooser(model, seed_key="S1", epsilon=0.6), menu, STUCK, turn=3)
    assert a == b


def test_the_bandit_explores_epsilon_of_the_time_and_logs_the_probability_of_each_pick():
    menu = menu_of(probe(), hint())
    chosen = [pick(BanditChooser(LinUCB(), seed_key=f"s{i}", epsilon=0.2), menu, FRESH) for i in range(2000)]
    other = sum(1 for c in chosen if c is not None and c.option_id == "B")
    assert 0.07 < other / 2000 < 0.13  # epsilon / k = 0.1
    assert {c.propensity for c in chosen if c is not None} == {0.9, 0.1}


def test_a_menu_with_no_choice_or_with_a_move_the_bandit_does_not_learn_goes_to_the_fallback():
    class Fallback:
        calls_made = 2

        def choose(self, **kw: Any) -> Choice:
            return Choice("B", "a model read it")

    assert pick(BanditChooser(LinUCB()), menu_of(probe())) is None
    verify = PolicyDecision(move=Move.VERIFY)
    confirm = PolicyDecision(move=Move.CONFIRM_ADVANCE)
    assert pick(BanditChooser(LinUCB()), menu_of(confirm, verify)) is None
    through = BanditChooser(LinUCB(), fallback=Fallback())  # type: ignore[arg-type]
    got = pick(through, menu_of(confirm, verify))
    assert got is not None and got.source == "LLM" and got.reason == "a model read it"
    assert through.calls_made == 2


# --- in the item loop -----------------------------------------------------------------------------------


def tutor(chooser: BanditChooser | None) -> ItemTutor:
    t = ItemTutor(
        ITEM,
        CHAPTER.lesson_of(ITEM.id),
        ActivityType.GUIDED_PRACTICE,
        TemplateRenderer(),
        validate_message,
        chooser=chooser,
    )
    t.start()
    return t


def events(t: ItemTutor, kind: EventType) -> list[dict[str, Any]]:
    return [e.payload for e in t.events if e.type == kind]


def trained_for_the_first_hint() -> LinUCB:
    model = LinUCB(alpha=0.0)
    x = context_vector({"so_lan_tra_loi": 1})
    for _ in range(30):
        model.update("HINT:1", x, 1.0)
        model.update("PROBE", x, 0.0)
    return model


def test_a_pick_is_recorded_with_its_arm_probability_and_context_and_paid_by_the_next_graded_answer():
    t = tutor(BanditChooser(trained_for_the_first_hint(), seed_key="S", epsilon=0.0))
    turn = t.on_student("0,5")  # wrong: the policy's move is PROBE, the bandit plays the first hint
    assert turn.move == Move.HINT and t.state.hint_levels == [HintLevel.H1]
    [chosen] = events(t, EventType.MOVE_CHOSEN)
    assert chosen["source"] == "BANDIT" and chosen["arm"] == "HINT:1" and chosen["propensity"] == 1.0
    assert chosen["option_id"] == "B" and chosen["options"] == ["PROBE", "HINT"]
    assert len(chosen["context"]) == DIM and set(chosen["scores"]) == {"PROBE", "HINT:1"}
    MoveChosen.model_validate(chosen)
    assert events(t, EventType.BANDIT_REWARD) == []  # nothing is paid before the child answers again
    t.on_student("0,9")  # right
    [paid] = events(t, EventType.BANDIT_REWARD)
    assert paid["arm"] == "HINT:1" and paid["outcome"] == "CORRECT" and paid["help"] == 1
    assert paid["reward"] == reward_of(Outcome.CORRECT, 1) and paid["version"] == BANDIT_VERSION
    assert paid["context"] == chosen["context"] and paid["turn"] == chosen["turn"]


def test_a_wrong_answer_after_the_pick_pays_nothing_for_the_help_it_gave():
    t = tutor(BanditChooser(trained_for_the_first_hint(), seed_key="S", epsilon=0.0))
    t.on_student("0,5")
    t.on_student("0,7")  # wrong again
    [paid] = events(t, EventType.BANDIT_REWARD)
    assert paid["outcome"] == "WRONG" and paid["reward"] == reward_of(Outcome.WRONG, 1) < 0


def test_a_pick_is_paid_once_and_a_pick_the_item_never_follows_is_not_paid():
    t = tutor(BanditChooser(trained_for_the_first_hint(), seed_key="S", epsilon=0.0))
    t.on_student("0,5")
    t.on_student("0,9")  # right: the item is resolved, and the pick was paid once
    assert len(events(t, EventType.BANDIT_REWARD)) == 1
    lone = tutor(BanditChooser(trained_for_the_first_hint(), seed_key="S", epsilon=0.0))
    lone.on_student("0,5")
    assert events(lone, EventType.BANDIT_REWARD) == []


def test_the_policy_still_checks_the_pick_and_a_model_pick_leaves_no_bandit_fields():
    class OffMenu:
        def choose(self, **kw: Any) -> Choice:
            return Choice("D", source="BANDIT", arm="HINT:1", propensity=1.0, context=context_vector(None))

    t = tutor(OffMenu())  # type: ignore[arg-type]
    assert t.on_student("0,5").move == Move.PROBE  # off the menu: the policy's own move is played
    [chosen] = events(t, EventType.MOVE_CHOSEN)
    assert chosen["accepted"] is False
    t.on_student("0,9")
    assert events(t, EventType.BANDIT_REWARD) == []  # a refused pick is never paid
    llm = tutor(type("P", (), {"choose": lambda self, **kw: Choice("A", "x")})())  # a model's pick
    llm.on_student("0,5")
    [c] = events(llm, EventType.MOVE_CHOSEN)
    assert c["source"] == "LLM" and not {"arm", "propensity", "context", "scores"} & set(c)


def test_a_session_rebuilt_from_its_events_plays_the_same_bandit_moves():
    live = tutor(BanditChooser(trained_for_the_first_hint(), seed_key="S", epsilon=0.0))
    live.on_student("0,5")
    live.on_student(HINT_REQUEST_TEXT)
    replay = tutor(recorded_choices(events(live, EventType.MOVE_CHOSEN)))  # type: ignore[arg-type]
    replay.on_student("0,5")
    replay.on_student(HINT_REQUEST_TEXT)
    moves = lambda t: [p["move"] for p in events(t, EventType.POLICY_DECISION)]  # noqa: E731
    assert moves(replay) == moves(live) and replay.state.hint_levels == live.state.hint_levels


def test_a_test_item_never_asks_the_bandit():
    chooser = BanditChooser(trained_for_the_first_hint(), epsilon=0.0)
    t = ItemTutor(
        ITEM,
        CHAPTER.lesson_of(ITEM.id),
        ActivityType.EXIT_ASSESSMENT,
        TemplateRenderer(),
        validate_message,
        chooser=chooser,
    )
    t.start()
    t.on_student("0,5")
    assert events(t, EventType.MOVE_CHOSEN) == []


# --- the store ------------------------------------------------------------------------------------------


REWARDS = [
    {"arm": "PROBE", "context": list(context_vector(FRESH)), "reward": 1.0, "version": BANDIT_VERSION},
    {"arm": "HINT:1", "context": list(context_vector(STUCK)), "reward": 0.6, "version": BANDIT_VERSION},
    {"arm": "HINT:1", "context": list(context_vector(STUCK)), "reward": 0.0, "version": BANDIT_VERSION},
]


async def test_the_store_adds_rewards_as_increments_and_loads_the_same_model_as_the_fold():
    repo = BanditRepository(InMemoryDatabase(), "S1")
    assert (await repo.load()).count("PROBE") == 0
    assert await repo.apply(REWARDS) == 3
    loaded = await repo.load()
    folded = fold(REWARDS)
    x = context_vector(STUCK)
    for arm in ("PROBE", "HINT:1"):
        assert loaded.count(arm) == folded.count(arm)
        assert loaded.score(arm, x) == pytest.approx(folded.score(arm, x))
    assert np.isfinite(loaded.ucb("HINT:2", x))  # an arm never seen is still scored


async def test_a_reward_of_another_version_is_not_added_and_a_school_sees_only_its_own():
    db = InMemoryDatabase()
    one, other = BanditRepository(db, "S1"), BanditRepository(db, "S2")
    assert await one.apply([{**REWARDS[0], "version": "contextual-bandit/0.0.1"}]) == 0
    await one.apply(REWARDS)
    assert (await other.load()).count("HINT:1") == 0 and (await one.load()).count("HINT:1") == 2


async def test_the_store_can_be_dropped_and_rebuilt_from_the_reward_events():
    repo = BanditRepository(InMemoryDatabase(), "S1")
    await repo.apply(REWARDS)
    await repo.apply(REWARDS)  # a double count, as after a crash
    await repo.rebuild(REWARDS)
    assert (await repo.load()).count("HINT:1") == 2


# --- through the API ------------------------------------------------------------------------------------


class QuotaRouter:
    """Every model is out of quota: the bandit's fallback gives nothing and the tutor uses templates."""

    max_calls_per_session = 15

    def chat(self, model_class, request, *, calls_used):
        from cavat.modules.ai_gateway.router import ChatOutcome, FallbackReason

        return ChatOutcome(None, FallbackReason.QUOTA_EXCEEDED, 0)


@pytest.fixture
async def served(monkeypatch):
    from cavat.db import ensure_indexes
    from cavat.main import app
    from cavat.modules.session import api as session_api
    from cavat.modules.session.api import get_database
    from fastapi.testclient import TestClient

    settings = session_api.get_settings()
    monkeypatch.setattr(settings, "allow_tutor_knowledge", False)
    monkeypatch.setattr(settings, "tutor_chooser", "bandit")
    monkeypatch.setattr(settings, "bandit_epsilon", 0.0)
    monkeypatch.setattr(session_api, "tutor_router", lambda: QuotaRouter())
    monkeypatch.setattr(session_api, "_hold_for_unavailable_models", lambda session, step, *args: step)
    database = InMemoryDatabase()
    await ensure_indexes(database)
    app.dependency_overrides[get_database] = lambda: database
    yield TestClient(app), database
    app.dependency_overrides.pop(get_database, None)


async def test_a_session_through_the_api_pays_the_bandit_once_the_child_answers_again(served):
    from cavat.modules.session import service
    from test_chapter_session_api import reply_text

    client, database = served
    an = {"X-Demo-Student": "an"}
    sid = client.post("/v1/sessions", json={"student_display_name": "An"}, headers=an).json()["session_id"]
    state = client.post(f"/v1/sessions/{sid}/join", headers=an).json()
    for key, text in (("k0", None), ("k1", "3/7"), ("k2", None)):  # a first answer, a wrong one, a right one
        body = {
            "item_attempt_id": state["teaching"]["input_id"],
            "kind": "ANSWER",
            "content": {"text": text or reply_text(state)},
            "expected_state_version": state["state_version"],
        }
        sent = client.post(f"/v1/sessions/{sid}/responses", json=body, headers={**an, "Idempotency-Key": key})
        assert sent.status_code == 200, sent.text
        state = client.get(f"/v1/sessions/{sid}/state", headers=an).json()
    stored = await BanditRepository(database, service.DEMO_SCHOOL_ID).load()
    # one pick, paid once: the replays of later commands never pay it again
    assert sum(stored.count(a) for a in ("PROBE", "HINT:1")) == 1
    doc = await database["learning_sessions"].find_one({})
    assert [e["payload"]["arm"] for e in doc["events"] if e["event_type"] == "BANDIT_REWARD"] == ["PROBE"]
