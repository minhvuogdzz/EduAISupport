"""ENG-5i (ADR-072, DI-177–187): what the third live run of Vuong showed (main 79404e4, 16/11/2026, session
01a1e237-f98e…, in memory). One test or a few per fault, on the words the child and the tutor really said.
Offline: the template renderer, scripted model outputs, no network.

1. the tutor's turns in the teaching loop said by templates although a model could speak: DI-180
2. "We around the bay took a boat trip." graded CORRECT; "bot" not named; "We ate seafod." walked through
   "eat → ate": DI-177, DI-178, DI-179
3. "con nhớ chi tiết cụm bought và souvenirs" (the child said "keychain and a hat"); "Bạn đã…": DI-181, DI-182
4. the generic hint "Did you swim? – Yes, I did." on "We took a boat trip around the bay."; the whole list of
   phrases pasted as a hint: DI-187, DI-183
5. after a feeling, a question of Mathematics: "Mình quay lại câu này nhé: <the reply to the feeling>": DI-183
6. "Con hỏi Did you swim? thì bạn trả lời…" read as a question: DI-183
7. the parent's report: a passed node's mistakes, the direction of the example: DI-186
8. a session opened when every node is passed (0 minutes), ``/health`` revision: DI-185, DI-184
"""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime

import pytest
from cavat.core.pedagogy import ActivityType, HintTarget, Move, Outcome
from cavat.modules.ai_gateway.base import ChatResult, Usage
from cavat.modules.ai_gateway.router import ChatOutcome
from cavat.modules.assessment.answer_check import check_answer
from cavat.modules.reports import english as report
from cavat.modules.session import chapter_service
from cavat.modules.teaching.loop import Awaiting, TeachingLoop
from cavat.modules.tutor.contracts import ItemState, PolicyDecision, RenderContext
from cavat.modules.tutor.english import LEAD_TASKS_EN, PROMPT_VERSION_EN
from cavat.modules.tutor.english_session import (
    ENGLISH_SESSION_VERSION,
    EnglishRenderer,
    english_tools,
    knowledge_tools,
    loop_options,
)
from cavat.modules.tutor.english_validator import validator_for
from cavat.modules.tutor.renderer import TemplateRenderer, fitting_generic_hints, select_hint

UNIT = "eng-g5-u11-family-time"
NOW = datetime(2026, 11, 16, 9, tzinfo=UTC)
BOAT = "We took a boat trip around the bay."


def unit():
    return chapter_service.chapters("english")[UNIT]


MATH = chapter_service.chapters()[chapter_service.DEFAULT_CHAPTER_ID]


def check(item_id: str, text: str):
    ch = unit()
    return check_answer(ch.item(item_id), text, ch.lesson_of(item_id))


def ctx(item_id: str, move: Move, *, student="", graded=None, level=None, reasons=(), attempt=1):
    ch = unit()
    return RenderContext(
        decision=PolicyDecision(move=move, level=level, target=HintTarget.TASK, reason_codes=tuple(reasons)),
        item=ch.item(item_id),
        package=ch.lesson_of(item_id),
        state=ItemState(item_id=item_id, activity=ActivityType.GUIDED_PRACTICE, attempt_no=attempt),
        student_text=student,
        check=graded,
        solved=graded is not None and graded.outcome == Outcome.CORRECT,
    )


class ScriptedRouter:
    """Answers each TUTOR_REASONING request with the next scripted message."""

    def __init__(self, messages):
        self.messages, self.requests = list(messages), []

    def chat(self, model_class, request, *, calls_used):
        self.requests.append(request)
        text = self.messages.pop(0) if self.messages else ""
        data = {"message": text, "safety_flag": False, "policy_feedback": ""}
        result = ChatResult(
            model="m", text=json.dumps(data, ensure_ascii=False), data=data, usage=Usage(1, 1, 2)
        )
        return ChatOutcome(result=result if text else None, fallback_reason=None, calls_made=1)


