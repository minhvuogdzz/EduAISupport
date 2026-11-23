#!/usr/bin/env python3
"""Sinh số liệu và bảng/biểu đồ TikZ của Chương 4 từ bản sao lưu database (chỉ đọc).

Cách dùng:
    python3 tools/db_tex.py <thư mục sao lưu của `make backup`>

Đầu vào là learning_sessions(.jsonl) và learning_sessions_archive(.jsonl); sự kiện của buổi nằm trong
trường `events` của từng buổi. Đầu ra chỉ có số tổng hợp, không có phản hồi học sinh hay mã tài khoản:
- docs/thesis/data/db-sessions.json
- figures/tab-db-*.tex, figures/fig-db-*.tex (không sửa tay)
"""

from __future__ import annotations

import json
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT.parent / "data" / "db-sessions.json"
FIG = ROOT / "figures"
HEADER = "% Sinh bởi tools/db_tex.py từ bản sao lưu database; không sửa tay.\n"

SHORT = {"dec": "Số thập phân", "area": "Diện tích", "en": "Tiếng Anh"}
SUBJECTS = [
    ("dec", "Toán, Số thập phân"),
    ("area", "Toán, Diện tích"),
    ("en", "Tiếng Anh, Unit 11"),
]


def load(folder: Path, name: str) -> list[dict]:
    path = folder / f"{name}.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def subject_of(session: dict) -> str:
    lesson = session["lesson_id"]
    if lesson.startswith("eng"):
        return "en"
    return "dec" if "decimals" in lesson else "area"


def num(x: float, nd: int = 1) -> str:
    s = f"{x:.{nd}f}".replace(".", "{,}")
    return f"${s}$"


def integer(x: int) -> str:
    return f"${x:,}$".replace(",", "\\,")


def pct(part: int, whole: int, nd: int = 1) -> str:
    return num(100 * part / whole, nd) + "\\%" if whole else "--"


def collect(sessions: list[dict]) -> dict:
    out: dict = {}
    for key, _ in SUBJECTS:
        rows = [s for s in sessions if subject_of(s) == key]
        full = [s for s in rows if any(e["event_type"] == "QUESTION_SHOWN" for e in s["events"])]
        c = Counter()
        res, outcome, hints, src, rej, fb = Counter(), Counter(), Counter(), Counter(), Counter(), Counter()
        node, models = Counter(), defaultdict(list)
        attempts, hint_counts = [], []
        for s in full:
            for e in s["events"]:
                t, p = e["event_type"], e["payload"]
                c[t] += 1
                if t == "ITEM_RESOLVED":
                    res[p["resolution"]] += 1
                    attempts.append(p["attempts"])
                    hint_counts.append(p["hints_count"])
                elif t == "ANSWER_SUBMITTED":
                    outcome[p["outcome"]] += 1
                elif t == "HINT_DELIVERED":
                    hints[p["hint_level"]] += 1
                elif t == "TUTOR_MESSAGE_SENT":
                    src[p.get("source")] += 1
                elif t == "OUTPUT_REJECTED":
                    for code in p["issue_codes"]:
                        rej[code] += 1
                elif t == "MODEL_FALLBACK":
                    fb[p["reason"]] += 1
                elif t == "NODE_DECISION":
                    node[p["action"]] += 1
                elif t == "MODEL_CALLED" and p.get("model") and p.get("prompt_tokens") is not None:
                    models[p["model"]].append((p["prompt_tokens"], p["completion_tokens"]))
        out[key] = {
            "sessions": len(rows),
            "with_content": len(full),
            "completed": sum(1 for s in full if s["state"]["lifecycle"] == "COMPLETED"),
            "accounts": len({s["student_id"] for s in full}),
            "events": sum(len(s["events"]) for s in full),
            "questions": c["QUESTION_SHOWN"],
            "answers": c["ANSWER_SUBMITTED"],
            "resolved": c["ITEM_RESOLVED"],
            "hint_requests": c["HINT_REQUESTED"],
            "resolution": dict(res),
            "outcome": dict(outcome),
            "hint_levels": {str(k): v for k, v in sorted(hints.items())},
            "tutor_source": dict(src),
            "rejected": dict(rej),
            "fallback": dict(fb),
            "node": dict(node),
            "attempts_mean": st.mean(attempts) if attempts else 0.0,
            "hints_mean": st.mean(hint_counts) if hint_counts else 0.0,
            "models": {
                m: {
                    "calls": len(v),
                    "prompt_mean": st.mean(a for a, _ in v),
                    "completion_mean": st.mean(b for _, b in v),
                }
                for m, v in models.items()
            },
        }
    # hai lần học Tiếng Anh dài nhất, để thấy tác dụng của đợt sửa lỗi
    en = sorted(
        (s for s in sessions if subject_of(s) == "en" and sum(e["event_type"] == "ITEM_RESOLVED" for e in s["events"]) >= 5),
        key=lambda s: s["created_at"]["$date"],
    )
    runs = []
    for s in en:
        src = Counter(e["payload"].get("source") for e in s["events"] if e["event_type"] == "TUTOR_MESSAGE_SENT")
        runs.append(
            {
                "items": sum(e["event_type"] == "ITEM_RESOLVED" for e in s["events"]),
                "model_calls": sum(e["event_type"] == "MODEL_CALLED" for e in s["events"]),
                "tutor_source": dict(src),
            }
        )
    out["en_runs"] = runs
    return out


