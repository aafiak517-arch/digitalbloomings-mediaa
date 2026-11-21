"""Pick the day's 2 promotional and 3 educational reels.

Selection rules:
- Promos go to two different products. Products in their seasonal selling
  window come first (closest to ending first), then the least recently
  promoted ones.
- A product never gets an angle it already used until every angle it has
  has been used once, so scripts don't repeat back to back.
- Educational topics rotate by least recently used.

History lives in a small JSON file so rotation survives between runs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path

from .checks import CheckResult
from .platforms import PlatformPost, build_posts
from .products import Product
from .scripts import (TOPICS, TOPICS_BY_ID, ReelScript, angles_for,
                      build_educational, build_promo)

PROMOS_PER_DAY = 2
EDUCATIONAL_PER_DAY = 3


@dataclass
class History:
    # product_id -> list of {"date", "angle"}
    promos: dict[str, list[dict]] = field(default_factory=dict)
    # topic_id -> last date used (ISO)
    topics: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path | None) -> "History":
        if not path or not Path(path).exists():
            return cls()
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(promos=data.get("promos", {}), topics=data.get("topics", {}))

    def save(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps({"promos": self.promos, "topics": self.topics}, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def last_promoted(self, product_id: str) -> str:
        entries = self.promos.get(product_id, [])
        return max((e["date"] for e in entries), default="")

    def used_angles(self, product_id: str) -> list[str]:
        return [e["angle"] for e in sorted(self.promos.get(product_id, []), key=lambda e: e["date"])]


@dataclass
class Reel:
    number: int
    script: ReelScript
    posts: list[PlatformPost]


@dataclass
class DailyKit:
    day: date
    reels: list[Reel]
    warnings: list[str]
    checks: dict[str, CheckResult] | None = None

    @property
    def promos(self) -> list[Reel]:
        return [r for r in self.reels if r.script.kind == "promo"]

    @property
    def educational(self) -> list[Reel]:
        return [r for r in self.reels if r.script.kind == "educational"]


def _product_priority(p: Product, day: date, history: History):
    left = p.days_left_in_season(day)
    in_season = left is not None
    return (
        0 if in_season else 1,
        left if in_season else 0,
        history.last_promoted(p.id),
        p.id,
    )


def choose_angle(product: Product, day: date, history: History,
                 exclude: set[str] | frozenset[str] = frozenset()) -> str:
    """Pick the next angle for a product; `exclude` holds angles already
    used by other promos today so the two daily promos never share a script."""
    available = [a for a in angles_for(product, day) if a not in exclude] or angles_for(product, day)
    used = history.used_angles(product.id)
    unused = [a for a in available if a not in used]
    if unused:
        return unused[0]
    # Everything used: pick the one used longest ago.
    last_index = {a: max(i for i, u in enumerate(used) if u == a) for a in available}
    return min(available, key=lambda a: last_index[a])


def choose_topics(day: date, history: History, count: int = EDUCATIONAL_PER_DAY) -> list[str]:
    order = {t.id: i for i, t in enumerate(TOPICS)}
    # Offset ties by day so a fresh history doesn't always start at topic 0.
    offset = day.toordinal() % len(TOPICS)
    ranked = sorted(
        (t.id for t in TOPICS),
        key=lambda tid: (history.topics.get(tid, ""), (order[tid] - offset) % len(TOPICS)),
    )
    return ranked[:count]


def plan_day(products: list[Product], day: date, history: History,
             checks: dict[str, CheckResult] | None = None) -> DailyKit:
    """Plan the day. With `checks` (see contentkit.checks), products whose
    link is dead or that have no usable HD preview are left out, and only
    previews that passed are used in the visual notes."""
    warnings: list[str] = []
    if checks is not None:
        for p in products:
            warnings += checks[p.id].messages()
        products = [
            replace(p, preview_files=tuple(checks[p.id].good_previews))
            for p in products if checks[p.id].promotable
        ]
    ranked = sorted(products, key=lambda p: _product_priority(p, day, history))
    chosen = ranked[:PROMOS_PER_DAY]
    if len(chosen) < PROMOS_PER_DAY:
        warnings.append(
            f"Only {len(chosen)} product(s) ready to promote; add or fix products to run "
            f"{PROMOS_PER_DAY} different promos a day."
        )

    reels: list[Reel] = []
    used_today: set[str] = set()
    for product in chosen:
        angle = choose_angle(product, day, history, used_today)
        used_today.add(angle)
        script = build_promo(product, angle, day)
        if checks is None and not product.preview_files:
            warnings.append(f"{product.id}: no preview_files listed; export real PDF pages first.")
        reels.append(Reel(len(reels) + 1, script, build_posts(script, product)))

    for tid in choose_topics(day, history):
        topic = TOPICS_BY_ID[tid]
        script = build_educational(topic)
        reels.append(Reel(len(reels) + 1, script, build_posts(script, None, topic.hashtags)))

    return DailyKit(day=day, reels=reels, warnings=warnings, checks=checks)


def record(kit: DailyKit, history: History) -> None:
    iso = kit.day.isoformat()
    for reel in kit.promos:
        entries = history.promos.setdefault(reel.script.product_id, [])
        entries.append({"date": iso, "angle": reel.script.key})
    for reel in kit.educational:
        history.topics[reel.script.key] = iso
