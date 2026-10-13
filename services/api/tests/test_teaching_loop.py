"""Teaching loop (M1-6): whole conversations on the decimals chapter, offline, with templates only."""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from fractions import Fraction
from pathlib import Path

import pytest
from cavat.core.pedagogy import Outcome
from cavat.modules.assessment.math_checker import check_answer, parse_literal
from cavat.modules.content.chapter_package import load_chapter
from cavat.modules.teaching.loop import Awaiting, MessageKind, TeachingLoop
from cavat.modules.tutor.item_loop import Phase

CHAPTER = load_chapter(
    Path(__file__).resolve().parents[3] / "docs/pedagogy/math-g5/chuong-so-thap-phan/chapter.yaml"
)
T0 = datetime(2026, 10, 6, 8, 0, tzinfo=UTC)
EXPLAINING = (Phase.VERIFYING, Phase.TEACH_BACK, Phase.AWAITING_REASON)


def correct_text(item_id: str) -> str:
    item, lesson = CHAPTER.item(item_id), CHAPTER.lesson_of(item_id)
    ans = item.answer
    if ans.type == "compare":
        left, right = parse_literal(ans.left).value, parse_literal(ans.right).value
        sign = "<" if left < right else ">" if left > right else "="
        larger, smaller = (ans.left, ans.right) if left > right else (ans.right, ans.left)
        text = {"sign": sign, "larger": larger, "smaller": smaller}[ans.ask]
    elif ans.type == "order":
        key = lambda n: Fraction(parse_literal(n).value)  # noqa: E731
        text = "; ".join(sorted(ans.numbers, key=key, reverse=ans.direction == "desc"))
    elif ans.type == "numeric":
        text = ans.value
    elif ans.type == "choice":
        text = next(o.id for o in ans.options if o.correct)
    elif ans.type == "boolean":
        text = "đúng" if ans.value else "sai"
    else:
        text = ans.sample_answer
    assert check_answer(item, text, lesson).outcome == Outcome.CORRECT, (item_id, text)
    return text


@dataclass
class Learner:
    """Answers right and explains with the item's explanation; retells with the node's key ideas."""

    wrong_once: set[str] = field(default_factory=set)  # items answered wrong the first time
    weak_retells: dict[str, int] = field(default_factory=dict)  # node -> retells without any key idea

    def reply(self, turn) -> str:
        if turn.awaiting == Awaiting.THEORY_REPLY:
            return "Con nghĩ là được ạ."
        if turn.awaiting == Awaiting.RETELL:
            node_id = next(m.node_id for m in reversed(turn.messages) if m.kind == MessageKind.RETELL_PROMPT)
            if self.weak_retells.get(node_id, 0):
                self.weak_retells[node_id] -= 1
                return "Con không nhớ ạ."
            return ". ".join(ideas[0] for ideas in CHAPTER.node(node_id).explain.key_ideas)
        item = CHAPTER.item(turn.item_id)
        if turn.item_phase in EXPLAINING:
            return item.explanation or "Vì con làm theo quy tắc cô dạy."
        if turn.item_id in self.wrong_once:
            self.wrong_once.discard(turn.item_id)
            return "123"
        return correct_text(turn.item_id)


def converse(learner, loop=None, turns=None, limit=600):
    loop = loop or TeachingLoop(CHAPTER, "s1")
    turns = turns if turns is not None else [loop.start(T0)]
    for _ in range(limit):
        if turns[-1].awaiting == Awaiting.NOTHING:
            return loop, turns
        now = T0 + timedelta(seconds=10 * len(turns))
        turns.append(loop.on_student(learner.reply(turns[-1]), now, seconds=10))
    raise AssertionError("the conversation never finished")


def test_a_strong_learner_is_taught_the_whole_chapter_through_conversation():
    loop, turns = converse(Learner())
    first = turns[0].messages
    assert [m.kind for m in first] == [MessageKind.NODE, MessageKind.THEORY]
    theory = CHAPTER.node("KC-DEC-FRAC").theory[0]
    assert first[1].text == f"{theory.text} {theory.ask}"
    projection = loop.projection()
    assert all(state.passed_at is not None for state in projection.nodes.values())
    summary = turns[-1].messages[-1]
    assert summary.kind == MessageKind.SUMMARY
    assert all(node.name in summary.text for node in CHAPTER.nodes)
    kinds = {m.kind for t in turns for m in t.messages}
    assert {MessageKind.EXAMPLE, MessageKind.RETELL_PROMPT, MessageKind.PASS, MessageKind.ITEM} <= kinds


