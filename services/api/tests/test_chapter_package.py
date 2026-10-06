"""Chapter package (M1-2): graph shape, references and teaching content checks on a small chapter."""

import copy
from pathlib import Path

import pytest
import yaml
from cavat.modules.content.chapter_package import load_chapter, validate_chapter
from cavat.modules.content.lesson_package import validate_package

CHAPTER_FILE = Path(__file__).resolve().parents[3] / "docs/pedagogy/math-g5/chuong-so-thap-phan/chapter.yaml"


def _item(item_id, kc, purpose="PRACTICE", level="B", transfer="none"):
    return {
        "id": item_id,
        "purpose": purpose,
        "kc_ids": [kc],
        "cognitive_level": level,
        "difficulty": 0.4,
        "transfer": transfer,
        "stem": f"Câu {item_id}",
        "answer": {"type": "boolean", "value": True}
        if purpose == "CONCEPT_CHECK"
        else {"type": "numeric", "value": "1"},
    }


LESSON = {
    "lesson_id": "mini",
    "version": "0.1.0",
    "status": "DRAFT",
    "subject": "math",
    "grade": 5,
    "title": "Bài mini",
    "objectives": [{"id": "LO1", "text": "Học A, B, C.", "kc_ids": ["A", "B", "C"]}],
    "kcs": [
        {"id": "A", "name": "A", "description": "a", "prerequisites": []},
        {"id": "B", "name": "B", "description": "b", "prerequisites": ["A"]},
        {"id": "C", "name": "C", "description": "c", "prerequisites": ["B"]},
    ],
    "items": [
        _item(f"{kc}-{kind}{n}", kc, purpose, level, transfer)
        for kc in "ABC"
        for kind, n, purpose, level, transfer in (
            ("CHK", 1, "CONCEPT_CHECK", "A", "none"),
            ("CMP", 1, "PRACTICE", "B", "none"),
            ("PR", 1, "PRACTICE", "B", "none"),
            ("PR", 2, "PRACTICE", "B", "none"),
            ("TR", 1, "PRACTICE", "D", "near"),
            ("EX", 1, "EXIT", "B", "none"),
        )
    ],
}


def _node(node_id, layer):
    return {
        "id": node_id,
        "name": f"Node {node_id}",
        "layer": layer,
        "description": "mô tả",
        "lesson_id": "mini",
        "theory": [
            {"id": "T1", "representation": "bảng hàng", "text": "Giảng.", "ask": "Con thấy sao?"},
            {"id": "T2", "representation": "trục số", "text": "Giảng cách khác.", "ask": "Còn cách này?"},
        ],
        "method": {"rule": "Quy tắc.", "steps": ["Bước 1."]},
        "worked_examples": [{"id": "W1", "problem": "Ví dụ", "steps": ["Làm.", "Vì sao."], "answer": "1"}],
        "explain": {"prompt": "Con nói lại giúp cô nhé?", "key_ideas": [["ý một"], ["ý hai", "ý 2"]]},
        "checks": [f"{node_id}-CHK1"],
        "completion": [f"{node_id}-CMP1"],
        "practice": [f"{node_id}-PR1", f"{node_id}-PR2"],
        "transfer": [f"{node_id}-TR1"],
    }


CHAPTER = {
    "chapter_id": "mini-chapter",
    "version": "0.1.0",
    "status": "DRAFT",
    "subject": "math",
    "grade": 5,
    "title": "Chương mini",
    "lessons": ["lesson.yaml"],
    "nodes": [_node("A", "BASIC"), _node("B", "BASIC"), _node("C", "IMPLEMENT")],
    "relations": [
        {"source": "A", "target": "B", "type": "PREREQUISITE"},
        {"source": "B", "target": "C", "type": "APPLICATION"},
    ],
}


def make(tmp_path, edit_chapter=None, edit_lesson=None):
    chapter, lesson = copy.deepcopy(CHAPTER), copy.deepcopy(LESSON)
    if edit_chapter:
        edit_chapter(chapter)
    if edit_lesson:
        edit_lesson(lesson)
    (tmp_path / "lesson.yaml").write_text(yaml.safe_dump(lesson, allow_unicode=True), encoding="utf-8")
    path = tmp_path / "chapter.yaml"
    path.write_text(yaml.safe_dump(chapter, allow_unicode=True), encoding="utf-8")
    return load_chapter(path)


def problems(tmp_path, edit_chapter=None, edit_lesson=None):
    return validate_chapter(make(tmp_path, edit_chapter, edit_lesson))


def test_a_valid_chapter_has_no_problems_and_a_learning_order(tmp_path):
    ch = make(tmp_path)
    assert validate_chapter(ch) == []
    assert ch.topological_order() == ["A", "B", "C"]
    assert (ch.prerequisites("C"), ch.dependents("A")) == (["B"], ["B"])
    assert ch.item("B-PR1").kc_ids == ["B"] and ch.lesson_of("B-PR1").lesson_id == "mini"


