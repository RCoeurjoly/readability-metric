#!/usr/bin/env python3
"""Convert word frequency JSONL files to and from compact CSV gzip snapshots."""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
from pathlib import Path


FIELDNAMES = ["rank", "item", "count", "cumulative_count", "coverage"]


def export_snapshot(source: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with source.open(encoding="utf-8") as inp, output.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
            with io.TextIOWrapper(gz, encoding="utf-8", newline="") as out:
                writer = csv.DictWriter(out, fieldnames=FIELDNAMES)
                writer.writeheader()
                for line in inp:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    writer.writerow({field: row[field] for field in FIELDNAMES})


def import_snapshot(source: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(source, "rt", encoding="utf-8", newline="") as inp, output.open("w", encoding="utf-8") as out:
        reader = csv.DictReader(inp)
        for row in reader:
            out.write(
                json.dumps(
                    {
                        "unit": "word",
                        "item": row["item"],
                        "count": int(row["count"]),
                        "rank": int(row["rank"]),
                        "cumulative_count": int(row["cumulative_count"]),
                        "coverage": float(row["coverage"]),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser("export")
    export_parser.add_argument("source")
    export_parser.add_argument("output")

    import_parser = subparsers.add_parser("import")
    import_parser.add_argument("source")
    import_parser.add_argument("output")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "export":
        export_snapshot(Path(args.source), Path(args.output))
    else:
        import_snapshot(Path(args.source), Path(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
