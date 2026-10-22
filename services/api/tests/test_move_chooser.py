"""AUTO-1 (ADR-031, DI-62): the policy offers the moves allowed on a turn, Qwen picks one, the policy checks
the pick. No option gives more help than the policy's own move; a test, a move that ends the item and the
fixed rules offer nothing; every pick is recorded and replayed without a model. Offline: scripted pickers."""

from __future__ import annotations

import itertools
import json
from typing import Any, cast

import pytest
from cavat.core.events import EventType
from cavat.core.pedagogy import ActivityType, ErrorClass, HintLevel, HintTarget, Move, Outcome
from cavat.modules.ai_gateway.base import ChatResult
from cavat.modules.ai_gateway.router import ChatOutcome, FallbackReason
from cavat.modules.assessment.math_checker import CheckResult
from cavat.modules.content.lesson_package import Item
from cavat.modules.session import chapter_service
from cavat.modules.teaching.loop import Awaiting, TeachingLoop
from cavat.modules.tutor.chooser import Choice, ModelChooser, RecordedChooser, describe, recorded_choices
from cavat.modules.tutor.contracts import ItemState, PolicyInput, StudentSnapshot
from cavat.modules.tutor.item_loop import HINT_REQUEST_TEXT, ItemTutor
from cavat.modules.tutor.policy import CHOICE_RULE, ItemFacts, accept, decide, options
from cavat.modules.tutor.renderer import TemplateRenderer
from cavat.modules.tutor.validator import validate_message

CHAPTER = chapter_service.chapters()["math-g5-decimals"]
ITEM = CHAPTER.item("TP-PR-01")  # "Viết phân số 9/10 dưới dạng số thập phân."
NOT_ITEM = cast(Item, object())  # the policy reads nothing from Item
OPEN_HELP = frozenset({Move.WORKED_GUIDANCE, Move.FULL_EXPLANATION, Move.CLOSE_ITEM, Move.CONFIRM_ADVANCE})


class Picks:
    """Picks the scripted option on every turn it is asked; remembers the menus it saw."""

    def __init__(self, *picks: str) -> None:
        self.picks, self.menus, self.situations = list(picks), [], []

    def choose(self, *, menu, stem, last_tutor, said, turn, situation=None):
        self.menus.append([o.decision.move for o in menu])
        self.situations.append(situation)
        return Choice(self.picks.pop(0), "con đang tự nghĩ") if self.picks else None


def tutor(chooser=None, activity: ActivityType = ActivityType.GUIDED_PRACTICE) -> ItemTutor:
    t = ItemTutor(
        ITEM, CHAPTER.lesson_of(ITEM.id), activity, TemplateRenderer(), validate_message, chooser=chooser
    )
    t.start()
    return t


def chosen(t: ItemTutor) -> list[dict[str, Any]]:
    return [e.payload for e in t.events if e.type == EventType.MOVE_CHOSEN]


# --- the menu ------------------------------------------------------------------------------------------


def _inp(
    outcome, trigger="ANSWER", activity=ActivityType.GUIDED_PRACTICE, error=None, mis=None, conf=0.0, **st
):
    check = CheckResult(outcome, error_class=error, misconception_id=mis, misconception_confidence=conf)
    return PolicyInput(
        item=NOT_ITEM,
        state=ItemState(item_id="I1", activity=activity, **st),
        check=check,
        trigger=trigger,
        snapshot=StudentSnapshot(),
    )


def test_the_first_wrong_answer_may_get_the_first_hint_instead_of_the_probe():
    inp = _inp(Outcome.WRONG, error=ErrorClass.PROCEDURAL, attempt_no=1)
    d = decide(inp)
    menu = options(inp, d)
    assert [(o.id, o.decision.move, o.decision.level) for o in menu] == [
        ("A", Move.PROBE, None),
        ("B", Move.HINT, HintLevel.H1),
    ]
    assert accept(menu, "A") == d
    played = accept(menu, "B")
    assert played is not None and CHOICE_RULE in played.rule_ids and "MODEL_CHOICE" in played.reason_codes
    assert accept(menu, "Z") is None  # the policy's check: a move off the menu is never played


