"""Node teaching policy: deterministic rules N-* over the chapter graph (plan v1, 5.4; ADR-018).

``decide`` maps the chapter, the node mastery projection (M1-3) and the session's teaching state to one
``NodeDecisionMade``. Each decision names its rule, so it can be explained, tested rule by rule and
replayed (rule 7: the policy is versioned). The LLM only phrases what a decision points to: a theory
variant, a worked example, an item or the retell prompt. Rules, in priority order:

- N-FINISH    no node left to learn and no stopped node to teach again: end the session with a summary;
- N-REVIEW    just after a pass: one item of a node passed earlier (interleaving);
- N-NEXT      no current node: resume the node on hold, else the first unlocked node not passed, else (DI-80)
              a node stopped today and not taught again yet: its second pass (another example, a short round
              of the questions not solved, no warm-up, recall or detour; once per node);
- N-PASS      the pass rule holds (DI-15);
- N-BUDGET    the node used its item budget, or has no item left: stop it, "cần học lại";
- N-REMEDIATE a critical misconception of an earlier node, a failed warm-up item, or a second failed
              check while a prerequisite is weak: put the node on hold and teach that prerequisite;
- N-WARMUP    entering a node whose prerequisite has no evidence in this session: one quick item of it;
- N-RECALL    (DI-52) entering a node without a warm-up, or its first check failed: the child recalls the key
              idea of a related node learnt before (the closest prerequisite first, then a similar node),
              once per pair in a session; the reply is judged like a retell and is evidence on that node;
- N-TEACH     nothing taught in this visit: the first theory variant not used in the session;
- N-CHECK     after teaching: a concept-check item, then the retell; later also when explanation is missing;
- N-RETEACH   the check failed: the next theory variant; none left, a worked example with high support;
- N-METHOD    the check passed: a worked example, then the "cùng làm" item;
- N-PRACTICE  successes, mastery or a misconception still missing: the next practice item;
- N-TRANSFER  enough practice but no application evidence: a transfer item.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable

from cavat.core.events import NodeDecisionMade
from cavat.core.pedagogy import PracticeSupport, TeachAction
from cavat.modules.assessment.projector import ChapterProjection, NodeState
from cavat.modules.content.chapter_package import Chapter, Node
from cavat.modules.content.lesson_package import Item
from cavat.modules.teaching.state import DEFAULT_CONFIG, NodePolicyConfig, TeachingState, Visit

_SUPPORT_BY_BAND = (
    PracticeSupport.EXPLAIN_FIRST,
    PracticeSupport.GUIDED,
    PracticeSupport.ASK_WHY,
    PracticeSupport.TRANSFER,
    PracticeSupport.CHALLENGE,
)


class PendingResult(RuntimeError):
    """The last item or retell has no result yet: the teaching loop must finish it first."""


def decide(
    chapter: Chapter,
    projection: ChapterProjection,
    state: TeachingState,
    config: NodePolicyConfig = DEFAULT_CONFIG,
) -> NodeDecisionMade:
    return _Policy(chapter, projection, state, config).decide()


def misconceptions_probed(item: Item) -> set[str]:
    """Misconceptions an item can reveal from its answer spec (compare and order items use bug rules)."""
    answer = item.answer
    if answer.type in ("numeric", "boolean"):
        return set(answer.wrong_answers.values())
    if answer.type == "choice":
        found = {m for o in answer.options for m in o.misconceptions}
        return found | {m for o in answer.options if o.probe for m in (o.probe.if_wrong, o.probe.if_correct)}
    return set()


class _Policy:
    def __init__(
        self, chapter: Chapter, projection: ChapterProjection, state: TeachingState, config: NodePolicyConfig
    ) -> None:
        self.chapter, self.state, self.config = chapter, state, config
        self.nodes: dict[str, NodeState] = projection.nodes
        self.order = chapter.topological_order()
        self.seen = {e.item_id for e in projection.evidence if e.item_id}  # items met in any session

    def decide(self) -> NodeDecisionMade:
        st = self.state
        if st.finished:
            return self._make(TeachAction.FINISH, "N-FINISH", reasons=["ALREADY_FINISHED"])
        visit = st.current
        if visit is None:
            return self._between_nodes()
        if visit.pending is not None or visit.retell_pending or visit.recall_pending is not None:
            what = visit.pending or (
                "the retell" if visit.retell_pending else f"the recall of {visit.recall_pending}"
            )
            raise PendingResult(f"waiting for {what} at {visit.node_id}")
        return self._in_node(visit)

    # ------------------------------------------------------------------ between nodes

    def _between_nodes(self) -> NodeDecisionMade:
        st = self.state
        if st.review_due and not st.waiting and (review := self._review()) is not None:
            return review
        if st.waiting:
            return self._make(TeachAction.ENTER_NODE, "N-NEXT", st.waiting[-1], reasons=["RESUME"])
        for node_id in self.order:
            ns = self.nodes[node_id]
            if node_id in st.stopped or ns.passed_at is not None:
                continue
            prerequisites = self.chapter.prerequisites(node_id)
            if all(self._done(p) for p in prerequisites):
                # FLOW-1 (DI-75): a period the child used up today does not end the session.
                after_stop = any(self.nodes[p].passed_at is None for p in prerequisites)
                reasons = ["UNLOCKED_AFTER_STOP" if after_stop else "UNLOCKED"]
                return self._make(TeachAction.ENTER_NODE, "N-NEXT", node_id, reasons=reasons)
        # FLOW-2 (DI-80): back to a period stopped today, once, in the order of the chapter.
        for node_id in self.order:
            if (
                node_id in st.stopped
                and node_id not in st.second_pass
                and self.nodes[node_id].passed_at is None
            ):
                pick = self._second_pass_pick(self.chapter.node(node_id))
                same = pick[2] if pick else []
                return self._make(TeachAction.ENTER_NODE, "N-NEXT", node_id, reasons=["SECOND_PASS", *same])
        return self._make(TeachAction.FINISH, "N-FINISH", reasons=["NO_NODE_LEFT"])

    def _done(self, node_id: str) -> bool:
        """Passed, or stopped today: the next period may come either way (DI-75)."""
        return self.nodes[node_id].passed_at is not None or node_id in self.state.stopped

    def _review(self) -> NodeDecisionMade | None:
        just = self.state.passed[-1] if self.state.passed else None
        passed = [n for n in self.order if n != just and self.nodes[n].passed_at is not None]
        for node_id in sorted(passed, key=lambda n: (self.nodes[n].mastery or 0.0, self.order.index(n))):
            node = self.chapter.node(node_id)
            fresh = self._fresh([*node.practice, *node.transfer])
            if fresh:
                return self._make(
                    TeachAction.REVIEW_ITEM, "N-REVIEW", node_id, fresh[0], reasons=[f"AFTER_PASS:{just}"]
                )
        return None

    # ------------------------------------------------------------------ in a node

    def _in_node(self, visit: Visit) -> NodeDecisionMade:
        node_id = visit.node_id
        node, ns = self.chapter.node(node_id), self.nodes[node_id]
        if ns.pass_now:
            return self._make(TeachAction.PASS_NODE, "N-PASS", node_id)
        if visit.items >= self._budget(visit, node):
            return self._make(TeachAction.STOP_NODE, "N-BUDGET", node_id, reasons=["BUDGET", *ns.missing])
        switch = None if visit.second else self._misconception_remediation(node_id)  # DI-80: no detour
        if switch is not None:
            return switch
        if visit.phase == "NEW":
            return self._start(visit, node)
        if visit.phase == "CHECK":
            return self._check(visit, node)
        if visit.phase == "CHECK_FAILED":
            return self._reteach(visit, node)
        return self._practice(visit, node, ns)

    def _misconception_remediation(self, node_id: str) -> NodeDecisionMade | None:
        for home in self._ancestors(node_id):
            active = [
                m
                for m in self.nodes[home].misconceptions
                if m.severity == "CRITICAL" and m.status != "RESOLVED"
            ]
            if active and self._may_remediate(node_id, home):
                return self._make(
                    TeachAction.SWITCH_TO_PREREQUISITE,
                    "N-REMEDIATE",
                    home,
                    reasons=[f"MISCONCEPTION:{active[0].id}"],
                )
        return None

    def _budget(self, visit: Visit, node: Node) -> int:
        return self.config.second_pass_items if visit.second else node.pass_rule.max_items

    def _start(self, visit: Visit, node: Node) -> NodeDecisionMade:
        if visit.second:
            return self._second_pass(visit, node)
        if visit.warmup_item is None:
            warmup = self._warmup(node)
            if warmup is not None:
                return warmup
            if not visit.recalls and (recall := self._recall(node, "AT_ENTRY")) is not None:
                return recall
        elif (
            visit.warmup_ok is False and visit.warmup_node and self._may_remediate(node.id, visit.warmup_node)
        ):
            return self._make(
                TeachAction.SWITCH_TO_PREREQUISITE,
                "N-REMEDIATE",
                visit.warmup_node,
                reasons=["WARMUP_FAILED"],
            )
        return self._teach(visit, node, "N-TEACH")

    def _second_pass_pick(self, node: Node) -> tuple[TeachAction, str, list[str]] | None:
        """DI-80: what teaches the node again, not used in this session yet: a worked example, else a theory
        variant, else the earliest used (``SAME_*``, the loop says it is done more slowly)."""
        used_examples = self.state.examples_used.get(node.id, [])
        used_variants = self.state.variants_used.get(node.id, [])
        for w in node.worked_examples:
            if w.id not in used_examples:
                return TeachAction.SHOW_WORKED_EXAMPLE, w.id, []
        for t in node.theory:
            if t.id not in used_variants:
                return TeachAction.TEACH_THEORY, t.id, []
        if used_examples:
            return TeachAction.SHOW_WORKED_EXAMPLE, used_examples[0], ["SAME_EXAMPLE"]
        if used_variants:
            return TeachAction.TEACH_THEORY, used_variants[0], ["SAME_VARIANT"]
        return None

    def _second_pass(self, visit: Visit, node: Node) -> NodeDecisionMade:
        """DI-80: the second pass teaches again with what the first did not use, then goes to the questions.
        No warm-up, recall or detour in it."""
        pick = self._second_pass_pick(node)
        if pick is None:
            return self._practice(visit, node, self.nodes[node.id], modelled=True)
        action, ref, same = pick
        support = PracticeSupport.EXPLAIN_FIRST if action == TeachAction.SHOW_WORKED_EXAMPLE else None
        return self._make(action, "N-RETEACH", node.id, ref, support, ["SECOND_PASS", *same])

    def _warmup(self, node: Node) -> NodeDecisionMade | None:
        missing = [p for p in self.chapter.prerequisites(node.id) if p not in self.state.evidence_nodes]
        for prereq in sorted(missing, key=lambda p: (self.nodes[p].mastery or 0.0, self.order.index(p))):
            pn = self.chapter.node(prereq)
            fresh = self._fresh([*pn.practice, *pn.checks, *pn.transfer])
            if fresh:
                return self._make(
                    TeachAction.WARMUP_ITEM, "N-WARMUP", prereq, fresh[0], reasons=[f"FOR:{node.id}"]
                )
        return None

    def _recall(self, node: Node, why: str) -> NodeDecisionMade | None:
        """DI-52: a related node the child has learnt (passed, or met in this session), not recalled for
        this node yet: a prerequisite first, the closest one first (the latest in the chapter order, the one
        the node builds on directly), then a similar node. Not one just re-taught."""
        if not self.config.recall_prior:
            return None
        prereqs = self.chapter.prerequisites(node.id)
        similar = [n for rel in ("SIMILAR", "SUBCLASS") for n in self.chapter.related(node.id, rel)]
        known = [
            n
            for n in dict.fromkeys([*prereqs, *similar])
            if n != node.id
            and (self.nodes[n].passed_at is not None or n in self.state.evidence_nodes)
            and (node.id, n) not in self.state.recalled
            and (node.id, n) not in self.state.remediated
            and self.chapter.node(n).explain.key_ideas
        ]
        if not known:
            return None
        pick = min(known, key=lambda n: (n not in prereqs, -self.order.index(n)))
        return self._make(TeachAction.RECALL_PRIOR, "N-RECALL", node.id, pick, reasons=[why])

    def _teach(self, visit: Visit, node: Node, rule: str, reasons: Iterable[str] = ()) -> NodeDecisionMade:
        used = self.state.variants_used.get(node.id, [])
        ids = [t.id for t in node.theory]
        variant = next((v for v in ids if v not in used), None)
        variant = variant or next((v for v in ids if v not in visit.taught), ids[0])
        return self._make(TeachAction.TEACH_THEORY, rule, node.id, variant, reasons=reasons)

    def _check(self, visit: Visit, node: Node) -> NodeDecisionMade:
        if visit.check_item is None:
            fresh = self._fresh(node.checks, visit=visit)
            if fresh:
                return self._make(TeachAction.CHECK_ITEM, "N-CHECK", node.id, fresh[0])
        if not visit.retell_asked:
            return self._make(TeachAction.ASK_RETELL, "N-CHECK", node.id)
        raise PendingResult(f"the check of {node.id} has no verdict")

    def _reteach(self, visit: Visit, node: Node) -> NodeDecisionMade:
        failures = visit.check_failures
        if failures >= self.config.remediate_after_check_failures and not visit.second:
            weak = [
                p
                for p in self.chapter.prerequisites(node.id)
                if not self.nodes[p].pass_now and self._may_remediate(node.id, p)
            ]
            if weak:
                weakest = min(weak, key=lambda p: (self.nodes[p].mastery or 0.0, self.order.index(p)))
                return self._make(
                    TeachAction.SWITCH_TO_PREREQUISITE, "N-REMEDIATE", weakest, reasons=["CHECK_FAILED_TWICE"]
                )
        if failures == 1 and not visit.second and (recall := self._recall(node, "CHECK_FAILED")) is not None:
            return recall
        untaught = [t.id for t in node.theory if t.id not in visit.taught]
        used = self.state.variants_used.get(node.id, [])
        variant = next((v for v in untaught if v not in used), untaught[0] if untaught else None)
        if variant is not None:
            return self._make(
                TeachAction.TEACH_THEORY, "N-RETEACH", node.id, variant, reasons=[f"CHECK_FAILED:{failures}"]
            )
        example = self._unused_example(visit, node)
        if example is not None:
            return self._make(
                TeachAction.SHOW_WORKED_EXAMPLE,
                "N-RETEACH",
                node.id,
                example,
                support=PracticeSupport.EXPLAIN_FIRST,
                reasons=["NO_VARIANT_LEFT"],
            )
        return self._practice(visit, node, self.nodes[node.id], modelled=True)

    def _practice(self, visit: Visit, node: Node, ns: NodeState, modelled: bool = False) -> NodeDecisionMade:
        support = self._support(ns)
        if not visit.examples and not modelled:
            example = self._unused_example(visit, node)
            if example is not None:
                return self._make(TeachAction.SHOW_WORKED_EXAMPLE, "N-METHOD", node.id, example)
        if not visit.completion_asked:
            fresh = self._fresh(node.completion, visit=visit)
            if fresh:
                return self._make(TeachAction.COMPLETION_ITEM, "N-METHOD", node.id, fresh[0], support)
        missing = set(ns.missing)
        active = {m.id for m in ns.misconceptions if m.status != "RESOLVED"}
        practice = self._fresh(node.practice, probing=active, visit=visit)
        if "UNDERSTOOD" in missing:
            # DI-49, also while a misconception is followed (0.3.1): the items probing it come first, but
            # one that adds the missing form still comes in time, or the budget ends the period (seen when
            # MISC-1 found "quên chia 2" and every probing item was a number to fill in).
            practice = self._covering(practice, ns, self._budget(visit, node) - visit.items)
        transfer = self._fresh(node.transfer, visit=visit)
        reasons = sorted(missing)
        # DI-80: in a second pass ``_fresh`` already brings back the items missed, so no DI-56 retry
        if "UNDERSTOOD" in missing and not visit.second and (again := self._retry_for_form(visit, node, ns)):
            return self._make(
                TeachAction.PRACTICE_ITEM, "N-PRACTICE", node.id, again, support, [*reasons, "RETRY_FORM"]
            )
        enough_practice = visit.practice_successes >= self.config.practice_before_transfer or not practice
        if "APPLICATION" in missing and transfer and enough_practice:
            return self._make(TeachAction.TRANSFER_ITEM, "N-TRANSFER", node.id, transfer[0], support, reasons)
        if missing & {"UNDERSTOOD", "MASTERY", "MISCONCEPTION"} and practice:
            return self._make(TeachAction.PRACTICE_ITEM, "N-PRACTICE", node.id, practice[0], support, reasons)
        if "APPLICATION" in missing and transfer:
            return self._make(TeachAction.TRANSFER_ITEM, "N-TRANSFER", node.id, transfer[0], support, reasons)
        if "EXPLANATION" in missing and visit.retells < self.config.max_retells:
            return self._make(TeachAction.ASK_RETELL, "N-CHECK", node.id, reasons=["EXPLANATION_MISSING"])
        if transfer:
            return self._make(TeachAction.TRANSFER_ITEM, "N-PRACTICE", node.id, transfer[0], support, reasons)
        checks = self._fresh(node.checks, visit=visit)
        if checks:
            return self._make(TeachAction.CHECK_ITEM, "N-PRACTICE", node.id, checks[0], support, reasons)
        return self._make(TeachAction.STOP_NODE, "N-BUDGET", node.id, reasons=["NO_ITEMS_LEFT", *reasons])

    # ------------------------------------------------------------------ helpers

    def _make(
        self,
        action: TeachAction,
        rule: str,
        node_id: str | None = None,
        ref: str | None = None,
        support: PracticeSupport | None = None,
        reasons: Iterable[str] = (),
    ) -> NodeDecisionMade:
        return NodeDecisionMade(
            action=action,
            node_id=node_id,
            ref=ref,
            support=support,
            rule_ids=[rule],
            reason_codes=list(reasons),
            policy_version=self.config.version,
        )

    def _may_remediate(self, node_id: str, prereq: str) -> bool:
        """Each (node, prerequisite) detour happens once per session, never to a node stopped already."""
        return prereq not in self.state.stopped and (node_id, prereq) not in self.state.remediated

    def _ancestors(self, node_id: str) -> list[str]:
        found: set[str] = set()
        todo = list(self.chapter.prerequisites(node_id))
        while todo:
            n = todo.pop()
            if n not in found:
                found.add(n)
                todo.extend(self.chapter.prerequisites(n))
        return [n for n in self.order if n in found]

    def _fresh(
        self, item_ids: Iterable[str], probing: Collection[str] = (), visit: Visit | None = None
    ) -> list[str]:
        """Items not asked in this session: those probing an active misconception first, then those
        never met in any session, then file order. In a second pass (DI-80) the items asked earlier and
        not self-solved (``missed``) come back too, once each in the visit."""
        if visit is not None and visit.second:
            candidates = [
                i
                for i in item_ids
                if i not in visit.asked and (i not in self.state.asked or i in self.state.missed)
            ]
        else:
            candidates = [i for i in item_ids if i not in self.state.asked]

        def key(pair: tuple[int, str]) -> tuple[bool, bool, int]:
            index, item_id = pair
            probes = bool(probing) and bool(misconceptions_probed(self.chapter.item(item_id)) & set(probing))
            return (not probes, item_id in self.seen, index)

        return [item_id for _, item_id in sorted(enumerate(candidates), key=key)]

    def _covering(self, item_ids: list[str], ns: NodeState, budget_left: int) -> list[str]:
        """DI-49: an item that adds the question form or cognitive level "understood" still lacks is moved
        forward when the list is longer than the budget left and, in file order, the budget would run out
        before it (two tries kept)."""

        def adds(item_id: str) -> bool:
            item = self.chapter.item(item_id)
            return item.answer.type not in ns.forms or item.cognitive_level not in ns.levels

        first = next((k for k, item_id in enumerate(item_ids) if adds(item_id)), None)
        if first is None or first < budget_left - 2 or len(item_ids) <= budget_left:
            return item_ids  # reached in time, or the whole list fits in the budget: file order
        return [item_ids[first], *item_ids[:first], *item_ids[first + 1 :]]

    def _retry_for_form(self, visit: Visit, node: Node, ns: NodeState) -> str | None:
        """DI-56: when no fresh item adds the question form or level "understood" still lacks, the item that
        adds it and was not solved earlier is asked once more (a period with one open question among its
        number items could never pass after a first miss on it)."""
        every = [*node.checks, *node.completion, *node.practice, *node.transfer]

        def adds(item_id: str) -> bool:
            item = self.chapter.item(item_id)
            return item.answer.type not in ns.forms or item.cognitive_level not in ns.levels

        if any(adds(i) for i in self._fresh(every)):
            return None
        return next((i for i in every if i in self.state.asked and i not in visit.retried and adds(i)), None)

    def _unused_example(self, visit: Visit, node: Node) -> str | None:
        used = self.state.examples_used.get(node.id, [])
        ids = [w.id for w in node.worked_examples if w.id not in visit.examples]
        return next((w for w in ids if w not in used), ids[0] if ids else None)

    def _support(self, ns: NodeState) -> PracticeSupport:
        """DI-8: the band of the node's mastery picks the support; no score yet means GUIDED."""
        if ns.mastery is None:
            return PracticeSupport.GUIDED
        return _SUPPORT_BY_BAND[sum(ns.mastery >= b for b in self.config.support_bands)]
