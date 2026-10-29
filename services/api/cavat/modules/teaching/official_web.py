"""BRAIN-2 / ADR-038: on-demand retrieval inside verified official educational publications.

No search engine, arbitrary URL, crawler, login or linked content. A concept chosen by the scope gate is
searched in the public text of the publisher's book. A missing definition stays missing.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import tempfile
import time
from html.parser import HTMLParser
from pathlib import Path

import httpx
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from cavat.core.vi_text import fold, normalize
from cavat.modules.observability.trace import network_request, source_event, traced
from cavat.modules.rag.retrieve import RagIndex
from cavat.modules.teaching.web import EXCERPT_CHARS, WebPage, eligible

BOOK_URL = "https://sachdientu.nxbgd.vn/thu-vien-so/doc-sach/sgv-toan.4491495468"
HOST = "sachdientu.nxbgd.vn"
FRACTION_URL = (
    "https://sj.ctu.edu.vn/ql/docgia/download/baibao-28144/12-GD-DUONG%20HUU%20TONG%2893-102%29.pdf"
)
OFFICIAL_URLS = {HOST: BOOK_URL, "sj.ctu.edu.vn": FRACTION_URL}
CACHE_SECONDS = 86400  # DI-86: revalidate daily; failures are never cached
MAX_BYTES = 2_000_000
TIMEOUT = 8.0

# Canonical concepts, their aliases, and the lesson terms that make them relevant. This is deliberately
# small: a new subject/source is an explicit change, never a model's choice of URL or search terms.
CONCEPTS = {
    "mẫu số": (("mau so",), ("phan so",)),
    "tử số": (("tu so",), ("phan so",)),
    "phân số thập phân": (("phan so thap phan",), ("phan so thap phan", "so thap phan")),
    "phân số": (("phan so",), ("phan so",)),
    "phần nguyên": (("phan nguyen",), ("so thap phan",)),
    "phần thập phân": (("phan thap phan",), ("so thap phan",)),
    "hàng phần mười": (("hang phan muoi", "phan muoi"), ("gia tri theo hang", "phan thap phan")),
    "hàng phần trăm": (("hang phan tram", "phan tram"), ("gia tri theo hang", "phan thap phan")),
    "hàng phần nghìn": (("hang phan nghin", "phan nghin"), ("gia tri theo hang", "phan thap phan")),
    "số thập phân bằng nhau": (("so thap phan bang nhau",), ("so thap phan bang nhau",)),
    "so sánh số thập phân": (("so sanh so thap phan", "so sanh hai so thap phan"), ("so sanh",)),
    "sắp xếp số thập phân": (("sap xep so thap phan",), ("sap xep",)),
    "số thập phân": (("so thap phan",), ("so thap phan",)),
    "diện tích hình tam giác": (
        ("dien tich hinh tam giac", "dien tich tam giac"),
        ("dien tich hinh tam giac", "dien tich tam giac"),
    ),
    "diện tích hình thang": (("dien tich hinh thang",), ("dien tich hinh thang",)),
    "đường cao của hình tam giác": (
        ("duong cao cua hinh tam giac", "duong cao tam giac", "chieu cao tam giac"),
        ("tam giac",),
    ),
    "đường cao của hình thang": (
        ("duong cao cua hinh thang", "duong cao hinh thang", "chieu cao hinh thang"),
        ("hinh thang",),
    ),
    "vuông góc": (("vuong goc",), ("tam giac", "hinh thang")),
    "đáy": (("day", "canh day"), ("tam giac", "hinh thang")),
    "hình tam giác": (("hinh tam giac", "tam giac"), ("tam giac",)),
    "hình thang": (("hinh thang",), ("hinh thang",)),
}
# Only a request to explain a named concept, with no extra entities/subject. In particular 'tỉ số phần
# trăm', 'thể tích hình thang' and a child's name cannot sneak through a substring match.
FRAMING = set(
    "co con em oi a nhe vay the la gi nghia sao vi tai nhu nao the nao thi nhung va cua mot hai "
    "cho hoi muon biet hieu giai thich giup noi lai ro hon cach dung de lam tim tinh doc viet "
    "khac nhau khong phai duoc bang voi can the nao lien quan".split()
)


def scoped_query(question: str, index: RagIndex, node_id: str | None) -> str:
    if not node_id or not eligible(question) or re.search(r"\d", question):
        return ""
    q = fold(normalize(question))
    q = re.sub(r"[^\w\s]", " ", q)
    q = " ".join(q.split())
    scope_ids = {node_id, *index.ancestors(node_id)}
    # Names, rather than example bodies, keep an incidental future term out of the scope gate.
    scope = " ".join(
        fold(normalize(c.title.split(" · ")[0]))
        for c in index.chunks
        if c.node_id in scope_ids and c.source == "chapter"
    )
    if "duong cao" in q or "chieu cao" in q:
        # A bare height question is resolved only when the current lesson identifies one shape.
        if not any(s in q for s in ("tam giac", "hinh thang")):
            current = " ".join(fold(normalize(c.title)) for c in index.chunks if c.node_id == node_id)
            shape = (
                "hinh thang" if "hinh thang" in current else "hinh tam giac" if "tam giac" in current else ""
            )
            if not shape:
                return ""
            q = re.sub(r"(?:duong cao|chieu cao)", f"duong cao cua {shape}", q)
    found: list[tuple[int, str]] = []
    remaining = q
    for concept, (aliases, allowed) in sorted(CONCEPTS.items(), key=lambda pair: -max(map(len, pair[1][0]))):
        for alias in sorted(aliases, key=len, reverse=True):
            pattern = rf"\b{re.escape(alias)}\b"
            if re.search(pattern, remaining):
                if not any(t in scope for t in allowed):
                    return ""  # an explicitly named future concept cannot be erased as framing
                found.append((len(alias), concept))
                remaining = re.sub(pattern, " ", remaining)
    if not found or set(remaining.split()) - FRAMING:
        return ""
    return max(found)[1]


class _BookText(HTMLParser):
    """Only the publisher's accessible page text; scripts, image alt and navigation never enter evidence."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.skip = False
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style", "noscript"):
            self.skip = True
        if self.depth:
            if tag == "div":
                self.depth += 1
            if tag == "br":
                self.parts.append("\n")
        elif tag == "div" and "js-page-speech-text" in dict(attrs).get("class", "").split():
            self.depth = 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript"):
            self.skip = False
        if tag == "div" and self.depth:
            self.depth -= 1
            if not self.depth:
                self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.depth and not self.skip:
            self.parts.append(data)


