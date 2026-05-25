"""Build frequency tables from EPUB corpora, focused on Chinese learning data."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

import readability_metric

try:  # pragma: no cover - optional dependency for proper Chinese word segmentation.
    import jieba  # type: ignore
except Exception:  # pragma: no cover
    jieba = None


def _iter_chinese_epub_texts(corpus_root: Path) -> Iterable[str]:
    for path in readability_metric.iter_epub_files([str(corpus_root)]):
        try:
            text = readability_metric.fallback_epub_text(str(path))
        except Exception:
            continue
        if readability_metric.detect_language_code(text).startswith("zh"):
            yield text


def _character_tokens(text: str) -> Iterable[str]:
    yield from readability_metric.CJK_RE.findall(text or "")


def _word_tokens(text: str) -> Iterable[str]:
    if jieba is None:
        yield from _character_tokens(text)
        return
    for token in jieba.lcut(text):
        if readability_metric.CJK_RE.search(token):
            yield token.strip()


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


def build_chinese_frequency_profiles(
    corpus_root: Path,
    min_count: int = 2,
    top: int = 0,
    include_chars: bool = True,
    include_words: bool = True,
) -> Dict[str, List[dict]]:
    char_counter: Counter[str] = Counter()
    word_counter: Counter[str] = Counter()

    for text in _iter_chinese_epub_texts(corpus_root):
        char_counter.update(_character_tokens(text))
        word_counter.update(_word_tokens(text))

    return {
        "chars": _to_ranked_entries(char_counter, "char", top=top, min_count=min_count) if include_chars else [],
        "words": _to_ranked_entries(word_counter, "word", top=top, min_count=min_count) if include_words else [],
    }


def _write_jsonl(path: Path, rows: Sequence[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as out_file:
        for row in rows:
            out_file.write(json.dumps(row, ensure_ascii=False) + "\n")


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Extract ranked Chinese chars and words from EPUB corpora.")
    parser.add_argument("--corpus-dir", required=True, help="Directory containing EPUB files")
    parser.add_argument("--output-chars", default="results/chinese-chars.jsonl")
    parser.add_argument("--output-words", default="results/chinese-words.jsonl")
    parser.add_argument("--top", type=int, default=0, help="Limit ranking output")
    parser.add_argument("--min-count", type=int, default=2)
    parser.add_argument("--chars-only", action="store_true", help="Only export character frequencies")
    parser.add_argument("--words-only", action="store_true", help="Only export word frequencies")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    include_chars = not args.words_only
    include_words = not args.chars_only

    profiles = build_chinese_frequency_profiles(
        Path(args.corpus_dir),
        min_count=max(1, args.min_count),
        top=max(0, args.top),
        include_chars=include_chars,
        include_words=include_words,
    )

    if include_chars:
        _write_jsonl(Path(args.output_chars), profiles["chars"])
    if include_words:
        _write_jsonl(Path(args.output_words), profiles["words"])

    print(
        f"Computed {len(profiles['chars'])} chars and {len(profiles['words'])} words"
        if args.words_only is False or args.chars_only is False
        else "No data requested"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
