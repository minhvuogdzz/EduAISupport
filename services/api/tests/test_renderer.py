"""TemplateRenderer (T03): every PRACTICE item × move renders a message that passes the validator.

Decisions are built by hand, so these tests do not depend on the policy engine (T02).
"""

from pathlib import Path

import pytest
from cavat.core.pedagogy import ActivityType, HintLevel, HintTarget, Move
from cavat.modules.content.lesson_package import Persona, load_lesson_package
from cavat.modules.tutor.contracts import (
    ItemState,
    MessageRenderer,
    PolicyDecision,
    RenderContext,
)
from cavat.modules.tutor.renderer import TemplateRenderer, select_hint
from cavat.modules.tutor.validator import validate_message

LESSON = Path(__file__).resolve().parents[3] / "docs/pedagogy/math-g5/so-sanh-so-thap-phan/lesson.yaml"
PKG = load_lesson_package(LESSON)
PRACTICE = PKG.items_for("PRACTICE")
RENDERER: MessageRenderer = TemplateRenderer()


def ctx_for(item, decision, **kw):
    state = ItemState(item_id=item.id, activity=ActivityType.GUIDED_PRACTICE)
    return RenderContext(decision=decision, item=item, package=PKG, state=state, **kw)


def render(item_id, move, **kw):
    decision_kw = {k: kw.pop(k) for k in ("level", "target", "misconception_id") if k in kw}
    ctx = ctx_for(PKG.item(item_id), PolicyDecision(move=move, **decision_kw), **kw)
    return RENDERER.render(ctx), ctx


def all_decisions():
    out = [PolicyDecision(move=m) for m in Move]
    out += [PolicyDecision(move=Move.HINT, target=t, level=lv) for t in HintTarget for lv in HintLevel if lv]
    out += [PolicyDecision(move=Move.COGNITIVE_CONFLICT, misconception_id=m.id) for m in PKG.misconceptions]
    out += [PolicyDecision(move=Move.WORKED_GUIDANCE, level=HintLevel.H6, target=HintTarget.STEP)]
    out += [PolicyDecision(move=Move.FULL_EXPLANATION, level=HintLevel.H7)]
    return out


@pytest.mark.parametrize("item", PRACTICE, ids=lambda i: i.id)
def test_every_practice_item_and_move_passes_the_validator(item):
    for decision in all_decisions():
        ctx = ctx_for(item, decision)
        msg = RENDERER.render(ctx)
        result = validate_message(msg.text, ctx)
        assert result.ok, f"{item.id} {decision}: {result.issues} in {msg.text!r}"


def test_every_move_has_a_template():
    for move in Move:
        msg, _ = render("GP-01", move)
        assert msg.text.strip(), move


def test_hint_exact_target_and_level():
    msg, _ = render("GP-02", Move.HINT, target=HintTarget.STEP, level=HintLevel.H4)
    assert msg.hint_ref == "GP-02:STEP:H4"
    assert msg.source == "TEMPLATE"
    assert msg.text == next(h.text for h in PKG.item("GP-02").hints if h.level == HintLevel.H4)


def test_hint_falls_back_to_same_target_lower_level():
    msg, _ = render("GP-01b", Move.HINT, target=HintTarget.STEP, level=HintLevel.H5)
    assert (msg.source, msg.hint_ref) == ("TEMPLATE", "GP-01b:STEP:H4")


def test_hint_falls_back_to_generic_hints():
    msg, _ = render("GP-01b", Move.HINT, target=HintTarget.STRATEGY, level=HintLevel.H3)
    assert (msg.source, msg.hint_ref) == ("GENERIC", "GENERIC:STRATEGY:H3")


def test_hint_falls_back_to_fixed_sentence():
    # GP-01 has CONCEPT only at H2 and the generic CONCEPT hint is H2 too, so nothing fits H1.
    msg, ctx = render("GP-01", Move.HINT, target=HintTarget.CONCEPT, level=HintLevel.H1)
    assert (msg.source, msg.hint_ref) == ("FALLBACK", None)
    assert validate_message(msg.text, ctx).ok


