"""REFORM-6 (plan 3.3 and 4.1): a child who has not understood is kept at the question and taught again; what
a child says is read for its meaning against the teacher's rule, with the model's claims checked.

Offline: a scripted router stands in for the models, the index runs on keywords.
"""

from __future__ import annotations

import pytest
from cavat.core.events import PAYLOAD_MODELS, EventType, RetellJudged
from cavat.core.memory_db import InMemoryDatabase
from cavat.modules.ai_gateway.base import ChatResult, ModelClass, estimate_prompt_tokens
from cavat.modules.ai_gateway.router import ChatOutcome, FallbackReason
from cavat.modules.assessment.retell import judge_retell
from cavat.modules.rag.service import RagService
from cavat.modules.session import chapter_service, service
from cavat.modules.teaching.grounded import GroundedSpeaker
from cavat.modules.teaching.loop import HOLD_REF, Awaiting, TeachingLoop
from cavat.modules.teaching.meaning import quote_in, verified_ideas
from cavat.modules.teaching.state import teaching_state
from cavat.modules.tutor.item_loop import Phase
from test_intent_agent import CH, clock, praised
from test_intent_agent import T0 as START
from test_teaching_loop import correct_text

FRAC = "KC-DEC-FRAC"
NODE = CH.node(FRAC)
VARIANT = NODE.theory[0]
NOT_UNDERSTOOD = ["ko", "hả", "???", "là sao má", "mẫu như nào"]
# in other words than the teacher's phrasings (idea 0 says "mẫu số là 10"), so the keywords miss them
PARAPHRASE = "mẫu của nó là mười, một trăm, một nghìn"
SAME_WORDS = "mẫu số là mười và mẫu số có mấy chữ số 0 thì phần thập phân có bấy nhiêu chữ số"


class Models:
    """Answers by model class: LIGHTWEIGHT reads the meaning, TUTOR_REASONING speaks."""

    def __init__(
        self,
        ideas=None,
        voice="Mình thử nghĩ lại từng bước nhé. Mẫu số là 10, 100 hay 1000 thì gọi là phân số thập phân.",
    ) -> None:
        self.ideas = ideas if ideas is not None else []
        self.voice = voice
        self.requests: list[tuple[ModelClass, object]] = []

    def chat(self, model_class, request, *, calls_used):
        self.requests.append((model_class, request))
        if model_class == ModelClass.LIGHTWEIGHT:
            data = {"ideas": self.ideas}
        elif self.voice is None:
            return ChatOutcome(None, FallbackReason.QUOTA_EXCEEDED, 0)
        else:
            data = {"message": self.voice, "safety_flag": False, "policy_feedback": ""}
        return ChatOutcome(ChatResult("fake", "", data), None, 1)

    def of(self, model_class: ModelClass) -> list:
        return [r for c, r in self.requests if c == model_class]


@pytest.fixture(scope="module")
async def index():
    rag = RagService(service.DEMO_SCHOOL_ID, chapter_service.chapters, embedder=lambda: None)
    return await rag.current(InMemoryDatabase())


def knows(turn) -> str:
    """What a child who knows the lesson answers to whatever the loop waits for."""
    if turn.awaiting == Awaiting.THEORY_REPLY:
        variant = next(t for t in CH.node(turn.node_id).theory if t.ask == turn.prompt)
        return variant.accept[0] if variant.accept else "Con nghĩ là được ạ."
    if turn.awaiting == Awaiting.RETELL:
        return ". ".join(ideas[0] for ideas in CH.node(turn.node_id).explain.key_ideas)
    item = CH.item(turn.item_id)
    if turn.item_phase in (Phase.VERIFYING, Phase.TEACH_BACK):
        return item.explanation
    return correct_text(turn.item_id)


def waiting(wait: Awaiting, **kw):
    """The loop at its first ``wait`` after a child who knows the lesson (so nothing was held before)."""
    loop = TeachingLoop(CH, "s1", **kw)
    turn, n = loop.start(START), 0
    while turn.awaiting != wait:
        assert turn.awaiting != Awaiting.NOTHING
        n += 1
        turn = loop.on_student(knows(turn), clock(n), 5)
    return loop, turn, n