def test_resuming_from_the_stored_events_continues_the_same_conversation():
    learner = Learner(wrong_once={"TP-PR-01"})
    loop, turns = TeachingLoop(CHAPTER, "s1"), []
    turns.append(loop.start(T0))
    while not (turns[-1].awaiting == Awaiting.ANSWER and turns[-1].item_id == "TP-PR-01"):
        turns.append(loop.on_student(learner.reply(turns[-1]), T0 + timedelta(seconds=len(turns)), 1))
    turns.append(loop.on_student(learner.reply(turns[-1]), T0 + timedelta(seconds=len(turns)), 1))  # wrong
    assert turns[-1].awaiting == Awaiting.ANSWER and turns[-1].item_id == "TP-PR-01"

    resumed = TeachingLoop.resume(CHAPTER, "s1", [], list(loop.events))
    for i in range(12):
        now, reply = T0 + timedelta(minutes=5 + i), learner.reply(turns[-1])
        original, again = loop.on_student(reply, now, 3), resumed.on_student(reply, now, 3)
        assert again.messages == original.messages and again.events == original.events
        turns.append(original)
    assert resumed.events == loop.events


def test_a_retell_without_the_key_ideas_gets_feedback_and_another_explanation():
    _, turns = converse(Learner(weak_retells={"KC-DEC-FRAC": 1}))
    first_retell = next(i for i, t in enumerate(turns) if t.awaiting == Awaiting.RETELL)
    after = turns[first_retell + 1].messages
    # "Con không nhớ ạ." asks for help (ADR-019): the tutor reminds the main idea of the node.
    assert after[0].kind == MessageKind.FEEDBACK and "nhắc lại ý chính" in after[0].text
    assert CHAPTER.node("KC-DEC-FRAC").description in after[0].text
    assert (after[1].kind, after[1].ref) == (MessageKind.THEORY, "T2")


def test_a_hint_request_goes_to_the_open_item():
    loop = TeachingLoop(CHAPTER, "s1")
    loop.start(T0)
    check = loop.on_student("Con nghĩ là 4/100 ạ.", T0 + timedelta(seconds=5), 5)
    assert (check.awaiting, check.item_id) == (Awaiting.ANSWER, "TP-CC-01")
    hinted = loop.on_hint_request(T0 + timedelta(seconds=20), 15)  # "Xin gợi ý": the hint at once (DI-35)
    assert [e.event_type for e in hinted.events][0] == "HINT_REQUESTED" and not hinted.choice_open
    assert "HINT_DELIVERED" in [e.event_type for e in hinted.events]
    assert hinted.messages[0].kind == MessageKind.ITEM and hinted.awaiting == Awaiting.ANSWER


def test_inputs_are_refused_when_nothing_is_expected():
    loop = TeachingLoop(CHAPTER, "s1")
    loop.start(T0)
    with pytest.raises(RuntimeError, match="open item"):
        loop.on_hint_request(T0)
    finished, _ = converse(Learner())
    with pytest.raises(RuntimeError, match="no student input expected"):
        finished.on_student("xin chào", T0)
    with pytest.raises(RuntimeError, match="already started"):
        finished.start(T0)


def test_a_worked_example_is_shown_step_by_step():
    _, turns = converse(Learner())
    example = next(m for t in turns for m in t.messages if m.kind == MessageKind.EXAMPLE)
    worked = CHAPTER.node(example.node_id).worked_examples[0]
    assert worked.problem in example.text and "Bước 1:" in example.text and worked.answer in example.text


# ------------------------------------------------------------------------ DI-52: asking back an earlier node


def until_recall(learner):
    loop, turns = TeachingLoop(CHAPTER, "s1"), []
    turns.append(loop.start(T0))
    while not any(m.ref == "RECALL" and m.kind == MessageKind.RETELL_PROMPT for m in turns[-1].messages):
        turns.append(loop.on_student(learner.reply(turns[-1]), T0 + timedelta(seconds=len(turns)), 1))
    return loop, turns


def test_a_new_node_asks_back_its_prerequisite_before_the_theory():
    _, turns = until_recall(Learner())
    asked = turns[-1]
    prompt = next(m for m in asked.messages if m.kind == MessageKind.RETELL_PROMPT)
    frac = CHAPTER.node("KC-DEC-FRAC")
    assert prompt.node_id == "KC-DEC-FRAC"
    assert "Khái niệm số thập phân" in prompt.text and "dùng tới bài Phân số thập phân" in prompt.text
    assert "nói lại giúp" not in asked.prompt and asked.prompt in frac.explain.prompt
    assert (asked.awaiting, asked.node_id) == (Awaiting.RETELL, "KC-DEC-FRAC")


def test_a_good_recall_is_praised_bridged_and_judged_as_evidence_on_the_earlier_node():
    loop, turns = until_recall(Learner())
    reply = ". ".join(ideas[0] for ideas in CHAPTER.node("KC-DEC-FRAC").explain.key_ideas)
    turn = loop.on_student(reply, T0 + timedelta(minutes=30), 8)
    judged = next(e.payload for e in turn.events if e.event_type == "RETELL_JUDGED")
    assert (judged["node_id"], judged["purpose"], judged["score"]) == ("KC-DEC-FRAC", "RECALL", 1.0)
    said = [(m.kind, m.node_id) for m in turn.messages]
    assert said[:2] == [(MessageKind.FEEDBACK, "KC-DEC-FRAC"), (MessageKind.THEORY, "KC-DEC-CONCEPT")]
    assert "nhớ bài cũ tốt lắm" in turn.messages[0].text and "Khái niệm số thập phân" in turn.messages[0].text


