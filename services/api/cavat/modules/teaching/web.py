"""Looking up a trusted source on the web when the teacher's documents do not answer (WEB-1, DI-51).

BRAIN-7 adds ``search_web.SearchEducation`` for discovery of new source pages with the same scope gate.
The policy below describes the legacy Wikipedia adapter, still available as WEB_LOOKUP=wikipedia.

The owner (2026-10-13): the tutor answers from the RAG first; when the child asks something the documents
do not cover, it may look further, but under control and only on official, accurate sites. So:

- **the RAG first**: a question the period's passages ground is answered from them; a question on a later
  period is never looked up (no teaching ahead, plan 5.5.3); only a question the documents leave unanswered
  comes here;
- **an allow-list of sources**: Vietnamese Wikipedia through its official API (free, no key, stable
  articles with sources). Nothing else is ever fetched: no general web search, no link from a page;
- **a safe question only** (``eligible``): a question with content, short, no contact data, none of the
  topics a 10-year-old's tutor leaves to adults (``UNSAFE``); what is sent is the question alone, with short
  forms written out and no name;
- **grounded words**: the excerpt is the evidence the answer is checked against (``GroundedSpeaker.check``,
  the same as for the documents); an answer that does not pass is not said, the question is kept for the
  teacher. The child hears where it comes from ("Theo Wikipedia tiếng Việt…"), the teacher sees the link.

Every lookup is recorded (``WEB_LOOKED``); a replay reads the recorded words and never fetches again.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from cavat.core.vi_text import fold, normalize
from cavat.modules.observability.trace import network_request, source_event, traced

WEB_VERSION = "web-lookup/0.3.0"
ALLOWED_HOSTS = ("sachdientu.nxbgd.vn", "sj.ctu.edu.vn", "vi.wikipedia.org")  # ADR-038
MAX_QUESTION_CHARS = 150
EXCERPT_CHARS = 1200  # what the model reads: the article's lead, the prompt stays < 3 000 token
TIMEOUT_S = 5.0

# DI-51: what a primary-school tutor never looks up for a child, whatever the source says. Folded words.
UNSAFE = (
    "tinh duc", "quan he", "khieu dam", "sex", "ma tuy", "thuoc phien", "can sa", "ruou", "bia ruou",
    "thuoc la", "co bac", "danh bac", "vu khi", "sung", "bom", "giet", "tu tu", "tu sat", "chet",
    "khung bo", "bao luc", "danh nhau", "hen ho", "nguoi yeu", "chinh tri", "ton giao", "dang phai",
)  # fmt: skip
_CONTACT = re.compile(r"\d{6,}|@|https?://|www\.", re.IGNORECASE)
_FILLERS = re.compile(r"\b(cô ơi|cô|ạ|à|vậy|nhỉ|hả|ơi|con muốn hỏi|cho con hỏi)\b", re.IGNORECASE)


@dataclass(frozen=True)
class WebPage:
    title: str
    url: str
    text: str  # the lead of the article, plain text
    host: str
    asked: str = ""  # the title asked for, when Wikipedia redirected it to this article
    excerpt_hash: str = ""
    publisher: str = ""
    retrieval: str = "fixed"  # DI-97: fixed publication or newly discovered, validated source
    search_engine: str = ""


class WebSource(Protocol):
    name: str

    def lookup(self, query: str) -> WebPage | None: ...


def eligible(question: str, *, max_chars: int = MAX_QUESTION_CHARS) -> bool:
    """A question the tutor may look up for a child: short, no contact data, none of the unsafe topics."""
    if len(question) > max_chars or _CONTACT.search(question):
        return False
    # lower case and no marks first: "MA TÚY" and "SEX?" are the words of the list, as the child typed them
    folded = f" {fold(normalize(question))} "
    return not any(f" {word} " in folded for word in UNSAFE)


# DI-51: a concept only ("X là gì"); a person ("là ai") is left to the teacher (history, politics).
_TOPIC = re.compile(
    r"^(?:cô ơi |cho con hỏi |con muốn hỏi |thế |vậy )*(.+?)\s+"
    r"(?:là gì|là cái gì|là con gì|nghĩa là gì|là gì vậy)\b"
)


def web_query(question: str) -> str:
    """What is sent: the concept a "X là gì" question asks about ("số nguyên tố"), or "" for any other one.
    A full-text search of a whole question finds anything ("nước sôi ở bao nhiêu độ" found "Hoa Kỳ"), so
    only a named concept is looked up, by the title of its article (DI-51)."""
    from cavat.modules.assessment.student_intent import expand_short_forms
    from cavat.modules.assessment.vi_numbers import normalize_text

    q = " ".join(_FILLERS.sub(" ", normalize_text(expand_short_forms(question))).split())
    m = _TOPIC.match(q)
    topic = m.group(1).strip(" ,.") if m else ""
    return topic if 2 <= len(topic) <= 60 and not re.search(r"\d", topic) else ""


def relevant(page: WebPage, query: str) -> bool:
    """The article is the concept asked about: its title, or the title Wikipedia redirected from, is it."""
    topic = fold(query.lower())
    for title in (fold(page.title.lower()), fold(page.asked.lower())):
        if topic and (title == topic or title.startswith(f"{topic} (")):
            return True
    return False


class WikipediaVi:
    """Vietnamese Wikipedia: the best search hit, then the lead of its article (MediaWiki API), cached."""

    name = "Wikipedia tiếng Việt"
    host = "vi.wikipedia.org"
    api = "https://vi.wikipedia.org/w/api.php"

    def __init__(self, cache_dir: Path | None = None, client: object | None = None) -> None:
        self.cache_dir = cache_dir
        self._client = client  # an httpx.Client (tests pass a fake with .get)

    def _get(self, params: dict[str, str]) -> dict:
        if self._client is None:
            import httpx

            self._client = httpx.Client(
                timeout=TIMEOUT_S,
                # Wikimedia's policy: a descriptive agent with a way to reach its maker
                headers={
                    "User-Agent": "CAVAT-AI-Tutor/0.1 (https://github.com/minhvuogdzz/EduAISupport; thesis)"
                },
            )
        with network_request(self.api) as network:
            response = self._client.get(self.api, params={**params, "format": "json", "formatversion": "2"})
            network["http_status"] = getattr(response, "status_code", 200)
            response.raise_for_status()
            return response.json()

    @traced("web")
    def lookup(self, query: str) -> WebPage | None:
        key = hashlib.sha256(query.encode()).hexdigest()[:24]
        cached = self.cache_dir / f"{key}.json" if self.cache_dir else None
        if cached is not None and cached.exists():
            data = json.loads(cached.read_text(encoding="utf-8"))
            source_event("wikipedia_cache_hit", kind="cache", url=self.api)
            return WebPage(**data) if data else None
        page = self._fetch(query)
        if cached is not None:
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_text(
                json.dumps(page.__dict__ if page else None, ensure_ascii=False), encoding="utf-8"
            )
        return page

    def _fetch(self, query: str) -> WebPage | None:
        """The article titled as the concept (redirects followed): one request, no search."""
        title = query[:1].upper() + query[1:]
        lead = self._get(
            {
                "action": "query",
                "prop": "extracts",
                "exintro": "1",
                "explaintext": "1",
                "redirects": "1",
                "titles": title,
            }
        )
        pages = lead.get("query", {}).get("pages", [])
        if not pages or pages[0].get("missing") or pages[0].get("invalid"):
            return None
        redirects = lead.get("query", {}).get("redirects") or lead.get("query", {}).get("normalized") or []
        asked = next((r.get("from", "") for r in redirects), "")
        title = pages[0].get("title", title)
        text = " ".join((pages[0].get("extract") or "").split())
        if not text or "có thể là" in text[:120]:  # a disambiguation page names several things
            return None
        url = f"https://{self.host}/wiki/{title.replace(' ', '_')}"
        return WebPage(title=title, url=url, text=text[:EXCERPT_CHARS], host=self.host, asked=asked)