def decisions(loop) -> list:
    return [e for e in loop.events if e.event_type == EventType.NODE_DECISION]


def judged(loop) -> list:
    return [e for e in loop.events if e.event_type == EventType.RETELL_JUDGED]


def said(turn) -> str:
    return " ".join(m.text for m in turn.messages)


# --------------------------------------------------------------------------- 3.3: theory


@pytest.mark.parametrize("text", NOT_UNDERSTOOD)
def test_theory_does_not_advance_the_first_time_and_asks_the_small_question_again(text):
    loop, turn, n = waiting(Awaiting.THEORY_REPLY)
    variant = next(t for t in NODE.theory if t.ask == turn.prompt)
    before = len(decisions(loop))
    held = loop.on_student(text, clock(n + 1), 5)
    assert len(decisions(loop)) == before  # no step taken
    assert held.awaiting == Awaiting.THEORY_REPLY and held.prompt == turn.prompt
    out = said(held)
    assert variant.ask in out and out.count("?") == 1 and not praised(out)
    assert variant.reply not in out  # the answer is not given back before the child tries again
    sent = [e.payload for e in held.events if e.event_type == EventType.TEACH_MESSAGE_SENT]
    assert sent[-1]["ref"] == HOLD_REF


@pytest.mark.parametrize("text", NOT_UNDERSTOOD)
def test_theory_closes_the_second_time_with_the_approved_reply_and_goes_on(text):
    loop, turn, n = waiting(Awaiting.THEORY_REPLY)
    variant = next(t for t in NODE.theory if t.ask == turn.prompt)
    loop.on_student(text, clock(n + 1), 5)
    before = len(decisions(loop))
    closed = loop.on_student("ko", clock(n + 2), 5)
    assert len(decisions(loop)) > before  # on to the next step
    out = said(closed)
    assert variant.reply in out and not praised(out)


def test_theory_a_right_answer_after_the_second_try_is_confirmed():
    loop, turn, n = waiting(Awaiting.THEORY_REPLY)
    variant = next(t for t in NODE.theory if t.ask == turn.prompt)
    loop.on_student("hả", clock(n + 1), 5)
    out = said(loop.on_student(variant.accept[0], clock(n + 2), 5))
    assert "Đúng rồi" in out and variant.reply in out


def test_theory_a_wrong_answer_is_held_once_too():
    loop, turn, n = waiting(Awaiting.THEORY_REPLY)
    before = len(decisions(loop))
    held = loop.on_student("Con nghĩ là 4/10 ạ", clock(n + 1), 5)
    assert len(decisions(loop)) == before and held.awaiting == Awaiting.THEORY_REPLY
    assert not praised(said(held))


def test_theory_a_right_first_answer_is_not_held():
    loop, turn, n = waiting(Awaiting.THEORY_REPLY)
    variant = next(t for t in NODE.theory if t.ask == turn.prompt)
    out = said(loop.on_student(variant.accept[0], clock(n + 1), 5))
    assert HOLD_REF not in [e.payload.get("ref") for e in loop.events if e.event_type == "TEACH_MESSAGE_SENT"]
    assert "Đúng rồi" in out


def test_theory_tiredness_and_demands_keep_their_own_path():
    loop, turn, n = waiting(Awaiting.THEORY_REPLY)
    before = len(decisions(loop))
    loop.on_student("chán quá", clock(n + 1), 5)
    assert len(decisions(loop)) > before  # the feeling is met and the explanation said, as before (DI-41)


def test_theory_a_resumed_session_knows_it_held_once():
    loop, turn, n = waiting(Awaiting.THEORY_REPLY)
    loop.on_student("hả", clock(n + 1), 5)
    resumed = TeachingLoop.resume(CH, "s1", [], list(loop.events))
    a, b = loop.on_student("ko", clock(n + 2), 5), resumed.on_student("ko", clock(n + 2), 5)
    assert a.messages == b.messages and a.events == b.events


def test_theory_without_a_model_teaches_again_from_the_approved_material():
    loop, turn, n = waiting(Awaiting.THEORY_REPLY)
    out = said(loop.on_student("hả", clock(n + 1), 5))
    material = [NODE.method.rule, *(t.text for t in NODE.theory if t.ask != turn.prompt)]
    assert any(m.strip() in out for m in material)


