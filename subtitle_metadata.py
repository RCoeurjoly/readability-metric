"""Hydrate OPUS OpenSubtitles manifests with IMDb title metadata."""

from __future__ import annotations

import argparse
import csv
import gzip
import sys
import json
import re
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


csv.field_size_limit(sys.maxsize)

IMDB_DATASETS = {
    "title.basics.tsv.gz": "https://datasets.imdbws.com/title.basics.tsv.gz",
    "title.episode.tsv.gz": "https://datasets.imdbws.com/title.episode.tsv.gz",
    "title.akas.tsv.gz": "https://datasets.imdbws.com/title.akas.tsv.gz",
}

CHINESE_AKA_REGIONS = {"CN", "HK", "MO", "SG", "TW"}
CHINESE_AKA_LANGUAGES = {"cmn", "yue", "zh", "zh-CN", "zh-Hans", "zh-Hant"}


@dataclass(frozen=True)
class SubtitlePathInfo:
    year_dir: str | None
    media_dir: str | None
    subtitle_file_id: str | None
    title_tconst: str | None
    parent_tconst: str | None
    season: int | None
    episode: int | None


def numeric_to_tconst(value: str | int | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or not text.isdigit():
        return None
    return f"tt{int(text):07d}"


def parse_opus_subtitle_path(path: str) -> SubtitlePathInfo:
    parts = Path(path).parts
    try:
        index = parts.index("zh_CN")
    except ValueError:
        index = -1
    year_dir = parts[index + 1] if index >= 0 and index + 1 < len(parts) else None
    media_dir = parts[index + 2] if index >= 0 and index + 2 < len(parts) else None
    filename = parts[-1] if parts else None
    subtitle_file_id = Path(filename).stem if filename else None

    title_tconst = None
    parent_tconst = None
    season = None
    episode = None
    if media_dir:
        fields = media_dir.split("_")
        if len(fields) >= 4 and all(field.isdigit() for field in fields[:4]):
            title_tconst = numeric_to_tconst(fields[0])
            parent_tconst = numeric_to_tconst(fields[1])
            season = int(fields[2])
            episode = int(fields[3])
        elif media_dir.isdigit():
            title_tconst = numeric_to_tconst(media_dir)

    return SubtitlePathInfo(
        year_dir=year_dir,
        media_dir=media_dir,
        subtitle_file_id=subtitle_file_id,
        title_tconst=title_tconst,
        parent_tconst=parent_tconst,
        season=season,
        episode=episode,
    )


def _clean_imdb_value(value: str | None) -> str | None:
    if value is None or value == r"\N":
        return None
    return value


def download_imdb_datasets(download_dir: Path, force: bool = False) -> dict[str, Path]:
    download_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for filename, url in IMDB_DATASETS.items():
        path = download_dir / filename
        if not path.exists() or force:
            partial = path.with_suffix(path.suffix + ".part")
            if partial.exists():
                partial.unlink()
            urllib.request.urlretrieve(url, partial)
            partial.replace(path)
        paths[filename] = path
    return paths


def collect_manifest_ids(manifest_path: Path) -> tuple[set[str], set[tuple[str, int, int]]]:
    title_ids: set[str] = set()
    episode_keys: set[tuple[str, int, int]] = set()
    with manifest_path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            info = parse_opus_subtitle_path(str(row.get("filepath") or ""))
            if info.title_tconst:
                title_ids.add(info.title_tconst)
            if info.parent_tconst:
                title_ids.add(info.parent_tconst)
            if info.parent_tconst and info.season is not None and info.episode is not None:
                episode_keys.add((info.parent_tconst, info.season, info.episode))
    return title_ids, episode_keys


def load_episode_map(path: Path, episode_keys: set[tuple[str, int, int]]) -> dict[tuple[str, int, int], str]:
    if not episode_keys:
        return {}
    episode_map: dict[tuple[str, int, int], str] = {}
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            parent = row.get("parentTconst")
            season_raw = _clean_imdb_value(row.get("seasonNumber"))
            episode_raw = _clean_imdb_value(row.get("episodeNumber"))
            if not parent or not season_raw or not episode_raw:
                continue
            if not season_raw.isdigit() or not episode_raw.isdigit():
                continue
            key = (parent, int(season_raw), int(episode_raw))
            if key in episode_keys:
                episode_map[key] = row["tconst"]
    return episode_map


def load_chinese_aka_flags(path: Path, wanted_ids: set[str]) -> dict[str, dict]:
    flags: dict[str, dict] = {}
    if not wanted_ids:
        return flags
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            title_id = row.get("titleId")
            if title_id not in wanted_ids:
                continue
            region = _clean_imdb_value(row.get("region"))
            language = _clean_imdb_value(row.get("language"))
            types = _clean_imdb_value(row.get("types")) or ""
            is_original = row.get("isOriginalTitle") == "1"
            if region not in CHINESE_AKA_REGIONS and language not in CHINESE_AKA_LANGUAGES:
                continue
            entry = flags.setdefault(
                title_id,
                {
                    "aka_regions": set(),
                    "aka_languages": set(),
                    "has_original_chinese_region_title": False,
                    "has_chinese_language_title": False,
                },
            )
            if region:
                entry["aka_regions"].add(region)
            if language:
                entry["aka_languages"].add(language)
            if language in CHINESE_AKA_LANGUAGES:
                entry["has_chinese_language_title"] = True
            if is_original and region in CHINESE_AKA_REGIONS:
                entry["has_original_chinese_region_title"] = True
            if "imdbDisplay" in types and region in CHINESE_AKA_REGIONS:
                entry["has_chinese_region_display_title"] = True
    for entry in flags.values():
        entry["aka_regions"] = sorted(entry["aka_regions"])
        entry["aka_languages"] = sorted(entry["aka_languages"])
    return flags


def load_title_basics(path: Path, wanted_ids: set[str]) -> dict[str, dict]:
    titles: dict[str, dict] = {}
    if not wanted_ids:
        return titles
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            tconst = row.get("tconst")
            if tconst in wanted_ids:
                titles[tconst] = {
                    "tconst": tconst,
                    "title_type": _clean_imdb_value(row.get("titleType")),
                    "primary_title": _clean_imdb_value(row.get("primaryTitle")),
                    "original_title": _clean_imdb_value(row.get("originalTitle")),
                    "start_year": _clean_imdb_value(row.get("startYear")),
                    "end_year": _clean_imdb_value(row.get("endYear")),
                }
    return titles


def _title_with_year(title: dict | None) -> str | None:
    if not title:
        return None
    name = title.get("primary_title") or title.get("original_title")
    if not name:
        return None
    year = title.get("start_year")
    return f"{name} ({year})" if year else name


def hydrated_title(info: SubtitlePathInfo, titles: dict[str, dict], episode_map: dict[tuple[str, int, int], str]) -> tuple[str | None, dict]:
    metadata: dict = {
        "opus_year_dir": info.year_dir,
        "opus_media_dir": info.media_dir,
        "subtitle_file_id": info.subtitle_file_id,
    }
    if info.parent_tconst:
        metadata["imdb_parent_tconst"] = info.parent_tconst
    if info.title_tconst:
        metadata["imdb_title_tconst"] = info.title_tconst
    if info.season is not None:
        metadata["season"] = info.season
    if info.episode is not None:
        metadata["episode"] = info.episode

    if info.parent_tconst and info.season is not None and info.episode is not None:
        key = (info.parent_tconst, info.season, info.episode)
        episode_tconst = episode_map.get(key)
        parent_title = titles.get(info.parent_tconst)
        episode_title = titles.get(episode_tconst) if episode_tconst else None
        if episode_tconst:
            metadata["imdb_episode_tconst"] = episode_tconst
        series_name = _title_with_year(parent_title)
        ep_name = episode_title.get("primary_title") if episode_title else None
        if series_name and ep_name:
            return f"{series_name} S{info.season:02d}E{info.episode:02d} - {ep_name}", metadata
        if series_name:
            return f"{series_name} S{info.season:02d}E{info.episode:02d}", metadata
        if episode_title:
            return _title_with_year(episode_title), metadata

    title = titles.get(info.title_tconst) if info.title_tconst else None
    return _title_with_year(title), metadata


def hydrate_manifest_rows(
    manifest_path: Path,
    output_path: Path,
    title_basics_path: Path,
    title_episode_path: Path,
    title_akas_path: Path | None = None,
) -> tuple[int, int]:
    title_ids, episode_keys = collect_manifest_ids(manifest_path)
    episode_map = load_episode_map(title_episode_path, episode_keys)
    title_ids.update(episode_map.values())
    titles = load_title_basics(title_basics_path, title_ids)
    chinese_aka_flags = load_chinese_aka_flags(title_akas_path, title_ids) if title_akas_path else {}

    total = 0
    matched = 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open(encoding="utf-8") as src, output_path.open("w", encoding="utf-8") as dst:
        for line in src:
            if not line.strip():
                continue
            total += 1
            row = json.loads(line)
            info = parse_opus_subtitle_path(str(row.get("filepath") or ""))
            title, metadata = hydrated_title(info, titles, episode_map)
            row.update(metadata)
            aka_title_id = metadata.get("imdb_parent_tconst") or metadata.get("imdb_title_tconst")
            aka_flags = chinese_aka_flags.get(str(aka_title_id), {}) if aka_title_id else {}
            if aka_flags:
                row["imdb_aka_regions"] = aka_flags.get("aka_regions", [])
                row["imdb_aka_languages"] = aka_flags.get("aka_languages", [])
                row["chinese_audio_likely"] = bool(
                    aka_flags.get("has_original_chinese_region_title")
                    or aka_flags.get("has_chinese_language_title")
                )
                row["chinese_audio_likely_reason"] = "imdb_chinese_region_or_language_aka"
            else:
                row["chinese_audio_likely"] = False
                row["chinese_audio_likely_reason"] = "no_chinese_region_or_language_aka"
            if title:
                matched += 1
                row["title"] = title
                row["hydrated_title"] = title
                row["title_source"] = "imdb_datasets"
            else:
                row["title_source"] = "opus_path_id"
            dst.write(json.dumps(row, ensure_ascii=False) + "\n")
    return total, matched



def filter_chinese_audio_likely(recommendations_path: Path, output_path: Path) -> tuple[int, int]:
    total = 0
    kept = 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with recommendations_path.open(encoding="utf-8") as src, output_path.open("w", encoding="utf-8") as dst:
        for line in src:
            if not line.strip():
                continue
            total += 1
            row = json.loads(line)
            if row.get("chinese_audio_likely"):
                kept += 1
                dst.write(json.dumps(row, ensure_ascii=False) + "\n")
    return total, kept

def hydrate_recommendations(manifest_path: Path, recommendations_path: Path, output_path: Path) -> tuple[int, int]:
    by_book_id: dict[str, dict] = {}
    with manifest_path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            by_book_id[str(row.get("book_id"))] = row

    total = 0
    matched = 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with recommendations_path.open(encoding="utf-8") as src, output_path.open("w", encoding="utf-8") as dst:
        for line in src:
            if not line.strip():
                continue
            total += 1
            row = json.loads(line)
            meta = by_book_id.get(str(row.get("book_id")))
            if meta:
                for key in (
                    "title",
                    "hydrated_title",
                    "title_source",
                    "imdb_title_tconst",
                    "imdb_parent_tconst",
                    "imdb_episode_tconst",
                    "season",
                    "episode",
                    "opus_year_dir",
                    "opus_media_dir",
                    "subtitle_file_id",
                    "imdb_aka_regions",
                    "imdb_aka_languages",
                    "chinese_audio_likely",
                    "chinese_audio_likely_reason",
                ):
                    if key in meta:
                        row[key] = meta[key]
                if meta.get("hydrated_title"):
                    matched += 1
            dst.write(json.dumps(row, ensure_ascii=False) + "\n")
    return total, matched


def _parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hydrate OPUS subtitle manifests with IMDb title metadata.")
    parser.add_argument("--manifest", default="results/zh-subtitles/manifest.jsonl")
    parser.add_argument("--output-manifest", default="results/zh-subtitles/manifest.hydrated.jsonl")
    parser.add_argument("--recommendations", default="results/zh-subtitle-recommendations.jsonl")
    parser.add_argument("--output-recommendations", default="results/zh-subtitle-recommendations.hydrated.jsonl")
    parser.add_argument("--output-chinese-audio-likely", default="results/zh-subtitle-recommendations.chinese-audio-likely.jsonl")
    parser.add_argument("--imdb-dir", default="~/Downloads/imdb-datasets")
    parser.add_argument("--force-download", action="store_true")
    parser.add_argument("--skip-recommendations", action="store_true")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = _parse_args(argv)
    imdb_paths = download_imdb_datasets(Path(args.imdb_dir).expanduser(), force=args.force_download)
    total, matched = hydrate_manifest_rows(
        Path(args.manifest),
        Path(args.output_manifest),
        imdb_paths["title.basics.tsv.gz"],
        imdb_paths["title.episode.tsv.gz"],
        imdb_paths.get("title.akas.tsv.gz"),
    )
    print(f"Hydrated {matched}/{total} manifest rows into {args.output_manifest}")
    if not args.skip_recommendations and Path(args.recommendations).exists():
        rec_total, rec_matched = hydrate_recommendations(
            Path(args.output_manifest),
            Path(args.recommendations),
            Path(args.output_recommendations),
        )
        print(f"Hydrated {rec_matched}/{rec_total} recommendation rows into {args.output_recommendations}")
        audio_total, audio_kept = filter_chinese_audio_likely(
            Path(args.output_recommendations),
            Path(args.output_chinese_audio_likely),
        )
        print(f"Wrote {audio_kept}/{audio_total} likely-Chinese-audio recommendation rows to {args.output_chinese_audio_likely}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