def brain(messages, name="Vuong") -> tuple[EnglishRenderer, ScriptedRouter]:
    router = ScriptedRouter(messages)
    tools = knowledge_tools(english_tools(unit()), True)
    renderer = EnglishRenderer(
        router, TemplateRenderer(), validator_for("english", lexicon=tools.lexicon), tools, student_name=name
    )
    return renderer, router


def rejected(renderer: EnglishRenderer) -> set[str]:
    return {code for group in renderer.last_trace.rejected for code in group}


def english_loop(**kw) -> TeachingLoop:
    return TeachingLoop(unit(), "s-eng5i", [], **loop_options(unit()), **kw)


def first_reply(loop: TeachingLoop) -> str:
    ch = unit()
    if loop.awaiting == Awaiting.THEORY_REPLY:
        variant = next(t for t in ch.node(loop._node).theory if t.id == loop._ref)
        return variant.accept[0] if variant.accept else "Con hiểu rồi ạ."
    if loop.awaiting == Awaiting.RETELL:
        return ". ".join(p[0] for p in ch.node(loop._node).explain.key_ideas)
    item = ch.item(loop.tutor.item.id)
    accept = getattr(item.answer, "accept", None)
    return accept[0] if accept else "A"


def until(loop: TeachingLoop, done, steps: int = 80) -> None:
    for _ in range(steps):
        if done(loop):
            return
        loop.on_student(first_reply(loop), NOW)
    pytest.fail("the state wanted was not reached")


def texts(turn) -> str:
    return " ".join(m.text for m in turn.messages)


THEORY_WAIT = lambda lp: lp.awaiting == Awaiting.THEORY_REPLY  # noqa: E731
RETELL_WAIT = lambda lp: lp.awaiting == Awaiting.RETELL  # noqa: E731


# ------------------------------------------------------------- 2. grading (DI-177, DI-178, DI-179)


def test_a_sentence_in_a_wrong_word_order_is_not_correct():
    graded = check("U11-VO-CP-01", "We around the bay took a boat trip.")
    assert graded.outcome == Outcome.WRONG
    assert graded.detail["en_code"] == "EN_STRUCTURE" and graded.detail["scrambled"] is True
    assert check("U11-VO-CP-01", BOAT).outcome == Outcome.CORRECT


def test_a_place_said_first_is_still_english():
    assert check("U11-VO-CP-01", "Around the bay, we took a boat trip.").outcome == Outcome.CORRECT


def test_bot_for_boat_is_a_spelling_slip_named_by_its_word():
    graded = check("U11-VO-CP-01", "We took a bot trip around the bay.")
    assert graded.outcome == Outcome.WRONG
    assert graded.detail["en_code"] == "EN_SLIP" and graded.detail["slips"] == ["bot"]


def test_another_word_is_not_a_slip():
    graded = check("U11-VO-CP-01", "We look a boat trip around the bay.")  # a consonant changed: "look"
    assert graded.detail.get("en_code") != "EN_SLIP"


def test_seafod_is_named_in_the_walk_through_not_eat_to_ate():
    graded = check("U11-VO-PR-02", "We ate seafod.")
    assert graded.detail["slips"] == ["seafod"]
    said = TemplateRenderer().render(
        ctx("U11-VO-PR-02", Move.WORKED_GUIDANCE, student="We ate seafod.", graded=graded)
    )
    assert "seafod" in said.text and "đổi thành ate" not in said.text, said.text


def test_the_model_walking_through_eat_to_ate_on_a_slip_is_refused():
    live = (
        "Tôm, cua, cá là hải sản. Ăn hải sản là eat seafood, chuyện đã qua thì eat đổi thành ate. "
        "Con nói tiếp nhé?"
    )
    good = (
        "Câu của con gần đúng rồi, chỉ có chữ seafod viết chưa đúng chính tả thôi. Con viết lại cả câu nhé?"
    )
    renderer, _ = brain([live, good])
    graded = check("U11-VO-PR-02", "We ate seafod.")
    message = renderer.render(
        ctx("U11-VO-PR-02", Move.WORKED_GUIDANCE, student="We ate seafod.", graded=graded)
    )
    assert message.source == "LLM" and "seafod" in message.text
    assert "MISSES_SLIP" in rejected(renderer)