# --------------------------------------------------------------------------- 3.3: retell


@pytest.mark.parametrize("text", NOT_UNDERSTOOD)
def test_retell_does_not_advance_the_first_time_and_asks_about_one_part(text):
    loop, turn, n = waiting(Awaiting.RETELL)
    before, seen = len(decisions(loop)), len(judged(loop))
    held = loop.on_student(text, clock(n + 1), 5)
    assert len(decisions(loop)) == before and len(judged(loop)) == seen
    assert held.awaiting == Awaiting.RETELL and held.prompt == turn.prompt
    out = said(held)
    assert out.count("?") == 1 and not praised(out)
    first_rule_part = NODE.method.rule.split(".")[0]
    assert (
        first_rule_part[:30] in out or NODE.description[:30] in out
    )  # a part of the rule, not the sample twice
    assert out != said(loop.on_student("ki", clock(n + 2), 5))  # (a second held message is different)


def test_retell_closes_the_second_time_with_the_main_idea_and_is_judged():
    loop, turn, n = waiting(Awaiting.RETELL)
    loop.on_student("???", clock(n + 1), 5)
    closed = loop.on_student("là sao má", clock(n + 2), 5)
    assert len(judged(loop)) == 1 and judged(loop)[0].payload["score"] == 0.0
    assert NODE.method.rule in said(closed) and not praised(said(closed))


def test_retell_what_was_said_in_the_two_tries_is_read_together():
    loop, turn, n = waiting(Awaiting.RETELL)
    loop.on_student("mẫu số là 10", clock(n + 1), 5)  # one idea of three: not enough, the child is helped
    closed = loop.on_student("bao nhiêu chữ số 0 thì có bấy nhiêu chữ số", clock(n + 2), 5)
    event = judged(loop)[0].payload
    assert event["ideas_found"] == [0, 1] and event["score"] >= 0.5
    assert "đúng ý" in said(closed)


def test_retell_a_full_retell_is_never_held():
    loop, turn, n = waiting(Awaiting.RETELL)
    loop.on_student(SAME_WORDS + ". thêm chữ số 0", clock(n + 1), 5)
    assert len(judged(loop)) == 1
    assert HOLD_REF not in [e.payload.get("ref") for e in loop.events if e.event_type == "TEACH_MESSAGE_SENT"]


# --------------------------------------------------------------------------- 4.1: the second tier


def live(models, index, calls_used=0, wait=Awaiting.RETELL):
    speaker = GroundedSpeaker(index, models, calls_used=calls_used)
    loop, turn, n = waiting(wait)
    loop.go_live(speaker=speaker)
    return loop, speaker, n


async def test_the_second_tier_is_not_called_when_the_keywords_are_enough(index):
    models = Models(ideas=[])
    loop, speaker, n = live(models, index)
    loop.on_student(SAME_WORDS + ". thêm chữ số 0", clock(n + 1), 5)
    assert models.of(ModelClass.LIGHTWEIGHT) == [] and speaker.calls_made == 0


@pytest.mark.parametrize("text", ["ko", "???", "hả", "ki", "là sao má"])
async def test_the_second_tier_is_not_called_for_a_refusal_or_nonsense(index, text):
    models = Models(ideas=[{"idea": 0, "quote": "mẫu số"}])
    loop, speaker, n = live(models, index)
    loop.on_student(text, clock(n + 1), 5)
    assert models.of(ModelClass.LIGHTWEIGHT) == []


async def test_a_claim_with_a_real_quote_counts_and_is_recorded(index):
    models = Models(
        ideas=[{"idea": 0, "quote": "mẫu của nó là mười"}, {"idea": 1, "quote": "đếm chữ số không"}]
    )
    loop, speaker, n = live(models, index)
    text = PARAPHRASE + " và thêm chữ số 0"
    out = loop.on_student(text, clock(n + 1), 5)
    event = judged(loop)[0].payload
    assert event["ideas_found"] == [
        0,
        2,
    ]  # idea 2 by keywords, idea 0 by quote; idea 1 had no quote in the text
    assert event["model_ideas"] == [0] and event["quotes"] == ["mẫu của nó là mười"]
    assert event["label_source"] == "LLM" and event["score"] == pytest.approx(2 / 3)
    assert len(models.of(ModelClass.LIGHTWEIGHT)) == 1 and speaker.calls_made == 1
    assert "đúng ý" in said(out)


