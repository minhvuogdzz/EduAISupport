#!/usr/bin/env python3
"""Biên dịch sẵn mỗi figures/fig-*.tex (TikZ, pgfplots) thành figures/pdf/fig-*.pdf.

Overleaf gói miễn phí giới hạn thời gian biên dịch; hơn hai mươi hình pgfplots làm vượt giới hạn, nên
luận văn chèn các tệp PDF này bằng \\includegraphics thay vì dựng lại hình mỗi lần.
    python3 tools/make_fig_pdfs.py   (cần tectonic)
"""
import re, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "figures" / "pdf"
OUT.mkdir(exist_ok=True)
PRE = r"""\documentclass[a4paper,13pt]{report}
\usepackage{fontspec}
\setmainfont{lmroman12-regular.otf}[BoldFont=lmroman12-bold.otf,ItalicFont=lmroman12-italic.otf,BoldItalicFont=lmroman10-bolditalic.otf]
\setsansfont{lmsans10-regular.otf}[BoldFont=lmsans10-bold.otf,ItalicFont=lmsans10-oblique.otf]
\setmonofont{lmmono12-regular.otf}
\usepackage[vietnamese=nohyphenation]{hyphsubst}
\usepackage[vietnamese]{babel}
\usepackage{amsmath,amssymb,tikz,pgfplots,booktabs}
\newcommand{\rid}[1]{\texttt{#1}}
\pgfplotsset{compat=1.16}
\usepgfplotslibrary{groupplots}
\usetikzlibrary{arrows.meta,positioning,fit,backgrounds,shapes.geometric,decorations.pathreplacing,calc}
\usepackage[paperwidth=17cm,paperheight=20cm,margin=0pt]{geometry}
\pagestyle{empty}
\begin{document}
\setlength{\linewidth}{15.9cm}\setlength{\textwidth}{15.9cm}
\centering
"""
names = sys.argv[1:] or [p.stem for p in sorted((ROOT / "figures").glob("fig-*.tex"))]
for n in names:
    src = ROOT / "figures" / f"{n}.tex"
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "f.tex").write_text(PRE + "\\input{" + str(src) + "}\n\\end{document}\n", encoding="utf-8")
        r = subprocess.run(["tectonic", "-X", "compile", "--outdir", str(d), str(d / "f.tex")], capture_output=True, text=True)
        if r.returncode:
            print("LỖI", n, r.stderr[-400:]); continue
        # cắt lề trắng
        pdf = d / "f.pdf"
        import fitz  # PyMuPDF, dùng để cắt lề trắng
        doc = fitz.open(str(pdf))
        pg = doc[0]
        rects = [r["rect"] for r in pg.get_drawings()] + [fitz.Rect(b[:4]) for b in pg.get_text("blocks")]
        box = rects[0]
        for r in rects[1:]:
            box |= r
        pg.set_cropbox(fitz.Rect(box.x0 - 3, box.y0 - 3, box.x1 + 3, box.y1 + 3) & pg.rect)
        doc.save(str(OUT / f"{n}.pdf"))
        print("ok", n)
