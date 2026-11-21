"""Product catalog loading and validation.

The catalog is the single source of truth for Gumroad links. Every promo reel
pulls its URL from here, so a product without a valid Gumroad URL is rejected
instead of being promoted with a guessed or placeholder link.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

GUMROAD_URL_RE = re.compile(
    r"^https://(?:[a-z0-9-]+\.)?gumroad\.com/l/[A-Za-z0-9_-]+/?$"
)
PLACEHOLDER_MARKERS = ("example", "xxx", "todo", "placeholder", "your-")


class CatalogError(ValueError):
    """Raised when the product catalog is missing data or has bad links."""


@dataclass(frozen=True)
class Product:
    id: str
    name: str
    gumroad_url: str
    ages: str
    pages: int
    highlights: tuple[str, ...]
    keywords: tuple[str, ...] = ()
    price: str | None = None
    preview_files: tuple[str, ...] = ()
    season_start: date | None = None
    season_end: date | None = None
    tags: tuple[str, ...] = field(default=())

    def in_season(self, day: date) -> bool:
        """True when `day` falls inside the product's selling window.

        Windows are compared by month/day so they repeat every year and may
        wrap the new year (e.g. Dec 1 to Jan 15).
        """
        if not self.season_start or not self.season_end:
            return False
        start = (self.season_start.month, self.season_start.day)
        end = (self.season_end.month, self.season_end.day)
        today = (day.month, day.day)
        if start <= end:
            return start <= today <= end
        return today >= start or today <= end

    def days_left_in_season(self, day: date) -> int | None:
        if not self.in_season(day):
            return None
        end = date(day.year, self.season_end.month, self.season_end.day)
        if end < day:
            end = date(day.year + 1, end.month, end.day)
        return (end - day).days


def validate_gumroad_url(url: str) -> None:
    if not isinstance(url, str) or not GUMROAD_URL_RE.match(url.strip()):
        raise CatalogError(
            f"'{url}' is not a Gumroad product URL "
            "(expected https://<store>.gumroad.com/l/<slug>)"
        )
    lowered = url.lower()
    if any(marker in lowered for marker in PLACEHOLDER_MARKERS):
        raise CatalogError(f"'{url}' looks like a placeholder, not a real link")


def _parse_date(value: str | None, field_name: str, pid: str) -> date | None:
    if value is None:
        return None
    try:
        # Accept "MM-DD" (recurring yearly) or full ISO dates.
        if re.fullmatch(r"\d{2}-\d{2}", value):
            return date.fromisoformat(f"2000-{value}")
        return date.fromisoformat(value)
    except ValueError as exc:
        raise CatalogError(f"{pid}: bad {field_name} '{value}'") from exc


def parse_product(raw: dict) -> Product:
    pid = raw.get("id") or "<missing id>"
    for key in ("id", "name", "gumroad_url", "ages", "pages", "highlights"):
        if key not in raw or raw[key] in (None, "", []):
            raise CatalogError(f"{pid}: missing required field '{key}'")
    validate_gumroad_url(raw["gumroad_url"])
    if not isinstance(raw["pages"], int) or raw["pages"] <= 0:
        raise CatalogError(f"{pid}: 'pages' must be a positive integer")
    highlights = tuple(raw["highlights"])
    if len(highlights) < 2:
        raise CatalogError(f"{pid}: list at least 2 highlights")
    season = raw.get("season") or {}
    start = _parse_date(season.get("start"), "season.start", pid)
    end = _parse_date(season.get("end"), "season.end", pid)
    if bool(start) != bool(end):
        raise CatalogError(f"{pid}: season needs both 'start' and 'end'")
    return Product(
        id=raw["id"],
        name=raw["name"],
        gumroad_url=raw["gumroad_url"].strip(),
        ages=raw["ages"],
        pages=raw["pages"],
        highlights=highlights,
        keywords=tuple(raw.get("keywords", ())),
        price=raw.get("price"),
        preview_files=tuple(raw.get("preview_files", ())),
        season_start=start,
        season_end=end,
        tags=tuple(raw.get("tags", ())),
    )


def load_catalog(path: str | Path) -> list[Product]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    items = data.get("products") if isinstance(data, dict) else data
    if not items:
        raise CatalogError("catalog has no products")
    products = [parse_product(item) for item in items]
    ids = [p.id for p in products]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise CatalogError(f"duplicate product ids: {sorted(dupes)}")
    return products