@pytest.mark.parametrize(
    "inp",
    [
        _inp(Outcome.WRONG, activity=ActivityType.EXIT_ASSESSMENT, attempt_no=1),  # a test: no choice
        _inp(Outcome.CORRECT, activity=ActivityType.EXIT_ASSESSMENT, attempt_no=1),  # a test ends the item
        _inp(Outcome.CORRECT, attempt_no=2, verified=True),  # "vì sao" was asked already
        _inp(Outcome.CORRECT, attempt_no=3, worked_shown=True),  # R-TEACH-BACK stays
        _inp(Outcome.WRONG, error=ErrorClass.CALCULATION, attempt_no=1),  # R-SLIP stays
        _inp(Outcome.WRONG, attempt_no=4, worked_shown=True, hint_levels=[HintLevel.H6]),  # R-FULL stays
        _inp(Outcome.WRONG, attempt_no=1, unproductive_turns=3),  # R-FRUSTRATION stays
    ],
)
def test_a_turn_without_free_choice_offers_nothing(inp):
    d = decide(inp)
    assert d is not None and options(inp, d) == ()


def test_no_option_ever_gives_more_help_than_the_policy():
    """Every reachable combination of outcome, activity, ladder and counters on the grid."""
    outcomes = [
        Outcome.WRONG,
        Outcome.PARTIAL,
        Outcome.HELP_REQUEST,
        Outcome.ANSWER_DEMAND,
        Outcome.ASKS_ABOUT,
    ]
    outcomes += [Outcome.CLARIFY_REQUEST, Outcome.NEGATIVE_AFFECT, Outcome.OFF_TOPIC, Outcome.UNPARSEABLE]
    activities = [ActivityType.CONCEPT_CHECK, ActivityType.GUIDED_PRACTICE, ActivityType.EXIT_ASSESSMENT]
    ladders = [[], [HintLevel.H1], [HintLevel.H1, HintLevel.H3], [HintLevel.H5]]
    seen = 0
    for outcome, activity, ladder, probes, offered, mis, nudges in itertools.product(
        outcomes, activities, ladders, (0, 1), (False, True), (None, "M1"), (0, 2)
    ):
        inp = _inp(
            outcome,
            "HINT_REQUEST" if outcome == Outcome.HELP_REQUEST else "ANSWER",
            activity,
            error=ErrorClass.CONCEPTUAL,
            mis=mis,
            conf=0.9 if mis else 0.0,
            attempt_no=len(ladder) + 1,
            hint_levels=list(ladder),
            hint_targets=[HintTarget.CONCEPT] * len(ladder),
            probes_sent=probes,
            choice_offered=offered,
            nudges_sent=nudges,
            affect_signals=1 if outcome == Outcome.NEGATIVE_AFFECT else 0,
        )
        facts = ItemFacts(counterexamples=frozenset({"M1"}))
        d = decide(inp, facts)
        menu = options(inp, d, facts)
        if activity == ActivityType.EXIT_ASSESSMENT:
            assert menu == ()
        if not menu:
            continue
        seen += 1
        assert menu[0].decision == d and 2 <= len(menu) <= 3
        for o in menu[1:]:
            alt = o.decision
            assert alt.move not in OPEN_HELP and alt.resolution is None
            if alt.level is not None:
                assert alt.level <= (d.level if d.level is not None else HintLevel.H1)
                assert alt.level <= HintLevel.H5
    assert seen > 50  # the grid does reach turns with a choice


# --- the item loop ------------------------------------------------------------------------------------