async def test_a_claim_without_a_quote_in_the_childs_words_is_dropped(index):
    models = Models(ideas=[{"idea": 0, "quote": "mẫu số là mười"}, {"idea": 1, "quote": ""}])
    loop, speaker, n = live(models, index)
    held = loop.on_student(PARAPHRASE, clock(n + 1), 5)  # "mẫu số là mười" is not in what the child said
    assert judged(loop) == [] and held.awaiting == Awaiting.RETELL  # nothing found: held, not advanced


async def test_the_model_never_lowers_what_the_keywords_found(index):
    models = Models(ideas=[])
    loop, speaker, n = live(models, index)
    loop.on_student("mẫu số là 10 nhưng con quên rồi", clock(n + 1), 5)
    loop.on_student("không nhớ nữa", clock(n + 2), 5)
    event = judged(loop)[0].payload
    assert event["ideas_found"] == [0] and event["label_source"] == "RUBRIC_RULE"
    assert event["model_ideas"] == [] and event["quotes"] == []


async def test_one_model_call_a_message_at_most(index):
    models = Models(ideas=[])
    loop, speaker, n = live(models, index)
    loop.on_student(PARAPHRASE, clock(n + 1), 5)
    assert len(models.of(ModelClass.LIGHTWEIGHT)) == 1
    loop.on_student(PARAPHRASE, clock(n + 2), 5)
    assert len(models.of(ModelClass.LIGHTWEIGHT)) == 2  # one more for the second message, never two


async def test_the_second_tier_stops_when_the_session_has_spent_three_quarters_of_its_calls(index):
    models = Models(ideas=[{"idea": 0, "quote": "mẫu của nó là mười"}])
    loop, speaker, n = live(models, index, calls_used=30)  # the cap is 40 (DI-71)
    loop.on_student(PARAPHRASE, clock(n + 1), 5)
    assert models.of(ModelClass.LIGHTWEIGHT) == []


async def test_a_model_that_is_down_leaves_the_keyword_judgement(index):
    models = Models(ideas=[])
    models.chat = lambda model_class, request, *, calls_used: ChatOutcome(
        None, FallbackReason.QUOTA_EXCEEDED, 0
    )
    loop, speaker, n = live(models, index)
    held = loop.on_student(PARAPHRASE, clock(n + 1), 5)
    assert held.awaiting == Awaiting.RETELL and judged(loop) == []


async def test_the_request_is_small_masked_and_strict(index):
    models = Models(ideas=[])
    loop, speaker, n = live(models, index)
    loop.on_student(PARAPHRASE + " gọi 0912345678", clock(n + 1), 5)
    request = models.of(ModelClass.LIGHTWEIGHT)[0]
    body = " ".join(m.content for m in request.messages)
    assert "0912345678" not in body and NODE.method.rule in body
    assert estimate_prompt_tokens(request) < 3000
    assert request.json_schema is not None and request.json_schema["additionalProperties"] is False


async def test_a_theory_answer_in_other_words_is_confirmed_by_a_quote(index):
    loop, turn, n = waiting(Awaiting.THEORY_REPLY)
    variant = next(t for t in NODE.theory if t.ask == turn.prompt)
    models = Models(ideas=[{"idea": 0, "quote": "bốn phần một trăm"}])
    loop.go_live(speaker=GroundedSpeaker(index, models))
    before = len(decisions(loop))
    out = said(loop.on_student("bốn phần một trăm ạ", clock(n + 1), 5))
    assert len(decisions(loop)) > before and "Đúng rồi" in out and variant.reply in out
    assert HOLD_REF not in [e.payload.get("ref") for e in loop.events if e.event_type == "TEACH_MESSAGE_SENT"]


