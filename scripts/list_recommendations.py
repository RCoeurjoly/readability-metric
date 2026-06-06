#!/usr/bin/env python3
"""Print readable recommendation rows from a recommendation JSONL file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", help="Recommendation JSONL file")
    parser.add_argument("--best", action="store_true", help="Show most comprehensible books")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--exclude-caltrash", action="store_true")
    parser.add_argument("--unit", choices=("word", "char"), default="word")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = [
        json.loads(line)
        for line in Path(args.path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if args.exclude_caltrash:
        rows = [row for row in rows if "/.caltrash/" not in str(row.get("filepath") or "")]
    coverage_key = f"known_{args.unit}_coverage"
    total_key = f"total_{args.unit}s"
    label = f"{args.unit}s"
    rows.sort(key=lambda row: row.get(coverage_key) or 0, reverse=args.best)

    for row in rows[: max(0, args.limit)]:
        pct = (row.get(coverage_key) or 0) * 100
        total = row.get(total_key) or 0
        title = row["title"] or ""
        creator = row.get("creator") or ""
        print(f"{pct:6.2f}%  {total:>8,} {label}  {title} - {creator}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