def test_a_scrambled_sentence_is_told_its_order_by_the_model_or_the_template():
    graded = check("U11-VO-CP-01", "We around the bay took a boat trip.")
    praise = "Đúng rồi, con nói rất hay! Con thử nói lại câu đó nhé?"
    renderer, _ = brain([praise] * 3)
    message = renderer.render(
        ctx("U11-VO-CP-01", Move.HINT, student="We around the bay took a boat trip.", graded=graded, level=1)
    )
    assert message.source == "TEMPLATE" and ("trật tự" in message.text or "thứ tự" in message.text)
    assert "MISSES_WORD_ORDER" in rejected(renderer)


# ------------------------------------------------- 3. the child's own words, "con" (DI-181, DI-182)


def test_praise_of_a_word_the_child_did_not_say_is_refused():
    live = "Thật tuyệt khi con nhớ chi tiết cụm bought và souvenirs trong câu. Mình sang câu tiếp theo nhé."
    good = "Con kể được cả keychain và hat, nhớ chi tiết lắm. Mình sang câu tiếp theo nhé."
    renderer, _ = brain([live, good])
    said = "I bought a keychain and a hat in Da Lat."
    message = renderer.render(
        ctx("U11-VO-TR-03", Move.CONFIRM_ADVANCE, student=said, graded=check("U11-VO-TR-03", said))
    )
    assert message.text == good
    assert "INVENTED_WORD" in rejected(renderer)


def test_remembering_a_sentence_is_an_instruction_not_a_claim():
    renderer, _ = brain([])
    ok = renderer._child_words("Con nhớ câu: [[en: We went to the zoo.]]", "a")
    assert "INVENTED_WORD" not in ok


@pytest.mark.parametrize(
    ("text", "refused"),
    [
        ("Bạn đã nói đúng rồi. Mình sang câu tiếp theo nhé.", True),
        ("Con giỏi lắm! Bạn nghĩ sao về câu này?", True),
        ("Con sửa giúp bạn Nam nhé?", False),
        ("Hai bạn nhỏ đã đi biển. Con nói lại nhé?", False),
    ],
)
def test_the_child_is_con_never_ban(text, refused):
    renderer, _ = brain([])
    assert ("ADDRESSES_BAN" in renderer._child_words(text, "")) is refused


# ------------------------------------------------- 4. hints on the item, not the list (DI-187, DI-183)


def test_a_generic_hint_of_another_pattern_never_reaches_the_boat_trip():
    ch = unit()
    item, pkg = ch.item("U11-VO-CP-01"), ch.lesson_of("U11-VO-CP-01")
    for hint in fitting_generic_hints(item, pkg):
        assert "Did you" not in hint.text and "swam" not in hint.text, hint.text
    for level in range(1, 8):
        found = select_hint(item, pkg, HintTarget.STRATEGY, level)
        if found is not None:
            assert "Did you swim" not in found[0].text


def test_mathematics_generic_hints_are_unchanged():
    for lesson in MATH.lessons.values():
        for item in lesson.items:
            kind = item.answer.type
            expected = [h for h in lesson.generic_hints if not h.answer_types or kind in h.answer_types]
            assert fitting_generic_hints(item, lesson) == expected


def test_the_hint_of_an_earlier_lesson_names_only_what_bears_on_the_item():
    loop = english_loop()
    node = unit().node("ENG5-U11-VOCAB")
    idea = loop._en_idea(node, BOAT, strict=True)
    assert "boat" in idea and "swim; take photos" not in idea, idea
    assert loop._en_idea(node, "Did you go to the zoo?", strict=True) == ""


# ------------------------------------------------------------- 5. back to the item's question (DI-183)


