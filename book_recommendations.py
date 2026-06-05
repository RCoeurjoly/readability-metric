"""Recommend Chinese books from per-book frequency profiles and a learner profile."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable


DEFAULT_PROFILE = "results/learner-profile.json"
DEFAULT_MANIFEST = "results/zh-books/manifest.jsonl"
DEFAULT_OUTPUT = "results/book-recommendations.jsonl"
DEFAULT_TOP_UNKNOWN = 20


def load_rank_map(path: Path, expected_unit: str) -> dict[str, int]:
    ranks: dict[str, int] = {}
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            unit = row.get("unit")
            if unit != expected_unit:
                raise ValueError(f"{path}:{line_number}: expected unit {expected_unit!r}, got {unit!r}")
            ranks[str(row["item"])] = int(row["rank"])
    return ranks


def load_profile(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_manifest(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as manifest:
        for line in manifest:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def iter_profile_rows(path: Path) -> Iterable[dict]:
    if not path.exists():
        return
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def profile_coverage(
    profile_path: Path,
    rank_map: dict[str, int],
    known_rank: int,
    top_unknown: int = DEFAULT_TOP_UNKNOWN,
) -> dict:
    total_tokens = 0
    known_tokens = 0
    unknown_tokens = 0
    unknown_items = []
    distinct_total = 0
    distinct_known = 0

    for row in iter_profile_rows(profile_path):
        item = str(row["item"])
        count = int(row["count"])
        rank = rank_map.get(item)
        total_tokens += count
        distinct_total += 1
        if rank is not None and rank <= known_rank:
            known_tokens += count
            distinct_known += 1
        else:
            unknown_tokens += count
            unknown_items.append(
                {
                    "item": item,
                    "count": count,
                    "global_rank": rank,
                }
            )

    unknown_items.sort(key=lambda row: (-row["count"], row["global_rank"] is None, row["global_rank"] or 0, row["item"]))
    return {
        "total_tokens": total_tokens,
        "known_tokens": known_tokens,
        "unknown_tokens": unknown_tokens,
        "known_coverage": known_tokens / total_tokens if total_tokens else 0.0,
        "distinct_total": distinct_total,
        "distinct_known": distinct_known,
        "distinct_unknown": distinct_total - distinct_known,
        "top_unknown": unknown_items[:top_unknown],
    }


def recommendation_score(char_stats: dict, word_stats: dict) -> float:
    return 0.8 * word_stats["known_coverage"] + 0.2 * char_stats["known_coverage"]


def score_book(
    manifest_row: dict,
    char_rank_map: dict[str, int],
    word_rank_map: dict[str, int],
    char_known_rank: int,
    word_known_rank: int,
    top_unknown: int = DEFAULT_TOP_UNKNOWN,
) -> dict | None:
    if not manifest_row.get("included"):
        return None
    book_dir = Path(manifest_row["book_dir"])
    char_stats = profile_coverage(book_dir / "chars.jsonl", char_rank_map, char_known_rank, top_unknown=top_unknown)
    word_stats = profile_coverage(book_dir / "words.jsonl", word_rank_map, word_known_rank, top_unknown=top_unknown)
    return {
        "book_id": manifest_row.get("book_id"),
        "title": manifest_row.get("title"),
        "creator": manifest_row.get("creator"),
        "filename": manifest_row.get("filename"),
        "filepath": manifest_row.get("filepath"),
        "book_dir": str(book_dir),
        "score": recommendation_score(char_stats, word_stats),
        "known_char_coverage": char_stats["known_coverage"],
        "known_word_coverage": word_stats["known_coverage"],
        "total_chars": char_stats["total_tokens"],
        "total_words": word_stats["total_tokens"],
        "unknown_char_tokens": char_stats["unknown_tokens"],
        "unknown_word_tokens": word_stats["unknown_tokens"],
        "distinct_chars": char_stats["distinct_total"],
        "distinct_words": word_stats["distinct_total"],
        "distinct_unknown_chars": char_stats["distinct_unknown"],
        "distinct_unknown_words": word_stats["distinct_unknown"],
        "top_unknown_chars": char_stats["top_unknown"],
        "top_unknown_words": word_stats["top_unknown"],
    }


def build_recommendations(
    manifest_path: Path,
    learner_profile_path: Path,
    output_path: Path,
    top_unknown: int = DEFAULT_TOP_UNKNOWN,
    limit: int = 0,
) -> list[dict]:
    learner = load_profile(learner_profile_path)
    char_path = Path(learner["frequency_lists"]["characters"])
    word_path = Path(learner["frequency_lists"]["words"])
    char_known_rank = int(learner["known_thresholds"]["char_rank"])
    word_known_rank = int(learner["known_thresholds"]["word_rank"])

    char_rank_map = load_rank_map(char_path, "char")
    word_rank_map = load_rank_map(word_path, "word")
    recommendations = []
    for row in load_manifest(manifest_path):
        scored = score_book(
            row,
            char_rank_map,
            word_rank_map,
            char_known_rank,
            word_known_rank,
            top_unknown=top_unknown,
        )
        if scored is not None:
            recommendations.append(scored)

    recommendations.sort(
        key=lambda row: (
            -row["known_word_coverage"],
            -row["known_char_coverage"],
            row["unknown_word_tokens"],
            row["distinct_unknown_words"],
            row["title"] or "",
        )
    )
    if limit:
        recommendations = recommendations[:limit]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as output:
        for row in recommendations:
            output.write(json.dumps(row, ensure_ascii=False) + "\n")
    return recommendations


def _parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recommend Chinese books from learner and per-book vocabulary profiles.")
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--learner-profile", default=DEFAULT_PROFILE)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--top-unknown", type=int, default=DEFAULT_TOP_UNKNOWN)
    parser.add_argument("--limit", type=int, default=0, help="Limit output rows after ranking")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = _parse_args(argv)
    recommendations = build_recommendations(
        Path(args.manifest),
        Path(args.learner_profile),
        Path(args.output),
        top_unknown=max(0, args.top_unknown),
        limit=max(0, args.limit),
    )
    print(f"Wrote {len(recommendations)} recommendations to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
