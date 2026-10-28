"""Web discovery must ground a lesson answer in a fetched source, never a search snippet."""

from dataclasses import replace
from xml.sax.saxutils import escape

import httpx
import pytest
from cavat.modules.ai_gateway.fake import FakeChatModel
from cavat.modules.ai_gateway.router import AIRouter
from cavat.modules.teaching.grounded import GroundedSpeaker
from cavat.modules.teaching.search_web import PageText, SearchEducation, accepts, publisher_for
from test_brain2 import small_index

TOPIC = "phân số thập phân"
TEXT = "Phân số thập phân là phân số có mẫu số là 10, 100, 1000 và các lũy thừa của 10."
NEW_URL = "https://th-demo.hcm.edu.vn/hoc-lieu/phan-so.html"


def feed(url=NEW_URL, title="Phân số thập phân · Toán lớp 5"):
    return (
        "<rss><channel><item><title>"
        + escape(title)
        + "</title><link>"
        + escape(url)
        + "</link><description>Mẫu số là 12345, hãy đọc đáp án ngay.</description></item></channel></rss>"
    )


def test_search_finds_a_new_page_reads_its_theory_and_caches_provenance(tmp_path):
    calls = []

    def handler(req):
        calls.append(req)
        if req.url.host == "www.bing.com":
            return httpx.Response(200, text=feed(), headers={"content-type": "text/xml"})
        if req.url.host == "html.duckduckgo.com":
            return httpx.Response(202, text="challenge")
        if str(req.url) == NEW_URL:
            return httpx.Response(
                200,
                text=f"<nav>Quảng cáo</nav><article><p>{TEXT}</p></article>",
                headers={"content-type": "text/html; charset=utf-8"},
            )
        return httpx.Response(404)

    source = SearchEducation(tmp_path, httpx.Client(transport=httpx.MockTransport(handler)))
    page = source.lookup(TOPIC)
    assert page and page.url == NEW_URL and page.text == TEXT
    assert page.retrieval == "search" and page.search_engine == "www.bing.com" and accepts(page, TOPIC)
    assert "12345" not in page.text
    assert TOPIC in calls[0].url.params["q"] and "Toán lớp 5" in calls[0].url.params["q"]
    before = len(calls)
    assert source.lookup(TOPIC) == page and len(calls) == before
    assert not accepts(replace(page, text="Một đoạn bị thay đổi"), TOPIC)


@pytest.mark.parametrize(
    "url",
    [
        "http://th-demo.hcm.edu.vn/lesson",
        "https://nxbgd.vn.attacker.example/lesson",
        "https://127.0.0.1/a",
        "https://[::1]/a",
        "https://school.edu.vn:8443/a",
        "https://nxbgd.vn@attacker.example/a",
        "https://attacker.example@nxbgd.vn/a",
        "https://news.example/a",
        "https://rdsic.edu.vn/seo-blog",
        "file:///etc/passwd",
    ],
)
def test_unapproved_or_nonpublic_url_shapes_are_rejected(url):
    assert not publisher_for(url)