def test_after_a_feeling_a_math_question_asks_the_item_again_not_the_reply_to_the_feeling():
    loop = english_loop()
    loop.start(NOW)
    until(loop, lambda lp: lp.awaiting == Awaiting.ANSWER)
    loop.on_student("hôm nay con buồn", NOW)
    feeling = loop.tutor.last_tutor
    said = texts(loop.on_student("diện tích hình thang tính sao cô", NOW))
    assert feeling.split("?")[0] not in said, said
    question = loop.tutor._resume_question()
    assert question in said, said
    assert "hình thang" not in said


# ------------------------------------------------------------- 6. a quote with "?" is no question (DI-183)


class QuestionSpeaker:
    """A grounded speaker without a model that reads any "?" as a question (the live rule's first test)."""

    router = None
    allow_knowledge = True
    knowledge_active = True
    web = None

    def is_question(self, text):
        return "?" in text

    def judge_meaning(self, *_, **__):
        return (), ()


def test_a_retell_quoting_did_you_swim_is_not_parked_as_a_question():
    loop = english_loop()
    loop.start(NOW)
    until(loop, RETELL_WAIT)
    loop.speaker = QuestionSpeaker()
    said = texts(loop.on_student("Con hỏi Did you swim? thì bạn trả lời Yes, I did.", NOW))
    assert "chưa tìm được câu trả lời chắc chắn" not in said, said
    assert loop._en_question("Did you swim là gì hả cô?")  # a real question about the sentence still is one


# ------------------------------------------------------------- 1. the model first (DI-180)


def test_a_right_theory_reply_is_praised_in_the_models_words_then_the_approved_reply():
    loop = english_loop()
    loop.start(NOW)
    until(loop, THEORY_WAIT)
    node = unit().node(loop._node)
    variant = next(t for t in node.theory if t.id == loop._ref)
    lead = "Con nhớ đúng lắm, cô vui ghê."
    router = ScriptedRouter([lead])
    tools = knowledge_tools(english_tools(unit()), True)
    loop.item_renderer = EnglishRenderer(
        router,
        TemplateRenderer(),
        validator_for("english", lexicon=tools.lexicon),
        tools,
        student_name="Vuong",
    )
    turn = loop.on_student(first_reply(loop), NOW)
    feedback = next(m for m in turn.messages if m.kind == "FEEDBACK")
    assert feedback.source == "LLM", feedback
    assert feedback.text.startswith(lead)
    if variant.reply:
        assert variant.reply in feedback.text  # the approved explanation, word for word
    assert len(router.requests) == 1


def test_a_lead_that_asks_a_question_is_refused_and_the_approved_lead_is_said():
    loop = english_loop()
    loop.start(NOW)
    until(loop, THEORY_WAIT)
    router = ScriptedRouter(["Con giỏi quá, con thấy sao?"] * 3)
    tools = knowledge_tools(english_tools(unit()), True)
    loop.item_renderer = EnglishRenderer(
        router, TemplateRenderer(), validator_for("english", lexicon=tools.lexicon), tools
    )
    turn = loop.on_student(first_reply(loop), NOW)
    feedback = next(m for m in turn.messages if m.kind == "FEEDBACK")
    assert feedback.source == "TEMPLATE"
    assert any("ASKS_IN_LEAD" in group for group in feedback.rejected)


def test_a_math_question_gets_the_models_words_without_the_math_then_the_item():
    loop = english_loop()
    loop.start(NOW)
    until(loop, lambda lp: lp.awaiting == Awaiting.ANSWER)
    router = ScriptedRouter(
        ["Cô biết con đang nghĩ tới bài Toán, mình để lát nữa nhé. Giờ mình quay lại tiếng Anh."]
    )
    tools = knowledge_tools(english_tools(unit()), True)
    loop.item_renderer = EnglishRenderer(
        router, TemplateRenderer(), validator_for("english", lexicon=tools.lexicon), tools
    )
    turn = loop.on_student("cô ơi diện tích hình thang tính sao ạ?", NOW)
    message = turn.messages[0]
    assert message.source == "LLM" and "bài Toán" in message.text
    assert loop.tutor._resume_question() in message.text
    sent = router.requests[0].messages[1].content
    assert (
        "hình thang" not in sent and "diện tích" not in sent
    )  # DI-139: the question never reaches the model


