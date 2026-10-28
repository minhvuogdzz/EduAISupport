"""Discover new lesson references through public search; only source pages become evidence (DI-97)."""

from __future__ import annotations

import hashlib
import io
import json
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
from pypdf import PdfReader

from cavat.core.vi_text import contains_phrase, fold, normalize
from cavat.modules.teaching.official_web import CONCEPTS, OfficialEducation
from cavat.modules.teaching.web import EXCERPT_CHARS, WebPage

TIMEOUT = 3.0
MAX_BYTES = 2_000_000
MAX_SEARCH_BYTES = 250_000
MAX_CANDIDATES = 6
MAX_PAGES = 2
CACHE_SECONDS = 86400
PUBLISHERS = {
    "nxbgd.vn": "NXB Giáo dục Việt Nam",
    "moet.gov.vn": "Bộ Giáo dục và Đào tạo",
    "hoc10.vn": "Học 10 · học liệu Cánh Diều",
    "sachcanhdieu.vn": "Sách Cánh Diều",
    "vndoc.com": "Tham khảo giáo dục · VnDoc",
    "vietjack.com": "Tham khảo giáo dục · VietJack",
    "hcm.edu.vn": "Cổng cơ sở giáo dục TP.HCM",
    "hanoi.edu.vn": "Cổng cơ sở giáo dục Hà Nội",
    "ctu.edu.vn": "Đại học Cần Thơ",
    "hnue.edu.vn": "Đại học Sư phạm Hà Nội",
    "hcmue.edu.vn": "Đại học Sư phạm TP.HCM",
}


def publisher_for(url: str) -> str:
    """Domain boundaries, HTTPS and ordinary public URLs; no model-selected host or redirect."""
    try:
        u = urlsplit(url)
        host = u.hostname or ""
        if u.scheme != "https" or u.username or u.password or u.port not in (None, 443):
            return ""
        if not re.fullmatch(r"[a-z0-9.-]+", host) or ".." in host:
            return ""
        for root, publisher in PUBLISHERS.items():
            if host == root or host.endswith("." + root):
                return publisher
    except ValueError:
        pass
    return ""


class PageText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "nav", "header", "footer", "form", "iframe"}:
            self.skip += 1
        elif tag in {"p", "li", "div", "br", "h1", "h2", "h3", "tr"} and not self.skip:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "nav", "header", "footer", "form", "iframe"}:
            self.skip = max(0, self.skip - 1)
        elif tag in {"p", "li", "div", "h1", "h2", "h3", "tr"} and not self.skip:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)

    @property
    def text(self):
        return "\n".join(" ".join(line.split()) for line in "".join(self.parts).splitlines())


