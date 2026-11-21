"""Command line entry point.

    python -m contentkit --catalog products.json --out kits/
    python -m contentkit --catalog products.json --date 2026-11-24 --record
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from .planner import History, plan_day, record
from .products import CatalogError, load_catalog
from .render import to_json, to_markdown
from .scripts import ScriptTooLongError


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="contentkit",
                                 description="Build the daily 5-reel content kit.")
    ap.add_argument("--catalog", required=True, help="products JSON file")
    ap.add_argument("--date", help="YYYY-MM-DD (default: today)")
    ap.add_argument("--out", default="kits", help="output folder (default: kits)")
    ap.add_argument("--history", default="kits/history.json",
                    help="rotation history file (default: kits/history.json)")
    ap.add_argument("--record", action="store_true",
                    help="save today's picks to history so tomorrow rotates")
    args = ap.parse_args(argv)

    try:
        day = date.fromisoformat(args.date) if args.date else date.today()
        products = load_catalog(args.catalog)
        history = History.load(args.history)
        kit = plan_day(products, day, history)
    except (CatalogError, ScriptTooLongError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    md = out / f"{day.isoformat()}.md"
    js = out / f"{day.isoformat()}.json"
    md.write_text(to_markdown(kit), encoding="utf-8")
    js.write_text(to_json(kit), encoding="utf-8")

    if args.record:
        record(kit, history)
        Path(args.history).parent.mkdir(parents=True, exist_ok=True)
        history.save(args.history)

    print(f"wrote {md} and {js}")
    for w in kit.warnings:
        print(f"warning: {w}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
