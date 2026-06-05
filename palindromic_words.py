"""Find palindromic words in a word list."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import TextIO


def is_palindrome(word: str, *, case_sensitive: bool = False) -> bool:
    """Return True when word reads the same forwards and backwards."""
    comparable = word if case_sensitive else word.casefold()
    return comparable == comparable[::-1]


def find_palindromes(
    words: Iterable[str],
    *,
    case_sensitive: bool = False,
    min_length: int = 2,
    unique: bool = False,
) -> Iterator[str]:
    """Yield palindromic words from an iterable of words."""
    seen: set[str] = set()

    for word in words:
        if len(word) < min_length or not is_palindrome(word, case_sensitive=case_sensitive):
            continue

        key = word if case_sensitive else word.casefold()
        if unique and key in seen:
            continue

        seen.add(key)
        yield word


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
        "--unique",
        action="store_true",
        help="Print each palindrome once, preserving the first spelling seen.",
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

    if args.word_file is None:
        words = read_words(sys.stdin, jsonl_field=args.jsonl_field)
    else:
        words = read_words(
            args.word_file.open(encoding="utf-8"),
            jsonl_field=args.jsonl_field,
        )

    for word in find_palindromes(
        words,
        case_sensitive=args.case_sensitive,
        min_length=args.min_length,
        unique=args.unique,
    ):
        print(word)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