def test_the_pick_is_played_and_recorded():
    picks = Picks("B")
    t = tutor(picks)
    turn = t.on_student("0,5")
    assert picks.menus == [[Move.PROBE, Move.HINT]]
    assert turn.move == Move.HINT and t.state.hint_levels == [HintLevel.H1]
    [pick] = chosen(t)
    assert pick == {
        "item_id": ITEM.id,
        "turn": 1,
        "option_id": "B",
        "options": ["PROBE", "HINT"],
        "move": "HINT",
        "reason": "con đang tự nghĩ",
        "accepted": True,
        "source": "LLM",
    }
    decision = [e.payload for e in t.events if e.type == EventType.POLICY_DECISION][-1]
    assert CHOICE_RULE in decision["rule_ids"]


def test_a_pick_off_the_menu_is_refused_and_the_policy_plays_its_own_move():
    t = tutor(Picks("D"))
    assert t.on_student("0,5").move == Move.PROBE
    assert [(p["option_id"], p["move"], p["accepted"]) for p in chosen(t)] == [("D", "PROBE", False)]


def test_no_chooser_or_no_pick_keeps_the_policy_move():
    assert tutor().on_student("0,5").move == Move.PROBE
    t = tutor(Picks())  # the model gave nothing (quota, budget)
    assert t.on_student("0,5").move == Move.PROBE and chosen(t) == []


def test_a_test_item_never_asks_the_chooser():
    picks = Picks("B")
    t = tutor(picks, ActivityType.EXIT_ASSESSMENT)
    t.on_student("0,5")
    t.on_student(HINT_REQUEST_TEXT)
    assert picks.menus == [] and chosen(t) == []


def test_a_session_rebuilt_from_its_events_plays_the_same_moves_without_a_model():
    live = tutor(Picks("B", "B"))
    live.on_student("0,5")
    live.on_student(HINT_REQUEST_TEXT)
    replay = tutor(recorded_choices(chosen(live)))
    replay.on_student("0,5")
    replay.on_student(HINT_REQUEST_TEXT)
    moves = lambda t: [e.payload["move"] for e in t.events if e.type == EventType.POLICY_DECISION]  # noqa: E731
    assert moves(replay) == moves(live)
    assert replay.state.hint_levels == live.state.hint_levels
    assert isinstance(recorded_choices([]), RecordedChooser)


def test_the_teaching_loop_replays_the_recorded_pick():
    from datetime import UTC, datetime

    now = datetime(2026, 10, 19, 9, 0, tzinfo=UTC)
    loop = TeachingLoop(CHAPTER, "s1")
    turn = loop.start(now)
    while turn.awaiting != Awaiting.ANSWER:
        turn = loop.on_student("Con nghĩ là được ạ.", now)
    loop.go_live(chooser=Picks("B", "B", "B"))
    for said in ("3/7", HINT_REQUEST_TEXT):
        if loop.awaiting == Awaiting.ANSWER:
            loop.on_student(said, now)
    picks = [e for e in loop.events if e.event_type == EventType.MOVE_CHOSEN]
    assert len(picks) == 1  # the wrong answer had a choice; "Xin gợi ý" gets the hint (DI-35)
    again = TeachingLoop.resume(CHAPTER, "s1", [], loop.events)  # no chooser: the record is replayed
    assert again.tutor is not None and loop.tutor is not None
    assert again.tutor.state.hint_levels == loop.tutor.state.hint_levels
    assert again.tutor.phase == loop.tutor.phase


# --- the model --------------------------------------------------------------------------------------------


class ScriptedRouter:
    def __init__(self, *answers: dict | None) -> None:
        self.answers, self.requests = list(answers), []

    def chat(self, model_class, request, *, calls_used):
        self.requests.append(request)
        data = self.answers.pop(0) if self.answers else None
        if data is None:
            return ChatOutcome(None, FallbackReason.QUOTA_EXCEEDED, 0)
        return ChatOutcome(ChatResult("qwen-test", str(data), data), None, 1)