def test_the_learning_order_must_have_no_cycle(tmp_path):
    def cycle(ch):
        ch["relations"].append({"source": "B", "target": "A", "type": "PREREQUISITE"})

    found = problems(tmp_path, cycle, lambda le: le["kcs"][0].update(prerequisites=["B"]))
    assert any("cycle" in p for p in found)


@pytest.mark.parametrize(
    ("relation", "expected"),
    [
        ({"source": "C", "target": "A", "type": "APPLICATION"}, "APPLICATION goes from a BASIC"),
        ({"source": "A", "target": "C", "type": "PREREQUISITE"}, "links nodes of the same layer"),
        ({"source": "A", "target": "Z", "type": "SIMILAR"}, "unknown node"),
        ({"source": "A", "target": "A", "type": "SIMILAR"}, "self loop"),
    ],
)
def test_relation_rules_from_the_paper(tmp_path, relation, expected):
    found = problems(tmp_path, lambda ch: ch["relations"].append(relation))
    assert any(expected in p for p in found), found


def test_an_implement_node_must_apply_a_basic_node(tmp_path):
    def drop(ch):
        ch["relations"] = [r for r in ch["relations"] if r["type"] != "APPLICATION"]

    found = problems(tmp_path, drop, lambda le: le["kcs"][2].update(prerequisites=[]))
    assert any("must apply at least one BASIC node" in p for p in found)


def test_teaching_content_must_be_complete(tmp_path):
    def thin(ch):
        node = ch["nodes"][0]
        node["theory"] = node["theory"][:1]
        node["explain"]["prompt"] = "Con nói lại."
        node["worked_examples"][0]["steps"] = ["Chỉ một bước."]
        node["practice"] = node["practice"][:1]
        node["transfer"] = []

    found = problems(tmp_path, thin)
    for expected in ("2 theory variants", "retell prompt", "worked example", "2 practice", "1 transfer"):
        assert any(expected in p for p in found), expected


def test_item_references_are_checked(tmp_path):
    def bad_refs(ch):
        node = ch["nodes"][1]
        node["checks"] = ["B-PR1"]  # a practice item used as a check
        node["practice"] = ["B-PR2", "A-PR1", "B-MISSING"]  # another node's item, a missing one
        node["transfer"] = ["B-EX1"]  # an exit item can never be practice

    found = problems(tmp_path, bad_refs)
    assert any("checks item B-PR1 must have purpose CONCEPT_CHECK" in p for p in found)
    assert any("A-PR1 does not practise this node" in p for p in found)
    assert any("B-MISSING is not in lesson" in p for p in found)
    assert any("transfer item B-EX1 must have purpose PRACTICE" in p for p in found)


def test_lesson_prerequisites_must_agree_with_the_graph(tmp_path):
    found = problems(tmp_path, edit_lesson=lambda le: le["kcs"][1].update(prerequisites=[]))
    assert any("B: lesson prerequisites [] differ from the graph ['A']" in p for p in found)


def test_item_ids_must_be_unique_across_the_chapter_lessons(tmp_path):
    other = copy.deepcopy(LESSON) | {"lesson_id": "other", "items": [copy.deepcopy(LESSON["items"][0])]}
    (tmp_path / "other.yaml").write_text(yaml.safe_dump(other, allow_unicode=True), encoding="utf-8")
    found = problems(tmp_path, lambda ch: ch["lessons"].append("other.yaml"))
    assert "item A-CHK1 is in lessons mini and other" in found


def test_a_lesson_cannot_be_listed_twice(tmp_path):
    with pytest.raises(ValueError, match="listed twice"):
        make(tmp_path, lambda ch: ch["lessons"].append("lesson.yaml"))


def test_the_pass_rule_must_be_reachable_with_the_node_items(tmp_path):
    def strict(ch):
        ch["nodes"][0]["pass_rule"] = {"min_levels": 4, "min_forms": 3, "min_successes": 6, "max_items": 5}

    found = [p for p in problems(tmp_path, strict) if p.startswith("A:")]
    assert found == [
        "A: 5 item(s), the pass rule needs 6 successes",
        "A: items cover 3 cognitive level(s), the pass rule needs 4",
        "A: items cover 2 question form(s), the pass rule needs 3",
        "A: the pass rule needs more successes than its item budget",
    ]


def test_the_decimals_chapter_is_valid():
    chapter = load_chapter(CHAPTER_FILE)
    assert validate_chapter(chapter) == []
    for lesson in chapter.lessons.values():
        assert validate_package(lesson) == [], lesson.lesson_id
    assert chapter.topological_order() == [
        "KC-DEC-FRAC",
        "KC-DEC-CONCEPT",
        "KC-DEC-PLACE",
        "KC-DEC-EQ",
        "KC-DEC-CMP",
        "KC-DEC-ORDER",
        "KC-DEC-APPLY",
    ]
    implement = [n.id for n in chapter.nodes if n.layer == "IMPLEMENT"]
    assert implement == ["KC-DEC-CMP", "KC-DEC-ORDER", "KC-DEC-APPLY"]
