"""Recommend books from per-book frequency profiles and a learner profile."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable


DEFAULT_PROFILE = "results/learner-profile.json"
DEFAULT_MANIFEST = "results/zh-books/manifest.jsonl"
DEFAULT_OUTPUT = "results/book-recommendations.jsonl"
DEFAULT_TOP_UNKNOWN = 20


def _normalizer(mode: str):
    if mode in {"", "none"}:
        return None
    try:
        import opencc  # type: ignore
    except Exception as error:  # pragma: no cover - depends on optional environment package.
        raise RuntimeError("Character rank normalization requires the opencc Python package") from error

    converter = opencc.OpenCC(mode)
    return converter.convert


def _put_min_rank(ranks: dict[str, int], item: str, rank: int) -> None:
    existing = ranks.get(item)
    if existing is None or rank < existing:
        ranks[item] = rank


def load_rank_map(path: Path, expected_unit: str, normalization: str = "none") -> dict[str, int]:
    ranks: dict[str, int] = {}
    normalize = _normalizer(normalization)
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            unit = row.get("unit")
            if unit != expected_unit:
                raise ValueError(f"{path}:{line_number}: expected unit {expected_unit!r}, got {unit!r}")
            item = str(row["item"])
            rank = int(row["rank"])
            _put_min_rank(ranks, item, rank)
            if normalize is not None:
                _put_min_rank(ranks, normalize(item), rank)
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


def recommendation_score(char_stats: dict | None, word_stats: dict) -> float:
    if char_stats is None:
        return word_stats["known_coverage"]
    return 0.8 * word_stats["known_coverage"] + 0.2 * char_stats["known_coverage"]


def score_book(
    manifest_row: dict,
    char_rank_map: dict[str, int] | None,
    word_rank_map: dict[str, int],
    char_known_rank: int | None,
    word_known_rank: int,
    top_unknown: int = DEFAULT_TOP_UNKNOWN,
    tags: list[dict] | None = None,
) -> dict | None:
    if not manifest_row.get("included"):
        return None
    book_dir = Path(manifest_row["book_dir"])
    char_stats = None
    if char_rank_map is not None and char_known_rank is not None:
        char_stats = profile_coverage(book_dir / "chars.jsonl", char_rank_map, char_known_rank, top_unknown=top_unknown)
    word_stats = profile_coverage(book_dir / "words.jsonl", word_rank_map, word_known_rank, top_unknown=top_unknown)
    row = {
        "book_id": manifest_row.get("book_id"),
        "title": manifest_row.get("title"),
        "creator": manifest_row.get("creator"),
        "filename": manifest_row.get("filename"),
        "filepath": manifest_row.get("filepath"),
        "media_type": manifest_row.get("media_type", "book"),
        "source": manifest_row.get("source"),
        "source_version": manifest_row.get("source_version"),
        "book_dir": str(book_dir),
        "score": recommendation_score(char_stats, word_stats),
        "known_char_coverage": char_stats["known_coverage"] if char_stats else None,
        "known_word_coverage": word_stats["known_coverage"],
        "total_chars": char_stats["total_tokens"] if char_stats else 0,
        "total_words": word_stats["total_tokens"],
        "unknown_char_tokens": char_stats["unknown_tokens"] if char_stats else 0,
        "unknown_word_tokens": word_stats["unknown_tokens"],
        "distinct_chars": char_stats["distinct_total"] if char_stats else 0,
        "distinct_words": word_stats["distinct_total"],
        "distinct_unknown_chars": char_stats["distinct_unknown"] if char_stats else 0,
        "distinct_unknown_words": word_stats["distinct_unknown"],
        "top_unknown_chars": char_stats["top_unknown"] if char_stats else [],
        "top_unknown_words": word_stats["top_unknown"],
    }
    if tags:
        row["tags"] = tags
    return row



def load_book_tags(path: Path | None) -> dict[str, list[dict]]:
    if path is None:
        return {}
    tags_by_book: dict[str, list[dict]] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            tags_by_book.setdefault(str(row["book_id"]), []).extend(row.get("tags", []))
    for tags in tags_by_book.values():
        tags.sort(key=lambda tag: (str(tag.get("list_id") or ""), tag.get("rank") or 0))
    return tags_by_book

def build_recommendations(
    manifest_path: Path,
    learner_profile_path: Path,
    output_path: Path,
    top_unknown: int = DEFAULT_TOP_UNKNOWN,
    limit: int = 0,
    tags_path: Path | None = None,
    ranked_only: bool = False,
    character_normalization: str = "none",
) -> list[dict]:
    learner = load_profile(learner_profile_path)
    word_path = Path(learner["frequency_lists"]["words"])
    word_known_rank = int(learner["known_thresholds"]["word_rank"])
    char_path_value = learner.get("frequency_lists", {}).get("characters")
    char_known_rank = learner.get("known_thresholds", {}).get("char_rank")

    char_rank_map = None
    if char_path_value and char_known_rank is not None:
        char_rank_map = load_rank_map(Path(char_path_value), "char", normalization=character_normalization)
        char_known_rank = int(char_known_rank)
    word_rank_map = load_rank_map(word_path, "word")
    tags_by_book = load_book_tags(tags_path)
    recommendations = []
    for row in load_manifest(manifest_path):
        book_id = str(row.get("book_id"))
        tags = tags_by_book.get(book_id, [])
        if ranked_only and not tags:
            continue
        scored = score_book(
            row,
            char_rank_map,
            word_rank_map,
            char_known_rank,
            word_known_rank,
            top_unknown=top_unknown,
            tags=tags,
        )
        if scored is not None:
            recommendations.append(scored)

    recommendations.sort(
        key=lambda row: (
            -row["known_word_coverage"],
            -(row["known_char_coverage"] or 0),
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
    parser = argparse.ArgumentParser(description="Recommend books from learner and per-book vocabulary profiles.")
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--learner-profile", default=DEFAULT_PROFILE)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--top-unknown", type=int, default=DEFAULT_TOP_UNKNOWN)
    parser.add_argument("--limit", type=int, default=0, help="Limit output rows after ranking")
    parser.add_argument("--tags", help="Book tag JSONL file; matching tags are copied into recommendation rows")
    parser.add_argument("--ranked-only", action="store_true", help="Only recommend books present in --tags")
    parser.add_argument(
        "--character-normalization",
        default="none",
        help="OpenCC mode used to add character-rank aliases, e.g. t2s for Simplified subtitle profiles",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = _parse_args(argv)
    recommendations = build_recommendations(
        Path(args.manifest),
        Path(args.learner_profile),
        Path(args.output),
        top_unknown=max(0, args.top_unknown),
        limit=max(0, args.limit),
        tags_path=Path(args.tags) if args.tags else None,
        ranked_only=args.ranked_only,
        character_normalization=args.character_normalization,
    )
    print(f"Wrote {len(recommendations)} recommendations to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