def test_qwen_sees_the_menu_and_the_words_but_never_the_answer():
    router = ScriptedRouter({"choice": "B", "reason": "Con cần một gợi ý nhỏ về cách đọc phân số."})
    t = tutor(ModelChooser(router))
    assert t.on_student("con không chắc, 0,5 ạ").move == Move.HINT
    [request] = router.requests
    case = json.loads(request.messages[1].content)
    assert case["hoc_sinh_vua_go"] == "con không chắc, 0,5 ạ"
    assert [o["ma"] for o in case["nuoc_di"]] == ["A", "B"]
    assert case["nuoc_di"][0]["mo_ta"] == describe(decide_first())
    # AUTO-4: how the child is doing on the item, and how much each move helps (the probe asks back)
    assert case["tinh_hinh"]["so_lan_tra_loi"] == 1 and case["tinh_hinh"]["so_goi_y_da_nhan"] == 0
    assert [o["muc_giup"] for o in case["nuoc_di"]] == [0, 1]
    assert "con đã sai từ 2 lần" in request.messages[0].content
    assert request.json_schema["properties"]["choice"]["enum"] == ["A", "B"]
    assert "0,9" not in request.messages[1].content and "0,9" not in request.messages[0].content
    assert chosen(t)[0]["reason"].startswith("Con cần")


def decide_first():
    inp = _inp(Outcome.WRONG, attempt_no=1)
    return decide(inp)


def test_the_chooser_spends_only_the_first_half_of_the_call_budget():
    router = ScriptedRouter({"choice": "B", "reason": ""})
    late = ModelChooser(router, calls_used=7, max_calls=15)
    t = tutor(late)
    assert t.on_student("0,5").move == Move.PROBE and router.requests == []
    early = ModelChooser(ScriptedRouter(None), calls_used=0, max_calls=15)  # quota: the policy's move
    assert tutor(early).on_student("0,5").move == Move.PROBE and early.calls_made == 0


# --- through the API: the teacher sees the pick ---------------------------------------------------------


class QuotaRouter:
    """Every model is out of quota: the renderer, the reader and the speaker fall back to templates."""

    max_calls_per_session = 15

    def chat(self, model_class, request, *, calls_used):
        return ChatOutcome(None, FallbackReason.QUOTA_EXCEEDED, 0)


@pytest.fixture
async def client(monkeypatch):
    from cavat.core.memory_db import InMemoryDatabase
    from cavat.db import ensure_indexes
    from cavat.main import app
    from cavat.modules.session import api as session_api
    from cavat.modules.session.api import get_database
    from fastapi.testclient import TestClient

    monkeypatch.setattr(session_api, "tutor_router", lambda: QuotaRouter())
    monkeypatch.setattr(session_api, "ModelChooser", lambda router, calls_used: Picks("B"))
    database = InMemoryDatabase()
    await ensure_indexes(database)
    app.dependency_overrides[get_database] = lambda: database
    yield TestClient(app)
    app.dependency_overrides.pop(get_database, None)


def test_the_teacher_sees_which_move_qwen_picked_and_why(client):
    from test_chapter_session_api import TEACHER, reply_text

    an = {"X-Demo-Student": "an"}
    created = client.post("/v1/sessions", json={"student_display_name": "An"}, headers=an).json()
    sid = created["session_id"]
    state = client.post(f"/v1/sessions/{sid}/join", headers=an).json()
    for key, text in (("k0", None), ("k1", "3/7")):
        body = {
            "item_attempt_id": state["teaching"]["input_id"],
            "kind": "ANSWER",
            "content": {"text": text or reply_text(state)},
            "expected_state_version": state["state_version"],
        }
        sent = client.post(f"/v1/sessions/{sid}/responses", json=body, headers={**an, "Idempotency-Key": key})
        assert sent.status_code == 200, sent.text
        state = client.get(f"/v1/sessions/{sid}/state", headers=an).json()

    transcript = client.get(f"/v1/sessions/{sid}/transcript", headers=TEACHER).json()
    tutor_turns = [t["tutor"] for s in transcript["segments"] for t in s["turns"] if t.get("tutor")]
    [picked] = [t for t in tutor_turns if t.get("chosen")]
    assert picked["move"] == "HINT" and CHOICE_RULE in picked["rule_ids"]
    assert picked["chosen"] == {
        "options": ["PROBE", "HINT"],
        "option_id": "B",
        "reason": "con đang tự nghĩ",
        "accepted": True,
    }