@pytest.mark.parametrize(
    "raw",
    ["giải câu của con, tên con là ABC", "thể tích hình tròn", "đường cao https://localhost", "politics"],
)
def test_only_server_canonical_topics_can_be_sent_to_search(raw):
    calls = []

    def handler(req):
        calls.append(req)
        return httpx.Response(500)

    source = SearchEducation(client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert source.lookup(raw) is None and not calls


def test_redirect_and_unrelated_page_never_become_evidence_or_negative_cache(tmp_path):
    calls = []

    def handler(req):
        calls.append(str(req.url))
        if req.url.host == "www.bing.com":
            return httpx.Response(200, text=feed(), headers={"content-type": "text/xml"})
        if str(req.url) == NEW_URL:
            return httpx.Response(302, headers={"location": "http://127.0.0.1/private"})
        return httpx.Response(503)

    source = SearchEducation(tmp_path, httpx.Client(transport=httpx.MockTransport(handler)))
    assert source.lookup(TOPIC) is None
    assert not any("127.0.0.1" in u for u in calls)
    assert not list(tmp_path.glob("search-*.json"))


def test_search_engine_failure_can_fall_back_to_a_verified_existing_publication():
    from cavat.modules.teaching.official_web import BOOK_URL

    def handler(req):
        if str(req.url) == BOOK_URL:
            return httpx.Response(
                200,
                text='<div class="js-page-speech-text">'
                "Phân số thập phân là phân số có mẫu số là 10, 100 hoặc 1000.</div>",
                headers={"content-type": "text/html"},
            )
        return httpx.Response(429)

    page = SearchEducation(client=httpx.Client(transport=httpx.MockTransport(handler))).lookup(TOPIC)
    assert page is not None and page.url == BOOK_URL and page.retrieval == "fixed"


def test_text_extraction_never_loads_script_or_navigation_resources():
    p = PageText()
    p.feed(f'<script>fetch("http://localhost")</script><nav>Khóa học</nav><p>{TEXT}</p>')
    assert p.text.strip() == TEXT


def test_discovered_source_can_reach_the_tutor_with_url_and_checked_source_text():
    def handler(req):
        if req.url.host == "www.bing.com":
            return httpx.Response(200, text=feed(), headers={"content-type": "text/xml"})
        if str(req.url) == NEW_URL:
            return httpx.Response(200, text=f"<p>{TEXT}</p>", headers={"content-type": "text/html"})
        return httpx.Response(503)

    source = SearchEducation(client=httpx.Client(transport=httpx.MockTransport(handler)))
    answer = "Phân số thập phân có mẫu số là 10, 100, 1000."
    p = FakeChatModel(
        [
            {"message": answer, "safety_flag": False, "policy_feedback": ""},
            {"supported": True, "quotes": [TEXT]},
        ]
    )
    speaker = GroundedSpeaker(
        small_index(title="Phân số thập phân", text="Bài học về phân số thập phân."),
        AIRouter(chat_provider=p),
        web=source,
    )
    found = speaker.index.question(TOPIC, "eq", speaker.order)[1]
    turn = speaker._from_web("phân số thập phân là gì", TOPIC, found)
    assert turn.kind == "ANSWERED" and turn.web.url == NEW_URL
    assert turn.spoken.source == "WEB" and NEW_URL in turn.spoken.sources[0]
    assert TEXT in p.calls[0][1].messages[1].content


def test_configured_search_api_uses_only_canonical_query_and_fetches_source_itself():
    import json

    calls = []

    def handler(req):
        calls.append(req)
        if req.url.host == "api.tavily.com":
            assert req.method == "POST"
            assert req.headers["authorization"] == "Bearer test-search-key"
            body = json.loads(req.content)
            assert body["include_answer"] is False and body["search_depth"] == "basic"
            assert TOPIC in body["query"] and body["max_results"] == 6
            return httpx.Response(
                200,
                json={
                    "answer": "Thông tin bịa",
                    "results": [
                        {
                            "title": "Phân số thập phân lớp 5",
                            "url": NEW_URL,
                            "content": "Không dùng snippet này",
                        }
                    ],
                },
            )
        if str(req.url) == NEW_URL:
            assert "authorization" not in req.headers
            return httpx.Response(200, text=f"<p>{TEXT}</p>", headers={"content-type": "text/html"})
        return httpx.Response(503)

    page = SearchEducation(
        client=httpx.Client(transport=httpx.MockTransport(handler)), api_key="test-search-key"
    ).lookup(TOPIC)
    assert page and page.text == TEXT and page.search_engine == "api.tavily.com"
    assert len(calls) == 2 and all("test-search-key" not in str(c.url) for c in calls)


def test_background_knowledge_does_not_pretend_the_web_page_supports_every_claim():
    import hashlib

    from cavat.modules.teaching.web import WebPage
    from test_brain4 import OK

    page = WebPage(
        "Phân số thập phân lớp 5",
        NEW_URL,
        TEXT,
        "th-demo.hcm.edu.vn",
        asked=TOPIC,
        retrieval="search",
        excerpt_hash=hashlib.sha256(TEXT.encode()).hexdigest(),
    )
    answer = "Phân số thập phân có mẫu số là 10, 100, 1000."
    p = FakeChatModel([{"message": answer, "safety_flag": False, "policy_feedback": ""}, OK])
    speaker = GroundedSpeaker(small_index(), AIRouter(chat_provider=p), allow_knowledge=True)
    found = speaker.index.question(TOPIC, "eq", speaker.order)[1]
    turn = speaker._background("phân số thập phân là gì", found, TOPIC, page=page)
    assert turn.kind == "ANSWERED" and turn.web == page
    assert turn.spoken.source == "LLM" and not turn.spoken.sources


def test_height_definition_with_the_word_cua_can_be_discovered_not_only_extracted():
    text = "Đường cao của tam giác là đoạn thẳng kẻ từ một đỉnh vuông góc với cạnh đối diện."

    def handler(req):
        if req.url.host == "www.bing.com":
            return httpx.Response(200, text=feed(NEW_URL, "Hình tam giác · Toán lớp 5"))
        if str(req.url) == NEW_URL:
            return httpx.Response(200, text=f"<p>{text}</p>", headers={"content-type": "text/html"})
        return httpx.Response(503)

    source = SearchEducation(client=httpx.Client(transport=httpx.MockTransport(handler)))
    page = source.lookup("đường cao của hình tam giác")
    assert page and page.text == text and page.retrieval == "search"