def write(name: str, text: str) -> None:
    (FIG / name).write_text(HEADER + text, encoding="utf-8")


def tab_overview(d: dict) -> None:
    rows = [
        ("Số buổi học đã ghi", lambda x: integer(x["sessions"])),
        ("Số buổi có nội dung", lambda x: integer(x["with_content"])),
        ("Số buổi đã hoàn thành", lambda x: integer(x["completed"])),
        ("Số tài khoản thử nghiệm", lambda x: integer(x["accounts"])),
        ("Số sự kiện", lambda x: integer(x["events"])),
        ("Số câu hỏi đã hiển thị", lambda x: integer(x["questions"])),
        ("Số lượt trả lời đã chấm", lambda x: integer(x["answers"])),
        ("Số câu đã giải quyết", lambda x: integer(x["resolved"])),
    ]
    body = ""
    for label, f in rows:
        body += label + " & " + " & ".join(f(d[k]) for k, _ in SUBJECTS) + " \\\\\n"
    head = "Chỉ số & " + " & ".join(SHORT[k] for k, _ in SUBJECTS) + " \\\\"
    write(
        "tab-db-overview.tex",
        "\\begin{table}[H]\n\\centering\n\\caption{Quy mô dữ liệu thử nghiệm đọc từ database}\\label{tab:db-overview}\n"
        "\\begin{tabular}{lrrr}\n\\toprule\n" + head + "\n\\midrule\n" + body + "\\bottomrule\n\\end{tabular}\n\\end{table}\n",
    )


def fig_resolution(d: dict) -> None:
    order = [("INDEPENDENT", "Tự làm", "black!15"), ("SUPPORTED", "Có gợi ý", "black!40"),
             ("WORKED", "Làm mẫu", "black!65"), ("UNRESOLVED", "Chưa giải quyết", "black!90")]
    coords = {}
    for code, _, _ in order:
        pts = []
        for i, (k, _) in enumerate(SUBJECTS):
            total = sum(d[k]["resolution"].values()) or 1
            pts.append(f"({100 * d[k]['resolution'].get(code, 0) / total:.1f},{i})")
        coords[code] = " ".join(pts)
    ycoords = ",".join(str(i) for i in range(len(SUBJECTS)))
    ylabels = ",".join("{" + n + "}" for _, n in SUBJECTS)
    adds = ""
    for code, label, color in order:
        adds += f"\\addplot[xbar stacked,fill={color},draw=black] coordinates {{{coords[code]}}};\n"
    legend = ",".join("{" + label + "}" for _, label, _ in order)
    write(
        "fig-db-resolution.tex",
        "\\begin{tikzpicture}\n\\begin{axis}[xbar stacked,width=0.58\\linewidth,height=5.4cm,yticklabel style={font=\\footnotesize,text width=3.6cm,align=right},xmin=0,xmax=100,"
        "bar width=14pt,xlabel={tỉ lệ câu theo cách giải quyết (\\%)},"
        f"ytick={{{ycoords}}},yticklabels={{{ylabels}}},y dir=reverse,"
        "tick label style={font=\\footnotesize},label style={font=\\small},xmajorgrids,"
        "legend style={font=\\footnotesize,at={(0.5,-0.35)},anchor=north,legend columns=2,/tikz/every even column/.append style={column sep=0.4cm},draw=none}]\n"
        + adds
        + f"\\legend{{{legend}}}\n\\end{{axis}}\n\\end{{tikzpicture}}\n",
    )


def fig_hints(d: dict) -> None:
    math = Counter()
    for k in ("dec", "area"):
        math.update({int(a): b for a, b in d[k]["hint_levels"].items()})
    en = Counter({int(a): b for a, b in d["en"]["hint_levels"].items()})

    def series(c: Counter) -> str:
        total = sum(c.values()) or 1
        return " ".join(f"({lv},{100 * c.get(lv, 0) / total:.1f})" for lv in range(1, 8))

    write(
        "fig-db-hints.tex",
        "\\begin{tikzpicture}\n\\begin{axis}[ybar,width=0.92\\linewidth,height=6cm,bar width=7pt,xlabel={bậc gợi ý},"
        "ylabel={tỉ lệ gợi ý đã đưa (\\%)},xtick={1,...,7},ymin=0,ymajorgrids,enlarge x limits=0.1,"
        "tick label style={font=\\footnotesize},label style={font=\\small},"
        "legend style={font=\\footnotesize,at={(0.97,0.95)},anchor=north east,draw=none}]\n"
        f"\\addplot[fill=black!25,draw=black] coordinates {{{series(math)}}};\n"
        f"\\addplot[fill=black!70,draw=black] coordinates {{{series(en)}}};\n"
        f"\\legend{{Toán ($n={sum(math.values())}$),Tiếng Anh ($n={sum(en.values())}$)}}\n"
        "\\end{axis}\n\\end{tikzpicture}\n",
    )


