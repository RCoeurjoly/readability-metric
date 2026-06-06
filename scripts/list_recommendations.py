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
    rows.sort(key=lambda row: row["known_word_coverage"], reverse=args.best)

    for row in rows[: max(0, args.limit)]:
        pct = row["known_word_coverage"] * 100
        words = row["total_words"]
        title = row["title"] or ""
        creator = row.get("creator") or ""
        print(f"{pct:6.2f}%  {words:>8,} words  {title} - {creator}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
