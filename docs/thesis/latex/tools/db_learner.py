#!/usr/bin/env python3
"""Phát lại nhật ký của tài khoản Vuong qua phép chiếu mức hiểu của hệ thống (Chương 4, mục 4.7).

Chạy bằng python của services/api (cần gói cavat):
    services/api/.venv/bin/python docs/thesis/latex/tools/db_learner.py <thư mục sao lưu>

Mỗi nội dung học được dựng lại đúng phiên bản chương mà buổi học đã dùng (bản kế hoạch đã xuất bản trong
teaching_plans, hoặc gói chương trong repo), rồi các buổi được gấp lần lượt theo thời gian bằng
``project_chapter``, đúng như trang giáo viên làm. Chỉ đọc; đầu ra là số tổng hợp.
"""

from __future__ import annotations

import json
import statistics as st
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT.parents[2] / "services" / "api"))

from cavat.modules.assessment.projector import project_chapter  # noqa: E402
from cavat.modules.session.chapter_service import build_chapter, chapter_for  # noqa: E402

FIG = ROOT / "figures"
DATA = ROOT.parent / "data" / "db-learner.json"
HEADER = "% Sinh bởi tools/db_learner.py từ bản sao lưu database; không sửa tay.\n"
NAMES = {"dec": "Số thập phân", "area": "Diện tích", "en": "Tiếng Anh, Unit 11"}