def fig_source(d: dict, others: dict) -> None:
    def merged(src: dict) -> Counter:
        c: Counter = Counter()
        for k in ("dec", "area"):
            c.update(src[k]["tutor_source"])
        return c

    groups = [("Toán, Vuong", merged(d)), ("Toán, tài khoản khác", merged(others))]
    for i, r in enumerate(d["en_runs"], 1):
        groups.append((f"Tiếng Anh, lần {i}", Counter(r["tutor_source"])))
    order = [("LLM", "Mô hình ngôn ngữ viết", "black!15"), ("TEMPLATE", "Câu mẫu của giáo viên", "black!45"),
             ("FALLBACK", "Dự phòng", "black!70"), ("GENERIC", "Câu chung", "black!95")]
    adds = ""
    for code, _, color in order:
        pts = []
        for i, (_, c) in enumerate(groups):
            total = sum(c.values()) or 1
            pts.append(f"({100 * c.get(code, 0) / total:.1f},{i})")
        adds += f"\\addplot[xbar stacked,fill={color},draw=black] coordinates {{{' '.join(pts)}}};\n"
    yt = ",".join(str(i) for i in range(len(groups)))
    yl = ",".join("{" + n + "}" for n, _ in groups)
    legend = ",".join("{" + label + "}" for _, label, _ in order)
    write(
        "fig-db-source.tex",
        "\\begin{tikzpicture}\n\\begin{axis}[xbar stacked,width=0.58\\linewidth,height=5.4cm,yticklabel style={font=\\footnotesize,text width=3.6cm,align=right},xmin=0,xmax=100,"
        "bar width=14pt,xlabel={tỉ lệ phản hồi của gia sư theo nguồn (\\%)},"
        f"ytick={{{yt}}},yticklabels={{{yl}}},y dir=reverse,"
        "tick label style={font=\\footnotesize},label style={font=\\small},xmajorgrids,"
        "legend style={font=\\footnotesize,at={(0.5,-0.35)},anchor=north,legend columns=2,/tikz/every even column/.append style={column sep=0.4cm},draw=none}]\n"
        + adds
        + f"\\legend{{{legend}}}\n\\end{{axis}}\n\\end{{tikzpicture}}\n",
    )


def tab_results(d: dict) -> None:
    rows = ""
    for label, key in [("Tự làm", "INDEPENDENT"), ("Có gợi ý", "SUPPORTED"), ("Làm mẫu", "WORKED"),
                       ("Chưa giải quyết", "UNRESOLVED")]:
        rows += label + " & " + " & ".join(
            f"{integer(d[k]['resolution'].get(key, 0))} ({pct(d[k]['resolution'].get(key, 0), sum(d[k]['resolution'].values()))})"
            for k, _ in SUBJECTS) + " \\\\\n"
    rows += "\\midrule\n"
    for label, key in [("Đúng", "CORRECT"), ("Đúng một phần", "PARTIAL"), ("Sai", "WRONG")]:
        rows += label + " & " + " & ".join(
            f"{integer(d[k]['outcome'].get(key, 0))} ({pct(d[k]['outcome'].get(key, 0), sum(d[k]['outcome'].values()))})"
            for k, _ in SUBJECTS) + " \\\\\n"
    rows += "\\midrule\nSố lần thử trung bình mỗi câu & " + " & ".join(num(d[k]["attempts_mean"], 2) for k, _ in SUBJECTS) + " \\\\\n"
    rows += "Số gợi ý trung bình mỗi câu & " + " & ".join(num(d[k]["hints_mean"], 2) for k, _ in SUBJECTS) + " \\\\\n"
    head = "Chỉ số & " + " & ".join(SHORT[k] for k, _ in SUBJECTS) + " \\\\"
    write(
        "tab-db-results.tex",
        "\\begin{table}[H]\n\\centering\n\\caption{Cách giải quyết câu và kết quả chấm từng lượt trả lời}\\label{tab:db-results}\n"
        "\\begin{tabular}{lrrr}\n\\toprule\n" + head + "\n\\midrule\n" + rows + "\\bottomrule\n\\end{tabular}\n\\end{table}\n",
    )


def tab_nodes(d: dict) -> None:
    acts = [("Vào bài học", "ENTER_NODE"), ("Dạy lý thuyết", "TEACH_THEORY"), ("Hỏi kể lại", "ASK_RETELL"),
            ("Làm mẫu", "SHOW_WORKED_EXAMPLE"), ("Câu luyện tập", "PRACTICE_ITEM"), ("Câu vận dụng", "TRANSFER_ITEM"),
            ("Ôn bài cũ", "RECALL_PRIOR"), ("Qua bài", "PASS_NODE"), ("Dừng bài", "STOP_NODE")]
    rows = ""
    for label, code in acts:
        rows += label + " & " + " & ".join(integer(d[k]["node"].get(code, 0)) for k, _ in SUBJECTS) + " \\\\\n"
    rows += "\\midrule\nTỉ lệ qua bài trên số lần vào & " + " & ".join(
        pct(d[k]["node"].get("PASS_NODE", 0), d[k]["node"].get("ENTER_NODE", 0)) for k, _ in SUBJECTS) + " \\\\\n"
    head = "Quyết định của chính sách dạy & " + " & ".join(SHORT[k] for k, _ in SUBJECTS) + " \\\\"
    write(
        "tab-db-nodes.tex",
        "\\begin{table}[H]\n\\centering\n\\caption{Quyết định của chính sách dạy ghi trong nhật ký}\\label{tab:db-nodes}\n"
        "\\begin{tabular}{lrrr}\n\\toprule\n" + head + "\n\\midrule\n" + rows + "\\bottomrule\n\\end{tabular}\n\\end{table}\n",
    )


