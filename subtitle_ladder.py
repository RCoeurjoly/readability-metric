"""Build watch ladders from subtitle episode profiles and a learner profile."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Iterable

import book_recommendations as br


DEFAULT_MANIFEST = "results/zh-mandarin-subtitles-archive/manifest.jsonl"
LEGACY_MANDARIN_MANIFEST = "results/zh-mandarin-subtitles/manifest.jsonl"
DEFAULT_PROFILE = "results/learner-profile.json"
DEFAULT_EPISODES_OUTPUT = "results/subtitle-ladder-episodes.jsonl"
DEFAULT_SERIES_OUTPUT = "results/subtitle-ladder-series.jsonl"
DEFAULT_TARGET_COVERAGE = 0.98
DEFAULT_MIN_COVERAGE = 0.95
DEFAULT_TOP_UNKNOWN = 20


def _series_key(row: dict) -> tuple[str, str, str, str]:
    return (
        str(row.get("collection") or ""),
        str(row.get("series") or ""),
        str(row.get("season") or ""),
        str(row.get("subtitle_variant") or ""),
    )


def _episode_sort_key(row: dict) -> tuple:
    episode_number = row.get("episode_number")
    return (
        row.get("collection") or "",
        row.get("series") or "",
        row.get("season") or "",
        row.get("subtitle_variant") or "",
        episode_number is None,
        episode_number or 0,
        row.get("filepath") or row.get("title") or "",
    )


def _watch_mode(word_coverage: float, min_coverage: float, target_coverage: float) -> str:
    if word_coverage >= target_coverage:
        return "extensive"
    if word_coverage >= min_coverage:
        return "ci"
    if word_coverage >= 0.90:
        return "assisted"
    return "skip"


def _copy_episode_metadata(scored: dict, manifest_row: dict) -> dict:
    row = dict(scored)
    for key in (
        "collection",
        "series",
        "season",
        "episode_title",
        "episode_number",
        "subtitle_variant",
        "cjk_character_count",
    ):
        if key in manifest_row:
            row[key] = manifest_row.get(key)
    return row


def score_subtitle_episodes(
    manifest_path: Path,
    learner_profile_path: Path,
    top_unknown: int = DEFAULT_TOP_UNKNOWN,
    character_normalization: str = "none",
) -> list[dict]:
    learner = br.load_profile(learner_profile_path)
    word_path = Path(learner["frequency_lists"]["words"])
    word_known_rank = int(learner["known_thresholds"]["word_rank"])
    char_path_value = learner.get("frequency_lists", {}).get("characters")
    char_known_rank = learner.get("known_thresholds", {}).get("char_rank")
    if char_known_rank is None:
        char_known_rank = learner.get("known_thresholds", {}).get("character_rank")

    char_rank_map = None
    if char_path_value and char_known_rank is not None:
        char_rank_map = br.load_rank_map(Path(char_path_value), "char", normalization=character_normalization)
        char_known_rank = int(char_known_rank)
    word_rank_map = br.load_rank_map(word_path, "word")

    rows = []
    for manifest_row in br.load_manifest(manifest_path):
        if manifest_row.get("media_type") != "subtitle":
            continue
        scored = br.score_book(
            manifest_row,
            char_rank_map,
            word_rank_map,
            char_known_rank,
            word_known_rank,
            top_unknown=top_unknown,
        )
        if scored is not None:
            rows.append(_copy_episode_metadata(scored, manifest_row))
    return rows


def annotate_episode_modes(episodes: list[dict], min_coverage: float, target_coverage: float) -> list[dict]:
    annotated = []
    for row in episodes:
        word_coverage = float(row["known_word_coverage"])
        annotated.append(
            {
                **row,
                "watch_mode": _watch_mode(word_coverage, min_coverage, target_coverage),
                "meets_min_coverage": word_coverage >= min_coverage,
                "meets_target_coverage": word_coverage >= target_coverage,
            }
        )
    annotated.sort(
        key=lambda row: (
            row["watch_mode"] == "skip",
            row["watch_mode"] == "assisted",
            row["watch_mode"] == "ci",
            -row["known_word_coverage"],
            -(row["known_char_coverage"] or 0),
            row["unknown_word_tokens"],
            row.get("series") or "",
            row.get("episode_number") or 0,
        )
    )
    return annotated


def _contiguous_count(sorted_rows: list[dict], threshold: float) -> int:
    count = 0
    for row in sorted_rows:
        if float(row["known_word_coverage"]) < threshold:
            break
        count += 1
    return count


def build_series_ladder(episodes: list[dict], min_coverage: float, target_coverage: float) -> list[dict]:
    grouped: dict[tuple[str, str, str, str], list[dict]] = defaultdict(list)
    for row in episodes:
        grouped[_series_key(row)].append(row)

    series_rows = []
    for key, rows in grouped.items():
        sorted_rows = sorted(rows, key=_episode_sort_key)
        coverages = [float(row["known_word_coverage"]) for row in sorted_rows]
        char_coverages = [float(row["known_char_coverage"] or 0) for row in sorted_rows]
        min_rows = [row for row in sorted_rows if float(row["known_word_coverage"]) >= min_coverage]
        target_rows = [row for row in sorted_rows if float(row["known_word_coverage"]) >= target_coverage]
        first = sorted_rows[0]
        collection, series, season, variant = key
        series_rows.append(
            {
                "collection": collection or None,
                "series": series or None,
                "season": season or None,
                "subtitle_variant": variant or None,
                "episode_count": len(sorted_rows),
                "watchable_episode_count": len(min_rows),
                "extensive_episode_count": len(target_rows),
                "contiguous_watchable_from_start": _contiguous_count(sorted_rows, min_coverage),
                "contiguous_extensive_from_start": _contiguous_count(sorted_rows, target_coverage),
                "first_episode_title": first.get("title"),
                "first_episode_coverage": first.get("known_word_coverage"),
                "min_word_coverage": min(coverages),
                "median_word_coverage": median(coverages),
                "mean_word_coverage": mean(coverages),
                "median_char_coverage": median(char_coverages) if char_coverages else None,
                "first_unwatchable_episode": next((row.get("title") for row in sorted_rows if float(row["known_word_coverage"]) < min_coverage), None),
                "recommended_start": first.get("title") if float(first["known_word_coverage"]) >= min_coverage else None,
            }
        )

    series_rows.sort(
        key=lambda row: (
            -row["contiguous_extensive_from_start"],
            -row["contiguous_watchable_from_start"],
            -row["median_word_coverage"],
            -row["watchable_episode_count"],
            row.get("collection") or "",
            row.get("series") or "",
            row.get("season") or "",
            row.get("subtitle_variant") or "",
        )
    )
    return series_rows


def resolve_manifest_path(path: Path) -> Path:
    if path.exists():
        return path
    if str(path) == DEFAULT_MANIFEST:
        legacy = Path(LEGACY_MANDARIN_MANIFEST)
        if legacy.exists():
            return legacy
    return path


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def build_subtitle_ladder(
    manifest_path: Path,
    learner_profile_path: Path,
    output_episodes_path: Path,
    output_series_path: Path,
    min_coverage: float = DEFAULT_MIN_COVERAGE,
    target_coverage: float = DEFAULT_TARGET_COVERAGE,
    top_unknown: int = DEFAULT_TOP_UNKNOWN,
    limit_episodes: int = 0,
    limit_series: int = 0,
    character_normalization: str = "none",
) -> tuple[list[dict], list[dict]]:
    episodes = score_subtitle_episodes(
        manifest_path,
        learner_profile_path,
        top_unknown=top_unknown,
        character_normalization=character_normalization,
    )
    annotated_episodes = annotate_episode_modes(episodes, min_coverage, target_coverage)
    series_rows = build_series_ladder(annotated_episodes, min_coverage, target_coverage)

    episode_output = annotated_episodes[:limit_episodes] if limit_episodes else annotated_episodes
    series_output = series_rows[:limit_series] if limit_series else series_rows
    write_jsonl(output_episodes_path, episode_output)
    write_jsonl(output_series_path, series_output)
    return episode_output, series_output


def _parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a Chinese subtitle watch ladder from learner coverage.")
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--learner-profile", default=DEFAULT_PROFILE)
    parser.add_argument("--output-episodes", default=DEFAULT_EPISODES_OUTPUT)
    parser.add_argument("--output-series", default=DEFAULT_SERIES_OUTPUT)
    parser.add_argument("--min-coverage", type=float, default=DEFAULT_MIN_COVERAGE, help="Minimum word coverage for CI/watchable mode")
    parser.add_argument("--target-coverage", type=float, default=DEFAULT_TARGET_COVERAGE, help="Word coverage for extensive mode")
    parser.add_argument("--top-unknown", type=int, default=DEFAULT_TOP_UNKNOWN)
    parser.add_argument("--limit-episodes", type=int, default=0)
    parser.add_argument("--limit-series", type=int, default=0)
    parser.add_argument(
        "--character-normalization",
        default="none",
        help="OpenCC mode used to add character-rank aliases, e.g. t2s for Simplified subtitle profiles",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = _parse_args(argv)
    episodes, series = build_subtitle_ladder(
        resolve_manifest_path(Path(args.manifest)),
        Path(args.learner_profile),
        Path(args.output_episodes),
        Path(args.output_series),
        min_coverage=args.min_coverage,
        target_coverage=args.target_coverage,
        top_unknown=max(0, args.top_unknown),
        limit_episodes=max(0, args.limit_episodes),
        limit_series=max(0, args.limit_series),
        character_normalization=args.character_normalization,
    )
    print(f"Wrote {len(episodes)} episode rows to {args.output_episodes}")
    print(f"Wrote {len(series)} series rows to {args.output_series}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
