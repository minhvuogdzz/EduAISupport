"""How sensitive the answer checks of INGEST-2 are: ``make eval-items`` (read-only, local only).

For every item whose answer the checks verified, each digit of the answer's first line is changed in turn
(to the next digit, and to the digit five away), the item is judged again, and the change counts as caught
when the item turns CONFLICT, or REVIEW for a digit of a worked explanation. A check that lets a wrong
digit through is a gap; the report lists where.

Reads the teacher's documents from the database of services/api/.env and builds the banks in memory: it
writes nothing to the database. The report goes to evals/reports/<date>-item-bank.md (counts and item ids,
no answers of the tests).
"""

from __future__ import annotations

import asyncio
import re
import sys
from collections import Counter
from dataclasses import replace
from datetime import date

from cavat import db
from cavat.config import REPO_ROOT, get_settings
from cavat.modules.ingest.build import ItemDraft, build_bank, judge
from cavat.modules.ingest.service import PREFIXES
from cavat.modules.library.repository import DocumentRepository
from cavat.modules.session.service import DEMO_SCHOOL_ID


def mutations(item: ItemDraft) -> list[str]:
    """The answer with one digit of its first line changed, every way."""
    first, _, rest = item.answer.partition("\n")
    out = []
    for m in re.finditer(r"\d", first):
        for step in (1, 5):
            digit = str((int(m.group(0)) + step) % 10)
            changed = first[: m.start()] + digit + first[m.end() :]
            out.append(changed + ("\n" + rest if rest else ""))
    return out


def sensitivity(items: list[ItemDraft]) -> tuple[int, int, Counter[str]]:
    caught = total = 0
    gaps: Counter[str] = Counter()
    for item in items:
        if item.status != "VERIFIED":
            continue
        for answer in mutations(item):
            again = judge(replace(item, answer=answer, findings=[], disputed=[]))
            total += 1
            if again.status in ("CONFLICT", "REVIEW"):
                caught += 1
            else:
                gaps[item.item_id] += 1
    return caught, total, gaps


async def main() -> None:
    settings = get_settings()
    if settings.mongodb_uri is None:
        sys.exit("MONGODB_URI chưa có trong services/api/.env.")
    documents = await DocumentRepository(db.get_db(settings), DEMO_SCHOOL_ID).list_all()
    lines = [f"# Ngân hàng câu hỏi nháp và độ nhạy của bộ kiểm đáp án ({date.today().isoformat()})", ""]
    lines += ["Chạy bằng `make eval-items` (INGEST-2). Chỉ đọc database, không ghi.", ""]
    for chapter_id, prefix in PREFIXES.items():
        items = build_bank(chapter_id, prefix, [d for d in documents if d.chapter_id == chapter_id])
        counts = Counter(i.status for i in items)
        caught, total, gaps = sensitivity(items)
        rate = f"{caught / total:.1%}" if total else "—"
        lines += [f"## {chapter_id}", ""]
        lines += [
            f"- Số câu: {len(items)}; theo trạng thái: "
            + ", ".join(f"{k} {v}" for k, v in counts.most_common())
        ]
        lines += [f"- Đáp án bị sửa một chữ số: {total} lần, bộ kiểm bắt được {caught} ({rate})"]
        loose = dict.fromkeys(
            f"{prefix}-BT-{i.label}" for i in items if not i.periods and i.source == "BAI_TAP"
        )
        if loose:
            lines += [f"- Câu bài tập chưa tiết nào của giáo án dùng: {', '.join(loose)}"]
        if gaps:
            worst = ", ".join(f"{k} ({v})" for k, v in gaps.most_common(12))
            lines += [f"- Câu còn lọt nhiều nhất: {worst}"]
        lines += [""]
        print(f"{chapter_id}: {len(items)} câu {dict(counts)}; độ nhạy {caught}/{total} = {rate}")
    out = REPO_ROOT / "evals" / "reports" / f"{date.today().isoformat()}-item-bank.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Báo cáo: {out.relative_to(REPO_ROOT)}")
    await db.close_client()


if __name__ == "__main__":
    asyncio.run(main())