def book_passages(html: str, concept: str) -> str:
    parser = _BookText()
    parser.feed(html)
    aliases = CONCEPTS[concept][0]
    candidates: list[tuple[int, str]] = []
    for line in re.split(r"\n|(?<=[.!;])\s+", "".join(parser.parts)):
        line = " ".join(line.split()).strip("–- ")
        # Some objectives include a complete definition in parentheses. Keep only that definition,
        # verbatim; an objective without one is still discarded below.
        definition = re.search(r"\((phân số có mẫu số là [^)]{4,100})\)", line, re.IGNORECASE)
        if definition and concept == "phân số thập phân":
            line = re.sub(r"^Nhận biết được\s+", "", line, flags=re.IGNORECASE)
        # Textbook thousands use a narrow/ordinary space; our vi-VN number reader expects 1000.
        line = re.sub(r"(?<=\d)[ \u00a0\u202f](?=\d{3}(?!\d))", "", line)
        folded = fold(normalize(line))
        hits = sum(a in folded for a in aliases)
        # A heading, exercise, answer key, instruction to the teacher or broken OCR is not a definition.
        if definition and concept == "phân số thập phân":
            hits += 1
        if not hits or not 8 <= len(line.split()) <= 110 or "?" in line:
            continue
        if line.startswith(("…", "...")) or folded.startswith(("cung la ", "van dung duoc ")):
            continue
        if re.match(r"(?:viet|chuyen|ve|doc|tinh|nhan biet|hieu|thuc hien)(?: \w+){0,2} duoc\b", folded):
            continue
        if re.search(r"\b(?:hon so|ti so|the tich|van toc|hinh tron|xac suat|bieu do)\b", folded):
            continue
        if re.search(
            r"\b(?:gv|hs|bai \d|yeu cau|muc tieu|dap so|ket qua|chon [abc]|goi mo|hoc sinh|"
            r"nhan biet duoc|biet cach|ve duoc|hieu duoc|thuc hien duoc)\b",
            folded,
        ):
            continue
        if not re.search(r"\b(?:la|co|goi|bang|khong|duoc|muon|neu|lay)\b", folded):
            continue
        candidates.append((hits + (3 if " la " in f" {folded} " else 0), line))
    chosen: list[str] = []
    for _, line in sorted(candidates, key=lambda pair: -pair[0]):
        if line in chosen or sum(map(len, chosen)) + len(line) > EXCERPT_CHARS:
            continue
        chosen.append(line)
        if len(chosen) == 3:
            break
    return "\n".join(chosen)


