"""Keyword index of the Hybrid RAG (plan v1, 5.5.2): BM25 written here, on syllables and pairs of adjacent
syllables ("phần mười" stays a phrase), on two forms of the text: with diacritics (exact) and folded
(children type "tai sao phai them so 0"). Numbers have one form: 0.25 and 0,25 are the same token.

BM25 and RRF rank passages; neither says whether any passage answers the question at all (the top one is
always first). ``coverage`` does: the share of the question's content syllables, weighted by idf, that a
passage contains. A syllable the corpus never uses ("mèo") weighs the most, so an off-topic question has
low coverage everywhere (DI-17). A syllable typed with diacritics must match with the same diacritics
("thủ đô Việt Nam" shares no word with "thứ", "độ", "viết", "năm"); one typed without matches the folded
text ("phan nguyen" matches "phần nguyên").
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence

from cavat.core.vi_text import fold, normalize

K1, B = 1.2, 0.75  # DI-17
# A dot used as the decimal mark (0.25, 3.5) becomes the Vietnamese comma; a thousands dot (1.000) stays.
_DECIMAL_DOT = re.compile(r"(?<![\d.])0\.(?=\d)|(?<=\d)\.(?=\d{1,2}(?![\d.]))")


# Words of a child's question that carry no content (folded): addressing, particles, question words.
FILLER = frozenset(
    "co oi a ah u ui con em minh ban hoi cho voi the nao sao gi la nhi vay day ma thi va cua nhe khong "
    "duoc chua roi ha ho giup biet hieu tai vi lam cai nay kia nhu bao may nghia".split()
)
_NUMBER = re.compile(r"^[\d.,/]+$")


def content_words(text: str) -> list[str]:
    """Syllables of ``text`` (as typed, normalized) that carry content: no filler word, no number."""
    norm = normalize(_DECIMAL_DOT.sub(lambda m: m.group(0).replace(".", ","), text))
    return [w for w in dict.fromkeys(norm.split()) if fold(w) not in FILLER and not _NUMBER.match(w)]


def tokens(text: str, folded: bool) -> list[str]:
    """Syllables and adjacent pairs of the normalized (or folded) text, filler words left out.

    A filler would otherwise make phrases out of grammar: "phần nguyên là gì" would match "phần nguyên là
    7" through the pair "nguyên là" better than the definition "bên trái dấu phẩy là phần nguyên".
    """
    norm = normalize(_DECIMAL_DOT.sub(lambda m: m.group(0).replace(".", ","), text))
    words = (fold(norm) if folded else norm).split()
    keep = [fold(w) not in FILLER for w in words]
    pairs = [
        f"{a}_{b}" for i, (a, b) in enumerate(zip(words, words[1:], strict=False)) if keep[i] and keep[i + 1]
    ]
    return [w for w, k in zip(words, keep, strict=True) if k] + pairs


class BM25:
    """Okapi BM25 over a fixed list of documents (token lists)."""

    def __init__(self, docs: Sequence[Sequence[str]]) -> None:
        self.n = len(docs)
        self.lengths = [len(d) for d in docs]
        self.avg = (sum(self.lengths) / self.n) if self.n else 0.0
        self.freqs = [Counter(d) for d in docs]
        df: Counter[str] = Counter()
        for f in self.freqs:
            df.update(f.keys())
        self.idf = {t: math.log(1 + (self.n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def scores(self, query: Sequence[str]) -> list[float]:
        out = [0.0] * self.n
        terms = [t for t in dict.fromkeys(query) if t in self.idf]
        for i, f in enumerate(self.freqs):
            length_norm = K1 * (1 - B + B * self.lengths[i] / self.avg) if self.avg else K1
            total = 0.0
            for t in terms:
                tf = f.get(t, 0)
                if tf:
                    total += self.idf[t] * tf * (K1 + 1) / (tf + length_norm)
            out[i] = total
        return out


class TwoFormBM25:
    """BM25 on the text with diacritics and on its folded form; a document keeps its better score."""

    def __init__(self, texts: Sequence[str]) -> None:
        self.exact = BM25([tokens(t, folded=False) for t in texts])
        self.folded = BM25([tokens(t, folded=True) for t in texts])

    def scores(self, query: str) -> list[float]:
        exact = self.exact.scores(tokens(query, folded=False))
        folded = self.folded.scores(tokens(query, folded=True))
        return [max(a, b) for a, b in zip(exact, folded, strict=True)]

    def coverage(self, query: str) -> list[float]:
        """For every document, the idf-weighted share of the query's content words it contains (0..1).

        A word unknown to the corpus weighs as a word in no document, the highest idf. A query with no
        content word ("là sao ạ") covers nothing: there is nothing to ground.
        """
        words = content_words(query)
        n = self.folded.n
        if not words or not n:
            return [0.0] * n
        unknown = math.log(1 + (n + 0.5) / 0.5)
        # (form, word, weight): a word typed without diacritics is looked up in the folded index.
        terms = [(self.folded if fold(w) == w else self.exact, w) for w in words]
        weights = [form.idf.get(w, unknown) for form, w in terms]
        total = sum(weights)
        return [
            sum(wt for (form, w), wt in zip(terms, weights, strict=True) if w in form.freqs[i]) / total
            for i in range(n)
        ]
