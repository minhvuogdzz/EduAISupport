"""Looking up the trusted source when the teacher's documents do not answer (WEB-1, DI-51). Offline: a fake
source and a fake HTTP client stand in for Vietnamese Wikipedia; tests never reach the network."""

import pytest
from cavat.core.memory_db import InMemoryDatabase
from cavat.modules.rag.service import RagService
from cavat.modules.session import chapter_service, service
from cavat.modules.teaching.grounded import GroundedSpeaker
from cavat.modules.teaching.web import WebPage, WikipediaVi, eligible, web_query
from test_grounded import CHAPTER, EQ, ScriptedRouter

BOILING = WebPage(
    title="Điểm sôi",
    url="https://vi.wikipedia.org/wiki/Điểm_sôi",
    text=(
        "Ở áp suất khí quyển tiêu chuẩn, nước sôi ở 100 độ C. "
        "Điểm sôi là nhiệt độ chất lỏng chuyển thành hơi."
    ),
    host="vi.wikipedia.org",
)


class FakeSource:
    name = "Wikipedia tiếng Việt"

    def __init__(self, page: WebPage | None) -> None:
        self.page, self.queries = page, []

    def lookup(self, query):
        self.queries.append(query)
        return self.page


@pytest.fixture(scope="module")
async def index():
    rag = RagService(service.DEMO_SCHOOL_ID, chapter_service.chapters, embedder=lambda: None)
    return await rag.current(InMemoryDatabase())


@pytest.mark.parametrize(
    ("question", "ok"),
    [
        ("nước sôi ở bao nhiêu độ vậy cô", True),
        ("số nguyên tố là gì", True),
        ("súng bắn thế nào", False),  # a topic left to adults
        ("con gọi cô số 0912345678 nhé", False),  # contact data never leaves the app
        ("vì sao " * 40, False),  # too long
        ("MA TÚY là gì", False),  # capitals are the same word
        ("Ma Tuý là gì ạ", False),
        ("SEX?", False),  # so is a mark stuck to it
        ("sex, là gì!", False),
        ("Bia, rượu là gì?", False),  # and a mark inside a two-word topic
        ("SÚNG BẮN THẾ NÀO???", False),
        ("SỐ NGUYÊN TỐ LÀ GÌ?", True),  # the same cleaning lets a safe question through
        ("Nước sôi ở bao nhiêu độ vậy cô?!", True),
    ],
)
def test_only_a_safe_short_question_may_be_looked_up(question, ok):
    assert eligible(question) is ok


def test_what_is_sent_is_the_concept_asked_about_only():
    assert web_query("cô ơi điểm sôi là gì vậy ạ?") == "điểm sôi"
    assert web_query("số nguyên tố là j") == "số nguyên tố"
    assert web_query("nước sôi ở bao nhiêu độ") == ""  # not a named concept: not looked up
    assert web_query("Bác Hồ là ai") == ""  # people are left to the teacher
    assert web_query("số 25 là gì") == ""


def test_an_article_is_used_only_when_it_is_the_concept():
    from cavat.modules.teaching.web import relevant

    assert relevant(BOILING, "điểm sôi")
    assert relevant(
        WebPage("Khối lập phương", "u", "t", "vi.wikipedia.org", asked="Hình lập phương"), "hình lập phương"
    )
    assert not relevant(WebPage("Hoa Kỳ", "u", "t", "vi.wikipedia.org"), "nước sôi")


def test_the_documents_come_first_and_the_source_is_not_asked(index):
    source = FakeSource(BOILING)
    router = ScriptedRouter("Viết thêm chữ số 0 vào tận cùng bên phải phần thập phân thì giá trị không đổi.")
    turn = GroundedSpeaker(index, router, web=source).answer(
        "sao thêm số 0 vào cuối mà số không đổi", node_id=EQ, pending=None
    )
    assert turn.kind == "ANSWERED" and turn.spoken.source == "LLM" and not source.queries


