# ruff: noqa: E501  (LaTeX strings: a generated line is as long as the table row it writes)
"""Tables and figures of the paper (docs/paper), written as LaTeX fragments in docs/paper/gen/ from the JSON
files of docs/paper/data/ (see paper_rag.py, paper_corpus.py, paper_student.py, paper_assessment.py,
paper_baselines.py). Standard library only. Every number of a generated table or plot comes from the data;
the text of the paper quotes the same numbers through ``numbers.tex``.

Run: ``python3 services/api/scripts/paper_figures.py`` (``make paper-data`` runs it after the data scripts).
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "docs/paper/data"
GEN = ROOT / "docs/paper/gen"
GEN.mkdir(parents=True, exist_ok=True)


def load(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


RAG, CORPUS, STUDENT, ASSESS, BASE = (
    load("rag.json"),
    load("corpus.json"),
    load("student.json"),
    load("assessment.json"),
    load("baselines.json"),
)
DEC, GEO = "math-g5-decimals", "math-g5-area-triangle-trapezoid"
CH_NAME = {DEC: "Số thập phân", GEO: "Diện tích tam giác, hình thang"}
CH_SHORT = {DEC: "STP", GEO: "DTTGHT"}


# ------------------------------------------------------------------------------ formatting


def num(x: float, nd: int = 2) -> str:
    """Decimal comma, as the Vietnamese standard writes it."""
    return f"{x:.{nd}f}".replace(".", ",")


def pct(x: float, nd: int = 0) -> str:
    return num(100 * x, nd) + r"\%"


def thou(n: int) -> str:
    return f"{n:,}".replace(",", r"\,")


# Bảng hẹp đặt trong một cột của bài hai cột: cột đầu xuống dòng thay vì kéo giãn bảng.
_ONE_COLUMN = {
    "tab-reading.tex",
    "tab-bank.tex",
    "tab-plan-stats.tex",
    "tab-sources.tex",
    "tab-baselines.tex",
    "tab-conformance.tex",
}


def write(name: str, text: str) -> None:
    if name in _ONE_COLUMN:
        text = text.replace(
            r"\begin{tabular}{@{}l", r"\begin{tabular}{@{}>{\raggedright\arraybackslash}p{3.4cm}", 1
        )
    (GEN / name).write_text(text.rstrip() + "\n", encoding="utf-8")


def tex_escape(s: str) -> str:
    s = s.replace("&", r"\&").replace("%", r"\%").replace("_", r"\_").replace("#", r"\#")
    for a, b in (
        ("↔", r"$\leftrightarrow$"),
        ("→", r"$\rightarrow$"),
        ("≤", r"$\leq$"),
        ("≥", r"$\geq$"),
        ("≈", r"$\approx$"),
    ):
        s = s.replace(a, b)
    return s


def zone_colour(m: float | None) -> str:
    if m is None:
        return "white"
    v = math.floor(m)
    return (
        "zoneA"
        if v >= 90
        else "zoneB"
        if v >= 75
        else "zoneC"
        if v >= 60
        else "zoneD"
        if v >= 40
        else "zoneE"
    )


def zone_text(m: float | None) -> str:
    return "white" if m is not None and zone_colour(m) in ("zoneA", "zoneE") else "ink"


def table(
    colspec: str,
    header: list[str],
    rows: list[list[str]],
    *,
    star: bool = False,
    font: str = r"\small",
    mid: set[int] | None = None,
) -> str:
    """A booktabs tabular. ``mid``: indices of rows after which a \\midrule is drawn."""
    wide = "X" in colspec or "Y" in colspec
    out = [
        font,
        rf"\begin{{tabularx}}{{\linewidth}}{{{colspec}}}" if wide else rf"\begin{{tabular}}{{{colspec}}}",
    ]
    out += [r"\toprule", " & ".join(header) + r" \\", r"\midrule"]
    for i, row in enumerate(rows):
        out.append(" & ".join(row) + r" \\")
        if mid and i in mid:
            out.append(r"\midrule")
    out += [r"\bottomrule", r"\end{tabularx}" if wide else r"\end{tabular}"]
    return "\n".join(out)


# ------------------------------------------------------------------------------ numbers.tex


def macros() -> dict[str, str]:
    d = CORPUS["documents"]
    b = CORPUS["banks"]
    p = CORPUS["plans"]
    pub = RAG["corpus"]["published"]
    out: dict[str, str] = {}

    def put(name: str, value) -> None:
        out[name] = (
            value if isinstance(value, str) else (thou(value) if isinstance(value, int) else num(value))
        )

    put("NDocs", sum(d[c]["n"] for c in d))
    put("NDocsDec", d[DEC]["n"])
    put("NDocsGeo", d[GEO]["n"])
    put("NPages", sum(d[c]["pages"] for c in d))
    put("NPagesDec", d[DEC]["pages"])
    put("NPagesGeo", d[GEO]["pages"])
    put("NSyll", sum(d[c]["syllables"] for c in d))
    put("NPagesText", sum(d[c]["reads"]["text_layer"] for c in d))
    put("NPagesOcr", sum(d[c]["reads"]["ocr"] for c in d))
    put("NOcrImages", sum(d[c]["reads"]["reason"].get("IMAGES", 0) for c in d))
    put("NOcrFigure", sum(d[c]["reads"]["reason"].get("FIGURE", 0) for c in d))
    put("NNumbersAdded", sum(d[c]["reads"]["numbers_added"] for c in d))
    put("NConfirmedPages", sum(d[c]["reads"]["confirmed_pages"] for c in d))
    put("NDisputedNumbers", sum(d[c]["reads"]["disputed_numbers"] for c in d))
    put("NReviewPages", sum(d[c]["reads"]["needs_review"] for c in d))
    put("NItems", sum(b[c]["items"] for c in b))
    put("NItemsDec", b[DEC]["items"])
    put("NItemsGeo", b[GEO]["items"])
    put("NVerified", sum(b[c]["status"].get("VERIFIED", 0) for c in b))
    put("NConflict", sum(b[c]["status"].get("CONFLICT", 0) for c in b))
    put("NDisputedItems", sum(b[c]["status"].get("DISPUTED", 0) for c in b))
    put("NReviewItems", sum(b[c]["status"].get("REVIEW", 0) for c in b))
    put("NUnchecked", sum(b[c]["status"].get("UNCHECKED", 0) for c in b))
    put("NAssess", sum(b[c]["assessment"] for c in b))
    put("NFigureItems", sum(b[c]["figure"] for c in b))
    put("NNodes", sum(p[c]["nodes"] for c in p))
    put("NNodesDec", p[DEC]["nodes"])
    put("NNodesGeo", p[GEO]["nodes"])
    put("NEdges", sum(sum(p[c]["relations"].values()) for c in p))
    put("NEdgesPrereq", sum(p[c]["relations"].get("PREREQUISITE", 0) for c in p))
    put("NEdgesApp", sum(p[c]["relations"].get("APPLICATION", 0) for c in p))
    put("NPlanItems", sum(p[c]["items"]["n"] for c in p))
    put("NPlanHints", sum(p[c]["items"]["hints"] for c in p))
    put("NMisconceptions", sum(p[c]["misconceptions"]["n"] for c in p))
    put("NCritical", sum(p[c]["misconceptions"]["critical"] for c in p))
    put("NDrafts", sum(p[c]["drafts"]["n"] for c in p))
    put("NDraftsOk", sum(p[c]["drafts"]["ok"] for c in p))
    put("NDraftsQwen", sum(p[c]["drafts"]["by_model"].get("qwen/qwen3.8-27b", 0) for c in p))
    put("NDraftsFallback", sum(p[c]["drafts"]["by_model"].get("openai/gpt-oss-120b", 0) for c in p))
    put("NDecisions", sum(p[c]["decisions"]["n"] for c in p))
    put("NApprove", sum(p[c]["decisions"]["by_action"].get("approve", 0) for c in p))
    put("NEdit", sum(p[c]["decisions"]["by_action"].get("edit", 0) for c in p))
    put("NReject", sum(p[c]["decisions"]["by_action"].get("reject", 0) for c in p))
    put("NChunks", pub["chunks"])
    put("NChunksDec", pub["by_chapter"][DEC])
    put("NChunksGeo", pub["by_chapter"][GEO])
    put("NPassages", pub["passages"]["n"])
    put("NPassagesTied", pub["passages"]["tied"])
    put("NPassagesSpread", pub["passages"]["spread"])
    put("NChunksSample", RAG["corpus"]["sample"]["chunks"])
    put("NVecDim", pub["vectors"]["dims"])
    # RAG sets
    sets = RAG["sets"]
    put("NQuestions", sum(s["n"] for s in sets.values()))
    put("NQuestionsInScope", sum(s["in_scope"] for s in sets.values()))
    # student sessions
    ch = STUDENT["chapters"]
    put("NEventsDec", ch[DEC]["events"])
    put("NEventsGeo", ch[GEO]["events"])
    put("NEvents", ch[DEC]["events"] + ch[GEO]["events"])
    put("NTutorMsg", sum(c["socratic"]["tutor_messages"] for c in ch.values()))
    put("NLeakChecked", sum(c["socratic"]["leak_checked"] for c in ch.values()))
    put("NLeaks", sum(c["socratic"]["leaks"] for c in ch.values()))
    put("NStudentMsg", sum(c["student_messages"] for c in ch.values()))
    put("NItemsResolved", sum(c["ladder"]["items"] for c in ch.values()))
    put("NDIs", 58)  # DI-1 .. DI-58 of the design documents
    mean_att = sum(t["att"] for t in targets()) / 7
    out["TargetMean"] = pct(mean_att)
    return out


def numbers() -> None:
    lines = [
        "% Sinh tự động từ docs/paper/data/*.json bởi services/api/scripts/paper_figures.py. Không sửa tay."
    ]
    for k, v in macros().items():
        lines.append(rf"\providecommand{{\{k}}}{{{v}}}")
    write("numbers.tex", "\n".join(lines))


# ------------------------------------------------------------------------------ corpus tables

KIND_VI = {
    "GIAO_AN": "Giáo án",
    "BAI_GIANG": "Bài giảng",
    "BAI_TAP": "Bài tập",
    "PHIEU": "Phiếu bài tập",
    "DE_KIEM_TRA": "Đề kiểm tra",
    "DAP_AN": "Đáp án",
    "LOI_SAI": "Lỗi sai thường gặp",
}
KIND_ORDER = ["GIAO_AN", "BAI_GIANG", "BAI_TAP", "PHIEU", "DE_KIEM_TRA", "DAP_AN", "LOI_SAI"]


def tab_docs() -> None:
    d = CORPUS["documents"]
    rows = []
    totals = defaultdict(int)
    for k in KIND_ORDER:
        cells = [KIND_VI[k]]
        for c in (DEC, GEO):
            v = d[c]["by_kind"].get(k, {"n": 0, "pages": 0, "syllables": 0})
            cells += [str(v["n"]), str(v["pages"]), thou(v["syllables"])]
            totals[(c, "n")] += v["n"]
            totals[(c, "p")] += v["pages"]
            totals[(c, "s")] += v["syllables"]
        cells.append(str(sum(d[c]["by_kind"].get(k, {"pages": 0})["pages"] for c in (DEC, GEO))))
        rows.append(cells)
    total = [r"\textbf{Cộng}"]
    for c in (DEC, GEO):
        total += [
            rf"\textbf{{{totals[(c, 'n')]}}}",
            rf"\textbf{{{totals[(c, 'p')]}}}",
            rf"\textbf{{{thou(totals[(c, 's')])}}}",
        ]
    total.append(rf"\textbf{{{sum(totals[(c, 'p')] for c in (DEC, GEO))}}}")
    rows.append(total)
    head = [
        r"\multirow{2}{*}{Loại tài liệu}",
        r"\multicolumn{3}{c}{Số thập phân}",
        r"\multicolumn{3}{c}{Diện tích tam giác, hình thang}",
        r"\multirow{2}{*}{\makecell{Tổng\\trang}}",
    ]
    body = [
        r"\small",
        r"\begin{tabular}{@{}lrrrrrrr@{}}",
        r"\toprule",
        " & ".join(head) + r" \\",
        r"\cmidrule(lr){2-4}\cmidrule(lr){5-7}",
    ]
    body.append(r" & Tệp & Trang & Âm tiết & Tệp & Trang & Âm tiết & \\")
    body.append(r"\midrule")
    for i, r in enumerate(rows):
        if i == len(rows) - 1:
            body.append(r"\midrule")
        body.append(" & ".join(r) + r" \\")
    body += [r"\bottomrule", r"\end{tabular}"]
    write("tab-docs.tex", "\n".join(body))


def tab_reading() -> None:
    d = CORPUS["documents"]

    def row(label: str, f) -> list[str]:
        a, b = f(d[DEC]), f(d[GEO])
        return [label, thou(a), thou(b), thou(a + b)]

    rows = [
        row("Trang tài liệu", lambda x: x["reads"]["pages"]),
        row("Đọc từ lớp chữ của PDF", lambda x: x["reads"]["text_layer"]),
        row(r"Đọc lại bằng mô hình ảnh (OCR)", lambda x: x["reads"]["ocr"]),
        row(r"\quad vì có ảnh (phân số là ảnh)", lambda x: x["reads"]["reason"].get("IMAGES", 0)),
        row(r"\quad vì có hình vẽ", lambda x: x["reads"]["reason"].get("FIGURE", 0)),
        row(r"Số chỉ OCR đọc được (phân số, số đo trên hình)", lambda x: x["reads"]["numbers_added"]),
        row(r"Trang được mô hình thứ hai xác nhận", lambda x: x["reads"]["confirmed_pages"]),
        row(r"Số hai lần đọc không khớp, chờ giáo viên", lambda x: x["reads"]["disputed_numbers"]),
        row(r"Trang cần giáo viên xem lại", lambda x: x["reads"]["needs_review"]),
    ]
    write(
        "tab-reading.tex",
        table(
            r"@{}lrrr@{}",
            ["Chỉ số", "Số thập phân", "Diện tích", "Cộng"],
            rows,
            mid={0, 2, 4},
        ),
    )


STATUS_VI = {
    "VERIFIED": "Đã kiểm đúng",
    "REVIEW": "Cần xem lại",
    "CONFLICT": "Mâu thuẫn",
    "DISPUTED": "Hai nguồn lệch",
    "UNCHECKED": "Chưa kiểm được",
}
CHECK_VI = {
    "RELATION": "Quan hệ viết trong đáp án",
    "CONVERSION": "Đổi đơn vị, phân số $\\leftrightarrow$ số thập phân",
    "ROUNDING": "Làm tròn",
    "COMPARE": "So sánh",
    "ORDER": "Sắp xếp thứ tự",
    "RANGE": "Tìm $x$ trong khoảng",
    "PLACE": "Hàng, giá trị theo hàng",
    "COMPOSE": "Gộp, tách số",
    "AREA": "Diện tích, chiều cao, đáy",
    "CHOICE": "Phương án trắc nghiệm",
    "TRUE_FALSE": "Đúng/Sai",
    "WORDS": "Đọc số bằng chữ",
    "DIGIT": "Chữ số",
    "EXTREME": "Số lớn nhất, bé nhất",
    "EQUAL": "Số bằng nhau",
    "GROUNDED": "Số có trong đề",
}


def tab_bank() -> None:
    b = CORPUS["banks"]
    src = {"PHIEU": "Phiếu bài tập", "BAI_TAP": "Bài tập", "DE_KIEM_TRA": "Đề kiểm tra"}
    rows = [
        ["Số câu hỏi", str(b[DEC]["items"]), str(b[GEO]["items"]), str(b[DEC]["items"] + b[GEO]["items"])]
    ]
    for k, label in src.items():
        a, c = b[DEC]["source"].get(k, 0), b[GEO]["source"].get(k, 0)
        rows.append([rf"\quad từ {label.lower()}", str(a), str(c), str(a + c)])
    rows.append(
        [
            "Câu của đề kiểm tra cuối chương",
            str(b[DEC]["assessment"]),
            str(b[GEO]["assessment"]),
            str(b[DEC]["assessment"] + b[GEO]["assessment"]),
        ]
    )
    rows.append(
        [
            "Câu có hình vẽ",
            str(b[DEC]["figure"]),
            str(b[GEO]["figure"]),
            str(b[DEC]["figure"] + b[GEO]["figure"]),
        ]
    )
    mid = {len(rows) - 1}
    for k, label in STATUS_VI.items():
        a, c = b[DEC]["status"].get(k, 0), b[GEO]["status"].get(k, 0)
        rows.append([label, str(a), str(c), str(a + c)])
    write(
        "tab-bank.tex",
        table(
            r"@{}lrrr@{}",
            ["Chỉ số", "Số thập phân", "Diện tích", "Cộng"],
            rows,
            mid={len(src) + 0, len(src) + 2, *mid},
        ),
    )
    # the checks themselves
    kinds = sorted(
        {k for c in b for k in b[c]["checks"]},
        key=lambda k: (-sum(b[c]["checks"].get(k, {"n": 0})["n"] for c in b), k),
    )
    rows2 = []
    for k in kinds:
        n = sum(b[c]["checks"].get(k, {"n": 0})["n"] for c in b)
        ok = sum(b[c]["checks"].get(k, {"ok": 0})["ok"] for c in b)
        rows2.append([CHECK_VI.get(k, k), str(n), str(ok), str(n - ok)])
    n_all = sum(int(r[1]) for r in rows2)
    ok_all = sum(int(r[2]) for r in rows2)
    rows2.append(
        [r"\textbf{Cộng}", rf"\textbf{{{n_all}}}", rf"\textbf{{{ok_all}}}", rf"\textbf{{{n_all - ok_all}}}"]
    )
    write(
        "tab-checks.tex",
        table(r"@{}lrrr@{}", ["Phép kiểm chính xác", "Số lần", "Khớp", "Lệch"], rows2, mid={len(rows2) - 2}),
    )


TYPE_VI = {
    "numeric": "Điền số",
    "open": "Đáp án mở",
    "boolean": "Đúng/Sai",
    "choice": "Trắc nghiệm",
    "compare": "So sánh",
    "order": "Sắp xếp",
}
PURPOSE_VI = {
    "PRACTICE": "Luyện tập",
    "CONCEPT_CHECK": "Kiểm tra hiểu",
    "EXIT": "Kiểm tra cuối tiết",
    "REVIEW": "Ôn tập",
}


def tab_plan_nodes() -> None:
    p = CORPUS["plans"]
    rows = []
    for c in (DEC, GEO):
        for n in p[c]["node_list"]:
            short = n["id"].split("-")[1]
            rule = n["pass_rule"]
            pre = ", ".join(x.split("-")[1] for x in n["prerequisites"]) or "—"
            if len(n["prerequisites"]) > 4:
                pre = f"{len(n['prerequisites'])} tiết"
            rows.append(
                [
                    f"{CH_SHORT[c]}-{short}",
                    tex_escape(n["name"]),
                    "cơ bản" if n["layer"] == "BASIC" else "thực hành",
                    pre,
                    str(n["theory"]),
                    str(n["examples"]),
                    str(n["checks"]),
                    str(n["completion"]),
                    str(n["practice"]),
                    str(n["transfer"]),
                    str(n["key_ideas"]),
                    str(rule["min_forms"])
                    + (r", \textbf{G}" if rule["require_explanation"] else "")
                    + (r"\textbf{Đ}" if rule["require_application"] else ""),
                ]
            )
    head = [
        "Tiết",
        "Tên tiết",
        "Lớp",
        "Sau",
        r"\rotatebox{90}{Cách giảng}",
        r"\rotatebox{90}{Ví dụ mẫu}",
        r"\rotatebox{90}{Kiểm tra hiểu}",
        r"\rotatebox{90}{Cùng làm}",
        r"\rotatebox{90}{Luyện tập}",
        r"\rotatebox{90}{Chuyển giao}",
        r"\rotatebox{90}{Ý chính}",
        r"\rotatebox{90}{Dạng, G/Đ}",
    ]
    out = [
        r"\scriptsize",
        r"\begin{tabularx}{\linewidth}{@{}l>{\raggedright\arraybackslash}Xllrrrrrrrr@{}}",
        r"\toprule",
        " & ".join(head) + r" \\",
        r"\midrule",
    ]
    for i, r in enumerate(rows):
        if i == p[DEC]["nodes"]:
            out.append(r"\midrule")
        out.append(" & ".join(r) + r" \\")
    out += [r"\bottomrule", r"\end{tabularx}"]
    write("tab-plan-nodes.tex", "\n".join(out))


def tab_plan_stats() -> None:
    p = CORPUS["plans"]
    rows: list[list[str]] = []

    def add(label, f):
        a, b = f(p[DEC]), f(p[GEO])
        rows.append([label, str(a), str(b), str(a + b)])

    add("Số tiết (đỉnh của đồ thị)", lambda x: x["nodes"])
    add(r"Quan hệ \textsc{prerequisite}", lambda x: x["relations"].get("PREREQUISITE", 0))
    add(r"Quan hệ \textsc{application}", lambda x: x["relations"].get("APPLICATION", 0))
    add("Số tầng của đồ thị", lambda x: x["depth"])
    mid = {3}
    add("Câu hỏi trong phương án dạy", lambda x: x["items"]["n"])
    for t in ("numeric", "open", "choice", "boolean", "compare", "order"):
        add(rf"\quad {TYPE_VI[t].lower()}", lambda x, t=t: x["items"]["by_type"].get(t, 0))
    mid.add(len(rows) - 1)
    for lv, label in (("A", "A nhận biết"), ("B", "B kỹ năng"), ("C", "C lập luận"), ("D", "D vận dụng")):
        add(rf"\quad mức {label}", lambda x, lv=lv: x["items"]["by_level"].get(lv, 0))
    mid.add(len(rows) - 1)
    add("Câu có gợi ý đã soạn", lambda x: x["items"]["with_hints"])
    add("Gợi ý (bậc H1--H3)", lambda x: x["items"]["hints"])
    add("Câu của đề kiểm tra cuối chương", lambda x: x["assessment_items"])
    mid.add(len(rows) - 1)
    add("Lỗi sai của giáo viên", lambda x: x["misconceptions"]["n"])
    add(r"\quad mức nghiêm trọng", lambda x: x["misconceptions"]["critical"])
    add("Câu bị loại khỏi phương án", lambda x: x["left_out"])
    write(
        "tab-plan-stats.tex",
        table(r"@{}lrrr@{}", ["Đối tượng", "Số thập phân", "Diện tích", "Cộng"], rows, mid=mid),
    )


def tab_drafts() -> None:
    p = CORPUS["plans"]
    kinds = ["HINT", "KEY_IDEA", "ACCEPT", "REPLY", "ASK"]
    kind_vi = {
        "HINT": "Gợi ý H1--H3 của câu",
        "KEY_IDEA": "Ý chính của bài kể lại",
        "ACCEPT": "Cách nói được chấp nhận",
        "REPLY": "Câu trả lời mẫu",
        "ASK": "Câu hỏi giải thích thiếu",
    }
    rows = []
    for k in kinds:
        n = sum(p[c]["drafts"]["by_kind"].get(k, {"n": 0})["n"] for c in p)
        ok = sum(p[c]["drafts"]["by_kind"].get(k, {"ok": 0})["ok"] for c in p)
        if n:
            rows.append([kind_vi[k], str(n), str(ok), pct(ok / n)])
    n_all, ok_all = sum(int(r[1]) for r in rows), sum(int(r[2]) for r in rows)
    rows.append(
        [
            r"\textbf{Cộng}",
            rf"\textbf{{{n_all}}}",
            rf"\textbf{{{ok_all}}}",
            rf"\textbf{{{pct(ok_all / n_all)}}}",
        ]
    )
    write(
        "tab-drafts.tex",
        table(
            r"@{}lrrr@{}",
            ["Loại đoạn do mô hình soạn", "Soạn", "Qua kiểm", "Tỉ lệ"],
            rows,
            mid={len(rows) - 2},
        ),
    )
    codes: dict[str, int] = defaultdict(int)
    for c in p:
        for k, v in p[c]["drafts"]["codes"].items():
            codes[k] += v
    code_vi = {
        "NEW_MATH_TERM": "Dùng thuật ngữ Toán không có trong đề hay quy tắc",
        "MISSING_QUESTION": "Không kết thúc bằng một câu hỏi",
        "UNGROUNDED_NUMBER": "Dùng số không có trong đề của câu",
        "MULTIPLE_QUESTIONS": "Nhiều hơn một câu hỏi",
        "EMPTY": "Rỗng",
        "NOT_IN_THE_RULE": "Ý chính không có trong quy tắc",
        "ANSWER_LEAK": "Nói ra đáp án",
        "TOO_LONG": "Quá dài",
    }
    rows = [
        [f"\\code{{{tex_escape(k)}}}", code_vi.get(k, k), str(v)]
        for k, v in sorted(codes.items(), key=lambda kv: -kv[1])
    ]
    write(
        "tab-draft-codes.tex",
        table(r"@{}llr@{}", ["Mã", "Lý do bị loại", "Lần"], rows),
    )
    # decisions of the review
    target_vi = {
        "hint": "Gợi ý của câu",
        "item": "Câu hỏi (đáp án, dạng chấm, tiết)",
        "node": "Tiết (nội dung chung)",
        "node/theory": "Cách giảng",
        "node/worked_examples": "Ví dụ mẫu",
        "node/pass_rule": "Luật qua tiết",
        "node/explain": "Ý chính, bài kể lại",
        "node/method": "Phương pháp",
    }
    targets: dict[str, int] = defaultdict(int)
    for c in p:
        for k, v in p[c]["decisions"]["by_target"].items():
            targets[k] += v
    rows = [[target_vi.get(k, k), str(v)] for k, v in sorted(targets.items(), key=lambda kv: -kv[1])]
    write("tab-decisions.tex", table(r"@{}lr@{}", ["Đối tượng được duyệt", "Quyết định"], rows))


def tab_chunks() -> None:
    kind_vi = {
        "theory": "Cách giảng lý thuyết",
        "method": "Phương pháp",
        "worked_example": "Ví dụ mẫu",
        "misconception_note": "Ghi chú lỗi sai",
        "source_passage": "Đoạn tài liệu giáo viên",
    }
    rows = []
    pub = RAG["corpus"]["published"]["by_kind"]
    total_n = sum(v["n"] for v in pub.values())
    for k in kind_vi:
        v = pub[k]
        rows.append(
            [
                kind_vi[k],
                str(v["n"]),
                num(v["mean"], 0),
                str(v["median"]).replace(".", ","),
                f"{v['p10']}--{v['p90']}",
                str(v["max"]),
                thou(v["total"]),
            ]
        )
    rows.append(
        [
            r"\textbf{Cộng}",
            rf"\textbf{{{total_n}}}",
            "",
            "",
            "",
            "",
            rf"\textbf{{{thou(sum(v['total'] for v in pub.values()))}}}",
        ]
    )
    write(
        "tab-chunks.tex",
        table(
            r"@{}lrrrrrr@{}",
            ["Loại đoạn", "Số đoạn", "TB", "Trung vị", "P10--P90", "Lớn nhất", "Âm tiết"],
            rows,
            mid={len(rows) - 2},
        ),
    )


# ------------------------------------------------------------------------------ knowledge graphs


def fig_graph() -> None:
    plans = CORPUS["plans"]
    out = [
        r"\begin{tikzpicture}[x=1cm,y=1cm,",
        r"  basic/.style={circle,draw=cavat,fill=soft,line width=0.8pt,minimum size=8.6mm,inner sep=0pt,font=\scriptsize\bfseries},",
        r"  impl/.style={rounded corners=2.5pt,draw=llm,fill=llmsoft,line width=0.8pt,minimum width=9.6mm,minimum height=7.2mm,inner sep=0pt,font=\scriptsize\bfseries},",
        r"  pre/.style={-{Latex[length=1.8mm]},draw=cavat,line width=0.9pt},",
        r"  app/.style={-{Latex[length=1.5mm]},draw=llm!80!black,dash pattern=on 2.2pt off 1.6pt,line width=0.5pt}]",
    ]
    y0 = {DEC: 0.0, GEO: -6.3}
    titles = {
        DEC: r"(a) Số thập phân: 11 tiết, 8 tầng",
        GEO: r"(b) Diện tích tam giác, hình thang: 8 tiết, 5 tầng",
    }
    dx = 1.62
    for c in (DEC, GEO):
        nodes = plans[c]["node_list"]
        by_depth: dict[int, list[dict]] = defaultdict(list)
        for n in nodes:
            by_depth[n["depth"]].append(n)
        pos: dict[str, tuple[float, float]] = {}
        for d, ns in by_depth.items():
            k = len(ns)
            for i, n in enumerate(ns):
                y = y0[c] + (i - (k - 1) / 2) * -1.15 + (0.0 if k == 1 else 0.0)
                pos[n["id"]] = (d * dx, y)
        out.append(
            rf"  \node[anchor=west,font=\small\bfseries] at (-0.5,{y0[c] + (1.5 if c == DEC else 2.2):.2f}) {{{titles[c]}}};"
        )
        for n in nodes:
            x, y = pos[n["id"]]
            style = "basic" if n["layer"] == "BASIC" else "impl"
            short = n["id"].split("-")[1]
            out.append(rf"  \node[{style}] ({c[-3:]}{short}) at ({x:.2f},{y:.2f}) {{{short}}};")
        pre = [e for e in plans[c]["edges"] if e["type"] == "PREREQUISITE"]
        app = [e for e in plans[c]["edges"] if e["type"] == "APPLICATION"]
        # application edges first (underneath), curved away from the row
        for e in app:
            a, b = e["source"].split("-")[1], e["target"].split("-")[1]
            (xa, ya), (xb, yb) = pos[e["source"]], pos[e["target"]]
            span = abs(xb - xa) / dx
            if span <= 1.01 and abs(ya - yb) < 0.2:
                out.append(rf"  \draw[app] ({c[-3:]}{a}) -- ({c[-3:]}{b});")
            else:
                bend = "bend right" if (yb <= ya + 0.01) else "bend left"
                angle = min(42, 12 + 5 * span)
                out.append(rf"  \draw[app] ({c[-3:]}{a}) to[{bend}={angle:.0f}] ({c[-3:]}{b});")
        for e in pre:
            a, b = e["source"].split("-")[1], e["target"].split("-")[1]
            out.append(rf"  \draw[pre] ({c[-3:]}{a}) -- ({c[-3:]}{b});")
    # legend
    out += [
        r"  \begin{scope}[shift={(0.0,-9.9)}]",
        r"    \node[basic] at (0,0) {};\node[anchor=west,font=\scriptsize] at (0.4,0) {tiết hình thành khái niệm (lớp cơ bản)};",
        r"    \node[impl] at (6.3,0) {};\node[anchor=west,font=\scriptsize] at (6.8,0) {tiết thực hành, vận dụng};",
        r"    \draw[pre] (0,-0.75) -- (0.9,-0.75);\node[anchor=west,font=\scriptsize] at (1.0,-0.75) {\textsc{prerequisite}: học tiết trước mới học tiết sau};",
        r"    \draw[app] (7.6,-0.75) -- (8.5,-0.75);\node[anchor=west,font=\scriptsize] at (8.6,-0.75) {\textsc{application}};",
        r"  \end{scope}",
        r"\end{tikzpicture}",
    ]
    write("fig-graph.tex", "\n".join(out))


# ------------------------------------------------------------------------------ ingestion pipeline


def fig_pipeline() -> None:
    m = macros()
    out = [
        r"\begin{tikzpicture}[x=1cm,y=1cm,",
        r"  stage/.style={draw=cavat,rounded corners=2pt,fill=soft,align=left,font=\scriptsize,text width=3.35cm,inner sep=4pt,minimum height=20mm},",
        r"  model/.style={stage,draw=llm,fill=llmsoft},",
        r"  human/.style={stage,draw=ink,fill=gray!12},",
        r"  head/.style={font=\scriptsize\bfseries,align=left},",
        r"  arr/.style={-{Latex[length=2mm]},thick,draw=ink!70}]",
        rf"  \node[human] (docs) at (0,0) {{\textbf{{1. Tài liệu}}\\ {m['NDocs']} tệp PDF của giáo viên,\\ {m['NPages']} trang, {m['NSyll']} âm tiết;\\ 7 loại: giáo án, bài giảng, bài tập, phiếu, đề, đáp án, lỗi sai}};",
        rf"  \node[model] (read) at (4.0,0) {{\textbf{{2. Đọc từng trang}}\\ lớp chữ: {m['NPagesText']} trang;\\ đọc lại bằng Gemini: {m['NPagesOcr']} trang (ảnh, hình vẽ);\\ kiểm số \DI{{43}}; mô hình thứ hai xác nhận}};",
        r"  \node[stage] (parse) at (8.0,0) {\textbf{3. Phân tích tất định}\\ cắt câu hỏi, đáp án, bài kể lại, lỗi sai;\\ gắn câu vào tiết của giáo án;\\ không dùng mô hình};",
        rf"  \node[stage] (verify) at (12.0,0) {{\textbf{{4. Kiểm đáp án chính xác}}\\ {m['NItems']} câu: {m['NVerified']} đã kiểm đúng;\\ {m['NConflict']} mâu thuẫn, {m['NDisputedItems']} lệch,\\ {m['NReviewItems']} xem lại, {m['NUnchecked']} chưa kiểm được}};",
        rf"  \node[stage] (plan) at (12.0,-3.1) {{\textbf{{5. Phương án dạy}}\\ đồ thị {m['NNodes']} tiết, {m['NEdges']} quan hệ;\\ {m['NPlanItems']} câu, {m['NMisconceptions']} lỗi sai;\\ lý thuyết, phương pháp, ví dụ lấy từ lời giáo viên}};",
        rf"  \node[model] (draft) at (8.0,-3.1) {{\textbf{{6. Mô hình soạn phần thiếu}}\\ {m['NDrafts']} đoạn (gợi ý, ý chính,\\ cách nói chấp nhận); bộ kiểm chứng\\ giữ {m['NDraftsOk']} đoạn}};",
        rf"  \node[human] (review) at (4.0,-3.1) {{\textbf{{7. Duyệt}}\\ {m['NDecisions']} quyết định:\\ {m['NApprove']} chấp nhận, {m['NEdit']} sửa,\\ {m['NReject']} loại; mỗi quyết định ghi người duyệt}};",
        rf"  \node[stage] (index) at (0,-3.1) {{\textbf{{8. Chỉ mục truy xuất}}\\ {m['NChunks']} đoạn ({m['NPassages']} đoạn tài liệu);\\ BM25 hai dạng và vector {m['NVecDim']} chiều;\\ gắn mỗi đoạn vào tiết}};",
        r"  \draw[arr] (docs) -- (read);\draw[arr] (read) -- (parse);\draw[arr] (parse) -- (verify);",
        r"  \draw[arr] (verify) -- (plan);\draw[arr] (plan) -- (draft);\draw[arr] (draft) -- (review);\draw[arr] (review) -- (index);",
        r"  \node[draw=cavat,fill=soft,minimum width=3mm,minimum height=3mm,inner sep=0pt] at (0.2,-5.35) {};\node[anchor=west,font=\scriptsize] at (0.45,-5.35) {thành phần tất định};",
        r"  \node[draw=llm,fill=llmsoft,minimum width=3mm,minimum height=3mm,inner sep=0pt] at (4.2,-5.35) {};\node[anchor=west,font=\scriptsize] at (4.45,-5.35) {có gọi mô hình ngôn ngữ (kết quả luôn qua bộ kiểm)};",
        r"  \node[draw=ink,fill=gray!12,minimum width=3mm,minimum height=3mm,inner sep=0pt] at (11.2,-5.35) {};\node[anchor=west,font=\scriptsize] at (11.45,-5.35) {con người};",
        r"\end{tikzpicture}",
    ]
    write("fig-pipeline.tex", "\n".join(out))


# ------------------------------------------------------------------------------ chunk figures

KIND_COLOUR = {
    "theory": "cavat",
    "method": "okgreen",
    "worked_example": "oksky",
    "misconception_note": "llm",
    "source_passage": "gray",
}
KIND_LABEL = {
    "theory": "cách giảng",
    "method": "phương pháp",
    "worked_example": "ví dụ mẫu",
    "misconception_note": "lỗi sai",
    "source_passage": "đoạn tài liệu",
}


def legend_tikz(items: list[tuple[str, str, str]], per_char: float = 0.135) -> str:
    """A legend drawn by hand under a plot: (label, kind, tikz options); kind is box or line."""
    out = [r"\begin{tikzpicture}[x=1cm,y=1cm]"]
    x = 0.0
    for label, kind, opts in items:
        if kind == "box":
            out.append(
                rf"\node[draw=none,fill={opts},minimum width=2.6mm,minimum height=2.6mm,inner sep=0pt] at ({x:.2f},0) {{}};"
            )
            x += 0.28
        else:
            out.append(rf"\draw[{opts},line width=0.9pt] ({x - 0.15:.2f},0) -- ({x + 0.45:.2f},0);")
            out.append(rf"\node[circle,fill=none,inner sep=0pt] at ({x + 0.15:.2f},0) {{}};")
            x += 0.62
        out.append(rf"\node[anchor=west,font=\scriptsize,inner sep=1pt] at ({x:.2f},0) {{{label}}};")
        x += len(label) * per_char + 0.45
    out.append(r"\end{tikzpicture}")
    return "\n".join(out)


def fig_chunks() -> None:
    pub = RAG["corpus"]["published"]
    kinds = list(KIND_LABEL)
    out = [
        r"\begin{tikzpicture}",
        r"\begin{groupplot}[group style={group size=2 by 1,horizontal sep=1.6cm},cavat]",
    ]
    # (a) the length of a chunk by kind: box q1-q3, median, whiskers p10-p90 (drawn by hand)
    out += [
        r"\nextgroupplot[title={(a) Độ dài đoạn theo loại},width=6.4cm,height=5.4cm,ylabel={âm tiết},ymin=0,ymax=320,xmin=0.4,xmax=5.6,"
        rf"xtick={{1,2,3,4,5}},xticklabels={{{','.join(KIND_LABEL[k] for k in kinds)}}},x tick label style={{rotate=30,anchor=east,font=\scriptsize}},"
        r"ymajorgrids]"
    ]
    for i, k in enumerate(kinds, 1):
        v = pub["by_kind"][k]
        c = KIND_COLOUR[k]
        out.append(rf"\draw[{c},line width=0.8pt] (axis cs:{i},{v['p10']}) -- (axis cs:{i},{v['q1']});")
        out.append(rf"\draw[{c},line width=0.8pt] (axis cs:{i},{v['q3']}) -- (axis cs:{i},{v['p90']});")
        out.append(
            rf"\draw[{c},line width=0.8pt] (axis cs:{i - 0.12},{v['p10']}) -- (axis cs:{i + 0.12},{v['p10']});"
        )
        out.append(
            rf"\draw[{c},line width=0.8pt] (axis cs:{i - 0.12},{v['p90']}) -- (axis cs:{i + 0.12},{v['p90']});"
        )
        out.append(
            rf"\filldraw[fill={c}!25,draw={c},line width=0.8pt] (axis cs:{i - 0.27},{v['q1']}) rectangle (axis cs:{i + 0.27},{v['q3']});"
        )
        out.append(
            rf"\draw[{c},line width=1.6pt] (axis cs:{i - 0.27},{v['median']}) -- (axis cs:{i + 0.27},{v['median']});"
        )
        out.append(
            rf"\node[font=\tiny,color=mute,anchor=south] at (axis cs:{i},{v['p90'] + 4}) {{n={v['n']}}};"
        )
    out.append(r"\draw[dashed,color=ink!60,line width=0.5pt] (axis cs:0.4,150) -- (axis cs:5.6,150);")
    out.append(r"\draw[dashed,color=ink!60,line width=0.5pt] (axis cs:0.4,300) -- (axis cs:5.6,300);")
    out.append(
        r"\node[font=\tiny,color=mute,anchor=south west] at (axis cs:0.45,152) {150};\node[font=\tiny,color=mute,anchor=south west] at (axis cs:0.45,302) {300};"
    )
    # (b) chunks of each node, stacked
    nodes = sorted(pub["per_node"], key=lambda n: (n.split("-")[0] != "STP", n))
    labels = [n.replace("STP-T", "S").replace("DTTGHT-T", "D") for n in nodes]
    out.append(
        r"\nextgroupplot[title={(b) Đoạn của từng tiết},width=8.2cm,height=5.4cm,ybar stacked,bar width=5pt,ymin=0,"
        r"ylabel={số đoạn},symbolic x coords={"
        + ",".join(labels)
        + r"},xtick=data,x tick label style={rotate=90,anchor=east,font=\tiny},ymajorgrids,enlarge x limits=0.04]"
    )
    for k in kinds:
        coords = " ".join(f"({lab},{pub['per_node'][n][k]})" for lab, n in zip(labels, nodes, strict=True))
        out.append(rf"\addplot+[fill={KIND_COLOUR[k]}!70,draw=none] coordinates {{{coords}}};")
    out += [r"\end{groupplot}", r"\end{tikzpicture}", r"\\[4pt]"]
    out.append(legend_tikz([(KIND_LABEL[k], "box", f"{KIND_COLOUR[k]}!70") for k in kinds]))
    write("fig-chunks.tex", "\n".join(out))


# ------------------------------------------------------------------------------ retrieval figures

CONFIG_LABEL = {
    "keyword": "Từ khóa",
    "semantic": "Ngữ nghĩa",
    "hybrid": "Lai",
    "keyword+rerank": "Từ khóa + xếp hạng lại",
    "hybrid+rerank": "Lai + xếp hạng lại",
    "flat-hybrid": "Lai phẳng",
    "flat-hybrid+rerank": "Lai phẳng + xếp hạng lại",
}
SET_LABEL = {
    "published_tune": "Phát hành, bộ chỉnh (18)",
    "published_holdout_v1": "Phát hành, giữ riêng v1 (14)",
    "published_holdout_v2": "Phát hành, giữ riêng v2 (20)",
    "sample_tune": "Chương mẫu, bộ chỉnh (57)",
    "sample_holdout": "Chương mẫu, giữ riêng (15)",
}
SET_COLOUR = {
    "published_tune": "cavat!45",
    "published_holdout_v1": "cavat!75",
    "published_holdout_v2": "cavat!60!black",
    "sample_tune": "llm!55",
    "sample_holdout": "llm!90!black",
}
ABLATION = ["keyword", "semantic", "hybrid", "keyword+rerank", "hybrid+rerank"]


def metric(set_name: str, config: str, key: str, routing: str = "on") -> float:
    return RAG["sets"][set_name]["configs"][config][routing]["metrics"][key]


def fig_ablation() -> None:
    labels = ["Từ khóa", "Ngữ nghĩa", "Lai", "Từ khóa+XH", "Lai+XH"]
    out = [
        r"\begin{tikzpicture}",
        r"\begin{groupplot}[group style={group size=2 by 1,horizontal sep=1.5cm},cavat,"
        r"width=7.9cm,height=5.2cm,ymin=0,ymax=1.05,ymajorgrids,symbolic x coords={"
        + ",".join(labels)
        + r"},xtick=data,"
        r"x tick label style={rotate=25,anchor=east,font=\scriptsize},enlarge x limits=0.12]",
    ]
    for title, key in (("(a) MRR", "mrr"), ("(b) Hit@3", "hit3")):
        out.append(rf"\nextgroupplot[title={{{title}}},ybar,bar width=4.2pt]")
        for s in SET_LABEL:
            coords = " ".join(
                f"({lab},{num(metric(s, c, key), 3).replace(',', '.')})"
                for lab, c in zip(labels, ABLATION, strict=True)
            )
            out.append(rf"\addplot+[fill={SET_COLOUR[s]},draw=none] coordinates {{{coords}}};")
    out += [r"\end{groupplot}", r"\end{tikzpicture}", r"\\[4pt]"]
    out.append(legend_tikz([(SET_LABEL[k], "box", SET_COLOUR[k]) for k in list(SET_LABEL)[:3]]))
    out.append(r"\\[1pt]")
    out.append(legend_tikz([(SET_LABEL[k], "box", SET_COLOUR[k]) for k in list(SET_LABEL)[3:]]))
    write("fig-ablation.tex", "\n".join(out))


def fig_hitk() -> None:
    out = [
        r"\begin{tikzpicture}",
        r"\begin{groupplot}[group style={group size=3 by 1,horizontal sep=1.0cm,y descriptions at=edge left},cavat,"
        r"width=5.6cm,height=5.0cm,ymin=0.3,ymax=1.03,xmin=1,xmax=10,xtick={1,3,5,7,10},ymajorgrids,xlabel={$k$},]",
    ]
    titles = {
        "published_tune": "(a) bộ chỉnh",
        "published_holdout_v1": "(b) giữ riêng v1",
        "published_holdout_v2": "(c) giữ riêng v2",
    }
    for i, s in enumerate(titles):
        extra = ",ylabel={Hit@$k$}" if i == 0 else ""
        out.append(rf"\nextgroupplot[title={{{titles[s]}}}{extra}]")
        series = [
            ("hybrid+rerank", "off", "ink!60", "dashed", "square*"),
            ("hybrid+rerank", "on", "cavat", "solid", "*"),
            ("flat-hybrid", "on", "llm", "dotted", "triangle*"),
        ]
        for cfg, routing, colour, style, mark in series:
            hk = RAG["sets"][s]["configs"][cfg][routing]["metrics"]["hit_k"]
            coords = " ".join(f"({k},{hk[str(k)]:.3f})" for k in range(1, 11))
            out.append(
                rf"\addplot[color={colour},{style},line width=0.9pt,mark={mark},mark size=1.4pt] coordinates {{{coords}}};"
            )
    out += [r"\end{groupplot}", r"\end{tikzpicture}", r"\\[4pt]"]
    out.append(
        legend_tikz(
            [
                ("không định tuyến", "line", "color=ink!60,dashed"),
                ("có định tuyến (sản phẩm)", "line", "color=cavat"),
                ("RAG phẳng, không đồ thị", "line", "color=llm,dotted"),
            ]
        )
    )
    write("fig-hitk.tex", "\n".join(out))


def fig_sweep() -> None:
    sweep = RAG["sweep"]
    labels = [("tắt" if r["margin"] >= 9 else num(r["margin"], 3).rstrip("0").rstrip(",")) for r in sweep]
    labels = [lab if lab else "0" for lab in labels]
    ticks = ",".join("{" + lab + "}" for lab in labels)
    out = [
        r"\begin{tikzpicture}",
        r"\begin{axis}[cavat,width=0.8\linewidth,height=5.2cm,ymin=0.4,ymax=1.0,ymajorgrids,xmin=-0.4,xmax=9.4,"
        r"xlabel={lề định tuyến $\varepsilon$ (cosine)},ylabel={MRR},"
        rf"xtick={{0,1,2,3,4,5,6,7,8,9}},xticklabels={{{ticks}}},x tick label style={{font=\scriptsize}}]",
    ]
    series = [
        ("published_tune", "ink!60", "mark=square*"),
        ("published_holdout_v1", "llm", "mark=triangle*"),
        ("published_holdout_v2", "cavat", "mark=*"),
    ]
    for key, colour, mark in series:
        coords = " ".join(f"({i},{r[key]['mrr']:.3f})" for i, r in enumerate(sweep))
        out.append(rf"\addplot[color={colour},{mark},mark size=1.6pt] coordinates {{{coords}}};")
    prod = next(i for i, r in enumerate(sweep) if abs(r["margin"] - RAG["meta"]["route_margin"]) < 1e-9)
    out.append(rf"\draw[dashed,color=ink!60] (axis cs:{prod},0.4) -- (axis cs:{prod},1.0);")
    out.append(
        rf"\node[font=\scriptsize,color=ink!70,anchor=south west] at (axis cs:{prod + 0.1},0.41) {{sản phẩm $\varepsilon=0{{,}}02$}};"
    )
    out += [r"\end{axis}", r"\end{tikzpicture}", r"\\[4pt]"]
    out.append(
        legend_tikz(
            [
                ("bộ chỉnh", "line", "color=ink!60"),
                ("giữ riêng v1", "line", "color=llm"),
                ("giữ riêng v2 (đóng băng)", "line", "color=cavat"),
            ]
        )
    )
    write("fig-sweep.tex", "\n".join(out))


def fig_grounding() -> None:
    import random

    rng = random.Random(7)
    on: list[float] = []
    later: list[float] = []
    off_math: list[float] = []
    off_other: list[float] = []
    for v in RAG["sets"].values():
        for r in v["configs"]["hybrid+rerank"]["on"]["rows"]:
            c = r["best_cosine"]
            if r["relevant"]:
                on.append(c)
            elif r["group"] == "bai-sau":
                later.append(c)
            elif r["group"] == "lac-de-toan":
                off_math.append(c)
            else:
                off_other.append(c)
    rows = [
        (f"Trong phạm vi (n={len(on)})", on, "cavat", "*"),
        (f"Bài sau (n={len(later)})", later, "llm", "triangle*"),
        (f"Toán ngoài chương (n={len(off_math)})", off_math, "llm", "square*"),
        (f"Lạc đề (n={len(off_other)})", off_other, "ink!70", "diamond*"),
    ]
    out = [
        r"\begin{tikzpicture}",
        r"\begin{axis}[cavat,width=0.88\linewidth,height=5.0cm,xmin=0.45,xmax=0.9,ymin=0.4,ymax=4.6,xlabel={cosine lớn nhất của các đoạn được chọn},"
        r"ytick={1,2,3,4},yticklabels={"
        + ",".join(r[0] for r in reversed(rows))
        + r"},y tick label style={font=\scriptsize},xmajorgrids]",
    ]
    for i, (_label, vals, colour, mark) in enumerate(reversed(rows), 1):
        coords = " ".join(f"({v:.3f},{i + (rng.random() - 0.5) * 0.55:.3f})" for v in vals)
        out.append(
            rf"\addplot[only marks,mark={mark},mark size=1.5pt,color={colour},fill opacity=0.65,draw opacity=0.9] coordinates {{{coords}}};"
        )
    out.append(r"\draw[dashed,color=llm,line width=0.9pt] (axis cs:0.65,0.4) -- (axis cs:0.65,4.6);")
    out.append(
        r"\node[anchor=south west,font=\scriptsize,color=llm] at (axis cs:0.655,4.05) {ngưỡng $0{,}65$};"
    )
    out += [r"\end{axis}", r"\end{tikzpicture}"]
    write("fig-grounding.tex", "\n".join(out))


# ------------------------------------------------------------------------------ statistics (seeded)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, centre - half), min(1.0, centre + half))


def boot_ci(values: list[float], b: int = 4000, seed: int = 20261014) -> tuple[float, float]:
    import random

    rng = random.Random(seed)
    n = len(values)
    if not n:
        return (0.0, 0.0)
    means = sorted(sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(b))
    return (means[int(0.025 * b)], means[int(0.975 * b) - 1])


def ci(lo: float, hi: float, nd: int = 2) -> str:
    return f"[{num(lo, nd)}; {num(hi, nd)}]"


def rows_of(set_name: str, config: str, routing: str = "on", *, in_scope: bool = True) -> list[dict]:
    rows = RAG["sets"][set_name]["configs"][config][routing]["rows"]
    return [r for r in rows if r["relevant"]] if in_scope else rows


def rr(r: dict) -> float:
    return 1 / r["first"] if r["first"] else 0.0


def hit(r: dict, k: int) -> float:
    return 1.0 if r["first"] and r["first"] <= k else 0.0


# ------------------------------------------------------------------------------ retrieval tables


def tab_ablation_main() -> None:
    head = [
        r"\multirow{2}{*}{Cấu hình}",
        r"\multicolumn{4}{c}{Phát hành, giữ riêng v2 ($n=20$)}",
        r"\multicolumn{3}{c}{Chương mẫu, giữ riêng ($n=15$)}",
    ]
    out = [
        r"\small",
        r"\begin{tabular}{@{}lrrrrrrr@{}}",
        r"\toprule",
        " & ".join(head) + r" \\",
        r"\cmidrule(lr){2-5}\cmidrule(lr){6-8}",
        r" & Hit@1 & Hit@3 & MRR & KTC 95\% của MRR & Hit@1 & Hit@3 & MRR \\",
        r"\midrule",
    ]
    configs = [
        "keyword",
        "semantic",
        "hybrid",
        "keyword+rerank",
        "hybrid+rerank",
        "flat-hybrid",
        "flat-hybrid+rerank",
    ]
    best_v2 = max(metric("published_holdout_v2", c, "mrr") for c in configs)
    for i, c in enumerate(configs):
        if i == 5:
            out.append(r"\midrule")
        r2 = rows_of("published_holdout_v2", c)
        m = metric("published_holdout_v2", c, "mrr")
        lo, hi = boot_ci([rr(r) for r in r2])
        mrr_txt = num(m, 3)
        if abs(m - best_v2) < 1e-9:
            mrr_txt = rf"\best{{{mrr_txt}}}"
        cells = [
            CONFIG_LABEL[c],
            num(metric("published_holdout_v2", c, "hit1"), 2),
            num(metric("published_holdout_v2", c, "hit3"), 2),
            mrr_txt,
            ci(lo, hi),
        ]
        if c in RAG["sets"]["sample_holdout"]["configs"] and not c.startswith("flat"):
            cells += [
                num(metric("sample_holdout", c, "hit1"), 2),
                num(metric("sample_holdout", c, "hit3"), 2),
                num(metric("sample_holdout", c, "mrr"), 3),
            ]
        else:
            cells += ["--", "--", "--"]
        out.append(" & ".join(cells) + r" \\")
    out += [r"\bottomrule", r"\end{tabular}"]
    write("tab-ablation-main.tex", "\n".join(out))
    tab_ablation_v2(configs, best_v2)


def tab_ablation_v2(configs: list[str], best_v2: float) -> None:
    """The v2 columns only, narrow enough for half a page in the compact version."""
    out = [
        r"\footnotesize",
        r"\begin{tabular}{@{}lrrrr@{}}",
        r"\toprule",
        r"Cấu hình & Hit@1 & Hit@3 & MRR & KTC 95\% \\",
        r"\midrule",
    ]
    for i, c in enumerate(configs):
        if i == 5:
            out.append(r"\midrule")
        lo, hi = boot_ci([rr(r) for r in rows_of("published_holdout_v2", c)])
        m = metric("published_holdout_v2", c, "mrr")
        mrr_txt = num(m, 3)
        if abs(m - best_v2) < 1e-9:
            mrr_txt = rf"\best{{{mrr_txt}}}"
        out.append(
            " & ".join(
                [
                    CONFIG_LABEL[c],
                    num(metric("published_holdout_v2", c, "hit1"), 2),
                    num(metric("published_holdout_v2", c, "hit3"), 2),
                    mrr_txt,
                    ci(lo, hi),
                ]
            )
            + r" \\"
        )
    out += [r"\bottomrule", r"\end{tabular}"]
    write("tab-ablation-v2.tex", "\n".join(out))


def tab_ablation_full() -> None:
    out = [
        r"\small",
        r"\begin{tabular}{@{}llrrrr@{}}",
        r"\toprule",
        r"Tập câu hỏi & Cấu hình & Hit@1 & Hit@3 & Hit@5 & MRR \\",
        r"\midrule",
    ]
    names = {
        "published_tune": "Phát hành, bộ chỉnh ($n=18$)",
        "published_holdout_v1": "Phát hành, giữ riêng v1 ($n=14$)",
        "published_holdout_v2": "Phát hành, giữ riêng v2 ($n=20$)",
        "sample_tune": "Chương mẫu, bộ chỉnh ($n=57$)",
        "sample_holdout": "Chương mẫu, giữ riêng ($n=15$)",
    }
    first = True
    for s, label in names.items():
        if not first:
            out.append(r"\midrule")
        first = False
        cfgs = list(RAG["sets"][s]["configs"])
        for i, c in enumerate(cfgs):
            m = RAG["sets"][s]["configs"][c]["on"]["metrics"]
            lab = label if i == 0 else ""
            out.append(
                f"{lab} & {CONFIG_LABEL[c]} & {num(m['hit1'])} & {num(m['hit3'])} & {num(m['hit5'])} & {num(m['mrr'], 3)} \\\\"
            )
        if "off" in RAG["sets"][s]["configs"].get("hybrid+rerank", {}):
            for c in ("keyword+rerank", "hybrid+rerank"):
                m = RAG["sets"][s]["configs"][c]["off"]["metrics"]
                out.append(
                    f" & {CONFIG_LABEL[c]}, không định tuyến & {num(m['hit1'])} & {num(m['hit3'])} & {num(m['hit5'])} & {num(m['mrr'], 3)} \\\\"
                )
    out += [r"\bottomrule", r"\end{tabular}"]
    write("tab-ablation-full.tex", "\n".join(out))


def tab_routing() -> None:
    st = RAG["stats"]
    names = {
        "published_tune": "Bộ chỉnh",
        "published_holdout_v1": "Giữ riêng v1",
        "published_holdout_v2": "Giữ riêng v2",
    }
    out = [
        r"\small",
        r"\begin{tabular}{@{}lrrrrrr@{}}",
        r"\toprule",
        r"Tập & $n$ & Hit@3 trước & Hit@3 sau & MRR trước & MRR sau & McNemar $p$ \\",
        r"\midrule",
    ]
    for s, label in names.items():
        v = st[s]
        out.append(
            f"{label} & {v['n']} & {num(v['hit3_before'])} & {num(v['hit3_after'])} & "
            f"{num(sum(rr(r) for r in rows_of(s, 'hybrid+rerank', 'off')) / v['n'], 3)} & "
            f"{num(sum(rr(r) for r in rows_of(s, 'hybrid+rerank', 'on')) / v['n'], 3)} & "
            f"{num(v['mcnemar']['p'], 3)} ({v['mcnemar']['fixed']}$\\uparrow$/{v['mcnemar']['broken']}$\\downarrow$) \\\\"
        )
    out.append(r"\midrule")
    # by group on v2
    for group, label in (
        ("cung-bai", "v2: hỏi trong bài đang học"),
        ("bai-truoc", "v2: hỏi khái niệm của bài trước"),
    ):
        before = [r for r in rows_of("published_holdout_v2", "hybrid+rerank", "off") if r["group"] == group]
        after = [r for r in rows_of("published_holdout_v2", "hybrid+rerank", "on") if r["group"] == group]
        n = len(after)
        out.append(
            f"{label} & {n} & {num(sum(hit(r, 3) for r in before) / n)} & {num(sum(hit(r, 3) for r in after) / n)} & "
            f"{num(sum(rr(r) for r in before) / n, 3)} & {num(sum(rr(r) for r in after) / n, 3)} & -- \\\\"
        )
    out += [r"\bottomrule", r"\end{tabular}"]
    write("tab-routing.tex", "\n".join(out))


def tab_flat() -> None:
    fl = RAG["stats"]["flat"]
    names = {
        "published_tune": "Bộ chỉnh",
        "published_holdout_v1": "Giữ riêng v1",
        "published_holdout_v2": "Giữ riêng v2",
    }
    out = [
        r"\small",
        r"\begin{tabular}{@{}llrrrrr@{}}",
        r"\toprule",
        r"Tập & Hệ truy xuất & Hit@3 & MRR & \makecell{Đoạn bài sau\\trong top-3} & \makecell{Câu bài sau\\bị trả lời} & \makecell{Câu ngoài\\chương bị trả lời} \\",
        r"\midrule",
    ]
    labels = {
        "hybrid+rerank": "CAVAT (đồ thị)",
        "flat-hybrid": "RAG phẳng",
        "flat-hybrid+rerank": "RAG phẳng + xếp hạng lại",
    }
    first = True
    for s, label in names.items():
        if not first:
            out.append(r"\midrule")
        first = False
        for i, c in enumerate(("hybrid+rerank", "flat-hybrid", "flat-hybrid+rerank")):
            v = fl[s][c]
            # CAVAT answers a later-period question never: the tutor says "bài sau" (decisions of the set)
            if c == "hybrid+rerank":
                dec = RAG["sets"][s]["decisions"]["on"]
                later_answered = sum(1 for d in dec if d["group"] == "bai-sau" and d["outcome"] == "ANSWER")
                off_answered = sum(
                    1 for d in dec if d["group"] in ("lac-de-toan", "lac-de") and d["outcome"] == "ANSWER"
                )
            else:
                later_answered, off_answered = v["later_answered"], v["off_answered"]
            out.append(
                f"{label if i == 0 else ''} & {labels[c]} & {num(v['hit3'])} & {num(v['mrr'], 3)} & "
                f"{v['ahead']}/{v['ahead_n']} & {later_answered}/{v['later_n']} & {off_answered}/{v['off_n']} \\\\"
            )
    out += [r"\bottomrule", r"\end{tabular}"]
    write("tab-flat.tex", "\n".join(out))


def tab_rag_decisions() -> None:
    names = {
        "published_tune": "Phát hành, chỉnh",
        "published_holdout_v1": "Phát hành, v1",
        "published_holdout_v2": "Phát hành, v2",
        "sample_tune": "Mẫu, chỉnh",
        "sample_holdout": "Mẫu, giữ riêng",
    }
    group_vi = {
        "cung-bai": "hỏi trong bài đang học",
        "bai-truoc": "hỏi khái niệm bài trước",
        "bai-sau": "hỏi bài sau",
        "lac-de-toan": "Toán ngoài chương",
        "lac-de": "lạc đề",
        "trong-chuong": "trong chương",
        "co-dau": "có dấu",
        "khong-dau": "không dấu",
        "sai-chinh-ta": "sai chính tả",
        "dien-dat-khac": "diễn đạt khác",
        "chinh-sach": "theo luật dạy",
        "dinh-nghia": "định nghĩa",
    }
    expect = {
        "cung-bai": "ANSWER",
        "bai-truoc": "ANSWER",
        "bai-sau": "LATER",
        "lac-de-toan": "PARKED",
        "lac-de": "PARKED",
    }
    out = [
        r"\small",
        r"\begin{tabular}{@{}llrrrrl@{}}",
        r"\toprule",
        r"Tập & Nhóm câu hỏi & $n$ & Trả lời & \makecell{``Bài sau''} & \makecell{Để lại\\cho cô} & Đúng \\",
        r"\midrule",
    ]
    first = True
    for s, label in names.items():
        dec = RAG["sets"][s]["decisions"]["on"]
        groups: dict[str, list[str]] = defaultdict(list)
        for d in dec:
            groups[d["group"]].append(d["outcome"])
        if not first:
            out.append(r"\midrule")
        first = False
        for i, (g, outs) in enumerate(groups.items()):
            exp = expect.get(g, "ANSWER" if g not in ("lac-de",) else "PARKED")
            if s.startswith("sample") and g == "lac-de":
                exp = "PARKED"
            ok = (
                sum(1 for o in outs if o == exp) if exp != "PARKED" else sum(1 for o in outs if o != "ANSWER")
            )
            out.append(
                f"{label if i == 0 else ''} & {group_vi.get(g, g)} & {len(outs)} & {outs.count('ANSWER')} & {outs.count('LATER')} & "
                f"{outs.count('PARKED')} & {ok}/{len(outs)} \\\\"
            )
    out += [r"\bottomrule", r"\end{tabular}"]
    write("tab-rag-decisions.tex", "\n".join(out))


def tab_failures() -> None:
    rows = RAG["sets"]["published_holdout_v2"]["configs"]["hybrid+rerank"]["on"]["rows"]
    dec = {d["id"]: d for d in RAG["sets"]["published_holdout_v2"]["decisions"]["on"]}
    expect = {
        "cung-bai": "ANSWER",
        "bai-truoc": "ANSWER",
        "bai-sau": "LATER",
        "lac-de-toan": "PARKED",
        "lac-de": "PARKED",
    }
    out = [
        r"\small",
        r"\begin{tabularx}{\linewidth}{@{}llYrrl@{}}",
        r"\toprule",
        r"Mã & Nhóm & Câu hỏi của con & Hạng đoạn đúng & Cosine & Quyết định \\",
        r"\midrule",
    ]
    n = 0
    for r in rows:
        d = dec[r["id"]]
        bad_rank = r["relevant"] and (r["first"] is None or r["first"] > 3)
        wrong_decision = (
            (d["outcome"] == "ANSWER") != (expect[r["group"]] == "ANSWER")
            if r["group"] in ("cung-bai", "bai-truoc")
            else False
        )
        if not (bad_rank or wrong_decision):
            continue
        n += 1
        rank = "--" if not r["relevant"] else (str(r["first"]) if r["first"] else ">20")
        out.append(
            f"{r['id']} & {r['group']} & ``{tex_escape(r['q'])}'' & {rank} & {num(r['best_cosine'], 2)} & "
            f"{ {'ANSWER': 'trả lời', 'LATER': 'báo bài sau', 'PARKED': 'để lại cho cô'}[d['outcome']] } \\\\"
        )
    out += [r"\bottomrule", r"\end{tabularx}"]
    write("tab-failures.tex", "\n".join(out))


# R5 and R6 come from the live run of the grounded speech (make eval-grounded, 2026-10-13, report
# evals/reports/2026-10-13-grounded-live.md): not part of the data scripts, kept here with their source.
GROUNDED_FAITHFUL = (5.00, 5.00)  # answers and bridges, judge scale 1-5
GROUNDED_BAD = (0, 14)  # turns the judge saw fabricating or leaking, of turns judged


def targets() -> list[dict]:
    """The seven design targets of the RAG and how much of each is attained (the rule is fixed in 8.4)."""
    hold = ["published_holdout_v2", "sample_holdout"]
    r1 = min(metric(s, "hybrid+rerank", "hit3") for s in hold)

    def off_rejected(s: str) -> tuple[int, int]:
        dec = [d for d in RAG["sets"][s]["decisions"]["on"] if d["group"] in ("lac-de-toan", "lac-de")]
        return sum(d["outcome"] != "ANSWER" for d in dec), len(dec)

    r2 = min(off_rejected(s)[0] / off_rejected(s)[1] for s in hold)

    def in_answered(s: str) -> float:
        dec = [
            d
            for d in RAG["sets"][s]["decisions"]["on"]
            if d["group"] in ("cung-bai", "bai-truoc", "trong-chuong")
        ]
        return sum(d["outcome"] == "ANSWER" for d in dec) / len(dec)

    r3 = min(in_answered(s) for s in hold)
    later = [d for d in RAG["sets"]["published_holdout_v2"]["decisions"]["on"] if d["group"] == "bai-sau"]
    r4 = sum(d["outcome"] != "ANSWER" for d in later) / len(later)
    r5 = min(GROUNDED_FAITHFUL) / 5
    r6 = 1 - GROUNDED_BAD[0] / GROUNDED_BAD[1]

    def best(s: str) -> bool:
        m = {c: metric(s, c, "mrr") for c in ABLATION}
        return m["hybrid+rerank"] >= max(m.values()) - 1e-9

    r7 = all(best(s) for s in hold)
    return [
        {
            "id": "R1",
            "what": "Truy xuất đúng đoạn cho câu hỏi trong bài (Hit@3)",
            "target": "$\\geq 0{,}90$",
            "got": num(r1),
            "att": min(1.0, r1 / 0.90),
        },
        {
            "id": "R2",
            "what": "Câu lạc đề, Toán ngoài chương không được trả lời",
            "target": "$\\geq 95\\%$",
            "got": pct(r2),
            "att": min(1.0, r2 / 0.95),
        },
        {
            "id": "R3",
            "what": "Câu trong chương được nhận là có căn cứ và trả lời",
            "target": "$\\geq 95\\%$",
            "got": pct(r3),
            "att": min(1.0, r3 / 0.95),
        },
        {
            "id": "R4",
            "what": "Không dạy trước nội dung bài sau",
            "target": "$100\\%$",
            "got": pct(r4),
            "att": r4,
        },
        {
            "id": "R5",
            "what": "Lời trả lời bám nguồn (giám khảo, thang 5)",
            "target": "$\\geq 95\\%$",
            "got": pct(r5),
            "att": min(1.0, r5 / 0.95),
        },
        {
            "id": "R6",
            "what": "Lượt bịa hoặc lộ đáp án",
            "target": "$\\leq 2\\%$",
            "got": pct(GROUNDED_BAD[0] / GROUNDED_BAD[1]),
            "att": 1.0 if r6 >= 0.98 else 0.98 / r6,
        },
        {
            "id": "R7",
            "what": "Lai + xếp hạng lại tốt nhất trong các thành phần (MRR)",
            "target": "có/không",
            "got": "có/không" if False else ("có" if r7 else "không"),
            "att": 1.0 if r7 else 0.0,
        },
    ]


def tab_targets() -> None:
    t = targets()
    out = [
        r"\small",
        r"\begin{tabularx}{\linewidth}{@{}lYlrr@{}}",
        r"\toprule",
        r"Mã & Định hướng & Mục tiêu & Đo được & Mức đạt \\",
        r"\midrule",
    ]
    for r in t:
        out.append(f"{r['id']} & {r['what']} & {r['target']} & {r['got']} & {pct(r['att'])} \\\\")
    mean_att = sum(r["att"] for r in t) / len(t)
    out += [
        r"\midrule",
        rf"\multicolumn{{4}}{{@{{}}l}}{{Mức đạt trung bình của bảy định hướng}} & \textbf{{{pct(mean_att)}}} \\",
        r"\bottomrule",
        r"\end{tabularx}",
    ]
    write("tab-targets.tex", "\n".join(out))


# ------------------------------------------------------------------------------ Socratic behaviour

MOVE_VI = {
    "PRESENT": "Nêu câu hỏi",
    "PROBE": "Hỏi con đã làm thế nào",
    "HINT": "Gợi ý",
    "COGNITIVE_CONFLICT": "Phản ví dụ",
    "NUDGE": "Nhắc khi im lặng",
    "REDIRECT": "Kéo về câu đang làm",
    "OFFER_CHOICE": "Mời chọn: thêm gợi ý hay tự thử",
    "ASK_CONFIRM": "Hỏi lại cách viết",
    "VERIFY": "Hỏi ``vì sao''",
    "CONFIRM_ADVANCE": "Xác nhận, sang câu sau",
    "WORKED_GUIDANCE": "Cùng làm từng bước",
    "FULL_EXPLANATION": "Giải thích đầy đủ",
    "TEACH_BACK": "Mời giảng lại",
    "CLOSE_ITEM": "Khép câu",
    "EXPLAIN": "Giải thích điều con hỏi",
}
MOVE_ORDER = [
    "PRESENT",
    "PROBE",
    "HINT",
    "COGNITIVE_CONFLICT",
    "EXPLAIN",
    "OFFER_CHOICE",
    "REDIRECT",
    "VERIFY",
    "CONFIRM_ADVANCE",
    "WORKED_GUIDANCE",
    "TEACH_BACK",
    "FULL_EXPLANATION",
    "CLOSE_ITEM",
]


def merged_moves() -> dict[str, dict]:
    acc: dict[str, dict] = {}
    for c in STUDENT["chapters"].values():
        for m, v in c["socratic"]["by_move"].items():
            a = acc.setdefault(
                m, {"n": 0, "words": 0.0, "one": 0, "none": 0, "many": 0, "leaks": 0, "numeric": 0}
            )
            a["n"] += v["n"]
            a["words"] += v["mean_words"] * v["n"]
            a["one"] += v["one_question"]
            a["none"] += v["no_question"]
            a["many"] += v["many_questions"]
            a["leaks"] += v["leaks"]
            a["numeric"] += v["numeric"]
    return acc


def tab_socratic() -> None:
    acc = merged_moves()
    rows = []
    for m in MOVE_ORDER:
        if m not in acc:
            continue
        a = acc[m]
        rows.append(
            [
                MOVE_VI[m],
                str(a["n"]),
                num(a["words"] / a["n"], 1),
                f"{a['one']}",
                f"{a['none']}",
                f"{a['many']}",
                f"{a['leaks']}/{a['numeric']}",
            ]
        )
    tot = {k: sum(a[k] for a in acc.values()) for k in ("n", "one", "none", "many", "leaks", "numeric")}
    words = sum(a["words"] for a in acc.values()) / tot["n"]
    rows.append(
        [
            r"\textbf{Cộng}",
            rf"\textbf{{{tot['n']}}}",
            rf"\textbf{{{num(words, 1)}}}",
            rf"\textbf{{{tot['one']}}}",
            rf"\textbf{{{tot['none']}}}",
            rf"\textbf{{{tot['many']}}}",
            rf"\textbf{{{tot['leaks']}/{tot['numeric']}}}",
        ]
    )
    write(
        "tab-socratic.tex",
        table(
            r"@{}lrrrrrr@{}",
            ["Nước đi", "Số lượt", r"Từ TB", "1 câu hỏi", "0 câu hỏi", r"$>1$ câu hỏi", r"Lộ đáp án"],
            rows,
            mid={len(rows) - 2},
        ),
    )


def tab_sources() -> None:
    ch = STUDENT["chapters"]
    src = ("TEMPLATE", "LLM", "FALLBACK")
    label = {
        "TEMPLATE": "Câu mẫu của giáo viên (không gọi mô hình)",
        "LLM": "Mô hình viết, đã qua bộ kiểm chứng",
        "FALLBACK": "Mô hình thử rồi dùng câu mẫu thay",
    }
    rows = []
    for k in src:
        a, b = ch[DEC]["socratic"]["by_source"].get(k, 0), ch[GEO]["socratic"]["by_source"].get(k, 0)
        rows.append([label[k], str(a), str(b), str(a + b)])
    rej: dict[str, int] = defaultdict(int)
    for c in ch.values():
        for k, v in c["socratic"]["rejected_codes"].items():
            rej[k] += v
    rows.append(
        [
            r"\textit{Lời của mô hình bị bộ kiểm chứng chặn}",
            str(sum(ch[DEC]["socratic"]["rejected_codes"].values())),
            str(sum(ch[GEO]["socratic"]["rejected_codes"].values())),
            str(sum(rej.values())),
        ]
    )
    write(
        "tab-sources.tex",
        table(r"@{}lrrr@{}", ["Nguồn của lời gia sư", "Số thập phân", "Diện tích", "Cộng"], rows, mid={2}),
    )


def fig_ladder() -> None:
    ch = STUDENT["chapters"]
    levels = ["1", "2", "3", "6"]
    out = [
        r"\begin{tikzpicture}",
        r"\begin{groupplot}[group style={group size=2 by 1,horizontal sep=1.7cm},cavat,width=6.8cm,height=5cm,ymajorgrids]",
    ]
    # (a) hints delivered by level and chapter
    out.append(
        r"\nextgroupplot[title={(a) Gợi ý đã đưa theo bậc},ybar stacked,bar width=12pt,ylabel={số gợi ý},symbolic x coords={H1,H2,H3,H6},xtick=data,ymin=0,enlarge x limits=0.2]"
    )
    for c, colour in ((DEC, "cavat"), (GEO, "llm")):
        coords = " ".join(f"(H{lv},{ch[c]['ladder']['by_level'].get(lv, 0)})" for lv in levels)
        out.append(rf"\addplot+[fill={colour}!70,draw=none] coordinates {{{coords}}};")
    # (b) items by the highest hint level and how they ended
    out.append(
        r"\nextgroupplot[title={(b) Câu theo bậc gợi ý cao nhất},ybar stacked,bar width=12pt,ylabel={số câu},symbolic x coords={H0,H1,H2,H6,H7},xtick=data,ymin=0,enlarge x limits=0.15]"
    )
    colours = {"INDEPENDENT": "zoneA", "SUPPORTED": "zoneB", "WORKED": "zoneD", "UNRESOLVED": "zoneE"}
    for res in ("INDEPENDENT", "SUPPORTED", "WORKED", "UNRESOLVED"):
        coords = []
        for lv in ("0", "1", "2", "6", "7"):
            n = sum(c["ladder"]["by_max_level"].get(lv, {}).get(res, 0) for c in ch.values())
            coords.append(f"(H{lv},{n})")
        out.append(rf"\addplot+[fill={colours[res]},draw=none] coordinates {{{' '.join(coords)}}};")
    out += [r"\end{groupplot}", r"\end{tikzpicture}", r"\\[4pt]"]
    out.append(
        legend_tikz([("Số thập phân", "box", "cavat!70"), ("Diện tích", "box", "llm!70")], per_char=0.125)
    )
    out.append(r"\hspace{1.2cm}")
    out.append(
        legend_tikz(
            [
                ("độc lập", "box", "zoneA"),
                ("có hỗ trợ", "box", "zoneB"),
                ("cùng làm", "box", "zoneD"),
                ("chưa giải được", "box", "zoneE"),
            ],
            per_char=0.125,
        )
    )
    write("fig-ladder.tex", "\n".join(out))


def fig_rules() -> None:
    ch = STUDENT["chapters"]
    item: dict[str, int] = defaultdict(int)
    node: dict[str, int] = defaultdict(int)
    for c in ch.values():
        for k, v in c["rules"]["item_rules"].items():
            item[k] += v
        for k, v in c["rules"]["node_rules"].items():
            node[k] += v
    out = [
        r"\begin{tikzpicture}",
        r"\begin{groupplot}[group style={group size=2 by 1,horizontal sep=1.6cm},cavat,width=6.6cm,xmajorgrids,xmin=0]",
    ]
    for title, data, colour in (
        ("(a) Luật của vòng một câu hỏi (R-*)", item, "cavat"),
        ("(b) Luật của chính sách dạy (N-*)", node, "llm"),
    ):
        names = [k for k, _ in sorted(data.items(), key=lambda kv: kv[1])]
        height = 0.28 * len(names) + 1.0
        out.append(
            rf"\nextgroupplot[title={{{title}}},xbar,bar width=5pt,height={height:.1f}cm,symbolic y coords={{{','.join(names)}}},ytick=data,"
            r"y tick label style={font=\scriptsize\sffamily},enlarge y limits=0.06,nodes near coords,nodes near coords style={font=\tiny},xmax="
            + str(int(max(data.values()) * 1.18))
            + "]"
        )
        coords = " ".join(f"({v},{k})" for k, v in sorted(data.items(), key=lambda kv: kv[1]))
        out.append(rf"\addplot[fill={colour}!70,draw=none] coordinates {{{coords}}};")
    out += [r"\end{groupplot}", r"\end{tikzpicture}"]
    write("fig-rules.tex", "\n".join(out))


def fig_messages() -> None:
    acc = merged_moves()
    moves = [m for m in MOVE_ORDER if m in acc]
    names = [MOVE_VI[m].replace("``", "").replace("''", "") for m in moves]  # top to bottom
    n = len(moves)
    labels = ",".join("{" + x + "}" for x in reversed(names))
    out = [
        r"\begin{tikzpicture}",
        rf"\begin{{axis}}[cavat,xbar,width=0.82\linewidth,height={0.42 * n + 1.4:.1f}cm,bar width=6pt,xmin=0,xmax=70,xmajorgrids,xlabel={{số từ trung bình của lượt gia sư}},"
        rf"ymin=0.4,ymax={n + 0.6},ytick={{{','.join(str(i) for i in range(1, n + 1))}}},yticklabels={{{labels}}},y tick label style={{font=\scriptsize}},"
        r"nodes near coords,nodes near coords style={font=\tiny}]",
    ]
    coords = " ".join(f"({acc[m]['words'] / acc[m]['n']:.1f},{n - i})" for i, m in enumerate(moves))
    out.append(rf"\addplot[fill=cavat!70,draw=none] coordinates {{{coords}}};")
    out.append(rf"\draw[dashed,color=llm] (axis cs:60,0.4) -- (axis cs:60,{n + 0.6});")
    out.append(rf"\node[font=\tiny,color=llm,anchor=south east] at (axis cs:60,{n - 0.6}) {{trần 60 từ}};")
    out += [r"\end{axis}", r"\end{tikzpicture}"]
    write("fig-messages.tex", "\n".join(out))


# ------------------------------------------------------------------------------ the learner model

DIMS = ["C", "R", "A", "T", "I", "S", "D"]
STATE_VI = ["Học", "Nhận ra", "Quy trình", "Khái niệm", "Vận dụng", "Thành thạo (tạm)"]


def short(node_id: str) -> str:
    return node_id.replace("STP-T", "T").replace("DTTGHT-T", "T")


def heat_cells(chapter: str) -> list[str]:
    """Rows of node x dimension: the colour is the zone of the value, the number its floor (as in the UI)."""
    nodes = STUDENT["chapters"][chapter]["nodes"]
    out = []
    cw, ch_ = 1.0, 0.62
    cols = DIMS
    for i, n in enumerate(nodes):
        y = -i * ch_
        out.append(rf"\node[anchor=east,font=\scriptsize] at (-0.55,{y:.2f}) {{{short(n['id'])}}};")
        for j, d in enumerate(cols):
            v = n["dims"][d]
            enough = v["in_mastery"]
            val = v["mean"] if enough else None
            colour = zone_colour(val)
            label = str(math.floor(val)) if val is not None else "--"
            txt = zone_text(val)
            fill = f"fill={colour}" if val is not None else "fill=gray!10"
            out.append(
                rf"\node[draw=white,{fill},minimum width={cw - 0.04}cm,minimum height={ch_ - 0.04}cm,inner sep=0pt,font=\scriptsize,text={txt}] at ({j * cw:.2f},{y:.2f}) {{{label}}};"
            )
        # composite and confidence
        m = n["mastery"]
        out.append(
            rf"\node[draw=white,fill={zone_colour(m)},minimum width={cw - 0.04}cm,minimum height={ch_ - 0.04}cm,inner sep=0pt,font=\scriptsize\bfseries,text={zone_text(m)}] at ({(len(cols) + 0.35) * cw:.2f},{y:.2f}) {{{math.floor(m) if m is not None else '--'}}};"
        )
        conf = n["confidence"]
        out.append(
            rf"\node[draw=white,fill=gray!{15 if conf < 30 else 0},minimum width={cw - 0.04}cm,minimum height={ch_ - 0.04}cm,inner sep=0pt,font=\scriptsize,text=ink] at ({(len(cols) + 1.35) * cw:.2f},{y:.2f}) {{{math.floor(conf)}}};"
        )
        out.append(
            rf"\node[anchor=west,font=\scriptsize] at ({(len(cols) + 2.0) * cw:.2f},{y:.2f}) {{{STATE_VI[n['level']]}{r', đã qua' if n['passed'] else ''}}};"
        )
    return out


def fig_heat() -> None:
    _heat_figure("fig-heat.tex", ((DEC, "(a) Số thập phân"), (GEO, "(b) Diện tích tam giác, hình thang")))
    # one chapter only, for the compact version of the paper
    _heat_figure("fig-heat-dec.tex", ((DEC, "Số thập phân"),))


def _heat_figure(filename: str, chapters: tuple[tuple[str, str], ...]) -> None:
    parts = [r"\begin{tikzpicture}[x=1cm,y=1cm]"]
    offset = 0.0
    for c, title in chapters:
        nodes = STUDENT["chapters"][c]["nodes"]
        parts.append(rf"\begin{{scope}}[shift={{(0,{offset:.2f})}}]")
        parts.append(rf"\node[anchor=west,font=\small\bfseries] at (-1.2,1.15) {{{title}}};")
        for j, d in enumerate(DIMS):
            parts.append(rf"\node[font=\scriptsize\bfseries] at ({j * 1.0:.2f},0.55) {{{d}}};")
        parts.append(rf"\node[font=\scriptsize\bfseries] at ({(len(DIMS) + 0.35) * 1.0:.2f},0.55) {{$M$}};")
        parts.append(
            rf"\node[font=\scriptsize\bfseries] at ({(len(DIMS) + 1.35) * 1.0:.2f},0.55) {{tin cậy}};"
        )
        parts.append(
            rf"\node[anchor=west,font=\scriptsize\bfseries] at ({(len(DIMS) + 2.0) * 1.0:.2f},0.55) {{mức hiểu}};"
        )
        parts += ["  " + x for x in heat_cells(c)]
        parts.append(r"\end{scope}")
        offset -= 0.62 * len(nodes) + 2.0
    # legend of the zones
    y = offset + 1.3
    x = 0.0
    for colour, label in (
        ("zoneE", "0--39"),
        ("zoneD", "40--59"),
        ("zoneC", "60--74"),
        ("zoneB", "75--89"),
        ("zoneA", "90--100"),
    ):
        parts.append(
            rf"\node[draw=white,fill={colour},minimum width=0.8cm,minimum height=0.4cm,inner sep=0pt] at ({x:.2f},{y:.2f}) {{}};"
        )
        parts.append(rf"\node[anchor=west,font=\scriptsize] at ({x + 0.5:.2f},{y:.2f}) {{{label}}};")
        x += 1.9
    parts.append(
        rf"\node[draw=white,fill=gray!10,minimum width=0.8cm,minimum height=0.4cm,inner sep=0pt] at ({x:.2f},{y:.2f}) {{}};"
    )
    parts.append(rf"\node[anchor=west,font=\scriptsize] at ({x + 0.5:.2f},{y:.2f}) {{chưa đủ bằng chứng}};")
    parts.append(r"\end{tikzpicture}")
    write(filename, "\n".join(parts))


def fig_traj() -> None:
    """Small multiples: the score M of each node after each event that moved it (the teacher's curve); the
    dashed line marks the event where the pass rule of the node first held."""
    out = []
    for c in (DEC, GEO):
        data = STUDENT["chapters"][c]
        nodes = [n["id"] for n in data["nodes"]]
        cols = 4
        rows_n = math.ceil(len(nodes) / cols)
        out.append(r"\begin{tikzpicture}")
        out.append(
            rf"\begin{{groupplot}}[group style={{group size={cols} by {rows_n},horizontal sep=0.55cm,vertical sep=0.85cm}},cavat,"
            r"width=4.0cm,height=3.2cm,ymin=0,ymax=100,ytick={0,40,60,75,90},"
            r"title style={font=\scriptsize\bfseries,yshift=-2pt},tick label style={font=\tiny},xlabel style={font=\tiny}]"
        )
        for n in nodes:
            pts = [t for t in data["trace"] if t["node"] == n and t["mastery"] is not None]
            node = next(x for x in data["nodes"] if x["id"] == n)
            k = max(len(pts), 1)
            out.append(rf"\nextgroupplot[title={{{short(n)}}},xmin=1,xmax={max(k, 2)}]")
            for lo, hi, colour in (
                (0, 40, "zoneE"),
                (40, 60, "zoneD"),
                (60, 75, "zoneC"),
                (75, 90, "zoneB"),
                (90, 100, "zoneA"),
            ):
                out.append(
                    rf"\fill[{colour},opacity=0.16] (axis cs:1,{lo}) rectangle (axis cs:{max(k, 2)},{hi});"
                )
            if pts:
                coords = " ".join(f"({i},{t['mastery']})" for i, t in enumerate(pts, 1))
                out.append(
                    rf"\addplot[color=ink,line width=0.7pt,mark=*,mark size=0.6pt] coordinates {{{coords}}};"
                )
            if node["passed_at"] is not None and pts:
                at = sum(1 for t in pts if t["seq"] <= node["passed_at"])
                out.append(
                    rf"\draw[color=cavat,dashed,line width=0.7pt] (axis cs:{max(at, 1)},0) -- (axis cs:{max(at, 1)},100);"
                )
        out.append(r"\end{groupplot}")
        out.append(r"\end{tikzpicture}")
        out.append(r"\par\vspace{4pt}")
    write("fig-traj.tex", "\n".join(out))


def tab_nodes_s1() -> None:
    out = [
        r"\scriptsize",
        r"\begin{tabular}{@{}lrrrrrrrrrrrl@{}}",
        r"\toprule",
        r"Tiết & $M$ & Tin cậy & Mức & \multicolumn{7}{c}{Trung bình từng chiều (\%)} & Thành công & Lỗi sai \\",
        r"\cmidrule(lr){5-11}",
        r" & & & & C & R & A & T & I & S & D & & \\",
        r"\midrule",
    ]
    for c in (DEC, GEO):
        for n in STUDENT["chapters"][c]["nodes"]:
            dims = " & ".join(
                num(n["dims"][d]["mean"], 0) if n["dims"][d]["in_mastery"] else "--" for d in DIMS
            )
            mis = ", ".join(f"{m['id'].split('-', 1)[-1]}×{m['count']}" for m in n["misconceptions"]) or "--"
            tag = CH_SHORT[c] + "-" + short(n["id"])
            out.append(
                f"{tag} & {num(n['mastery'], 1)} & {num(n['confidence'], 0)} & {n['level']} & {dims} & {n['successes']} & {tex_escape(mis)} \\\\"
            )
        if c == DEC:
            out.append(r"\midrule")
    out += [r"\bottomrule", r"\end{tabular}"]
    write("tab-nodes-s1.tex", "\n".join(out))


# ------------------------------------------------------------------------------ the market comparison

SYS_LABEL = {
    "B1": r"B1: chatbot thường (Gemini)",
    "B2": r"B2: cùng mô hình + lời nhắc Socratic",
    "C": r"C: CAVAT",
}


def tab_baselines() -> None:
    sy = BASE["systems"]
    rows = []

    def line(label, f, fmt=lambda v: str(v)):
        rows.append([label] + [fmt(f(sy[s])) for s in ("B1", "B2", "C")])

    line("Số lượt gia sư được chấm", lambda v: v["turns"])
    line("Nói ra đáp án (luật tất định)", lambda v: v["says_answer"])
    line("Giám khảo thấy lộ đáp án", lambda v: v["judge_leak"])
    line("Lượt có hơn một câu hỏi", lambda v: v["more_than_one_question"])
    line("Lượt dài hơn 60 từ", lambda v: v["over_limit_words"])
    line("Số từ trung bình mỗi lượt", lambda v: v["words_mean"], lambda x: num(x, 0))
    line(r"Khen một đáp án sai là đúng (trong 4 lượt sai)", lambda v: v["approves_wrong"])
    mid = {len(rows) - 1}
    line("Giám khảo: đáp đúng ý của con", lambda v: v["follows_intent"], lambda x: num(x))
    line("Giám khảo: theo phương pháp Socratic", lambda v: v["socratic"], lambda x: num(x))
    line("Giám khảo: hợp với trẻ 10 tuổi", lambda v: v["child_friendly"], lambda x: num(x))
    line("Giám khảo: bám bài đang làm", lambda v: v["on_topic"], lambda x: num(x))
    write(
        "tab-baselines.tex",
        table(r"@{}lrrr@{}", ["Chỉ số (13 vai, 25 lượt)", "B1", "B2", "C (CAVAT)"], rows, mid=mid),
    )


def fig_baselines() -> None:
    sy = BASE["systems"]
    metrics_ = [
        (r"nói ra đáp án\\(luật tất định)", "says_answer"),
        (r"giám khảo\\thấy lộ", "judge_leak"),
        (r"hơn một\\câu hỏi", "more_than_one_question"),
        (r"dài hơn\\$60$ từ", "over_limit_words"),
    ]
    names = ",".join("{" + m[0] + "}" for m in metrics_)
    out = [
        r"\begin{tikzpicture}",
        r"\begin{axis}[cavat,ybar,bar width=7pt,width=\linewidth,height=5.2cm,ymin=0,ymax=100,ymajorgrids,"
        r"ylabel={\% số lượt},"
        rf"xtick={{0,1,2,3}},xticklabels={{{names}}},xticklabel style={{font=\scriptsize,align=center}},"
        r"enlarge x limits=0.16,nodes near coords,nodes near coords style={font=\tiny},"
        r"every node near coord/.append style={/pgf/number format/fixed,/pgf/number format/precision=0},"
        r"legend style={at={(0.5,1.03)},anchor=south,draw=none,legend columns=-1,font=\scriptsize,"
        r"/tikz/every even column/.append style={column sep=0.25cm}},area legend]",
    ]
    for s, colour in (("B1", "llm"), ("B2", "ink!40"), ("C", "cavat")):
        coords = " ".join(f"({i},{100 * sy[s][k] / sy[s]['turns']:.1f})" for i, (_, k) in enumerate(metrics_))
        out.append(rf"\addplot[fill={colour},draw=none] coordinates {{{coords}}};")
    out.append(r"\legend{B1: chatbot thường,B2: lời nhắc Socratic,C: CAVAT}")
    out += [r"\end{axis}", r"\end{tikzpicture}"]
    write("fig-baselines.tex", "\n".join(out))


def tab_roles() -> None:
    out = [
        r"\small",
        r"\begin{tabularx}{\linewidth}{@{}Yrrrrrr@{}}",
        r"\toprule",
        r" & \multicolumn{3}{c}{Nói ra đáp án (lượt)} & \multicolumn{3}{c}{Socratic (giám khảo, 1--5)} \\",
        r"\cmidrule(lr){2-4}\cmidrule(lr){5-7}",
        r"Vai & B1 & B2 & C & B1 & B2 & C \\",
        r"\midrule",
    ]
    for role, v in BASE["roles"].items():
        cells = [tex_escape(role)]
        for key in ("says_answer",):
            for s in ("B1", "B2", "C"):
                cells.append(f"{v[s][key]}/{v[s]['turns']}" if s in v else "--")
        for s in ("B1", "B2", "C"):
            cells.append(num(v[s]["socratic"], 1) if s in v and v[s]["socratic"] is not None else "--")
        out.append(" & ".join(cells) + r" \\")
    out += [r"\bottomrule", r"\end{tabularx}"]
    write("tab-roles.tex", "\n".join(out))


def tab_grading() -> None:
    g = BASE["grading"]
    out = [
        r"\small",
        r"\begin{tabular}{@{}lrrrrrr@{}}",
        r"\toprule",
        r" & \multicolumn{3}{c}{v1 (36 câu, đã xem trước GRADE-1)} & \multicolumn{3}{c}{v2 (35 câu, giữ riêng)} \\",
        r"\cmidrule(lr){2-4}\cmidrule(lr){5-7}",
        r"Người chấm & Đúng & Sai dương & Sai âm & Đúng & Sai dương & Sai âm \\",
        r"\midrule",
    ]
    for s in ("B1", "B2", "C"):
        cells = [SYS_LABEL[s]]
        for tag in ("v1", "v2"):
            r = g[tag][s]
            cells += [f"{r['right']}/{g[tag]['n']}", str(r["false_positive"]), str(r["false_negative"])]
        out.append(" & ".join(cells) + r" \\")
    out += [r"\bottomrule", r"\end{tabular}"]
    write("tab-grading.tex", "\n".join(out))


# ------------------------------------------------------------------------------ the assessment


def tab_conformance() -> None:
    c = ASSESS["conformance"]

    rows = []

    def add(label: str, f) -> None:
        rows.append([label] + [f(c[k]) for k in ("mixed", "strong")])

    add("Số chuỗi sự kiện / số sự kiện", lambda v: f"{v['streams']} / {thou(v['events'])}")
    add(r"Chênh lệch lớn nhất của $M$ với công thức đóng", lambda v: num(v["max_dev_mastery"], 3))
    add("Chênh lệch lớn nhất của độ tin cậy", lambda v: num(v["max_dev_confidence"], 3))
    add("Mức hiểu khác công thức (chuỗi)", lambda v: str(v["level_mismatch"]))
    add(
        "Gate giải thích, vận dụng khác công thức",
        lambda v: str(v["explanation_mismatch"] + v["application_mismatch"]),
    )
    add("Đổi thứ tự sự kiện làm đổi $M$", lambda v: str(v["order_violations"]))
    add("Phát lại cho kết quả khác", lambda v: str(v["replay_violations"]))
    add("$M$ ngoài $[0;100]$", lambda v: str(v["bounds_violations"]))
    add("Mức vượt gate (DI-6, §53)", lambda v: str(v["gate_violations"]))
    add("Thêm một bậc gợi ý mà $M$ tăng", lambda v: f"{v['more_help_violations']}/{v['more_help_checked']}")
    add(
        "Sai thành đúng độc lập mà $M$ giảm",
        lambda v: f"{v['better_outcome_violations']}/{v['better_outcome_checked']}",
    )
    write(
        "tab-conformance.tex",
        table(r"@{}lrr@{}", ["Phép kiểm", "Học sinh bất kỳ", "Học sinh khá"], rows, mid={0, 2, 4, 7}),
    )


def fig_curves() -> None:
    cv = ASSESS["curves"]
    out = [
        r"\begin{tikzpicture}",
        r"\begin{groupplot}[group style={group size=2 by 1,horizontal sep=1.3cm},cavat,width=7.4cm,height=5.4cm,ymin=0,ymax=100,ymajorgrids,xlabel={số câu đã làm}]",
    ]
    out.append(
        r"\nextgroupplot[title={(a) Bậc gợi ý cao nhất của mỗi câu đúng},xmin=1,xmax=15,ylabel={$M$ của tiết},xtick={1,5,10,15}]"
    )
    for lo, hi in ((0, 40), (40, 60), (60, 75), (75, 90), (90, 100)):
        if lo in (0, 60, 90):
            out.append(rf"\fill[black,opacity=0.05] (axis cs:1,{lo}) rectangle (axis cs:15,{hi});")
    for h in range(8):
        colour = f"cavat!{round(100 - 9 * h)}" if h < 7 else "llm"
        coords = " ".join(f"({k},{v})" for k, v in enumerate(cv["independence"][str(h)], 1) if v is not None)
        out.append(
            rf"\addplot[color={colour},line width=0.9pt,mark=*,mark size=0.8pt] coordinates {{{coords}}};"
        )
        end = cv["independence"][str(h)][-1]
        out.append(rf"\node[font=\tiny,anchor=west,color={colour}] at (axis cs:15.1,{end}) {{H{h}}};")
    out.append(
        r"\nextgroupplot[title={(b) Sáu kiểu người học},xmin=1,xmax=14,xtick={1,5,10,14},legend pos=south east]"
    )
    for lo, hi in ((0, 40), (40, 60), (60, 75), (75, 90), (90, 100)):
        if lo in (0, 60, 90):
            out.append(rf"\fill[black,opacity=0.05] (axis cs:1,{lo}) rectangle (axis cs:14,{hi});")
    styles = {
        "đều, không gợi ý": ("cavat", "solid"),
        "sai rồi học dần": ("okgreen", "solid"),
        "luôn cần gợi ý H6": ("llm", "solid"),
        "đoán": ("ink!60", "dashed"),
        "đúng sai xen kẽ": ("oksky", "dashed"),
        "toàn sai": ("ink", "dotted"),
    }
    for name, (colour, style) in styles.items():
        tr = cv["patterns"][name]["trace"]
        coords = " ".join(f"({k},{v})" for k, v in enumerate(tr, 1) if v is not None)
        out.append(rf"\addplot[color={colour},{style},line width=1pt] coordinates {{{coords}}};")
    out += [r"\end{groupplot}", r"\end{tikzpicture}", r"\\[4pt]"]
    out.append(legend_tikz([(n, "line", f"color={c},{st}") for n, (c, st) in styles.items()], per_char=0.115))
    write("fig-curves.tex", "\n".join(out))


def tab_staircase() -> None:
    rows = []
    for g in ASSESS["gates"]:
        missing = {
            "MASTERY": "điểm",
            "UNDERSTOOD": "hiểu",
            "EXPLANATION": "giải thích",
            "APPLICATION": "vận dụng",
            "MISCONCEPTION": "lỗi sai",
        }
        miss = ", ".join(missing[m] for m in g["missing"]) or "--"
        rows.append(
            [
                tex_escape(g["step"]),
                num(g["mastery"], 1) if g["mastery"] is not None else "--",
                num(g["confidence"], 0),
                f"{g['level']} {STATE_VI[g['level']]}" if g["mastery"] is not None else "0 Chưa học",
                r"\tick" if g["pass_now"] else "",
                miss,
            ]
        )
    write(
        "tab-staircase.tex",
        table(r"@{}Yrrlcl@{}", ["Bước", "$M$", "Tin cậy", "Mức", "Qua", "Còn thiếu"], rows),
    )


def tab_known_groups() -> None:
    kg = ASSESS["known_groups"]
    persona = {
        "gioi": "giỏi: đúng ngay, kể lại đúng ý",
        "sai-dang": "sai dạng: đúng giá trị, sai cách viết",
        "bi": "bí: ``con không biết'' rồi tự làm",
        "hay-sai": "hay sai: sai, xin gợi ý, rồi đúng",
        "phu-thuoc": "phụ thuộc: bốn lần ``không biết'' mỗi câu",
    }
    out = [
        r"\small",
        r"\begin{tabular}{@{}lrrrrrrrr@{}}",
        r"\toprule",
        r"\multirow{2}{*}{Học sinh mẫu} & \multicolumn{4}{c}{Số thập phân (11 tiết)} & \multicolumn{4}{c}{Diện tích (8 tiết)} \\",
        r"\cmidrule(lr){2-5}\cmidrule(lr){6-9}",
        r" & Qua & Gợi ý & $\bar M$ (số tiết) & $\bar I$ & Qua & Gợi ý & $\bar M$ (số tiết) & $\bar I$ \\",
        r"\midrule",
    ]
    for key, label in persona.items():
        cells = [label]
        for c in (DEC, GEO):
            r = kg[c][key]
            seen = sum(1 for n in r["per_node"] if n["M"] is not None)
            cells += [
                f"{r['passed']}/{r['nodes']}",
                str(r["hints"]),
                f"{num(r['mastery_mean'], 1)} ({seen})",
                num(r["dims"].get("I", 0), 1),
            ]
        out.append(" & ".join(cells) + r" \\")
    out += [r"\bottomrule", r"\end{tabular}"]
    write("tab-known-groups.tex", "\n".join(out))


def tab_sensitivity() -> None:
    sens = ASSESS["sensitivity"]
    out = [
        r"\small",
        r"\begin{tabularx}{\linewidth}{@{}llYrrrr@{}}",
        r"\toprule",
        r"\multirow{2}{*}{DI} & \multirow{2}{*}{Thay đổi} & & \multicolumn{2}{c}{Số thập phân} & \multicolumn{2}{c}{Diện tích} \\",
        r"\cmidrule(lr){4-5}\cmidrule(lr){6-7}",
        r" & & & $|\Delta M|$ TB & Đổi mức/qua & $|\Delta M|$ TB & Đổi mức/qua \\",
        r"\midrule",
    ]
    a, b = sens[DEC]["rows"], sens[GEO]["rows"]
    for ra, rb in zip(a, b, strict=True):
        out.append(
            f"{ra['di']} & {tex_escape(ra['change'])} & & {num(ra['mean_abs_dM'], 1)} & {ra['level_changes']}/{ra['pass_changes']} & "
            f"{num(rb['mean_abs_dM'], 1)} & {rb['level_changes']}/{rb['pass_changes']} \\\\"
        )
    out += [r"\bottomrule", r"\end{tabularx}"]
    write("tab-sensitivity.tex", "\n".join(out))


def tab_v2_questions() -> None:
    rows = RAG["sets"]["published_holdout_v2"]["configs"]["hybrid+rerank"]["on"]["rows"]
    dec = {d["id"]: d for d in RAG["sets"]["published_holdout_v2"]["decisions"]["on"]}
    group_vi = {
        "cung-bai": "trong bài",
        "bai-truoc": "bài trước",
        "bai-sau": "bài sau",
        "lac-de-toan": "Toán ngoài chương",
        "lac-de": "lạc đề",
    }
    out_vi = {"ANSWER": "trả lời", "LATER": "bài sau", "PARKED": "giữ cho cô"}
    body = [
        r"{\scriptsize",
        r"\begin{tabular}{@{}lllp{7.4cm}rl@{}}",
        r"\toprule",
        r"Mã & Nhóm & Tiết & Câu hỏi (nguyên văn) & Hạng & Quyết định \\",
        r"\midrule",
    ]
    for r in rows:
        node = r["node"].replace("STP-T", "STP-").replace("DTTGHT-T", "DTTGHT-")
        rank = "--" if not r["relevant"] else (str(r["first"]) if r["first"] else ">20")
        outcome = out_vi[dec[r["id"]]["outcome"]]
        body.append(
            f"{r['id']} & {group_vi[r['group']]} & {node} & {tex_escape(r['q'])} & {rank} & {outcome} \\\\"
        )
    body += [r"\bottomrule", r"\end{tabular}", "}"]
    write("tab-v2-questions.tex", "\n".join(body))


def tab_trace() -> None:
    """The signals of the top passages of one question, without and with the routing (DI-57)."""
    t = RAG["traces"]["V13"]
    kind_vi = {
        "theory": "cách giảng",
        "method": "phương pháp",
        "worked_example": "ví dụ mẫu",
        "misconception_note": "lỗi sai",
        "source_passage": "đoạn tài liệu",
    }

    def short_node(n: str | None) -> str:
        return (n or "--").replace("STP-T", "STP-").replace("DTTGHT-T", "DTTGHT-")

    out = [
        r"\small",
        r"\begin{tabular}{@{}rllrrrrrrc@{}}",
        r"\toprule",
        r"Hạng & Loại & Tiết & BM25 & cos & cosine & $d_G$ & fuse & điểm & Đúng \\",
        r"\midrule",
    ]
    for label, key in (("Không định tuyến", "off"), ("Có định tuyến ($\\varepsilon=0{,}02$)", "on")):
        out.append(rf"\multicolumn{{10}}{{@{{}}l}}{{\textit{{{label}}}}} \\")
        for x in t[key]:
            mark = "\\tick" if x["relevant"] else ""
            out.append(
                f"{x['rank']} & {kind_vi[x['kind']]} & {short_node(x['node'])} & "
                f"{x['bm25_rank'] or '--'} & {x['cos_rank'] or '--'} & {num(x['cosine'], 3)} & {x['distance']} & "
                f"{num(100 * x['fused'], 2)} & {num(100 * x['final'], 2)} & {mark} \\\\"
            )
        if key == "off":
            out.append(r"\midrule")
    out += [r"\bottomrule", r"\end{tabular}"]
    write("tab-trace.tex", "\n".join(out))


def main() -> None:
    for fn in (
        numbers,
        tab_docs,
        tab_reading,
        tab_bank,
        tab_plan_nodes,
        tab_plan_stats,
        tab_drafts,
        tab_chunks,
        fig_graph,
        fig_pipeline,
        fig_chunks,
        fig_ablation,
        fig_hitk,
        fig_sweep,
        fig_grounding,
        tab_ablation_main,
        tab_ablation_full,
        tab_routing,
        tab_flat,
        tab_rag_decisions,
        tab_failures,
        tab_targets,
        tab_socratic,
        tab_sources,
        fig_ladder,
        fig_rules,
        fig_messages,
        tab_baselines,
        fig_baselines,
        tab_roles,
        tab_grading,
        tab_conformance,
        fig_curves,
        tab_staircase,
        tab_known_groups,
        tab_sensitivity,
        fig_heat,
        fig_traj,
        tab_nodes_s1,
        tab_v2_questions,
        tab_trace,
    ):
        fn()
    print(f"written {len(list(GEN.glob('*.tex')))} fragments to {GEN.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
