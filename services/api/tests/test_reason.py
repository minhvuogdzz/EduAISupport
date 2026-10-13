"""WHY-1 (DI-55): the child's "vì sao" judged by the rubric; a vague one is asked once more."""

import pytest
from cavat.core.events import EventType
from cavat.core.pedagogy import Move
from cavat.modules.assessment.reason import ONE_CUE, TWO_CUES, VAGUE, judge_reason
from test_item_loop import PKG, moves, of_type, resolved, talk, tutor

GP09 = PKG.item("GP-09")


@pytest.mark.parametrize(
    "text",
    ["Vì con làm theo quy tắc cô dạy", "vì con nghĩ vậy", "tại vì đúng mà", "con nhận ra là vậy ạ"],
)
def test_a_reply_that_says_nothing_of_the_item_is_vague(text):
    judged = judge_reason(GP09, text, PKG)
    assert judged.vague and judged.quality == VAGUE


def test_numbers_terms_and_the_solution_make_an_explanation():
    assert judge_reason(GP09, "vì bạn An so sánh 25 với 3 như số tự nhiên", PKG).quality == TWO_CUES
    assert judge_reason(GP09, "vi phan thap phan phai so sanh tung hang", PKG).quality >= ONE_CUE
    assert judge_reason(GP09, "vì 25 với 3", PKG).cues == ("NUMBER",)


def test_a_one_word_term_counts_only_with_its_diacritics():
    assert judge_reason(GP09, "vì nhân lên", PKG).cues == ("TERM",)
    assert judge_reason(GP09, "vì con nhận ra", PKG).vague  # "nhận" is not "nhân"


def test_a_vague_why_is_asked_once_more_then_the_item_ends():
    t = tutor("GP-09")
    turns = talk(t, "sai", "vì con làm theo quy tắc cô dạy", "vì con thấy thế")
    assert moves(turns) == [Move.PRESENT, Move.VERIFY, Move.VERIFY, Move.CONFIRM_ADVANCE]
    assert "muốn nghe rõ hơn" in turns[2].text
    decisions = of_type(t.events, EventType.POLICY_DECISION)
    assert decisions[2]["reason_codes"] == ["VAGUE", "ASK_AGAIN"]
    said = of_type(t.events, EventType.EXPLANATION_SUBMITTED)
    assert [(e["label_source"], e["reasoning_quality"]) for e in said] == [("RUBRIC_RULE", VAGUE)] * 2
    assert resolved(t)["resolution"] == "INDEPENDENT"


def test_a_vague_why_then_a_real_one_is_recorded_as_a_real_one():
    t = tutor("GP-09")
    talk(t, "sai", "vì con nghĩ vậy", "vì bạn An so sánh 25 với 3 như số tự nhiên")
    said = of_type(t.events, EventType.EXPLANATION_SUBMITTED)
    assert [e["reasoning_quality"] for e in said] == [VAGUE, TWO_CUES]
    resolved(t)


def test_a_vague_why_is_no_evidence_and_a_real_one_is():
    from cavat.core.events import ExplanationSubmitted
    from cavat.modules.assessment.projector import project_chapter
    from test_node_policy import CHAPTER, Ev, resolved

    item_id = CHAPTER.node("KC-DEC-FRAC").practice[0]

    def why(quality):
        said = ExplanationSubmitted(
            item_id=item_id,
            text="...",
            reasoning_quality=quality,
            label_source="RUBRIC_RULE",
            label_confidence=1,
        )
        return Ev(EventType.EXPLANATION_SUBMITTED, said.model_dump(mode="json"))

    base = [resolved(item_id)]
    r = lambda events: project_chapter(events, CHAPTER).nodes["KC-DEC-FRAC"]  # noqa: E731
    assert r([*base, why(VAGUE)]) == r(base)  # neither credit nor penalty
    assert r([*base, why(TWO_CUES)]) != r(base)
