"""Dựng bảng và đồ thị của mục bandit (Chương 4) từ docs/thesis/data/bandit-eval.json.

Chạy: python3 docs/thesis/latex/tools/bandit_tex.py  (make eval-bandit tạo tệp JSON trước).
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT.parent / "data" / "bandit-eval.json"
report = json.loads(DATA.read_text(encoding="utf-8"))
policies = report["policies"]

NAMES = {
    "policy": "Nước của chính sách",
    "random": "Ngẫu nhiên",
    "least-help": "Giúp ít nhất",
    "bandit": "Bandit ($\\varepsilon=0{,}1$)",
    "bandit-greedy": "Bandit ($\\varepsilon=0$)",
    "oracle": "Oracle",
}


def num(pair, digits=3):
    mean, half = pair
    return f"{mean:.{digits}f}".replace(".", "{,}") + " \\pm " + f"{half:.{digits}f}".replace(".", "{,}")


rows = []
for key, label in NAMES.items():
    p = policies[key]
    rows.append(
        f"{label} & ${num(p['regret_total'], 1)}$ & ${num(p['best_move_rate_last_quarter'])}$ "
        f"& ${num(p['reward_last_quarter'])}$ \\\\"
    )
table = (
    "% Sinh bởi tools/bandit_tex.py từ docs/thesis/data/bandit-eval.json; không sửa tay.\n"
    "\\begin{table}[ht]\n\\centering\n"
    "\\caption{Kết quả trên môi trường mô phỏng, $3\\,000$ lượt, $30$ hạt giống, trung bình $\\pm$ khoảng tin cậy "
    "$95\\%$. Hai cột cuối tính trên một phần tư số lượt cuối.}\n"
    "\\label{tab:bandit-results}\n\\small\n"
    "\\begin{tabularx}{\\linewidth}{@{}Xrrr@{}}\n\\toprule\n"
    "Chính sách & Hối tiếc tích lũy & Chọn đúng nước tốt nhất & Phần thưởng \\\\\n\\midrule\n"
    + "\n".join(rows)
    + "\n\\bottomrule\n\\end{tabularx}\n\\end{table}\n"
)
(ROOT / "figures" / "tab-bandit.tex").write_text(table, encoding="utf-8")

styles = {
    "policy": "black,dotted,line width=0.9pt",
    "random": "black!60,dashed,line width=0.9pt",
    "least-help": "black!60,dash dot,line width=0.9pt",
    "bandit": "black,solid,line width=1.2pt",
    "bandit-greedy": "black!45,solid,line width=0.9pt",
}
legend = {
    "policy": "Nước của chính sách",
    "random": "Ngẫu nhiên",
    "least-help": "Giúp ít nhất",
    "bandit": "Bandit ($\\varepsilon=0{,}1$)",
    "bandit-greedy": "Bandit ($\\varepsilon=0$)",
}
lines = [
    "% Sinh bởi tools/bandit_tex.py từ docs/thesis/data/bandit-eval.json; không sửa tay.",
    "\\begin{tikzpicture}",
    "\\begin{axis}[width=0.92\\linewidth,height=6.4cm,xlabel={số lượt đã chơi},"
    "ylabel={hối tiếc trung bình mỗi lượt},xmin=0,xmax=3000,ymin=0,ymajorgrids,xtick={0,1000,2000,3000},",
    "  legend style={font=\\footnotesize,at={(0.5,-0.32)},anchor=north,legend columns=3,draw=none},",
    "  tick label style={font=\\footnotesize},label style={font=\\small},axis lines=left]",
]
for key in styles:
    curve = policies[key]["regret_curve"]
    coords = " ".join(f"({(i + 1) * 100},{v:.4f})" for i, v in enumerate(curve))
    lines.append(f"\\addplot[{styles[key]}] coordinates {{{coords}}};")
lines.append("\\legend{" + ",".join("{" + legend[k] + "}" for k in styles) + "}")
lines += ["\\end{axis}", "\\end{tikzpicture}"]
(ROOT / "figures" / "fig-bandit-regret.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")

ips = report["ips_check"]
print("ips", {k: [round(x, 3) for x in v] for k, v in ips.items()})
print("rounds", report["rounds"], "seeds", report["seeds"], "share", report["best_arm_share"])