def test_a_question_the_documents_do_not_answer_is_answered_from_the_article(index):
    source = FakeSource(BOILING)
    router = ScriptedRouter("Nước sôi ở 100 độ C khi ở áp suất khí quyển tiêu chuẩn.")
    turn = GroundedSpeaker(index, router, web=source).answer(
        "điểm sôi là gì vậy cô", node_id=EQ, pending=None
    )
    assert turn.kind == "ANSWERED" and turn.spoken.source == "WEB" and turn.web == BOILING
    assert turn.spoken.text.startswith("Theo Wikipedia tiếng Việt, cô kể con nghe nhé:")
    assert turn.spoken.sources == ("Wikipedia tiếng Việt: Điểm sôi · https://vi.wikipedia.org/wiki/Điểm_sôi",)
    assert source.queries == ["điểm sôi"]
    assert "Điểm sôi" in router.user_text()


def test_an_answer_the_article_does_not_carry_is_not_said(index):
    """Two refused answers: the article's own sentence is said, word for word (as for the documents)."""
    router = ScriptedRouter("Nước sôi ở 90 độ.", "Nước sôi ở 80 độ.")  # numbers the article does not have
    turn = GroundedSpeaker(index, router, web=FakeSource(BOILING)).answer(
        "điểm sôi là gì vậy cô", node_id=EQ, pending=None
    )
    assert turn.kind == "ANSWERED" and len(turn.spoken.rejected) == 2
    assert "90" not in turn.spoken.text and "Điểm sôi là nhiệt độ" in turn.spoken.text


def test_an_article_the_model_finds_no_answer_in_is_kept_for_the_teacher(index):
    turn = GroundedSpeaker(index, ScriptedRouter(""), web=FakeSource(BOILING)).answer(
        "điểm sôi là gì vậy cô", node_id=EQ, pending=None
    )
    assert turn.kind == "PARKED" and turn.web == BOILING


def test_without_a_model_a_sentence_of_the_article_is_said_word_for_word(index):
    turn = GroundedSpeaker(index, None, web=FakeSource(BOILING)).answer(
        "điểm sôi là gì", node_id=EQ, pending=None
    )
    assert turn.kind == "ANSWERED" and "Điểm sôi là nhiệt độ" in turn.spoken.text


def test_unsafe_questions_and_later_periods_are_never_looked_up(index):
    source = FakeSource(BOILING)
    speaker = GroundedSpeaker(index, ScriptedRouter(), web=source, order=CHAPTER.topological_order())
    assert speaker.answer("súng bắn thế nào", node_id=EQ, pending=None).kind == "PARKED"
    first = CHAPTER.topological_order()[0]
    later = speaker.answer("so sánh hai số thập phân như thế nào", node_id=first, pending=None)
    assert later.kind == "LATER" and not source.queries


def test_a_page_from_another_host_is_never_used(index):
    elsewhere = WebPage("Nước", "https://example.com/nuoc", "Nước sôi ở 100 độ C.", "example.com")
    turn = GroundedSpeaker(index, None, web=FakeSource(elsewhere)).answer(
        "điểm sôi là gì", node_id=EQ, pending=None
    )
    assert turn.kind == "PARKED"


class FakeHttp:
    def __init__(self) -> None:
        self.calls = []

    def get(self, url, params):
        self.calls.append(params)

        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "query": {
                        "redirects": [{"from": "Nhiệt độ sôi", "to": "Điểm sôi"}],
                        "pages": [{"title": "Điểm sôi", "extract": "Nước   sôi ở 100 độ C.\nĐiểm sôi là…"}],
                    }
                }

        return Response()


def test_wikipedia_is_asked_for_the_article_by_its_title_once_then_cached(tmp_path):
    http = FakeHttp()
    wiki = WikipediaVi(cache_dir=tmp_path, client=http)
    page = wiki.lookup("nhiệt độ sôi")
    assert page.url == "https://vi.wikipedia.org/wiki/Điểm_sôi" and page.text.startswith(
        "Nước sôi ở 100 độ C."
    )
    assert page.asked == "Nhiệt độ sôi" and http.calls[0]["titles"] == "Nhiệt độ sôi"
    assert wiki.lookup("nhiệt độ sôi") == page and len(http.calls) == 1  # cached