def test_a_reason_that_slips_into_another_script_is_cut_there():
    from cavat.modules.tutor.chooser import clean_reason

    assert clean_reason("cần hỏi lại để hiểu con đang nghĩ gì trước khi介入") == (
        "cần hỏi lại để hiểu con đang nghĩ gì trước khi…"
    )
    assert clean_reason("介入") == ""
    assert clean_reason("  Con cần một gợi ý nhỏ. ") == "Con cần một gợi ý nhỏ."


def test_the_chooser_reads_how_the_child_is_doing_on_the_item():
    from cavat.modules.tutor.chooser import situation

    picks = Picks("A")
    tutor(picks).on_student("0,5")
    [first] = picks.situations
    assert first["so_lan_tra_loi"] == 1 and first["co_da_hoi_cach_lam"] is False
    state = ItemState(
        item_id="I1",
        activity=ActivityType.GUIDED_PRACTICE,
        attempt_no=3,
        hint_levels=[HintLevel.H1, HintLevel.H2],
        unproductive_turns=2,
        help_requests=1,
        affect_signals=1,
        probes_sent=1,
        misconception_counts={"M1": 2, "M2": 1},
    )
    assert situation(state) == {
        "so_lan_tra_loi": 3,
        "so_goi_y_da_nhan": 2,
        "bac_goi_y_cao_nhat": 2,
        "luot_chua_tien_bo": 2,
        "so_lan_xin_goi_y": 1,
        "dau_hieu_nan": 1,
        "co_da_hoi_cach_lam": True,
        "loi_lap_lai_nhieu_nhat": 2,
    }


# --- AUTO-5: "vì sao" after a right answer -------------------------------------------------------------


def test_a_right_answer_the_policy_closes_may_get_why_instead():
    inp = _inp(Outcome.CORRECT, attempt_no=2, hint_levels=[HintLevel.H1])
    d = decide(inp)
    assert d is not None and d.move == Move.CONFIRM_ADVANCE
    menu = options(inp, d)
    assert [(o.id, o.decision.move, o.decision.level, o.decision.resolution) for o in menu] == [
        ("A", Move.CONFIRM_ADVANCE, None, d.resolution),
        ("B", Move.VERIFY, None, None),
    ]
    played = accept(menu, "B")
    assert played is not None and played.rule_ids == ("R-VERIFY", CHOICE_RULE)
    assert describe(menu[1].decision).startswith("Con đã đúng: hỏi con vì sao")


def test_why_after_a_right_answer_keeps_the_resolution():
    """Wrong once, then right: the chooser asks why, the item closes after the reply as it would have."""
    plain = tutor()
    plain.on_student("0,09")
    assert plain.on_student("0,9").resolved

    picks = Picks("A", "B")  # the policy's move on the wrong answer, then "vì sao"
    t = tutor(picks)
    t.on_student("0,09")
    turn = t.on_student("0,9")
    assert picks.menus[-1] == [Move.CONFIRM_ADVANCE, Move.VERIFY]
    assert not turn.resolved and turn.move == Move.VERIFY and "?" in turn.text
    assert chosen(t)[-1]["move"] == "VERIFY" and chosen(t)[-1]["accepted"] is True
    assert t.on_student("vì mẫu số là 10 nên có một chữ số sau dấu phẩy").resolved
    assert resolved(plain) and resolved(t) == resolved(plain)


def resolved(t: ItemTutor) -> list[Any]:
    return [e.payload.get("resolution") for e in t.events if e.type == EventType.ITEM_RESOLVED]
