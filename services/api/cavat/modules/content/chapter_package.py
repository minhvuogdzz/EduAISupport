"""Chapter package: the knowledge graph of one chapter and what the tutor teaches at each node.

Plan v1 (`docs/plan/plan-v1-teaching-knowledge-graph.md`, section 5.1) and ADR-018. Loaded from YAML
(`docs/pedagogy/**/chapter.yaml`); the items themselves stay in the chapter's lesson packages.

The graph follows the 2T-KT paper (Li et al., Information Fusion 126, 2026): nodes sit in two layers,
BASIC concepts and IMPLEMENT concepts (the operations that apply them). Inside a layer a node can have a
PREREQUISITE, a SUBCLASS or a SIMILAR node; between layers the only relation is APPLICATION, from a BASIC
node to the IMPLEMENT node that applies it. PREREQUISITE and APPLICATION both mean "learn the source
first": together they are the learning order and must have no cycle.

Each node carries its teaching content by stage (the paper's Exposure, Comprehension, Practice and
Transfer): theory explained in at least two ways, the rule and its method, worked examples, a retell
prompt with the ideas a good explanation must contain, and the items used to check, practise and apply.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from cavat.modules.content.lesson_package import Item, LessonPackage, Persona, load_lesson_package

NodeLayer = Literal["BASIC", "IMPLEMENT"]
RelationType = Literal["PREREQUISITE", "SUBCLASS", "SIMILAR", "APPLICATION"]
Stage = Literal["EXPOSURE", "COMPREHENSION", "PRACTICE", "TRANSFER"]

ORDER_RELATIONS = frozenset({"PREREQUISITE", "APPLICATION"})  # "learn the source before the target"


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TheoryVariant(_Model):
    """One way of explaining the node (stage EXPOSURE). Re-teaching uses a variant not used yet."""

    id: str
    representation: str  # the concrete picture it relies on: bảng hàng, trục số, tiền, đo độ dài...
    text: str  # short: three or four sentences
    ask: str  # the question that ends the explanation and makes the student think
    # ADR-019: what the tutor says after the student's reply to `ask` (the reason, in one or two
    # sentences), and the ways of writing the right answer. Not graded: the theory is teaching, not a test.
    reply: str = ""
    accept: list[str] = []


class Method(_Model):
    rule: str
    steps: list[str]


class WorkedExample(_Model):
    """'Cô làm mẫu': every step says what is done and why."""

    id: str
    problem: str
    steps: list[str]
    answer: str


class ExplainSpec(_Model):
    """The retell prompt of stage COMPREHENSION and what a good explanation must contain.

    Each key idea lists phrasings that count as that idea (DI: keyword rubric until the LLM label of
    milestone 2). Matching is done on normalized text.
    """

    prompt: str
    key_ideas: list[list[str]]


class PassRule(_Model):
    """When the student may leave the node (DI-15, defaults from blueprint PART 26.1)."""

    min_mastery: float = Field(default=0.75, ge=0.0, le=1.0)  # level 4 APPLIED (§4-§8)
    min_successes: int = Field(default=3, ge=1)  # §52 UNDERSTOOD: >= 3 successful evidence
    min_levels: int = Field(default=2, ge=1)  # ... on >= 2 cognitive levels
    min_forms: int = Field(default=2, ge=1)  # ... and >= 2 question forms
    require_explanation: bool = True  # DI-6: reasoning evidence with mu_R >= 0.6
    require_application: bool = True  # DI-6: application evidence
    max_items: int = Field(default=12, ge=1)  # N-BUDGET


class Node(_Model):
    id: str  # also the KC id in its lesson package
    name: str
    layer: NodeLayer
    description: str
    lesson_id: str  # the lesson package holding the node's items
    theory: list[TheoryVariant]
    method: Method
    worked_examples: list[WorkedExample]
    explain: ExplainSpec
    checks: list[str]  # CONCEPT_CHECK items (stage COMPREHENSION)
    completion: list[str] = Field(default_factory=list)  # "cùng làm" items (stage PRACTICE)
    practice: list[str]  # PRACTICE items (stage PRACTICE)
    transfer: list[str]  # PRACTICE items of a new form (stage TRANSFER)
    pass_rule: PassRule = Field(default_factory=PassRule)
    home_tip: str = ""  # for the parent: how to practise this node at home, in everyday words


class Relation(_Model):
    source: str
    target: str
    type: RelationType
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    origin: Literal["TEACHER", "LLM"] = "TEACHER"  # LLM-proposed relations keep their score (2T-KT)


class ChapterPackage(_Model):
    chapter_id: str
    version: str
    status: Literal["DRAFT", "APPROVED", "PUBLISHED", "ARCHIVED"]
    subject: Literal["math"]
    grade: int
    locale: str = "vi-VN"
    title: str
    persona: Persona = Field(default_factory=Persona)
    lessons: list[str]  # lesson.yaml paths, relative to the chapter file
    nodes: list[Node]
    relations: list[Relation]


@dataclass(frozen=True)
class Chapter:
    """A chapter package with its lesson packages loaded."""

    package: ChapterPackage
    lessons: Mapping[str, LessonPackage]  # by lesson_id
    _items: Mapping[str, tuple[Item, LessonPackage]] = field(default_factory=dict, repr=False)

    @property
    def nodes(self) -> list[Node]:
        return self.package.nodes

    def node(self, node_id: str) -> Node:
        for node in self.package.nodes:
            if node.id == node_id:
                return node
        raise KeyError(node_id)

    def item(self, item_id: str) -> Item:
        return self._items[item_id][0]

    def lesson_of(self, item_id: str) -> LessonPackage:
        return self._items[item_id][1]

    def prerequisites(self, node_id: str) -> list[str]:
        """Nodes to learn before this one (PREREQUISITE and APPLICATION edges into it), in file order."""
        return [r.source for r in self.package.relations if r.target == node_id and r.type in ORDER_RELATIONS]

    def dependents(self, node_id: str) -> list[str]:
        return [r.target for r in self.package.relations if r.source == node_id and r.type in ORDER_RELATIONS]

    def related(self, node_id: str, relation: RelationType) -> list[str]:
        """Neighbours by one relation type, in either direction (SIMILAR is symmetric)."""
        out = [r.target for r in self.package.relations if r.source == node_id and r.type == relation]
        out += [r.source for r in self.package.relations if r.target == node_id and r.type == relation]
        return out

    def topological_order(self) -> list[str]:
        """Learning order: every node after its prerequisites; file order breaks ties. Raises on a cycle."""
        order: list[str] = []
        done: set[str] = set()
        remaining = [n.id for n in self.package.nodes]
        while remaining:
            ready = next((n for n in remaining if set(self.prerequisites(n)) <= done), None)
            if ready is None:
                raise ValueError(f"learning order has a cycle among {remaining}")
            order.append(ready)
            done.add(ready)
            remaining.remove(ready)
        return order


def load_chapter(path: str | Path) -> Chapter:
    path = Path(path)
    package = ChapterPackage.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    lessons: dict[str, LessonPackage] = {}
    for rel in package.lessons:
        lesson = load_lesson_package(path.parent / rel)
        if lesson.lesson_id in lessons:
            raise ValueError(f"lesson {lesson.lesson_id} is listed twice in {path.name}")
        lessons[lesson.lesson_id] = lesson
    items = {it.id: (it, lesson) for lesson in lessons.values() for it in lesson.items}
    return Chapter(package=package, lessons=lessons, _items=items)


def validate_chapter(chapter: Chapter) -> list[str]:
    """Invariants beyond the schema: graph shape, references, and enough teaching content per node."""
    problems: list[str] = []
    pkg = chapter.package
    nodes = {n.id: n for n in pkg.nodes}
    if len(nodes) != len(pkg.nodes):
        problems.append("duplicate node ids")

    seen: set[tuple[str, str, str]] = set()
    for r in pkg.relations:
        name = f"{r.source} -{r.type}-> {r.target}"
        if r.source not in nodes or r.target not in nodes:
            problems.append(f"{name}: unknown node")
            continue
        if r.source == r.target:
            problems.append(f"{name}: self loop")
        if (r.source, r.target, r.type) in seen:
            problems.append(f"{name}: duplicate relation")
        seen.add((r.source, r.target, r.type))
        same_layer = nodes[r.source].layer == nodes[r.target].layer
        if r.type == "APPLICATION" and not (
            nodes[r.source].layer == "BASIC" and nodes[r.target].layer == "IMPLEMENT"
        ):
            problems.append(f"{name}: APPLICATION goes from a BASIC to an IMPLEMENT node")
        if r.type != "APPLICATION" and not same_layer:
            problems.append(f"{name}: {r.type} links nodes of the same layer (use APPLICATION across)")
    try:
        chapter.topological_order()
    except ValueError as exc:
        problems.append(str(exc))

    owner: dict[str, str] = {}  # item ids are chapter-wide: Chapter.item() looks them up without a lesson
    for lesson in chapter.lessons.values():
        for it in lesson.items:
            if it.id in owner and owner[it.id] != lesson.lesson_id:
                problems.append(f"item {it.id} is in lessons {owner[it.id]} and {lesson.lesson_id}")
            owner.setdefault(it.id, lesson.lesson_id)

    for node in pkg.nodes:
        if node.layer == "IMPLEMENT" and not any(
            r.target == node.id and r.type == "APPLICATION" for r in pkg.relations
        ):
            problems.append(f"{node.id}: an IMPLEMENT node must apply at least one BASIC node")
        problems += _node_content_problems(chapter, node)
        problems += _node_item_problems(chapter, node)
        problems += _pass_rule_problems(chapter, node)
        problems += _lesson_prerequisite_problems(chapter, node)
    if not any(not chapter.prerequisites(n.id) for n in pkg.nodes):
        problems.append("no starting node: every node has a prerequisite")
    return problems


def _node_content_problems(chapter: Chapter, node: Node) -> list[str]:
    problems: list[str] = []
    representations = {t.representation for t in node.theory}
    if len(node.theory) < 2 or len(representations) < 2:
        problems.append(f"{node.id}: needs at least 2 theory variants with different representations")
    for t in node.theory:
        if not t.ask.rstrip().endswith("?"):
            problems.append(f"{node.id}/{t.id}: the theory must end with a question")
    if not node.method.rule or not node.method.steps:
        problems.append(f"{node.id}: method needs a rule and at least one step")
    if not node.worked_examples or any(len(w.steps) < 2 for w in node.worked_examples):
        problems.append(f"{node.id}: needs a worked example with at least 2 steps")
    if not node.explain.key_ideas or any(not idea for idea in node.explain.key_ideas):
        problems.append(f"{node.id}: explain needs key ideas")
    if not node.explain.prompt.rstrip().endswith("?"):
        problems.append(f"{node.id}: the retell prompt must be a question")
    for name, refs, minimum in (
        ("checks", node.checks, 1),
        ("practice", node.practice, 2),
        ("transfer", node.transfer, 1),
    ):
        if len(refs) < minimum:
            problems.append(f"{node.id}: needs at least {minimum} {name} item(s)")
    return problems


def _node_item_problems(chapter: Chapter, node: Node) -> list[str]:
    problems: list[str] = []
    lesson = chapter.lessons.get(node.lesson_id)
    if lesson is None:
        return [f"{node.id}: unknown lesson {node.lesson_id}"]
    if node.id not in {kc.id for kc in lesson.kcs}:
        problems.append(f"{node.id}: not a KC of lesson {node.lesson_id}")
    groups = (("checks", node.checks, "CONCEPT_CHECK"), ("completion", node.completion, "PRACTICE"))
    groups += (("practice", node.practice, "PRACTICE"), ("transfer", node.transfer, "PRACTICE"))
    used: set[str] = set()
    for name, refs, purpose in groups:
        for item_id in refs:
            if item_id in used:
                problems.append(f"{node.id}: item {item_id} is used twice")
            used.add(item_id)
            try:
                item = lesson.item(item_id)
            except KeyError:
                problems.append(f"{node.id}: {name} item {item_id} is not in lesson {node.lesson_id}")
                continue
            if item.purpose != purpose:
                problems.append(f"{node.id}: {name} item {item_id} must have purpose {purpose}")
            if node.id not in item.kc_ids:
                problems.append(f"{node.id}: {name} item {item_id} does not practise this node")
            if name == "transfer" and item.transfer == "none" and item.cognitive_level not in ("D", "E"):
                problems.append(f"{node.id}: transfer item {item_id} is neither a transfer nor level D/E")
    return problems


def _pass_rule_problems(chapter: Chapter, node: Node) -> list[str]:
    """The node's items must make its pass rule reachable (§52 UNDERSTOOD, DI-15).

    A cognitive level is A-E (DIAG items diagnose, they are not a level); a question form is the answer
    type (DI: choice, numeric, compare, order, boolean, open). "Cùng làm" items give part of the solution,
    so they are not counted (DI): the student must reach the rule with the items done alone.
    """
    lesson = chapter.lessons.get(node.lesson_id)
    if lesson is None:
        return []
    known = {it.id: it for it in lesson.items}
    refs = (*node.checks, *node.practice, *node.transfer)
    items = [known[ref] for ref in refs if ref in known]
    rule = node.pass_rule
    levels = {it.cognitive_level for it in items} - {"DIAG"}
    forms = {it.answer.type for it in items}
    problems: list[str] = []
    needs = "the pass rule needs"
    if len(items) < rule.min_successes:
        problems.append(f"{node.id}: {len(items)} item(s), {needs} {rule.min_successes} successes")
    if len(levels) < rule.min_levels:
        problems.append(f"{node.id}: items cover {len(levels)} cognitive level(s), {needs} {rule.min_levels}")
    if len(forms) < rule.min_forms:
        problems.append(f"{node.id}: items cover {len(forms)} question form(s), {needs} {rule.min_forms}")
    if rule.min_successes > rule.max_items:
        problems.append(f"{node.id}: the pass rule needs more successes than its item budget")
    return problems


def _lesson_prerequisite_problems(chapter: Chapter, node: Node) -> list[str]:
    """The chapter graph is the source of truth; the lesson's KC prerequisites must agree with it."""
    lesson = chapter.lessons.get(node.lesson_id)
    kc = next((k for k in lesson.kcs if k.id == node.id), None) if lesson else None
    if kc is None:
        return []
    in_lesson = {k.id for k in lesson.kcs}
    from_graph = {p for p in chapter.prerequisites(node.id) if p in in_lesson}
    if set(kc.prerequisites) != from_graph:
        lesson_view, graph_view = sorted(kc.prerequisites), sorted(from_graph)
        return [f"{node.id}: lesson prerequisites {lesson_view} differ from the graph {graph_view}"]
    return []