def test_a_child_who_does_not_remember_hears_the_earlier_idea_then_the_new_node_is_taught():
    loop, _ = until_recall(Learner())
    turn = loop.on_student("con ko nhớ ạ", T0 + timedelta(minutes=30), 8)
    assert CHAPTER.node("KC-DEC-FRAC").description in turn.messages[0].text
    assert (turn.messages[1].kind, turn.messages[1].node_id) == (MessageKind.THEORY, "KC-DEC-CONCEPT")
    before = [s for s in loop.projection().trace if s.node_id == "KC-DEC-FRAC"]
    assert before[-1].mastery < before[-2].mastery  # the failed recall counts against the earlier node


def test_a_session_waiting_for_a_recall_resumes_the_same_way():
    loop, _ = until_recall(Learner())
    resumed = TeachingLoop.resume(CHAPTER, "s1", [], list(loop.events))
    assert resumed.current_turn().prompt == loop.current_turn().prompt
    now = T0 + timedelta(minutes=30)
    original, again = (
        loop.on_student("phân số có mẫu số 10", now, 3),
        resumed.on_student("phân số có mẫu số 10", now, 3),
    )
    assert again.messages == original.messages and again.events == original.events


def test_a_retell_prompt_that_only_names_the_node_is_asked_back_in_general_words():
    from cavat.modules.teaching.loop import recall_question

    frac = CHAPTER.node("KC-DEC-FRAC")
    assert recall_question(frac).startswith("phân số thập phân là phân số thế nào")
    generic = frac.model_copy(
        update={
            "explain": frac.explain.model_copy(
                update={"prompt": "Con nói lại giúp cô bằng lời của con: phân số thập phân thế nào?"}
            )
        }
    )
    assert recall_question(generic) is None
    bare = frac.model_copy(
        update={"explain": frac.explain.model_copy(update={"prompt": "Các bước nào em đã làm?"})}
    )
    assert recall_question(bare) is None


# --------------------------------------------------------------- DI-53: the earlier node after a wrong answer


def until_item_of(node_id, learner):
    loop, turns = TeachingLoop(CHAPTER, "s1"), []
    turns.append(loop.start(T0))
    while not (
        turns[-1].awaiting == Awaiting.ANSWER
        and turns[-1].node_id == node_id
        and turns[-1].item_phase == Phase.AWAITING
        and CHAPTER.item(turns[-1].item_id).kc_ids[0] == node_id
    ):
        turns.append(loop.on_student(learner.reply(turns[-1]), T0 + timedelta(seconds=len(turns)), 1))
    return loop, turns


def test_a_first_wrong_answer_brings_back_the_closest_prerequisite_once():
    loop, turns = until_item_of("KC-DEC-CMP", Learner())
    item_id = turns[-1].item_id
    flip = {"<": ">", ">": "<", "=": "<"}
    wrong = loop.on_student(flip[correct_text(item_id)], T0 + timedelta(hours=1), 5)
    hint = [m for m in wrong.messages if m.ref == "RECALL_HINT"]
    assert len(hint) == 1 and hint[0].node_id == "KC-DEC-EQ"  # the closest of PLACE and EQ
    assert CHAPTER.node("KC-DEC-EQ").description in hint[0].text and "Gợi ý từ bài cũ" in hint[0].text
    if wrong.awaiting == Awaiting.ANSWER and wrong.item_id == item_id and wrong.item_phase == Phase.AWAITING:
        again = loop.on_student("456", T0 + timedelta(hours=1, seconds=30), 5)
        assert not [m for m in again.messages if m.ref == "RECALL_HINT"]


def test_the_first_node_has_no_earlier_node_to_bring_back():
    loop, turns = until_item_of("KC-DEC-FRAC", Learner())
    wrong = loop.on_student("123", T0 + timedelta(hours=1), 5)
    assert not [m for m in wrong.messages if m.ref == "RECALL_HINT"]


def test_a_reminder_of_an_earlier_node_survives_the_replay():
    loop, turns = until_item_of("KC-DEC-PLACE", Learner())
    loop.on_student("123", T0 + timedelta(hours=1), 5)
    resumed = TeachingLoop.resume(CHAPTER, "s1", [], list(loop.events))
    now = T0 + timedelta(hours=2)
    original, again = loop.on_student("789", now, 3), resumed.on_student("789", now, 3)
    assert again.messages == original.messages and again.events == original.events