def tab_models(d: dict) -> None:
    agg: dict = defaultdict(lambda: {"calls": 0, "p": 0.0, "c": 0.0})
    for k, _ in SUBJECTS:
        for m, v in d[k]["models"].items():
            a = agg[m]
            a["calls"] += v["calls"]
            a["p"] += v["prompt_mean"] * v["calls"]
            a["c"] += v["completion_mean"] * v["calls"]
    rows = ""
    for m, a in sorted(agg.items(), key=lambda x: -x[1]["calls"]):
        rows += f"\\texttt{{{m.replace('_', chr(92) + '_')}}} & {integer(a['calls'])} & {num(a['p'] / a['calls'], 0)} & {num(a['c'] / a['calls'], 0)} \\\\\n"
    fb = Counter()
    for k, _ in SUBJECTS:
        fb.update(d[k]["fallback"])
    names = {"QUOTA": "hết hạn mức", "UNAVAILABLE": "mô hình không phản hồi", "INVALID_OUTPUT": "kết quả không hợp lệ"}
    total_fb = sum(fb.values())
    fbrows = "".join(f"{names.get(r, r)} & {integer(n)} & {pct(n, total_fb)} \\\\\n" for r, n in fb.most_common())
    write(
        "tab-db-models.tex",
        "\\begin{table}[H]\n\\centering\n\\caption{Các mô hình ngôn ngữ được gọi: số lần gọi và số token trung bình mỗi lần}\\label{tab:db-models}\n"
        "\\begin{tabular}{lrrr}\n\\toprule\nMô hình & Số lần gọi & Token vào & Token ra \\\\\n\\midrule\n"
        + rows + "\\bottomrule\n\\end{tabular}\n\\end{table}\n"
        "\\begin{table}[H]\n\\centering\n\\caption{Lý do chuyển sang mô hình kế tiếp}\\label{tab:db-fallback}\n"
        "\\begin{tabular}{lrr}\n\\toprule\nLý do & Số lần & Tỉ lệ \\\\\n\\midrule\n"
        + fbrows + "\\bottomrule\n\\end{tabular}\n\\end{table}\n",
    )


def tab_rejected(d: dict) -> None:
    names = {
        "OUT_OF_UNIT_ENGLISH": "từ tiếng Anh ngoài tư liệu của bài",
        "ANSWER_LEAK": "lộ đáp án",
        "MULTIPLE_QUESTIONS": "nhiều hơn một câu hỏi",
        "MISSING_QUESTION": "thiếu câu hỏi",
        "OFF_ITEM_ENGLISH": "từ ngoài tư liệu của câu",
        "INTELLIGENCE_PRAISE": "khen trí thông minh",
        "TOO_LONG": "quá dài",
        "WRONG_ADDRESS": "xưng hô sai",
        "MODEL_FALLBACK:session_cap": "hết số lệnh gọi của buổi",
        "MODEL_FALLBACK:validation": "mô hình vẫn không qua kiểm chứng",
    }
    rej: dict = defaultdict(lambda: [0, 0])
    for i, (k, _) in enumerate(SUBJECTS):
        for code, n in d[k]["rejected"].items():
            rej[code][0 if k != "en" else 1] += n
    rows = ""
    for code, (m, e) in sorted(rej.items(), key=lambda x: -(x[1][0] + x[1][1])):
        rows += f"{names.get(code, code)} & {integer(m)} & {integer(e)} \\\\\n"
    write(
        "tab-db-rejected.tex",
        "\\begin{table}[H]\n\\centering\n\\caption{Lý do bộ kiểm chứng từ chối phản hồi của gia sư}\\label{tab:db-rejected}\n"
        "\\begin{tabular}{lrr}\n\\toprule\nLý do từ chối & Toán & Tiếng Anh \\\\\n\\midrule\n" + rows
        + "\\bottomrule\n\\end{tabular}\n\\end{table}\n",
    )


def per_session(sessions: list[dict]) -> list[dict]:
    """Từng buổi có nội dung của một tài khoản, theo thứ tự thời gian."""
    rows = []
    for s in sorted(sessions, key=lambda x: x["created_at"]["$date"]):
        ev = s["events"]
        res = [e["payload"] for e in ev if e["event_type"] == "ITEM_RESOLVED"]
        if not res:
            continue
        src = Counter(e["payload"].get("source") for e in ev if e["event_type"] == "TUTOR_MESSAGE_SENT")
        rows.append(
            {
                "subject": subject_of(s),
                "date": s["created_at"]["$date"][:10],
                "status": s["state"]["lifecycle"],
                "items": len(res),
                "independent": sum(r["resolution"] == "INDEPENDENT" for r in res) / len(res),
                "hints": st.mean(r["hints_count"] for r in res),
                "model_calls": sum(e["event_type"] == "MODEL_CALLED" for e in ev),
                "llm_share": src["LLM"] / sum(src.values()) if sum(src.values()) else 0.0,
                "order": [r["resolution"] == "INDEPENDENT" for r in res],
            }
        )
    return rows


