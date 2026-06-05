"""Build frequency tables from EPUB corpora, focused on Chinese learning data."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import html
import json
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, DefaultDict, Dict, Iterable, List, Sequence, Tuple

import readability_metric

try:  # pragma: no cover - optional dependency for proper Chinese word segmentation.
    import jieba  # type: ignore
    import jieba.posseg as jieba_posseg  # type: ignore
except Exception:  # pragma: no cover
    jieba = None
    jieba_posseg = None


def _iter_chinese_epub_texts(corpus_root: Path, verbose: bool = False) -> Iterable[str]:
    epub_paths = list(readability_metric.iter_epub_files([str(corpus_root)]))
    total = len(epub_paths)
    if verbose:
        print(f"Found {total} EPUB files in {corpus_root}")

    if total == 0:
        return

    kept = 0
    non_chinese = 0
    read_failed = 0
    for index, path in enumerate(epub_paths, start=1):
        if verbose:
            print(f"Scanning {index}/{total}: {path.name}")

        try:
            text = readability_metric.fallback_epub_text(str(path))
        except Exception:
            read_failed += 1
            if verbose:
                print(f"  skipped (read failed): {path.name}")
            continue

        if readability_metric.detect_language_code(text).startswith("zh"):
            kept += 1
            if verbose:
                print(f"  kept (Chinese): {path.name}")
            yield text
        else:
            non_chinese += 1
            if verbose:
                print(f"  skipped (non-Chinese): {path.name}")

    if verbose:
        print(
            "Scanned "
            f"{total} EPUB files: "
            f"{kept} kept as Chinese, "
            f"{non_chinese} non-Chinese, "
            f"{read_failed} failed"
        )


def _character_tokens(text: str) -> Iterable[str]:
    yield from readability_metric.CJK_RE.findall(text or "")


def _word_tokens(text: str) -> Iterable[str]:
    if jieba is None:
        yield from _character_tokens(text)
        return
    for token in jieba.lcut(text):
        if readability_metric.CJK_RE.search(token):
            yield token.strip()


def _coarse_pos(raw_pos: str) -> str:
    if not raw_pos:
        return "other"
    if raw_pos.startswith("n"):
        return "noun"
    if raw_pos.startswith("v"):
        return "verb"
    if raw_pos.startswith("a"):
        return "adjective"
    if raw_pos.startswith("d"):
        return "adverb"
    if raw_pos in {"r", "rr", "rz", "rg"}:
        return "pronoun"
    if raw_pos in {"m", "q"}:
        return "quantifier"
    if raw_pos in {"p", "u", "c"}:
        return "function"
    return "other"


def _word_tokens_with_pos(text: str) -> Iterable[Tuple[str, str]]:
    if jieba_posseg is None:
        for token in _word_tokens(text):
            yield token.strip(), ""
        return

    for item in jieba_posseg.cut(text):
        token = (item.word or "").strip()
        raw_pos = item.flag or ""
        if token and readability_metric.CJK_RE.search(token):
            yield token, raw_pos


def _to_ranked_entries(counter: Counter, unit: str, top: int, min_count: int) -> List[dict]:
    total_tokens = sum(counter.values())
    if total_tokens == 0:
        return []

    ranked = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    entries: List[dict] = []
    cumulative = 0
    rank = 1
    for token, count in ranked:
        if count < min_count:
            break
        cumulative += count
        entries.append(
            {
                "unit": unit,
                "item": token,
                "count": int(count),
                "rank": rank,
                "cumulative_count": cumulative,
                "coverage": cumulative / total_tokens,
            }
        )
        rank += 1
        if top and len(entries) >= top:
            break
    return entries


def _extract_phrase_counts(text: str, max_len: int = 3) -> Counter:
    if max_len < 2:
        return Counter()

    tokens = list(_word_tokens(text))
    if len(tokens) < 2:
        return Counter()

    phrases = Counter()
    max_len = min(max_len, len(tokens))
    for span in range(2, max_len + 1):
        for index in range(len(tokens) - span + 1):
            phrase = "".join(tokens[index : index + span])
            if not phrase:
                continue
            if not all(readability_metric.CJK_RE.search(char) for char in phrase):
                continue
            phrases[phrase] += 1
    return phrases


def build_chinese_frequency_profiles(
    corpus_root: Path,
    min_count: int = 2,
    top: int = 0,
    include_chars: bool = True,
    include_words: bool = True,
    include_phrases: bool = False,
    phrase_max_length: int = 3,
    with_pos: bool = False,
    verbose: bool = False,
) -> Dict[str, List[dict]]:
    char_counter: Counter[str] = Counter()
    word_counter: Counter[str] = Counter()
    phrase_counter: Counter[str] = Counter()
    word_pos_counter: DefaultDict[str, Counter] = defaultdict(Counter)

    for text in _iter_chinese_epub_texts(corpus_root, verbose=verbose):
        char_counter.update(_character_tokens(text))
        if with_pos:
            for word, raw_pos in _word_tokens_with_pos(text):
                word_counter[word] += 1
                word_pos_counter[word][_coarse_pos(raw_pos)] += 1
        else:
            word_counter.update(_word_tokens(text))

        if include_phrases:
            phrase_counter.update(_extract_phrase_counts(text, max_len=phrase_max_length))

    words = _to_ranked_entries(word_counter, "word", top=top, min_count=min_count) if include_words else []
    if with_pos:
        for entry in words:
            pos_counts = word_pos_counter.get(entry["item"], Counter())
            if pos_counts:
                ranked = sorted(pos_counts.items(), key=lambda item: (-item[1], item[0]))
                total = sum(value for _, value in ranked)
                entry["pos_primary"] = ranked[0][0]
                entry["pos_distribution"] = [
                    {
                        "pos": pos,
                        "count": int(count),
                        "share": count / total if total else 0.0,
                    }
                    for pos, count in ranked
                ]
            else:
                entry["pos_primary"] = "other"
                entry["pos_distribution"] = [{"pos": "other", "count": entry["count"], "share": 1.0}]

    return {
        "chars": _to_ranked_entries(char_counter, "char", top=top, min_count=min_count) if include_chars else [],
        "words": words,
        "phrases": _to_ranked_entries(phrase_counter, "phrase", top=top, min_count=min_count) if include_phrases else [],
    }




def _book_id(path: Path) -> str:
    digest = hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:10]
    return f"{path.stem}-{digest}"


def _book_metadata(path: Path, text: str, book_id: str, included: bool, reason: str | None = None) -> dict:
    metadata: Dict[str, Any] = {}
    try:
        metadata = readability_metric.fallback_epub_metadata(str(path))
    except Exception:
        metadata = {}
    detected_language = readability_metric.detect_language_code(text) if text else "unknown"
    record = {
        "filepath": str(path),
        "filename": path.name,
        "book_id": book_id,
        "title": metadata.get("title"),
        "creator": metadata.get("creator"),
        "original_language": metadata.get("original_language") or metadata.get("language"),
        "detected_language": detected_language,
        "cjk_character_count": len(list(_character_tokens(text))),
        "included": included,
        "chars_profile": "chars.jsonl" if included else None,
        "words_profile": "words.jsonl" if included else None,
    }
    if reason:
        record["reason"] = reason
    return record


def build_chinese_frequency_profile_from_text(
    text: str,
    min_count: int = 2,
    top: int = 0,
    include_chars: bool = True,
    include_words: bool = True,
) -> Dict[str, List[dict]]:
    char_counter: Counter[str] = Counter()
    word_counter: Counter[str] = Counter()
    if include_chars:
        char_counter.update(_character_tokens(text))
    if include_words:
        word_counter.update(_word_tokens(text))
    return {
        "chars": _to_ranked_entries(char_counter, "char", top=top, min_count=min_count) if include_chars else [],
        "words": _to_ranked_entries(word_counter, "word", top=top, min_count=min_count) if include_words else [],
    }


def write_book_frequency_profile(
    epub_path: Path,
    output_books_dir: Path,
    min_count: int = 1,
    top: int = 0,
    include_chars: bool = True,
    include_words: bool = True,
    min_cjk_chars: int = 100,
    verbose: bool = False,
) -> dict:
    path = Path(epub_path)
    book_id = _book_id(path)
    book_dir = output_books_dir / book_id
    book_dir.mkdir(parents=True, exist_ok=True)
    try:
        text = readability_metric.fallback_epub_text(str(path))
    except Exception as error:
        record = _book_metadata(path, "", book_id, included=False, reason="read failed")
        record["error_type"] = type(error).__name__
        record["error"] = str(error)
        (book_dir / "book.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        if verbose:
            print(f"  skipped (read failed): {path.name}")
        return record

    cjk_count = len(list(_character_tokens(text)))
    metadata = {}
    try:
        metadata = readability_metric.fallback_epub_metadata(str(path))
    except Exception:
        metadata = {}
    original_language = metadata.get("original_language") or metadata.get("language")
    required_cjk_chars = 1 if readability_metric.is_chinese_language(original_language) else min_cjk_chars
    included = cjk_count >= required_cjk_chars
    reason = None if included else f"fewer than {required_cjk_chars} CJK characters"
    record = _book_metadata(path, text, book_id, included=included, reason=reason)
    record["required_cjk_character_count"] = required_cjk_chars
    if included:
        record["chars_profile"] = "chars.jsonl" if include_chars else None
        record["words_profile"] = "words.jsonl" if include_words else None
        profiles = build_chinese_frequency_profile_from_text(
            text,
            min_count=min_count,
            top=top,
            include_chars=include_chars,
            include_words=include_words,
        )
        if include_chars:
            _write_jsonl(book_dir / "chars.jsonl", profiles["chars"])
        if include_words:
            _write_jsonl(book_dir / "words.jsonl", profiles["words"])
        if verbose:
            print(f"  kept (CJK chars={cjk_count}): {path.name}")
    elif verbose:
        print(f"  skipped (CJK chars={cjk_count}): {path.name}")

    (book_dir / "book.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


def read_profile_counts(path: Path) -> Counter:
    counter: Counter[str] = Counter()
    if not path.exists():
        return counter
    with path.open(encoding="utf-8") as profile:
        for line in profile:
            if not line.strip():
                continue
            row = json.loads(line)
            counter[str(row["item"])] += int(row["count"])
    return counter


def merge_profile_counts(book_dirs: Sequence[Path], unit: str) -> Counter:
    filename = "chars.jsonl" if unit == "char" else "words.jsonl"
    aggregate: Counter[str] = Counter()
    for book_dir in book_dirs:
        aggregate.update(read_profile_counts(Path(book_dir) / filename))
    return aggregate


def write_merged_profiles(
    book_dirs: Sequence[Path],
    output_chars: Path,
    output_words: Path,
    min_count: int = 1,
    top: int = 0,
    include_chars: bool = True,
    include_words: bool = True,
) -> Dict[str, List[dict]]:
    profiles = {"chars": [], "words": []}
    if include_chars:
        profiles["chars"] = _to_ranked_entries(merge_profile_counts(book_dirs, "char"), "char", top=top, min_count=min_count)
        _write_jsonl(output_chars, profiles["chars"])
    if include_words:
        profiles["words"] = _to_ranked_entries(merge_profile_counts(book_dirs, "word"), "word", top=top, min_count=min_count)
        _write_jsonl(output_words, profiles["words"])
    return profiles


def _book_dirs_from_manifest(path: Path) -> List[Path]:
    book_dirs: List[Path] = []
    with path.open(encoding="utf-8") as manifest:
        for line_number, line in enumerate(manifest, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            book_dir = row.get("book_dir")
            if not book_dir:
                raise ValueError(f"{path}:{line_number}: missing book_dir")
            book_dirs.append(Path(book_dir))
    return book_dirs


def build_book_frequency_profiles(
    corpus_root: Path,
    output_books_dir: Path,
    min_count: int = 1,
    top: int = 0,
    include_chars: bool = True,
    include_words: bool = True,
    min_cjk_chars: int = 100,
    jobs: int = 1,
    verbose: bool = False,
) -> List[Path]:
    epub_paths = list(readability_metric.iter_epub_files([str(corpus_root)]))
    if verbose:
        print(f"Found {len(epub_paths)} EPUB files in {corpus_root}")

    records: List[dict] = []
    if jobs > 1 and len(epub_paths) > 1:
        with concurrent.futures.ProcessPoolExecutor(max_workers=jobs) as executor:
            futures = [
                executor.submit(
                    write_book_frequency_profile,
                    path,
                    output_books_dir,
                    min_count,
                    top,
                    include_chars,
                    include_words,
                    min_cjk_chars,
                    verbose,
                )
                for path in epub_paths
            ]
            for future in concurrent.futures.as_completed(futures):
                records.append(future.result())
    else:
        for index, path in enumerate(epub_paths, start=1):
            if verbose:
                print(f"Scanning {index}/{len(epub_paths)}: {path.name}")
            records.append(
                write_book_frequency_profile(
                    path,
                    output_books_dir,
                    min_count=min_count,
                    top=top,
                    include_chars=include_chars,
                    include_words=include_words,
                    min_cjk_chars=min_cjk_chars,
                    verbose=verbose,
                )
            )

    manifest_path = output_books_dir / "manifest.jsonl"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    records.sort(key=lambda row: row.get("filepath") or "")
    with manifest_path.open("w", encoding="utf-8") as manifest:
        for record in records:
            book_dir = output_books_dir / str(record["book_id"])
            manifest.write(json.dumps({**record, "book_dir": str(book_dir)}, ensure_ascii=False) + "\n")

    included_dirs = [output_books_dir / str(record["book_id"]) for record in records if record.get("included")]
    if verbose:
        skipped = len(records) - len(included_dirs)
        print(f"Scanned {len(records)} EPUB files: {len(included_dirs)} kept as CJK, {skipped} skipped")
    return included_dirs

def _strip_html_markup(value: str) -> str:
    cleaned = html.unescape(value)
    cleaned = cleaned.replace("<br>", " ")
    cleaned = cleaned.replace("<br/>", " ")
    cleaned = cleaned.replace("<br />", " ")
    return "".join(ch for ch in cleaned if ch not in "<>\"'").strip()


def _is_open_license(name: str | None) -> bool:
    if not name:
        return False
    normalized = name.strip().lower()
    if not normalized:
        return False
    if "all rights reserved" in normalized or "rights reserved" in normalized:
        return False
    allowed_markers = (
        "creative commons",
        "cc",
        "public domain",
        "cc0",
        "gfdl",
        "free documentation",
        "attribution",
    )
    return any(marker in normalized for marker in allowed_markers)


def _fetch_wikimedia_image(query: str, timeout: float = 10.0) -> Dict[str, Any]:
    endpoint = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": "6",
        "gsrlimit": "1",
        "prop": "imageinfo",
        "iiprop": "url|mime|size|extmetadata",
        "format": "json",
        "origin": "*",
    }
    request = urllib.request.Request(
        f"{endpoint}?{urllib.parse.urlencode(params)}",
        headers={"User-Agent": "readability-metric image fetcher"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            payload = json.load(response)
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as error:
        return {
            "status": "error",
            "provider": "wikimedia",
            "query": query,
            "error": str(error),
            "is_open_license": False,
        }

    pages = payload.get("query", {}).get("pages")
    if not pages:
        return {
            "status": "missing",
            "provider": "wikimedia",
            "query": query,
            "is_open_license": False,
            "license": None,
        }

    first_page = next(iter(pages.values()), None)
    if not first_page:
        return {
            "status": "missing",
            "provider": "wikimedia",
            "query": query,
            "is_open_license": False,
            "license": None,
        }

    infos = first_page.get("imageinfo") or []
    if not infos:
        return {
            "status": "missing",
            "provider": "wikimedia",
            "query": query,
            "is_open_license": False,
            "license": None,
        }

    info = infos[0]
    extmetadata = info.get("extmetadata", {})
    license_name = None
    if isinstance(extmetadata, dict):
        raw_license = extmetadata.get("License", {}).get("value") or extmetadata.get("LicenseShortName", {}).get("value")
        if raw_license:
            license_name = _strip_html_markup(raw_license)

    open_license = _is_open_license(license_name)
    return {
        "status": "hit",
        "provider": "wikimedia",
        "query": query,
        "is_open_license": open_license,
        "license": license_name,
        "image_url": info.get("url"),
        "width": info.get("width"),
        "height": info.get("height"),
        "mime": info.get("mime"),
        "byte_size": info.get("size"),
        "source_url": first_page.get("canonicalurl"),
    }


def _load_image_cache(path: Path) -> Dict[str, dict]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def _save_image_cache(path: Path, cache: Dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def enrich_with_images(
    entries: Sequence[dict],
    image_limit: int = 0,
    cache: Dict[str, dict] | None = None,
    require_open_license: bool = True,
    fetcher=_fetch_wikimedia_image,
) -> Tuple[List[dict], Dict[str, int]]:
    image_cache = cache if cache is not None else {}
    enriched: List[dict] = []
    stats = {"requested": 0, "hits": 0, "miss": 0, "skipped_non_open": 0, "errors": 0}

    source = list(entries)
    if image_limit:
        source = source[:image_limit]

    for entry in source:
        stats["requested"] += 1
        item = entry.get("item")
        cached = image_cache.get(str(item))
        if cached is not None:
            result = cached
        else:
            result = fetcher(str(item))
            image_cache[str(item)] = result

        if result.get("status") == "hit":
            if require_open_license and not result.get("is_open_license"):
                result = {
                    **result,
                    "status": "skipped_non_open",
                }
                stats["skipped_non_open"] += 1
            else:
                stats["hits"] += 1
        elif result.get("status") == "missing":
            stats["miss"] += 1
        else:
            stats["errors"] += 1

        out = dict(entry)
        out["image"] = result
        out["image_status"] = result.get("status")
        enriched.append(out)

    return enriched, stats


def _write_jsonl(path: Path, rows: Sequence[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as out_file:
        for row in rows:
            out_file.write(json.dumps(row, ensure_ascii=False) + "\n")


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Extract ranked Chinese chars and words from EPUB corpora.")
    parser.add_argument("--corpus-dir", help="Directory containing EPUB files")
    parser.add_argument("--output-chars", default="results/chinese-chars.jsonl")
    parser.add_argument("--output-words", default="results/chinese-words.jsonl")
    parser.add_argument("--output-phrases", default="results/chinese-phrases.jsonl")
    parser.add_argument("--top", type=int, default=0, help="Limit ranking output")
    parser.add_argument("--min-count", type=int, default=2)
    parser.add_argument("--output-books", help="Directory for per-book frequency profiles")
    parser.add_argument("--merge-manifest", help="JSONL manifest of per-book profile directories to merge")
    parser.add_argument("--min-cjk-chars", type=int, default=100, help="Minimum CJK character count for per-book profile inclusion")
    parser.add_argument("--jobs", type=int, default=1, help="Parallel workers for per-book extraction")
    parser.add_argument("--verbose", action="store_true", help="Print progress while scanning EPUB files")
    parser.add_argument("--chars-only", action="store_true", help="Only export character frequencies")
    parser.add_argument("--words-only", action="store_true", help="Only export word frequencies")
    parser.add_argument("--with-pos", action="store_true", help="Attach POS info to words")
    parser.add_argument("--with-phrases", action="store_true", help="Include frequent multi-word phrases")
    parser.add_argument("--phrase-max-length", type=int, default=3)
    parser.add_argument("--fetch-images", action="store_true", help="Fetch Wikimedia images for selected units")
    parser.add_argument("--image-output", default="results/chinese-images.jsonl")
    parser.add_argument("--image-cache", default=".vocab-image-cache.json")
    parser.add_argument("--image-limit", type=int, default=0)
    parser.add_argument("--allow-non-open", action="store_true", help="Keep non-open-license hits")
    parser.add_argument("--image-unit-filter", default="all", choices=("all", "char", "word", "phrase"))
    return parser.parse_args(argv)


def _filtered_items(profiles: Dict[str, List[dict]], unit_filter: str) -> List[dict]:
    if unit_filter == "all":
        return list(profiles.get("chars", [])) + list(profiles.get("words", [])) + list(profiles.get("phrases", []))
    return list(profiles.get(f"{unit_filter}s" if unit_filter != "phrase" else "phrases", []))


def main(argv=None) -> int:
    args = _parse_args(argv)
    include_chars = not args.words_only
    include_words = not args.chars_only
    if not include_chars and not include_words:
        print("No output type selected. Use --chars-only or --words-only")
        return 1

    min_count = max(1, args.min_count)
    top = max(0, args.top)
    include_phrases = bool(args.with_phrases)

    if args.merge_manifest:
        book_dirs = _book_dirs_from_manifest(Path(args.merge_manifest))
        profiles = write_merged_profiles(
            book_dirs,
            Path(args.output_chars),
            Path(args.output_words),
            min_count=min_count,
            top=top,
            include_chars=include_chars,
            include_words=include_words,
        )
        print(
            f"Merged {len(book_dirs)} book profiles into "
            f"{len(profiles['chars']) if include_chars else 0} chars, "
            f"{len(profiles['words']) if include_words else 0} words"
        )
    elif args.output_books:
        if not args.corpus_dir:
            print("--output-books requires --corpus-dir")
            return 1
        book_dirs = build_book_frequency_profiles(
            Path(args.corpus_dir),
            Path(args.output_books),
            min_count=min_count,
            top=top,
            include_chars=include_chars,
            include_words=include_words,
            min_cjk_chars=max(1, args.min_cjk_chars),
            jobs=max(1, args.jobs),
            verbose=args.verbose,
        )
        profiles = write_merged_profiles(
            book_dirs,
            Path(args.output_chars),
            Path(args.output_words),
            min_count=min_count,
            top=top,
            include_chars=include_chars,
            include_words=include_words,
        )
        if include_phrases:
            print("--with-phrases is ignored when --output-books is used")
        print(
            f"Computed {len(profiles['chars']) if include_chars else 0} chars, "
            f"{len(profiles['words']) if include_words else 0} words "
            f"from {len(book_dirs)} book profiles"
        )
    else:
        if not args.corpus_dir:
            print("provide --corpus-dir or --merge-manifest")
            return 1
        profiles = build_chinese_frequency_profiles(
            Path(args.corpus_dir),
            min_count=min_count,
            top=top,
            include_chars=include_chars,
            include_words=include_words,
            include_phrases=include_phrases,
            phrase_max_length=max(2, args.phrase_max_length),
            with_pos=args.with_pos,
            verbose=args.verbose,
        )

        if include_chars:
            _write_jsonl(Path(args.output_chars), profiles["chars"])
        if include_words:
            _write_jsonl(Path(args.output_words), profiles["words"])
        if include_phrases and args.output_phrases:
            _write_jsonl(Path(args.output_phrases), profiles["phrases"])

        print(
            f"Computed {len(profiles['chars']) if include_chars else 0} chars, "
            f"{len(profiles['words']) if include_words else 0} words, "
            f"{len(profiles['phrases']) if include_phrases else 0} phrases"
        )

    if args.fetch_images:
        image_items = _filtered_items(profiles, args.image_unit_filter)
        cache = _load_image_cache(Path(args.image_cache))
        enriched, stats = enrich_with_images(
            image_items,
            image_limit=max(0, args.image_limit),
            cache=cache,
            require_open_license=not args.allow_non_open,
        )
        _write_jsonl(Path(args.image_output), enriched)
        _save_image_cache(Path(args.image_cache), cache)
        print(
            "Image fetch: requested={requested} hits={hits} miss={miss} skipped={skipped_non_open} errors={errors}".format(
                **stats
            )
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