def fraction_passages(text: str, concept: str) -> str:
    """Only the paper's explicit SGK definitions; no numerical PDF formula/OCR or research discussion."""
    text = " ".join(text.split())
    prefix = "Mẫu số" if concept == "mẫu số" else "Tử số" if concept == "tử số" else "(?:Mẫu số|Tử số)"
    matches = re.findall(rf"{prefix} (?:là|cho biết)[^.!?]{{10,240}}[.!]", text)
    matches = re.findall(r"Mỗi phân số có tử số và mẫu số[”\".]*", text) + matches
    return " ".join(dict.fromkeys(matches))[:EXCERPT_CHARS]


class OfficialEducation:
    name = "Tài liệu giáo dục chính thống"

    def __init__(self, cache_dir: Path | None = None, client: httpx.Client | None = None) -> None:
        self.cache_dir, self.client = cache_dir, client

    def _text(self, url: str, *, pdf: bool = False) -> str:
        key = hashlib.sha256(url.encode()).hexdigest()[:20]
        cache = self.cache_dir / f"official-v2-{key}.json" if self.cache_dir else None
        if cache and cache.is_file():
            try:
                saved = json.loads(cache.read_text())
                age = time.time() - saved["time"]
                if 0 <= age < CACHE_SECONDS and saved["url"] == url:
                    source_event("official_page_cache_hit", kind="cache", url=url)
                    return str(saved["text"])
            except (ValueError, KeyError, OSError, TypeError):
                pass
        client = self.client or httpx.Client(timeout=TIMEOUT, follow_redirects=False)
        try:
            with network_request(url) as network:
                with client.stream("GET", url, follow_redirects=False) as response:
                    network["http_status"] = response.status_code
                    if response.status_code != 200 or str(response.url) != url:
                        return ""  # no redirect, even to a different official host
                    media = response.headers.get("content-type", "")
                    if not pdf and "text/html" not in media:
                        return ""
                    body = bytearray()
                    for part in response.iter_bytes():
                        body.extend(part)
                        if len(body) > MAX_BYTES:
                            return ""
                    if pdf:
                        if not body.startswith(b"%PDF"):
                            return ""
                        reader = PdfReader(io.BytesIO(body))
                        if len(reader.pages) > 20:
                            return ""
                        text = "\n".join(page.extract_text() or "" for page in reader.pages)
                    else:
                        text = body.decode("utf-8", errors="replace")
        finally:
            if self.client is None:
                client.close()
        if cache and text:
            cache.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode="w", dir=cache.parent, delete=False) as stream:
                stream.write(json.dumps({"url": url, "time": time.time(), "text": text}))
                temporary = Path(stream.name)
            try:
                temporary.replace(cache)
            finally:
                temporary.unlink(missing_ok=True)
        return text

    @traced("web")
    def lookup(self, query: str) -> WebPage | None:
        if query not in CONCEPTS:
            return None
        try:
            foundation = query in ("mẫu số", "tử số", "phân số")
            url = FRACTION_URL if foundation else BOOK_URL
            text = (
                fraction_passages(self._text(url, pdf=True), query)
                if foundation
                else book_passages(self._text(url), query)
            )
        except (httpx.HTTPError, OSError, PdfReadError, ValueError):
            return None
        if not text:
            return None
        return WebPage(
            "Tổ chức cho học sinh lớp 4 tiếp cận phân số dựa trên số phần / toàn thể"
            if foundation
            else "SGV – Toán 5",
            url,
            text,
            "sj.ctu.edu.vn" if foundation else HOST,
            asked=query,
            excerpt_hash=hashlib.sha256(text.encode()).hexdigest(),
            publisher="Tạp chí Khoa học Đại học Cần Thơ" if foundation else "NXB Giáo dục Việt Nam",
        )