def test_template_with_two_questions_is_skipped():
    # GP-09 TASK H1 and the generic TASK H1 each ask two questions (content proposal in the PR).
    msg, _ = render("GP-09", Move.HINT, target=HintTarget.TASK, level=HintLevel.H1)
    assert msg.source == "FALLBACK"
    assert msg.text.count("?") == 1


def test_select_hint_without_target_uses_any_target():
    hint, source, ref = select_hint(PKG.item("GP-01"), PKG, None, HintLevel.H3)
    assert (hint.level, source, ref) == (HintLevel.H3, "TEMPLATE", "GP-01:STRATEGY:H3")


def test_counter_example_fills_left_and_right_for_compare_items():
    msg, _ = render("GP-01", Move.COGNITIVE_CONFLICT, misconception_id="DEC-M01")
    assert "0,25 mét dây" in msg.text and "0,3 mét dây" in msg.text
    assert "{" not in msg.text
    assert msg.hint_ref == "DEC-M01:COUNTER:1"


def test_counter_example_with_placeholders_is_skipped_for_other_items():
    msg, _ = render("GP-06", Move.COGNITIVE_CONFLICT, misconception_id="DEC-M01")
    assert "{" not in msg.text
    assert msg.hint_ref == "DEC-M01:COUNTER:2"


def test_cognitive_conflict_without_misconception_falls_back_to_a_hint():
    msg, _ = render("GP-01", Move.COGNITIVE_CONFLICT, target=HintTarget.STEP, level=HintLevel.H4)
    assert msg.hint_ref == "GP-01:STEP:H4"


def test_worked_guidance_shows_every_step_but_the_last():
    item = PKG.item("GP-02")
    msg, _ = render("GP-02", Move.WORKED_GUIDANCE)
    for step in item.worked_solution[:-1]:
        assert step in msg.text
    assert item.worked_solution[-1] not in msg.text
    assert msg.text.endswith("?")
    assert msg.hint_ref == "GP-02:WORKED:1-2"


def test_full_explanation_is_explanation_plus_teach_back_invitation():
    item = PKG.item("GP-02")
    msg, _ = render("GP-02", Move.FULL_EXPLANATION)
    assert msg.text.startswith(item.explanation)
    assert msg.text.endswith("?")
    assert msg.hint_ref == "GP-02:EXPLANATION"


def test_verify_uses_item_prompt_then_lesson_default():
    msg, _ = render("GP-01", Move.VERIFY)
    assert msg.text == PKG.item("GP-01").verify_prompt
    msg, _ = render("GP-01b", Move.VERIFY)
    assert msg.text == PKG.default_verify_prompt


def test_probe_uses_the_option_probe_when_the_student_chose_it():
    msg, _ = render("GP-08", Move.PROBE, student_text="Bạn Lan ạ")
    assert msg.hint_ref == "GP-08:PROBE:A"
    assert "9,8 và 9,75" in msg.text
    msg, _ = render("GP-08", Move.PROBE, student_text="Hoa")
    assert msg.hint_ref is None


def test_redirect_ends_with_one_question_even_without_rephrase():
    msg, ctx = render("GP-01b", Move.REDIRECT)
    assert PKG.item("GP-01b").stem in msg.text
    assert msg.text.count("?") == 1 and msg.text.endswith("?")
    assert validate_message(msg.text, ctx).ok


def test_persona_is_used_in_fixed_sentences():
    msg, _ = render("GP-01", Move.NUDGE, persona=Persona(tutor_self="thầy", student_address="em"))
    assert msg.text.startswith("Em ")
    assert "thầy" in msg.text and "con" not in msg.text.split()


def test_renderer_is_deterministic():
    for move in Move:
        assert render("GP-07", move)[0] == render("GP-07", move)[0]