async def test_a_theory_answer_the_quote_does_not_support_is_held(index):
    loop, turn, n = waiting(Awaiting.THEORY_REPLY)
    models = Models(ideas=[{"idea": 0, "quote": "bốn phần một trăm"}])
    loop.go_live(speaker=GroundedSpeaker(index, models))
    before = len(decisions(loop))
    held = loop.on_student("năm phần mười ạ", clock(n + 1), 5)
    assert len(decisions(loop)) == before and held.awaiting == Awaiting.THEORY_REPLY


async def test_the_teaching_again_is_in_the_models_words_when_they_pass_the_check(index):
    models = Models()
    loop, speaker, n = live(models, index, wait=Awaiting.THEORY_REPLY)
    out = said(loop.on_student("hả", clock(n + 1), 5))
    assert models.voice in out and len(models.of(ModelClass.TUTOR_REASONING)) == 1
    assert out.count("?") == 1


async def test_the_teaching_again_does_not_give_the_answer_back(index):
    models = Models(voice="Tô 4 ô trong 100 ô thì phần tô màu là 4/100 hình vuông.")
    loop, speaker, n = live(models, index, wait=Awaiting.THEORY_REPLY)
    out = said(loop.on_student("hả", clock(n + 1), 5))
    assert "4/100 hình vuông" not in out  # the template is said instead


# --------------------------------------------------------------------------- 4.1: events and replay


def test_an_old_retell_event_still_reads():
    old = {"node_id": FRAC, "text": "mẫu số 10", "ideas_found": [0], "ideas_total": 3, "score": 1 / 3}
    event = PAYLOAD_MODELS[EventType.RETELL_JUDGED].model_validate(old)
    assert event.model_ideas == [] and event.quotes == [] and event.label_source == "RUBRIC_RULE"


def test_the_rule_judgement_records_how_it_was_made():
    event = judge_retell(FRAC, "mẫu số là 10", NODE.explain)
    assert isinstance(event, RetellJudged) and event.label_source == "RUBRIC_RULE" and event.model_ideas == []


async def test_a_replay_reads_the_event_and_calls_no_model(index):
    models = Models(
        ideas=[{"idea": 0, "quote": "mẫu của nó là mười"}, {"idea": 1, "quote": "đếm chữ số không"}]
    )
    loop, speaker, n = live(models, index)
    loop.on_student(PARAPHRASE + " và đếm chữ số không", clock(n + 1), 5)
    first = teaching_state(loop.events)
    calls = len(models.requests)
    resumed = TeachingLoop.resume(CH, "s1", [], list(loop.events))  # templates only, no speaker
    assert teaching_state(resumed.events).__dict__.keys() == first.__dict__.keys()
    assert resumed.awaiting == loop.awaiting and len(models.requests) == calls


# --------------------------------------------------------------------------- the checking of a claim


@pytest.mark.parametrize(
    ("quote", "said", "ok"),
    [
        ("mẫu của nó là mười", "con nghĩ mẫu của nó là mười, một trăm", True),
        ("MẪU CỦA NÓ LÀ MƯỜI", "mau cua no la muoi, mot tram", True),  # case and diacritics do not matter
        ("mẫu số là mười", "mẫu của nó là mười", False),  # not the child's words
        ("", "mẫu của nó là mười", False),
        ("mẫu", "mẫu của nó là mười", False),  # too short to show anything
        ("ko", "ko biết", False),
    ],
)
def test_a_quote_must_be_in_the_childs_words(quote, said, ok):
    assert quote_in(quote, said) is ok


def test_ideas_need_a_real_index_a_quote_and_are_new():
    said = "mẫu của nó là mười, thêm chữ số không"
    data = {
        "ideas": [
            {"idea": 0, "quote": "mẫu của nó là mười"},
            {"idea": 0, "quote": "mẫu của nó là mười"},  # twice
            {"idea": 2, "quote": "thêm chữ số không"},  # already found by the keywords
            {"idea": 7, "quote": "thêm chữ số không"},  # no such idea
            {"idea": "1", "quote": "thêm chữ số không"},  # not an integer
            {"idea": 1, "quote": "nói bừa"},  # not in the words
        ]
    }
    assert verified_ideas(data, said, found=[2], total=3) == ([0], ["mẫu của nó là mười"])
    assert verified_ideas(None, said, found=[], total=3) == ([], [])
    assert verified_ideas({"ideas": "x"}, said, found=[], total=3) == ([], [])
