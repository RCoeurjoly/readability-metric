"""Build Chinese vocabulary profiles from subtitle corpora."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import html
import json
import re
import urllib.request
import zipfile
from collections import Counter
from io import BytesIO
from pathlib import Path
from typing import Iterable, Sequence

from lxml import etree

import readability_metric
from vocabulary_pipeline import (
    _character_tokens,
    _write_jsonl,
    build_frequency_profile_from_text,
    write_merged_profiles,
)


DEFAULT_OPUS_API = "https://opus.nlpl.eu/opusapi"
DEFAULT_OPUS_CORPUS = "OpenSubtitles"
DEFAULT_OPUS_LANGUAGE = "zh_CN"
DEFAULT_SOURCE = "OPUS OpenSubtitles"

ASS_OVERRIDE_RE = re.compile(r"\{\\[^}]*\}")
HTML_TAG_RE = re.compile(r"<[^>]+>")
SRT_TIMING_RE = re.compile(r"^\d{1,2}:\d{2}:\d{2}[,.]\d{1,3}\s+-->\s+\d{1,2}:\d{2}:\d{2}[,.]\d{1,3}")
LOCAL_SUBTITLE_EXTENSIONS = {".srt", ".ass"}


def _subtitle_id(name: str) -> str:
    stem = Path(name).stem or "subtitle"
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-") or "subtitle"
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:10]
    return f"{safe_stem}-{digest}"


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def clean_subtitle_line(value: str) -> str:
    cleaned = html.unescape(value or "")
    cleaned = ASS_OVERRIDE_RE.sub(" ", cleaned)
    cleaned = HTML_TAG_RE.sub(" ", cleaned)
    cleaned = cleaned.replace("\\N", " ").replace("\\n", " ")
    cleaned = cleaned.replace("\ufeff", " ")
    cleaned = re.sub(r"\[[^\]]*\]", " ", cleaned)
    cleaned = re.sub(r"\([^)]*(?:字幕|subtitles?|www\.|http)[^)]*\)", " ", cleaned, flags=re.I)
    cleaned = " ".join(cleaned.split())
    if not cleaned:
        return ""
    if cleaned.isdigit() or SRT_TIMING_RE.match(cleaned):
        return ""
    if re.fullmatch(r"[-_=~*#.:：。!?！？,，、\s]+", cleaned):
        return ""
    return cleaned


def extract_opus_xml_text(data: bytes) -> str:
    lines: list[str] = []
    for _event, element in etree.iterparse(BytesIO(data), events=("end",), recover=True):
        if _local_name(element.tag) == "s":
            line = clean_subtitle_line("".join(element.itertext()))
            if line:
                lines.append(line)
            element.clear()
    if lines:
        return "\n".join(lines)
    fallback = clean_subtitle_line(etree.fromstring(data, parser=etree.XMLParser(recover=True)).xpath("string()"))
    return fallback


def decode_subtitle_bytes(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "gb18030", "big5"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def extract_srt_text(text: str) -> str:
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.isdigit() or SRT_TIMING_RE.match(line):
            continue
        cleaned = clean_subtitle_line(line)
        if cleaned:
            lines.append(cleaned)
    return "\n".join(lines)


def extract_ass_text(text: str) -> str:
    lines: list[str] = []
    in_events = False
    text_index = 9
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lower = line.lower()
        if lower == "[events]":
            in_events = True
            continue
        if line.startswith("[") and lower != "[events]":
            in_events = False
            continue
        if not in_events:
            continue
        if lower.startswith("format:"):
            fields = [field.strip().casefold() for field in line.split(":", 1)[1].split(",")]
            if "text" in fields:
                text_index = fields.index("text")
            continue
        if lower.startswith("dialogue:"):
            payload = line.split(":", 1)[1].lstrip()
            parts = payload.split(",", text_index)
            if len(parts) <= text_index:
                continue
            cleaned = clean_subtitle_line(parts[text_index])
            if cleaned:
                lines.append(cleaned)
    return "\n".join(lines)


def extract_local_subtitle_text(path: Path) -> str:
    text = decode_subtitle_bytes(path.read_bytes())
    suffix = path.suffix.casefold()
    if suffix == ".srt":
        return extract_srt_text(text)
    if suffix == ".ass":
        return extract_ass_text(text)
    return clean_subtitle_line(text)


def iter_local_subtitle_paths(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.casefold() in LOCAL_SUBTITLE_EXTENSIONS:
            yield path


def local_subtitle_metadata(path: Path, root: Path) -> dict:
    relative_path = path.relative_to(root)
    parts = relative_path.parts
    collection = parts[0] if len(parts) > 1 else None
    series = parts[1] if len(parts) > 2 else (path.parent.name if path.parent != root else None)
    episode = path.stem
    title = f"{series} - {episode}" if series else episode
    return {
        "filepath": str(relative_path),
        "filename": path.name,
        "title": title,
        "creator": None,
        "collection": collection,
        "series": series,
        "episode_title": episode,
    }


def normalize_chinese_text(text: str, mode: str = "t2s") -> str:
    if mode in {"none", ""}:
        return text
    try:
        import opencc  # type: ignore
    except Exception as error:  # pragma: no cover - depends on optional environment package.
        raise RuntimeError("Chinese script normalization requires the opencc Python package") from error

    converter = opencc.OpenCC(mode)
    return converter.convert(text)


def query_opus_download_url(
    api_url: str = DEFAULT_OPUS_API,
    corpus: str = DEFAULT_OPUS_CORPUS,
    language: str = DEFAULT_OPUS_LANGUAGE,
) -> tuple[str, str]:
    query = (
        f"{api_url}?corpus={corpus}"
        f"&source={language}"
        "&preprocessing=xml"
        "&version=latest"
    )
    with urllib.request.urlopen(query) as response:
        payload = json.loads(response.read().decode("utf-8"))

    candidates = []
    for row in payload.get("corpora", []):
        url = str(row.get("url") or "")
        if row.get("source") == language and not row.get("target") and url.endswith(".zip"):
            candidates.append(row)
    if not candidates:
        raise RuntimeError(f"No monolingual OPUS XML zip found for {corpus} {language}")
    selected = sorted(candidates, key=lambda row: str(row.get("version") or ""), reverse=True)[0]
    return str(selected["url"]), str(selected.get("version") or "unknown")


def download_opus_archive(
    download_dir: Path,
    force: bool = False,
    api_url: str = DEFAULT_OPUS_API,
    corpus: str = DEFAULT_OPUS_CORPUS,
    language: str = DEFAULT_OPUS_LANGUAGE,
    verbose: bool = False,
) -> tuple[Path, str]:
    url, version = query_opus_download_url(api_url=api_url, corpus=corpus, language=language)
    archive_path = download_dir / Path(url).name
    if archive_path.exists() and not force:
        if zipfile.is_zipfile(archive_path):
            if verbose:
                print(f"Using existing archive: {archive_path}")
            return archive_path, version
        if verbose:
            print(f"Ignoring incomplete or invalid archive: {archive_path}")

    download_dir.mkdir(parents=True, exist_ok=True)
    partial_path = archive_path.with_suffix(archive_path.suffix + ".part")
    if partial_path.exists():
        partial_path.unlink()
    if verbose:
        print(f"Downloading {url} -> {archive_path}")
    urllib.request.urlretrieve(url, partial_path)
    if not zipfile.is_zipfile(partial_path):
        raise RuntimeError(f"Downloaded file is not a valid zip archive: {partial_path}")
    partial_path.replace(archive_path)
    return archive_path, version


def iter_xml_member_names(archive_path: Path) -> Iterable[str]:
    with zipfile.ZipFile(archive_path) as archive:
        for info in sorted(archive.infolist(), key=lambda item: item.filename):
            if info.is_dir() or not info.filename.lower().endswith(".xml"):
                continue
            yield info.filename


def _chunked(items: Sequence[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(items), size):
        yield list(items[index : index + size])


def write_subtitle_frequency_profile(
    member_name: str,
    data: bytes,
    output_items_dir: Path,
    language: str = "zh",
    source: str = DEFAULT_SOURCE,
    source_version: str = "unknown",
    min_count: int = 1,
    top: int = 0,
    min_cjk_chars: int = 1,
    normalize: str = "t2s",
    verbose: bool = False,
) -> dict:
    item_id = _subtitle_id(member_name)
    item_dir = output_items_dir / item_id
    item_dir.mkdir(parents=True, exist_ok=True)

    try:
        text = extract_opus_xml_text(data)
        normalized_text = normalize_chinese_text(text, normalize)
    except Exception as error:
        record = {
            "filepath": member_name,
            "filename": Path(member_name).name,
            "book_id": item_id,
            "title": Path(member_name).stem,
            "creator": None,
            "language": language,
            "media_type": "subtitle",
            "source": source,
            "source_version": source_version,
            "included": False,
            "reason": "read failed",
            "error_type": type(error).__name__,
            "error": str(error),
            "chars_profile": None,
            "words_profile": None,
        }
        (item_dir / "book.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return record

    cjk_count = len(list(_character_tokens(normalized_text)))
    included = cjk_count >= min_cjk_chars
    record = {
        "filepath": member_name,
        "filename": Path(member_name).name,
        "book_id": item_id,
        "title": Path(member_name).stem,
        "creator": None,
        "original_language": language,
        "detected_language": readability_metric.detect_language_code(normalized_text) if normalized_text else "unknown",
        "language": language,
        "media_type": "subtitle",
        "source": source,
        "source_version": source_version,
        "cjk_character_count": cjk_count,
        "included": included,
        "chars_profile": "chars.jsonl" if included else None,
        "words_profile": "words.jsonl" if included else None,
        "required_cjk_character_count": min_cjk_chars,
    }
    if not included:
        record["reason"] = f"fewer than {min_cjk_chars} CJK characters"
    else:
        profiles = build_frequency_profile_from_text(
            normalized_text,
            language=language,
            min_count=min_count,
            top=top,
            include_chars=True,
            include_words=True,
        )
        _write_jsonl(item_dir / "chars.jsonl", profiles["chars"])
        _write_jsonl(item_dir / "words.jsonl", profiles["words"])
        if verbose:
            print(f"  kept (CJK chars={cjk_count}): {member_name}")

    (item_dir / "book.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


def write_subtitle_frequency_batch(
    archive_path: Path,
    member_names: Sequence[str],
    output_items_dir: Path,
    language: str = "zh",
    source: str = DEFAULT_SOURCE,
    source_version: str = "unknown",
    min_count: int = 1,
    top: int = 0,
    min_cjk_chars: int = 1,
    normalize: str = "t2s",
    verbose: bool = False,
) -> list[dict]:
    records: list[dict] = []
    with zipfile.ZipFile(archive_path) as archive:
        for member_name in member_names:
            records.append(
                write_subtitle_frequency_profile(
                    member_name,
                    archive.read(member_name),
                    output_items_dir,
                    language=language,
                    source=source,
                    source_version=source_version,
                    min_count=min_count,
                    top=top,
                    min_cjk_chars=min_cjk_chars,
                    normalize=normalize,
                    verbose=verbose,
                )
            )
    return records


def write_local_subtitle_frequency_profile(
    subtitle_path: Path,
    corpus_root: Path,
    output_items_dir: Path,
    language: str = "zh",
    source: str = "Mandarin Subtitles Archive",
    source_version: str = "local",
    min_count: int = 1,
    top: int = 0,
    min_cjk_chars: int = 1,
    normalize: str = "t2s",
    verbose: bool = False,
) -> dict:
    relative_name = str(subtitle_path.relative_to(corpus_root))
    item_id = _subtitle_id(relative_name)
    item_dir = output_items_dir / item_id
    item_dir.mkdir(parents=True, exist_ok=True)
    metadata = local_subtitle_metadata(subtitle_path, corpus_root)

    try:
        text = extract_local_subtitle_text(subtitle_path)
        normalized_text = normalize_chinese_text(text, normalize)
    except Exception as error:
        record = {
            **metadata,
            "book_id": item_id,
            "language": language,
            "media_type": "subtitle",
            "source": source,
            "source_version": source_version,
            "included": False,
            "reason": "read failed",
            "error_type": type(error).__name__,
            "error": str(error),
            "chars_profile": None,
            "words_profile": None,
        }
        (item_dir / "book.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return record

    cjk_count = len(list(_character_tokens(normalized_text)))
    included = cjk_count >= min_cjk_chars
    detected_language = readability_metric.detect_language_code(normalized_text) if normalized_text else "unknown"
    record = {
        **metadata,
        "book_id": item_id,
        "original_language": language,
        "detected_language": detected_language,
        "language": language,
        "media_type": "subtitle",
        "source": source,
        "source_version": source_version,
        "cjk_character_count": cjk_count,
        "included": included,
        "chars_profile": "chars.jsonl" if included else None,
        "words_profile": "words.jsonl" if included else None,
        "required_cjk_character_count": min_cjk_chars,
    }
    if not included:
        record["reason"] = f"fewer than {min_cjk_chars} CJK characters"
    else:
        profiles = build_frequency_profile_from_text(
            normalized_text,
            language=language,
            min_count=min_count,
            top=top,
            include_chars=True,
            include_words=True,
        )
        _write_jsonl(item_dir / "chars.jsonl", profiles["chars"])
        _write_jsonl(item_dir / "words.jsonl", profiles["words"])
        if verbose:
            print(f"  kept (CJK chars={cjk_count}): {relative_name}")

    (item_dir / "book.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


def write_local_subtitle_frequency_batch(
    corpus_root: Path,
    paths: Sequence[Path],
    output_items_dir: Path,
    language: str = "zh",
    source: str = "Mandarin Subtitles Archive",
    source_version: str = "local",
    min_count: int = 1,
    top: int = 0,
    min_cjk_chars: int = 1,
    normalize: str = "t2s",
    verbose: bool = False,
) -> list[dict]:
    return [
        write_local_subtitle_frequency_profile(
            path,
            corpus_root,
            output_items_dir,
            language=language,
            source=source,
            source_version=source_version,
            min_count=min_count,
            top=top,
            min_cjk_chars=min_cjk_chars,
            normalize=normalize,
            verbose=verbose,
        )
        for path in paths
    ]


def _write_manifest(output_items_dir: Path, records: Sequence[dict]) -> list[Path]:
    manifest_path = output_items_dir / "manifest.jsonl"
    records = sorted(records, key=lambda row: row.get("filepath") or "")
    with manifest_path.open("w", encoding="utf-8") as manifest:
        for record in records:
            item_dir = output_items_dir / str(record["book_id"])
            manifest.write(json.dumps({**record, "book_dir": str(item_dir)}, ensure_ascii=False) + "\n")
    return [output_items_dir / str(record["book_id"]) for record in records if record.get("included")]


def build_subtitle_frequency_profiles(
    archive_path: Path,
    output_items_dir: Path,
    output_chars: Path,
    output_words: Path,
    language: str = "zh",
    source: str = DEFAULT_SOURCE,
    source_version: str = "unknown",
    min_count: int = 1,
    top: int = 0,
    min_cjk_chars: int = 1,
    normalize: str = "t2s",
    jobs: int = 1,
    limit: int = 0,
    verbose: bool = False,
) -> list[Path]:
    member_names = list(iter_xml_member_names(archive_path))
    if limit:
        member_names = member_names[:limit]
    if verbose:
        print(f"Found {len(member_names)} XML subtitle documents in {archive_path}")

    records: list[dict] = []
    if jobs > 1 and len(member_names) > 1:
        batches = list(_chunked(member_names, 100))
        with concurrent.futures.ProcessPoolExecutor(max_workers=jobs) as executor:
            futures = [
                executor.submit(
                    write_subtitle_frequency_batch,
                    archive_path,
                    batch,
                    output_items_dir,
                    language,
                    source,
                    source_version,
                    min_count,
                    top,
                    min_cjk_chars,
                    normalize,
                    verbose,
                )
                for batch in batches
            ]
            completed = 0
            for future in concurrent.futures.as_completed(futures):
                batch_records = future.result()
                records.extend(batch_records)
                completed += len(batch_records)
                if verbose:
                    print(f"Processed {completed}/{len(member_names)} subtitle documents")
    else:
        with zipfile.ZipFile(archive_path) as archive:
            for index, name in enumerate(member_names, start=1):
                if verbose:
                    print(f"Scanning {index}/{len(member_names)}: {name}")
                records.append(
                    write_subtitle_frequency_profile(
                        name,
                        archive.read(name),
                        output_items_dir,
                        language=language,
                        source=source,
                        source_version=source_version,
                        min_count=min_count,
                        top=top,
                        min_cjk_chars=min_cjk_chars,
                        normalize=normalize,
                        verbose=verbose,
                    )
                )

    included_dirs = _write_manifest(output_items_dir, records)
    write_merged_profiles(
        included_dirs,
        output_chars,
        output_words,
        min_count=min_count,
        top=top,
        include_chars=True,
        include_words=True,
    )
    if verbose:
        print(f"Scanned {len(records)} subtitles: {len(included_dirs)} kept as {language}, {len(records) - len(included_dirs)} skipped")
    return included_dirs


def build_local_subtitle_frequency_profiles(
    corpus_root: Path,
    output_items_dir: Path,
    output_chars: Path,
    output_words: Path,
    language: str = "zh",
    source: str = "Mandarin Subtitles Archive",
    source_version: str = "local",
    min_count: int = 1,
    top: int = 0,
    min_cjk_chars: int = 1,
    normalize: str = "t2s",
    jobs: int = 1,
    limit: int = 0,
    verbose: bool = False,
) -> list[Path]:
    subtitle_paths = list(iter_local_subtitle_paths(corpus_root))
    if limit:
        subtitle_paths = subtitle_paths[:limit]
    if verbose:
        print(f"Found {len(subtitle_paths)} local subtitle files in {corpus_root}")

    records: list[dict] = []
    if jobs > 1 and len(subtitle_paths) > 1:
        batches = list(_chunked(subtitle_paths, 100))
        with concurrent.futures.ProcessPoolExecutor(max_workers=jobs) as executor:
            futures = [
                executor.submit(
                    write_local_subtitle_frequency_batch,
                    corpus_root,
                    batch,
                    output_items_dir,
                    language,
                    source,
                    source_version,
                    min_count,
                    top,
                    min_cjk_chars,
                    normalize,
                    verbose,
                )
                for batch in batches
            ]
            completed = 0
            for future in concurrent.futures.as_completed(futures):
                batch_records = future.result()
                records.extend(batch_records)
                completed += len(batch_records)
                if verbose:
                    print(f"Processed {completed}/{len(subtitle_paths)} local subtitle files")
    else:
        for index, subtitle_path in enumerate(subtitle_paths, start=1):
            if verbose:
                print(f"Scanning {index}/{len(subtitle_paths)}: {subtitle_path.relative_to(corpus_root)}")
            records.append(
                write_local_subtitle_frequency_profile(
                    subtitle_path,
                    corpus_root,
                    output_items_dir,
                    language=language,
                    source=source,
                    source_version=source_version,
                    min_count=min_count,
                    top=top,
                    min_cjk_chars=min_cjk_chars,
                    normalize=normalize,
                    verbose=verbose,
                )
            )

    included_dirs = _write_manifest(output_items_dir, records)
    write_merged_profiles(
        included_dirs,
        output_chars,
        output_words,
        min_count=min_count,
        top=top,
        include_chars=True,
        include_words=True,
    )
    if verbose:
        print(f"Scanned {len(records)} local subtitles: {len(included_dirs)} kept as {language}, {len(records) - len(included_dirs)} skipped")
    return included_dirs


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Extract ranked Chinese vocabulary profiles from subtitle corpora.")
    parser.add_argument("--language", default="zh", choices=("zh",), help="Subtitle language to process")
    parser.add_argument("--source", default="opus-opensubtitles", choices=("opus-opensubtitles", "local-folder"))
    parser.add_argument("--opus-language", default=DEFAULT_OPUS_LANGUAGE)
    parser.add_argument("--opus-api", default=DEFAULT_OPUS_API)
    parser.add_argument("--archive", help="Existing OPUS zip archive to process instead of downloading")
    parser.add_argument("--corpus-root", help="Local subtitle folder for --source local-folder")
    parser.add_argument("--download-dir", default="~/Downloads/subtitles/opus-opensubtitles-zh_CN")
    parser.add_argument("--force-download", action="store_true")
    parser.add_argument("--output-items", default="results/zh-subtitles")
    parser.add_argument("--output-chars", default="results/zh-subtitle-chars.jsonl")
    parser.add_argument("--output-words", default="results/zh-subtitle-words.jsonl")
    parser.add_argument("--min-count", type=int, default=1)
    parser.add_argument("--top", type=int, default=0)
    parser.add_argument("--min-cjk-chars", type=int, default=1)
    parser.add_argument("--normalize", default="t2s", choices=("t2s", "s2t", "none"))
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--limit", type=int, default=0, help="Process only the first N XML documents")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    if args.source == "local-folder":
        if not args.corpus_root:
            raise SystemExit("--corpus-root is required for --source local-folder")
        included_dirs = build_local_subtitle_frequency_profiles(
            Path(args.corpus_root).expanduser(),
            Path(args.output_items),
            Path(args.output_chars),
            Path(args.output_words),
            language=args.language,
            source="Mandarin Subtitles Archive",
            source_version="local",
            min_count=max(1, args.min_count),
            top=max(0, args.top),
            min_cjk_chars=max(1, args.min_cjk_chars),
            normalize=args.normalize,
            jobs=max(1, args.jobs),
            limit=max(0, args.limit),
            verbose=args.verbose,
        )
    else:
        if args.archive:
            archive_path = Path(args.archive).expanduser()
            source_version = "local"
        else:
            archive_path, source_version = download_opus_archive(
                Path(args.download_dir).expanduser(),
                force=args.force_download,
                api_url=args.opus_api,
                language=args.opus_language,
                verbose=args.verbose,
            )

        included_dirs = build_subtitle_frequency_profiles(
            archive_path,
            Path(args.output_items),
            Path(args.output_chars),
            Path(args.output_words),
            language=args.language,
            source=DEFAULT_SOURCE,
            source_version=source_version,
            min_count=max(1, args.min_count),
            top=max(0, args.top),
            min_cjk_chars=max(1, args.min_cjk_chars),
            normalize=args.normalize,
            jobs=max(1, args.jobs),
            limit=max(0, args.limit),
            verbose=args.verbose,
        )
    print(
        f"Computed subtitle profiles for {len(included_dirs)} items into "
        f"{args.output_items}, {args.output_chars}, {args.output_words}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