def tab_sessions(rows: list[dict]) -> None:
    names = {"dec": "Số thập phân", "area": "Diện tích", "en": "Tiếng Anh"}
    status = {"COMPLETED": "xong", "ACTIVE": "dừng"}
    body = ""
    for i, r in enumerate(rows, 1):
        y, m, d = r["date"].split("-")
        body += (
            f"{i} & {d}/{m} & {names[r['subject']]} & {status.get(r['status'], r['status'])} & {integer(r['items'])} & "
            f"{pct(round(r['independent'] * r['items']), r['items'])} & {num(r['hints'], 2)} & {integer(r['model_calls'])} \\\\\n"
        )
    write(
        "tab-db-sessions.tex",
        "\\begin{table}[H]\n\\centering\n\\caption{Các buổi học của tài khoản Vuong có ít nhất một câu đã giải quyết}\\label{tab:db-sessions}\n"
        "\\small\n\\begin{tabular}{rllrrrrr}\n\\toprule\n"
        "Buổi & Ngày & Nội dung & Kết thúc & Số câu & Tự làm & Gợi ý/câu & Gọi mô hình \\\\\n\\midrule\n"
        + body + "\\bottomrule\n\\end{tabular}\n\\end{table}\n",
    )


def fig_curves(rows: list[dict]) -> None:
    def pts(sub: str) -> str:
        rs = [r for r in rows if r["subject"] == sub and r["items"] >= 8]
        return " ".join(f"({i},{100 * r['independent']:.1f})" for i, r in enumerate(rs, 1))

    def within(subs: tuple[str, ...]) -> str:
        flags = [f for r in rows if r["subject"] in subs and r["items"] >= 8 for f in r["order"]]
        n = len(flags)
        out = []
        for q in range(5):
            part = flags[q * n // 5 : (q + 1) * n // 5]
            out.append(f"({q + 1},{100 * sum(part) / len(part):.1f})" if part else "")
        return " ".join(x for x in out if x)

    write(
        "fig-db-curve.tex",
        "\\begin{tikzpicture}\n\\begin{axis}[width=0.92\\linewidth,height=6cm,xlabel={thứ tự buổi (theo ngày học, mỗi nội dung tính riêng)},"
        "ylabel={tỉ lệ câu tự làm (\\%)},ymin=0,ymax=100,xtick={1,...,9},ymajorgrids,tick label style={font=\\footnotesize},"
        "label style={font=\\small},legend style={font=\\footnotesize,at={(0.5,-0.3)},anchor=north,legend columns=3,draw=none}]\n"
        f"\\addplot[black,solid,mark=*,line width=1pt] coordinates {{{pts('dec')}}};\n"
        f"\\addplot[black!55,dashed,mark=square*,line width=1pt] coordinates {{{pts('area')}}};\n"
        f"\\addplot[black!80,dotted,mark=triangle*,line width=1pt] coordinates {{{pts('en')}}};\n"
        "\\legend{{Toán, Số thập phân},{Toán, Diện tích},{Tiếng Anh, Unit 11}}\n\\end{axis}\n\\end{tikzpicture}\n",
    )
    write(
        "fig-db-within.tex",
        "\\begin{tikzpicture}\n\\begin{axis}[width=0.92\\linewidth,height=5.6cm,xlabel={năm phần của buổi học, từ đầu đến cuối},"
        "ylabel={tỉ lệ câu tự làm (\\%)},ymin=0,ymax=100,xtick={1,...,5},ymajorgrids,tick label style={font=\\footnotesize},"
        "label style={font=\\small},legend style={font=\\footnotesize,at={(0.5,-0.32)},anchor=north,legend columns=2,draw=none}]\n"
        f"\\addplot[black,solid,mark=*,line width=1pt] coordinates {{{within(('dec', 'area'))}}};\n"
        f"\\addplot[black!70,dashed,mark=square*,line width=1pt] coordinates {{{within(('en',))}}};\n"
        "\\legend{Toán,Tiếng Anh}\n\\end{axis}\n\\end{tikzpicture}\n",
    )


PAPER = ROOT.parents[1] / "paper" / "data"


def grading_counts(sessions: list[dict]) -> dict:
    """Chấm lượt trả lời, nhận diện lỗi quan niệm, chấm "vì sao" và chấm kể lại, theo môn."""
    out = {}
    for name, keys in (("math", ("dec", "area")), ("en", ("en",))):
        outcome, errors, misc, why, retell = Counter(), Counter(), Counter(), Counter(), Counter()
        voice = 0
        for s in sessions:
            if subject_of(s) not in keys:
                continue
            for e in s["events"]:
                t, p = e["event_type"], e["payload"]
                if t == "ANSWER_SUBMITTED":
                    outcome[p["outcome"]] += 1
                    voice += p["modality"] != "TEXT"
                    if p["outcome"] == "WRONG":
                        errors[p["error_class"] if p["error_class"] not in (None, "UNKNOWN") else "NONE"] += 1
                elif t == "MISCONCEPTION_DETECTED":
                    misc[p["source"]] += 1
                elif t == "EXPLANATION_SUBMITTED":
                    q = p["reasoning_quality"]
                    why["none" if q is None else f"{q:.1f}"] += 1
                elif t == "RETELL_JUDGED":
                    sc = p["score"]
                    retell["full" if sc >= 0.99 else ("zero" if sc <= 0.01 else "part")] += 1
        out[name] = {"outcome": dict(outcome), "errors": dict(errors), "misconception": dict(misc),
                     "why": dict(why), "retell": dict(retell), "voice": voice}
    return out


def tab_grading(g: dict) -> None:
    m, e = g["math"], g["en"]
    names = {"CONCEPTUAL": "Lỗi khái niệm", "PROCEDURAL": "Lỗi quy trình", "FORMAT": "Lỗi cách viết đáp số",
             "NONE": "Chưa phân loại được"}
    rows = ""
    for code, label in names.items():
        a, b = m["errors"].get(code, 0), e["errors"].get(code, 0)
        rows += f"{label} & {integer(a)} ({pct(a, sum(m['errors'].values()))}) & {integer(b)} ({pct(b, sum(e['errors'].values()))}) \\\\\n"
    rows += f"\\midrule\nTổng số lượt chấm sai & {integer(sum(m['errors'].values()))} & {integer(sum(e['errors'].values()))} \\\\\n"
    rows += f"Lượt chấm đúng một phần & {integer(m['outcome'].get('PARTIAL', 0))} & {integer(e['outcome'].get('PARTIAL', 0))} \\\\\n"
    rows += f"Lỗi quan niệm được nhận ra & {integer(sum(m['misconception'].values()))} & {integer(sum(e['misconception'].values()))} \\\\\n"
    src = {"NUMERIC": "qua so sánh số", "BUG_RULE": "qua luật lỗi", "CHOICE": "qua phương án trắc nghiệm",
           "LLM": "qua nhãn do mô hình đề xuất"}
    for code, label in src.items():
        a, b = m["misconception"].get(code, 0), e["misconception"].get(code, 0)
        if a or b:
            rows += f"\\quad {label} & {integer(a)} & {integer(b)} \\\\\n"
    write(
        "tab-db-grading.tex",
        "\\begin{table}[H]\n\\centering\n\\caption{Phân loại các lượt chấm sai và nhận ra lỗi quan niệm ở tài khoản Vuong}\\label{tab:db-grading}\n"
        "\\begin{tabular}{lrr}\n\\toprule\nChỉ số & Toán & Tiếng Anh \\\\\n\\midrule\n" + rows + "\\bottomrule\n\\end{tabular}\n\\end{table}\n",
    )


def fig_quality(g: dict) -> None:
    def share(d: dict, keys: list[str]) -> str:
        total = sum(d.get(k, 0) for k in keys) or 1
        return " ".join(f"({i + 1},{100 * d.get(k, 0) / total:.1f})" for i, k in enumerate(keys))

    why_keys, retell_keys = ["0.2", "0.6", "1.0"], ["zero", "part", "full"]
    common = ("ybar,width=6.4cm,height=5.4cm,bar width=8pt,ymin=0,ymax=125,ytick={0,20,40,60,80,100},ymajorgrids,enlarge x limits=0.25,"
              "tick label style={font=\\footnotesize},label style={font=\\small},"
              "ylabel={tỉ lệ (\\%)},legend style={font=\\footnotesize,at={(0.97,0.97)},anchor=north east,draw=none}")
    write(
        "fig-db-quality.tex",
        "\\begin{tikzpicture}\n"
        f"\\begin{{axis}}[{common},xlabel={{điểm phản hồi cho câu hỏi vì sao}},xtick={{1,2,3}},xticklabels={{{{0,2}},{{0,6}},{{1,0}}}}]\n"
        f"\\addplot[fill=black!25,draw=black] coordinates {{{share(g['math']['why'], why_keys)}}};\n"
        f"\\addplot[fill=black!70,draw=black] coordinates {{{share(g['en']['why'], why_keys)}}};\n"
        "\\legend{Toán,Tiếng Anh}\n\\end{axis}\n"
        f"\\begin{{axis}}[{common},at={{(7.1cm,0)}},xlabel={{điểm trình bày lại}},xtick={{1,2,3}},xticklabels={{{{không có}},{{một phần}},{{đủ ý}}}}]\n"
        f"\\addplot[fill=black!25,draw=black] coordinates {{{share(g['math']['retell'], retell_keys)}}};\n"
        f"\\addplot[fill=black!70,draw=black] coordinates {{{share(g['en']['retell'], retell_keys)}}};\n"
        "\\legend{Toán,Tiếng Anh}\n\\end{axis}\n\\end{tikzpicture}\n",
    )


def tab_golden() -> None:
    b = json.loads((PAPER / "baselines.json").read_text(encoding="utf-8"))["grading"]
    names = {"C": "Bộ chấm tất định của CAVAT", "B1": "Chatbot thường", "B2": "Chatbot Socratic"}
    rows = ""
    for ver, label in (("v1", "Bộ 1, đã xem trước khi sửa bộ chấm"), ("v2", "Bộ 2, giữ riêng")):
        d = b[ver]
        rows += f"\\multicolumn{{5}}{{l}}{{\\emph{{{label}: {d['n']} câu, trong đó {d['positives']} câu đúng}}}} \\\\\n"
        for k in ("C", "B1", "B2"):
            r = d[k]
            rows += f"\\quad {names[k]} & {integer(r['right'])}/{integer(d['n'])} & {pct(r['right'], d['n'])} & {integer(r['false_positive'])} & {integer(r['false_negative'])} \\\\\n"
        rows += "\\midrule\n"
    rows = rows.rsplit("\\midrule\n", 1)[0]
    write(
        "tab-golden-grading.tex",
        "\\begin{table}[H]\n\\centering\n\\caption{Chấm các câu trả lời điển hình của trẻ, đã gán nhãn tay. Nhận nhầm: nhận một câu sai là đúng; bác nhầm: bác một câu đúng}\\label{tab:golden-grading}\n"
        "\\small\n\\begin{tabular}{>{\\raggedright\\arraybackslash}p{6.5cm}rrrr}\n\\toprule\nHệ chấm & Chấm đúng & Tỉ lệ & Nhận nhầm & Bác nhầm \\\\\n\\midrule\n"
        + rows + "\\bottomrule\n\\end{tabular}\n\\end{table}\n",
    )


def tab_conformance() -> None:
    a = json.loads((PAPER / "assessment.json").read_text(encoding="utf-8"))
    c = a["conformance"]
    mixed, strong = c["mixed"], c["strong"]

    def dev(x: float) -> str:
        return num(x, 4)

    rows = [
        ("Số chuỗi sự kiện", integer(mixed["streams"]), integer(strong["streams"])),
        ("Số sự kiện", integer(mixed["events"]), integer(strong["events"])),
        ("Sai lệch lớn nhất của $M$ so với công thức đóng (điểm trên $100$)", dev(mixed["max_dev_mastery"]), dev(strong["max_dev_mastery"])),
        ("Sai lệch trung bình của $M$", dev(mixed["mean_dev_mastery"]), dev(strong["mean_dev_mastery"])),
        ("Sai lệch lớn nhất của độ tin cậy", dev(mixed["max_dev_confidence"]), dev(strong["max_dev_confidence"])),
        ("Lệch mức hiểu", integer(mixed["level_mismatch"]), integer(strong["level_mismatch"])),
        ("Vi phạm thứ tự, phát lại, giới hạn hoặc cổng", integer(sum(mixed[k] for k in ("order_violations", "replay_violations", "bounds_violations", "gate_violations"))), integer(sum(strong[k] for k in ("order_violations", "replay_violations", "bounds_violations", "gate_violations")))),
        ("Thêm gợi ý mà $M$ tăng", f"{mixed['more_help_violations']}/{mixed['more_help_checked']}", f"{strong['more_help_violations']}/{strong['more_help_checked']}"),
        ("Thay câu sai bằng câu đúng độc lập mà $M$ giảm", f"{mixed['better_outcome_violations']}/{mixed['better_outcome_checked']}", f"{strong['better_outcome_violations']}/{strong['better_outcome_checked']}"),
    ]
    body = "".join(f"{a_} & {b_} & {c_} \\\\\n" for a_, b_, c_ in rows)
    write(
        "tab-learner-conformance.tex",
        "\\begin{table}[H]\n\\centering\n\\caption{Kiểm tương đương giữa phép chiếu mức hiểu và công thức đóng viết độc lập, trên các chuỗi sự kiện ngẫu nhiên}\\label{tab:learner-conformance}\n"
        "\\small\n\\begin{tabular}{p{7.4cm}rr}\n\\toprule\nChỉ số & Học sinh bất kỳ & Học sinh khá \\\\\n\\midrule\n" + body + "\\bottomrule\n\\end{tabular}\n\\end{table}\n",
    )
    # nhóm đã biết
    names = {"gioi": "Giỏi", "sai-dang": "Hay sai dạng", "bi": "Hay xin gợi ý", "hay-sai": "Hay sai", "phu-thuoc": "Phụ thuộc gợi ý"}
    rows = ""
    for k, label in names.items():
        cells = []
        for chap in ("math-g5-decimals", "math-g5-area-triangle-trapezoid"):
            g = a["known_groups"][chap][k]
            cells += [f"{g['passed']}/{g['nodes']}", num(g["mastery_mean"], 1), num(g["level_mean"], 2)]
        rows += label + " & " + " & ".join(cells) + " \\\\\n"
    write(
        "tab-learner-groups.tex",
        "\\begin{table}[H]\n\\centering\n\\caption{Điểm hiểu bài mà phép chiếu gán cho năm kiểu học sinh kịch bản đã biết trước}\\label{tab:learner-groups}\n"
        "\\small\n\\begin{tabular}{lrrrrrr}\n\\toprule\n& \\multicolumn{3}{c}{Số thập phân} & \\multicolumn{3}{c}{Diện tích}\\\\\n"
        "\\cmidrule(lr){2-4}\\cmidrule(lr){5-7}\nKiểu học sinh & Qua bài & $M$ TB & Mức TB & Qua bài & $M$ TB & Mức TB \\\\\n\\midrule\n"
        + rows + "\\bottomrule\n\\end{tabular}\n\\end{table}\n",
    )


MOVE_NAMES = {
    "PRESENT": "Nêu đề", "PROBE": "Hỏi cách làm", "HINT": "Gợi ý", "OFFER_CHOICE": "Mời chọn gợi ý hay tự thử",
    "EXPLAIN": "Giải thích theo yêu cầu", "VERIFY": "Hỏi vì sao", "CONFIRM_ADVANCE": "Khen và sang câu sau",
    "COGNITIVE_CONFLICT": "Ví dụ phản biện", "REDIRECT": "Kéo về câu", "CLOSE": "Khép câu",
    "WORKED_GUIDANCE": "Làm mẫu", "TEACH_BACK": "Mời giảng lại", "CLOSE_ITEM": "Khép câu", "FULL_EXPLANATION": "Giải thích đầy đủ",
    "NUDGE": "Nhắc nhẹ",
}


def socratic_counts(sessions: list[dict]) -> dict:
    """Đặc điểm phản hồi của gia sư theo nước đi: số lượt, số từ, số câu hỏi và nguồn."""
    by_move: dict[str, dict] = {}
    for s in sessions:
        for e in s["events"]:
            if e["event_type"] != "TUTOR_MESSAGE_SENT":
                continue
            p = e["payload"]
            m = by_move.setdefault(p["move"], {"n": 0, "words": [], "multi": 0, "none": 0, "long": 0, "src": Counter()})
            q = p["text"].count("?")
            m["n"] += 1
            m["words"].append(p["words"])
            m["multi"] += q > 1
            m["none"] += q == 0
            m["long"] += p["words"] > 60
            m["src"][p.get("source")] += 1
    out = {}
    for k, m in by_move.items():
        out[k] = {"n": m["n"], "words_mean": st.mean(m["words"]), "multi": m["multi"], "none": m["none"],
                  "long": m["long"], "src": dict(m["src"])}
    return out


def tab_socratic(soc: dict) -> None:
    order = sorted(soc.items(), key=lambda x: -x[1]["n"])
    body = ""
    tot = Counter()
    for k, m in order:
        body += (f"{MOVE_NAMES.get(k, k)} & {integer(m['n'])} & {num(m['words_mean'], 1)} & {integer(m['none'])} & "
                 f"{integer(m['multi'])} & {integer(m['long'])} \\\\\n")
        tot["n"] += m["n"]; tot["none"] += m["none"]; tot["multi"] += m["multi"]; tot["long"] += m["long"]
    mean_all = sum(m["words_mean"] * m["n"] for m in soc.values()) / tot["n"]
    body += (f"\\midrule\nCộng & {integer(tot['n'])} & {num(mean_all, 1)} & {integer(tot['none'])} & "
             f"{integer(tot['multi'])} & {integer(tot['long'])} \\\\\n")
    write(
        "tab-db-socratic.tex",
        "\\begin{table}[H]\n\\centering\n\\caption{Phản hồi của Gia sư AI trong các buổi của tài khoản Vuong, theo nước đi của chính sách. Không có câu hỏi: số lượt không có dấu hỏi; nhiều hơn một câu hỏi: số lượt có nhiều hơn một dấu hỏi; trên $60$ từ: số lượt dài hơn $60$ từ}\\label{tab:db-socratic}\n"
        "\\small\n\\begin{tabular}{lrrrrr}\n\\toprule\n"
        "Nước đi & Số lượt & Từ TB & Không hỏi & $>1$ hỏi & $>60$ từ \\\\\n\\midrule\n"
        + body + "\\bottomrule\n\\end{tabular}\n\\end{table}\n",
    )
    pts = []
    labels = []
    for i, (k, m) in enumerate(order[:8], 1):
        pts.append(f"({i},{m['words_mean']:.1f})")
        labels.append("{" + MOVE_NAMES.get(k, k) + "}")
    write(
        "fig-db-words.tex",
        "\\begin{tikzpicture}\n\\begin{axis}[ybar,width=0.96\\linewidth,height=6.2cm,bar width=12pt,ymin=0,ymax=80,ymajorgrids,"
        "ylabel={số từ trung bình của lượt},xtick={1,...,8},xticklabels={" + ",".join(labels) + "},"
        "xticklabel style={font=\\scriptsize,rotate=30,anchor=east},enlarge x limits=0.08,tick label style={font=\\footnotesize},"
        "label style={font=\\small},legend style={font=\\footnotesize,at={(0.97,0.95)},anchor=north east,draw=none}]\n"
        f"\\addplot[fill=black!35,draw=black] coordinates {{{' '.join(pts)}}};\n"
        "\\draw[dashed,black,line width=0.9pt] (axis cs:0.4,60) -- (axis cs:8.6,60);\n"
        "\\end{axis}\n\\end{tikzpicture}\n",
    )


def main(folder: Path) -> None:
    sessions = load(folder, "learning_sessions") + load(folder, "learning_sessions_archive")
    vuong = [s for s in sessions if s["student_display_name"] == "Vuong"]
    others = [s for s in sessions if s["student_display_name"] != "Vuong"]
    d = collect(vuong)
    rows = per_session(vuong)
    d["sessions_list"] = [{k: v for k, v in r.items() if k != "order"} for r in rows]
    d["others"] = collect(others)
    dall = collect(sessions)
    d["all"] = dall
    tab_sessions(rows)
    fig_curves(rows)
    g = grading_counts(vuong)
    d["grading"] = g
    tab_grading(g)
    fig_quality(g)
    soc = socratic_counts(vuong)
    d["socratic"] = soc
    tab_socratic(soc)
    tab_golden()
    tab_conformance()
    tab_overview(d)
    fig_resolution(d)
    fig_hints(d)
    fig_source(d, d["others"])
    tab_results(d)
    tab_nodes(d)
    tab_models(dall)
    tab_rejected(dall)
    DATA.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print("OK", {k: d[k]["with_content"] for k, _ in SUBJECTS}, "runs", len(d["en_runs"]))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
