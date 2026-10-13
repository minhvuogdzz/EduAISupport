"""Which misconceptions of the published chapters the tutor can recognise: `make misconception-coverage`.

MISC-1 (DI-54): the published plans are read from the database of services/api/.env (read only) and
enriched by `misconception_rules`; the report says, per period, how many items reveal a misconception
in a wrong answer, and which misconceptions the teacher's documents name stay unrecognisable (no family
of mistakes, or no item where their wrong answer can be computed). Written to
evals/reports/<date>-misconception-coverage.md.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import date

from cavat import db
from cavat.config import REPO_ROOT, get_settings
from cavat.modules.assessment.misconception_rules import RULES_VERSION, coverage, families
from cavat.modules.session import chapter_service
from cavat.modules.session.service import DEMO_SCHOOL_ID


async def main() -> int:
    database = db.get_db(get_settings())
    await chapter_service.load_published(database, DEMO_SCHOOL_ID)
    await db.close_client()
    lines = [
        f"# Lỗi sai gia sư nhận ra được trên hai chương đã phát hành ({date.today().isoformat()})",
        "",
        f"`{RULES_VERSION}` (DI-54). Lệnh: `make misconception-coverage` (chỉ đọc database).",
    ]
    for _, chapter in sorted(chapter_service.chapters().items()):
        if not chapter.package.version.startswith("tl-"):
            continue  # a chapter file, not a published plan
        rows = list(coverage(chapter))
        by_item: dict[str, set[str]] = defaultdict(set)
        for _, item_id, _, mid in rows:
            by_item[item_id].add(mid)
        lines += [
            "",
            f"## {chapter.package.title}",
            "",
            "| Tiết | Câu số/chọn | Câu nhận ra lỗi sai | Lỗi sai nhận ra |",
            "|---|---|---|---|",
        ]
        for node_id in chapter.topological_order():
            items = [
                it
                for lesson in chapter.lessons.values()
                for it in lesson.items
                if node_id in it.kc_ids and it.answer.type in ("numeric", "choice")
            ]
            found = [it for it in items if it.id in by_item]
            mids = sorted({m for it in found for m in by_item[it.id]})
            lines.append(
                f"| {chapter.node(node_id).name} | {len(items)} | {len(found)} | {', '.join(mids) or '—'} |"
            )
        recognised = {mid for _, _, _, mid in rows}
        bugs = {m.id for lesson in chapter.lessons.values() for m in lesson.misconceptions if m.bug_rule}
        found_ids = recognised | bugs
        every = [m for lesson in chapter.lessons.values() for m in lesson.misconceptions]
        family_of = {m.id: families(m) for m in every}
        lines += ["", "Lỗi sai trong tài liệu:", ""]
        for m in every:
            fam = ", ".join(sorted(family_of[m.id])) or "chưa có họ lỗi"
            kin = sorted(o.id for o in every if o.id in found_ids and family_of[o.id] & family_of[m.id])
            if m.id in bugs:
                state = "nhận ra (câu so sánh)"
            elif m.id in recognised:
                state = "nhận ra"
            elif kin:
                state = f"cùng họ, câu sai được ghi vào {', '.join(kin)}"
            else:
                state = "**chưa nhận ra**"
            lines.append(f"- {m.id} ({m.severity}) «{m.name}»: {fam}; {state}")
    report = "\n".join(lines) + "\n"
    print(report)
    out = REPO_ROOT / "evals/reports" / f"{date.today().isoformat()}-misconception-coverage.md"
    out.write_text(report, encoding="utf-8")
    print(f"Report: {out.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