def load(folder: Path, name: str) -> list[dict]:
    return [json.loads(x) for x in (folder / f"{name}.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]


def events_of(s: dict) -> list[SimpleNamespace]:
    out = []
    for e in s["events"]:
        t = e["occurred_at"]
        t = t["$date"] if isinstance(t, dict) else t
        out.append(
            SimpleNamespace(
                event_type=e["event_type"],
                payload=e["payload"],
                session_id=s["_id"],
                occurred_at=datetime.fromisoformat(t.replace("Z", "+00:00")),
            )
        )
    return out


def key_of(s: dict) -> str:
    if s["lesson_id"].startswith("eng"):
        return "en"
    return "dec" if "decimals" in s["lesson_id"] else "area"


def chapter_of(s: dict, plans: dict):
    plan = plans.get(s["lesson_id"], {})
    snap = plan.get("published", {}).get(s["lesson_version"])
    if snap is not None:
        return build_chapter(snap["package"], snap["lessons"])
    subject = "english" if s["lesson_id"].startswith("eng") else "math"
    return chapter_for(s["lesson_id"], None, subject)


def write(name: str, text: str) -> None:
    (FIG / name).write_text(HEADER + text, encoding="utf-8")


def num(x: float | None, nd: int = 1) -> str:
    return "--" if x is None else "$" + f"{x:.{nd}f}".replace(".", "{,}") + "$"


def main(folder: Path) -> None:
    sessions = load(folder, "learning_sessions") + load(folder, "learning_sessions_archive")
    plans = {d["chapter_id"]: d for d in load(folder, "teaching_plans")}
    vuong = sorted(
        (s for s in sessions if s["student_display_name"] == "Vuong"), key=lambda s: s["created_at"]["$date"]
    )
    result: dict = {}
    for k in ("dec", "area", "en"):
        chain = [
            s
            for s in vuong
            if key_of(s) == k
            and any(e["event_type"] == "ITEM_RESOLVED" for e in s["events"])
            and (k == "en" or s["lesson_version"].startswith("tl-"))
        ]
        history: list = []
        steps = []
        projection = None
        for s in chain:
            history += events_of(s)
            projection = project_chapter(history, chapter_of(s, plans))
            nodes = list(projection.nodes.values())
            ms = [n.mastery for n in nodes if n.mastery is not None]
            steps.append(
                {
                    "date": s["created_at"]["$date"][:10],
                    "nodes": len(nodes),
                    "passed": sum(n.passed_at is not None for n in nodes),
                    "mean_m": st.mean(ms) if ms else None,
                    "mean_level": st.mean(n.level for n in nodes),
                }
            )
        assert projection is not None
        nodes = list(projection.nodes.values())
        dims = {}
        for d in ("C", "R", "A", "T", "I"):
            vals = [n.dimensions[d].mean for n in nodes if n.dimensions[d].n_eff > 0]
            vals = [v * 100 if v <= 1 else v for v in vals]
            dims[d] = st.mean(vals) if vals else None
        mis = Counter(m.status for n in nodes for m in n.misconceptions)
        miss = Counter(g for n in nodes if n.passed_at is None for g in n.missing)
        result[k] = {
            "sessions": len(chain),
            "steps": steps,
            "levels": dict(Counter(n.level for n in nodes)),
            "dims": dims,
            "misconceptions": dict(mis),
            "missing": dict(miss),
            "per_node_m": [n.mastery for n in nodes],
            "confidence_mean": st.mean(n.confidence for n in nodes),
        }
    DATA.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    tables(result)
    print("OK", {k: (v["sessions"], v["steps"][-1]["passed"], v["steps"][-1]["nodes"]) for k, v in result.items()})


def tables(r: dict) -> None:
    keys = ("dec", "area", "en")
    rows = [
        ("Số buổi đã gấp", lambda x: f"${x['sessions']}$"),
        ("Số bài của chương", lambda x: f"${x['steps'][-1]['nodes']}$"),
        ("Số bài đã qua", lambda x: f"${x['steps'][-1]['passed']}$"),
        ("Điểm hiểu bài $M$ trung bình", lambda x: num(x["steps"][-1]["mean_m"])),
        ("Mức hiểu trung bình (thang $0$--$5$)", lambda x: num(x["steps"][-1]["mean_level"], 2)),
        ("Độ tin cậy trung bình", lambda x: num(x["confidence_mean"])),
        ("Chiều khái niệm $C$", lambda x: num(x["dims"]["C"])),
        ("Chiều lập luận $R$", lambda x: num(x["dims"]["R"])),
        ("Chiều vận dụng $A$", lambda x: num(x["dims"]["A"])),
        ("Chiều độc lập $I$", lambda x: num(x["dims"]["I"])),
    ]
    body = "".join(lab + " & " + " & ".join(f(r[k]) for k in keys) + " \\\\\n" for lab, f in rows)
    head = "Chỉ số & Số thập phân & Diện tích & Tiếng Anh \\\\"
    write(
        "tab-db-mastery.tex",
        "\\begin{table}[H]\n\\centering\n\\caption{Trạng thái mức hiểu của tài khoản Vuong sau khi gấp mọi buổi của từng chương}\\label{tab:db-mastery}\n"
        "\\begin{tabular}{lrrr}\n\\toprule\n" + head + "\n\\midrule\n" + body + "\\bottomrule\n\\end{tabular}\n\\end{table}\n",
    )
    series = []
    styles = ["black,solid,mark=*", "black!55,dashed,mark=square*", "black!80,dotted,mark=triangle*"]
    for k, style in zip(keys, styles):
        pts = " ".join(f"({i},{s['mean_m']:.1f})" for i, s in enumerate(r[k]["steps"], 1) if s["mean_m"] is not None)
        series.append(f"\\addplot[{style},line width=1pt] coordinates {{{pts}}};\n")
    legend = ",".join("{" + NAMES[k] + "}" for k in keys)
    write(
        "fig-db-mastery.tex",
        "\\begin{tikzpicture}\n\\begin{axis}[width=0.92\\linewidth,height=6cm,xlabel={số buổi đã gấp vào phép chiếu},"
        "ylabel={điểm hiểu bài $M$ trung bình},ymin=60,ymax=100,xtick={1,...,6},ymajorgrids,tick label style={font=\\footnotesize},"
        "label style={font=\\small},legend style={font=\\footnotesize,at={(0.5,-0.3)},anchor=north,legend columns=3,draw=none}]\n"
        + "".join(series) + f"\\legend{{{legend}}}\n\\end{{axis}}\n\\end{{tikzpicture}}\n",
    )
    bars = []
    fills = ["black!20", "black!50", "black!80"]
    for k, fill in zip(keys, fills):
        pts = " ".join(f"({i},{m:.1f})" for i, m in enumerate(r[k]["per_node_m"], 1) if m is not None)
        bars.append(f"\\addplot[fill={fill},draw=black] coordinates {{{pts}}};\n")
    write(
        "fig-db-nodem.tex",
        "\\begin{tikzpicture}\n\\begin{axis}[ybar,width=0.96\\linewidth,height=6cm,bar width=4pt,xlabel={thứ tự bài trong chương},"
        "ylabel={điểm hiểu bài $M$},ymin=0,ymax=100,xtick={1,...,11},ymajorgrids,enlarge x limits=0.06,"
        "tick label style={font=\\footnotesize},label style={font=\\small},"
        "legend style={font=\\footnotesize,at={(0.5,-0.3)},anchor=north,legend columns=3,draw=none}]\n"
        + "".join(bars) + f"\\legend{{{legend}}}\n\\end{{axis}}\n\\end{{tikzpicture}}\n",
    )


if __name__ == "__main__":
    main(Path(sys.argv[1]))