class SearchLinks(HTMLParser):
    """DuckDuckGo result links only, never suggestions, ads, snippets or linked page resources."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hits: list[tuple[str, str]] = []
        self.href = ""
        self.label: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and "result__a" in a.get("class", "").split():
            self.href = a.get("href", "")
            self.label = []

    def handle_data(self, data):
        if self.href:
            self.label.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.href:
            raw = self.href
            u = urlsplit(raw)
            if (u.hostname or "") in {"duckduckgo.com", "html.duckduckgo.com"}:
                raw = parse_qs(u.query).get("uddg", [""])[0]
            self.hits.append((" ".join(self.label), raw))
            self.href = ""


def aliases_for(concept: str) -> tuple[str, ...]:
    return CONCEPTS[concept][0] + {
        "đường cao của hình tam giác": (
            "duong cao cua tam giac",
            "chieu cao cua hinh tam giac",
            "chieu cao cua tam giac",
        ),
        "đường cao của hình thang": ("duong cao cua hinh thang", "chieu cao cua hinh thang"),
    }.get(concept, ())


def passages(text: str, concept: str) -> str:
    """Relevant theory paragraphs, not search snippets or task/answer lists."""
    if concept not in CONCEPTS:
        return ""
    aliases = aliases_for(concept)
    paragraphs = re.split(r"\n+|(?<=[.!?])\s+(?=[A-ZÀ-Ỹ])", text)
    choices = []
    for line in paragraphs:
        line = " ".join(line.split())
        lowered = fold(normalize(line))
        if not 8 <= len(line.split()) <= 130:
            continue
        if not any(contains_phrase(line, a) for a in aliases):
            continue
        if re.search(r"\b(?:dap an|dap so|bai tap|chon [abcd]|dang nhap|mua sach|gio hang)\b", lowered):
            continue
        if not re.search(r"\b(?:la|co|goi|bang|khong|duoc|muon|neu|lay|gom|nghia)\b", lowered):
            continue
        if line not in choices and sum(map(len, choices)) + len(line) < EXCERPT_CHARS:
            choices.append(line)
        if len(choices) == 2:
            break
    return "\n".join(choices)


def accepts(page: WebPage, query: str) -> bool:
    return bool(
        page.retrieval == "search"
        and query in CONCEPTS
        and page.asked == query
        and publisher_for(page.url)
        and urlsplit(page.url).hostname == page.host
        and passages(page.text, query)
        and page.excerpt_hash == hashlib.sha256(page.text.encode()).hexdigest()
    )


class SearchEducation:
    name = "Tìm kiếm tài liệu giáo dục theo bài học"

    def __init__(
        self, cache_dir: Path | None = None, client: httpx.Client | None = None, *, api_key: str | None = None
    ):
        self.cache_dir, self.client, self.api_key = cache_dir, client, api_key

    def _read(self, client, url, limit=MAX_BYTES, *, method="GET", **kwargs):
        with client.stream(method, url, follow_redirects=False, **kwargs) as response:
            if response.status_code != 200 or str(response.url) != url:
                return None
            body = bytearray()
            for part in response.iter_bytes():
                body.extend(part)
                if len(body) > limit:
                    return None
            return bytes(body), response.headers.get("content-type", "")

    def _search(self, client, concept):
        # Never include the student's words, name, numbers, item, history or a model-authored URL.
        grade = "Toán tiểu học" if concept in {"mẫu số", "tử số", "phân số"} else "Toán lớp 5"
        term = {
            "đường cao của hình tam giác": "đường cao tam giác",
            "đường cao của hình thang": "đường cao hình thang",
        }.get(concept, concept)
        query = f'"{term}" {grade} lý thuyết'
        seen = set()
        endpoints = (["https://api.tavily.com/search"] if self.api_key else []) + [
            "https://www.bing.com/search",
            "https://html.duckduckgo.com/html/",
        ]
        for endpoint in endpoints:
            try:
                if endpoint.startswith("https://api.tavily.com"):
                    got = self._read(
                        client,
                        endpoint,
                        MAX_SEARCH_BYTES,
                        method="POST",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        json={
                            "query": query,
                            "search_depth": "basic",
                            "max_results": MAX_CANDIDATES,
                            "include_domains": list(PUBLISHERS),
                            "include_answer": False,
                            "include_raw_content": False,
                        },
                    )
                else:
                    params = {"q": query, "format": "rss"} if "bing.com" in endpoint else {"q": query}
                    url = str(httpx.URL(endpoint, params=params))
                    got = self._read(client, url, MAX_SEARCH_BYTES)
                if got is None:
                    continue
                body, media = got
                if endpoint.startswith("https://api.tavily.com"):
                    data = json.loads(body)
                    hits = [
                        (row.get("title", ""), row.get("url", ""))
                        for row in data.get("results", [])
                        if isinstance(row, dict)
                        and isinstance(row.get("title", ""), str)
                        and isinstance(row.get("url"), str)
                    ]
                elif "bing.com" in endpoint:
                    if b"<!DOCTYPE" in body.upper():
                        continue
                    root = ET.fromstring(body)
                    hits = [
                        (i.findtext("title") or "", i.findtext("link") or "")
                        for i in root.findall("./channel/item")
                    ]
                elif "text/html" in media:
                    parser = SearchLinks()
                    parser.feed(body.decode("utf-8", errors="replace"))
                    hits = parser.hits
                else:
                    continue
                for title, target in hits:
                    if not publisher_for(target) or target in seen:
                        continue
                    label = fold(normalize(title + " " + urlsplit(target).path.replace("-", " ")))
                    if not any(alias in label for alias in (*aliases_for(concept), *CONCEPTS[concept][1])):
                        continue
                    grades = {int(n) for n in re.findall(r"lop (\d+)", label)}
                    if grades and not grades.intersection({4, 5} if grade == "Toán tiểu học" else {5}):
                        continue
                    seen.add(target)
                    yield title[:200], target, urlsplit(endpoint).hostname
                    if len(seen) >= MAX_CANDIDATES:
                        return
                if seen and endpoint.startswith("https://api.tavily.com"):
                    return
            except (httpx.HTTPError, ValueError, TypeError, AttributeError, ET.ParseError):
                continue

    def lookup(self, query: str) -> WebPage | None:
        if query not in CONCEPTS:
            return None
        key = hashlib.sha256(query.encode()).hexdigest()[:24]
        cache = self.cache_dir / f"search-v1-{key}.json" if self.cache_dir else None
        if cache and cache.is_file():
            try:
                data = json.loads(cache.read_text())
                page = WebPage(**data["page"])
                if 0 <= time.time() - data["time"] < CACHE_SECONDS and accepts(page, query):
                    return page
            except (OSError, ValueError, TypeError, KeyError):
                pass
        client = self.client or httpx.Client(timeout=TIMEOUT, follow_redirects=False)
        page = None
        started, fetched = time.monotonic(), 0
        try:
            candidates = sorted(
                self._search(client, query),
                key=lambda hit: publisher_for(hit[1]).startswith("Tham khảo"),
            )
            for title, url, engine in candidates:
                if fetched >= MAX_PAGES or time.monotonic() - started > 10:
                    break
                fetched += 1
                try:
                    got = self._read(client, url)
                    if got is None:
                        continue
                    body, media = got
                    if body.startswith(b"%PDF") and "pdf" in media:
                        reader = PdfReader(io.BytesIO(body))
                        if len(reader.pages) > 30:
                            continue
                        text = "\n".join(p.extract_text() or "" for p in reader.pages)
                    elif "text/html" in media:
                        parser = PageText()
                        parser.feed(body.decode("utf-8", errors="replace"))
                        text = parser.text
                    else:
                        continue
                    excerpt = passages(text, query)
                    if not excerpt:
                        continue
                    page = WebPage(
                        title or query,
                        url,
                        excerpt,
                        urlsplit(url).hostname or "",
                        asked=query,
                        excerpt_hash=hashlib.sha256(excerpt.encode()).hexdigest(),
                        publisher=publisher_for(url),
                        retrieval="search",
                        search_engine=engine or "",
                    )
                    break
                except Exception:  # noqa: BLE001 - a malformed/unreadable public source is skipped
                    continue
            if page is None:
                # Preserve access to known publications if public search is blocked or yields nothing useful.
                return OfficialEducation(cache_dir=self.cache_dir, client=client).lookup(query)
        finally:
            if self.client is None:
                client.close()
        if page and cache:
            try:
                cache.parent.mkdir(parents=True, exist_ok=True)
                # Query-specific file; partially written caches are ignored on the next read.
                cache.write_text(json.dumps({"time": time.time(), "page": asdict(page)}, ensure_ascii=False))
            except OSError:
                pass
        return page