def test_the_lead_tasks_never_ask_and_the_versions_moved():
    for key, task in LEAD_TASKS_EN.items():
        assert "?" not in task, key
    assert PROMPT_VERSION_EN == "tutor-prompt-en.v5"
    assert ENGLISH_SESSION_VERSION == "english-session/1.4.0"


def test_a_mathematics_loop_has_no_english_lead():
    loop = TeachingLoop(MATH, "s-math", [], **chapter_service._loop_options(MATH))
    assert loop._english is False
    spoken = loop._bridged("theory_right", "reply", "Lời giải.", "con nghĩ là 0,5", asked="?", judged="đúng")
    assert spoken.source == "TEMPLATE" and spoken.text.endswith("Lời giải.")


# ------------------------------------------------------------- 7. the parent's report (DI-186)


def test_an_example_says_what_the_child_said_then_the_right_word():
    assert report.shown("eat → ate") == "con nói “eat”, đúng là “ate”"
    assert report.shown("thiếu “around the bay”") == "thiếu “around the bay”"


# ------------------------------------------------------------- 8. no 0-minute session, the running commit


def test_a_new_student_has_lessons_left():
    ch = unit()
    session = chapter_service.new_session(ch, "school", "student-x", "X")
    assert chapter_service.nothing_left(ch, session, NOW, []) is False


def test_health_says_the_commit_this_code_runs(tmp_path, monkeypatch):
    from cavat import revision

    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=revision.SOURCE, capture_output=True, text=True)
    revision.revision.cache_clear()
    monkeypatch.setenv("CAVAT_REVISION", "35d15a687acf")
    if head.returncode == 0:
        assert revision.revision() == head.stdout.strip()  # the stale .env value does not win
    revision.revision.cache_clear()
    assert revision.revision(tmp_path) == "35d15a687acf"  # no git (the Docker image): the build's value
    revision.revision.cache_clear()


# ------------------------------------------------------------- 8b. the API: no session stored (DI-185)


@pytest.fixture
async def api_client(monkeypatch):
    from cavat.core.memory_db import InMemoryDatabase
    from cavat.db import ensure_indexes
    from cavat.main import app
    from cavat.modules.session import api as session_api
    from cavat.modules.session.api import get_database
    from fastapi.testclient import TestClient

    monkeypatch.setattr(session_api, "tutor_router", lambda: None)
    database = InMemoryDatabase()
    await ensure_indexes(database)
    app.dependency_overrides[get_database] = lambda: database
    yield TestClient(app), database
    app.dependency_overrides.pop(get_database, None)


def test_a_unit_passed_whole_opens_no_zero_minute_session(api_client, monkeypatch):
    client, _ = api_client
    who = {"X-Demo-Student": "vuong-5i"}
    monkeypatch.setattr(chapter_service, "nothing_left", lambda *a, **k: True)
    refused = client.post("/v1/sessions", json={"lesson_id": UNIT}, headers=who)
    assert refused.status_code == 409
    body = refused.json()["error"]
    assert body["details"]["reason"] == "UNIT_COMPLETED" and "học xong" in body["message"]
    assert client.get("/v1/sessions/mine", headers=who).json() == []  # nothing was stored
    monkeypatch.undo()
    monkeypatch.setattr("cavat.modules.session.api.tutor_router", lambda: None)
    assert client.post("/v1/sessions", json={"lesson_id": UNIT}, headers=who).status_code == 201


def test_mathematics_never_asks_whether_anything_is_left(api_client, monkeypatch):
    client, _ = api_client
    asked = []
    monkeypatch.setattr(chapter_service, "nothing_left", lambda *a, **k: asked.append(1) or True)
    made = client.post("/v1/sessions", json={}, headers={"X-Demo-Student": "binh-5i"})
    assert made.status_code == 201 and asked == []
