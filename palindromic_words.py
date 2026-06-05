"""Find word pairs where one word is the reverse of another."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import TextIO


def is_two_character_repeat(word: str) -> bool:
    """Return True for two-character words made from the same character."""
    return len(word) == 2 and word[0] == word[1]


def normalize_word(word: str, *, case_sensitive: bool = False) -> str:
    """Return the comparison form for a word."""
    return word if case_sensitive else word.casefold()


def find_mirror_pairs(
    words: Iterable[str],
    *,
    case_sensitive: bool = False,
    min_length: int = 2,
    max_length: int | None = None,
) -> Iterator[tuple[str, str]]:
    """Yield pairs where the second word is the reverse of the first."""
    words_by_key: dict[str, str] = {}
    yielded: set[frozenset[str]] = set()

    for word in words:
        if (
            len(word) < min_length
            or (max_length is not None and len(word) > max_length)
            or is_two_character_repeat(word)
        ):
            continue

        key = normalize_word(word, case_sensitive=case_sensitive)
        reverse_key = key[::-1]
        if key == reverse_key:
            continue

        if reverse_key in words_by_key:
            pair_key = frozenset((key, reverse_key))
            if pair_key not in yielded:
                yielded.add(pair_key)
                yield words_by_key[reverse_key], word

        words_by_key.setdefault(key, word)


def read_words(stream: TextIO, *, jsonl_field: str = "item") -> Iterator[str]:
    """Yield words from plain text or JSONL records."""
    for line_number, line in enumerate(stream, start=1):
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.startswith("{"):
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as error:
                raise ValueError(f"invalid JSON on line {line_number}: {error.msg}") from error

            try:
                word = record[jsonl_field]
            except KeyError as error:
                raise ValueError(f"missing JSONL field {jsonl_field!r} on line {line_number}") from error

            if isinstance(word, str):
                yield word
            continue

        yield from stripped.split()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "word_file",
        nargs="?",
        type=Path,
        help="Text file containing words. Reads stdin when omitted.",
    )
    parser.add_argument(
        "--case-sensitive",
        action="store_true",
        help="Compare words without lowercasing them first.",
    )
    parser.add_argument(
        "--min-length",
        type=int,
        default=2,
        help="Minimum word length to include. Defaults to 2.",
    )
    parser.add_argument(
        "--max-length",
        type=int,
        default=None,
        help="Maximum word length to include. Defaults to no upper limit.",
    )
    parser.add_argument(
        "--unique",
        action="store_true",
        help="Deprecated; mirror pairs are always printed once.",
    )
    parser.add_argument(
        "--jsonl-field",
        default="item",
        help="Field to read from JSONL records. Defaults to item.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)

    if args.min_length < 1:
        raise SystemExit("--min-length must be at least 1")

    if args.max_length is not None and args.max_length < args.min_length:
        raise SystemExit(
            f"--max-length must be greater than or equal to --min-length ({args.min_length})"
        )

    if args.word_file is None:
        words = read_words(sys.stdin, jsonl_field=args.jsonl_field)
    else:
        words = read_words(
            args.word_file.open(encoding="utf-8"),
            jsonl_field=args.jsonl_field,
        )

    for word, reverse_word in find_mirror_pairs(
        words,
        case_sensitive=args.case_sensitive,
        min_length=args.min_length,
        max_length=args.max_length,
    ):
        print(f"{word}\t{reverse_word}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
