"""Where the bandit's learning lives: one document per school, bandit version and arm (BANDIT-1, ADR-058).

A document holds the additive sums of ``bandit.LinUCB`` (``n``, ``b_i``, ``a_i_j``), so one reward is one
``$inc``: atomic on Atlas M0, which has no multi-document transaction (CLAUDE.md rule 10), and independent of
the order of the rewards. The collection is a projection of the ``BANDIT_REWARD`` events and can be dropped
and rebuilt from them (``rebuild``): only the item loop produces rewards, never a model (rule 3). Every
document carries ``school_id`` and every query is scoped to it (rule 5).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from cavat.core.repository import ASCENDING, IndexSpec, TenantScopedRepository, new_id
from cavat.modules.tutor.bandit import BANDIT_VERSION, DEFAULT_ALPHA, DEFAULT_RIDGE, LinUCB, increments

_META = frozenset({"_id", "school_id", "version", "arm"})


class BanditRepository(TenantScopedRepository):
    collection_name = "bandit_arms"
    indexes = (
        IndexSpec(
            (("school_id", ASCENDING), ("version", ASCENDING), ("arm", ASCENDING)),
            "bandit_arm_unique",
            unique=True,
        ),
    )

    async def load(self, *, alpha: float = DEFAULT_ALPHA, ridge: float = DEFAULT_RIDGE) -> LinUCB:
        """The school's bandit under the current version: an empty one until rewards arrive."""
        docs = await self._find({"version": BANDIT_VERSION})
        per_arm = {d["arm"]: {k: v for k, v in d.items() if k not in _META} for d in docs}
        return LinUCB.from_stats(per_arm, alpha=alpha, ridge=ridge)

    async def apply(self, rewards: Iterable[Mapping[str, Any]]) -> int:
        """Add the rewards of a committed command. Returns how many were added."""
        added = 0
        for r in rewards:
            if r.get("version") != BANDIT_VERSION:
                continue  # a reward of another version belongs to another projection
            await self._find_one_and_update(
                {"version": BANDIT_VERSION, "arm": r["arm"]},
                {"$inc": increments(r["context"], float(r["reward"])), "$setOnInsert": {"_id": new_id()}},
                upsert=True,
            )
            added += 1
        return added

    async def rebuild(self, rewards: Iterable[Mapping[str, Any]]) -> int:
        """Drop the school's projection and fold the rewards again (replay)."""
        for doc in await self._find({"version": BANDIT_VERSION}):
            await self._delete_one({"_id": doc["_id"]})
        return await self.apply(rewards)
