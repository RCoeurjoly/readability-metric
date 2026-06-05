"""Adaptive quiz for ranked Chinese character and word lists."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List


AnswerFn = Callable[["VocabularyEntry"], bool | None]


@dataclass(frozen=True)
class VocabularyEntry:
    unit: str
    item: str
    rank: int
    count: int
    cumulative_count: int
    coverage: float


@dataclass(frozen=True)
class QuizResult:
    unit: str
    known_rank: int
    asked: int
    total_entries: int
    total_appearances: int
    coverage: float
    stopped_early: bool = False


def load_ranked_entries(path: Path, expected_unit: str | None = None) -> List[VocabularyEntry]:
    entries: List[VocabularyEntry] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            unit = str(row.get("unit", ""))
            if expected_unit and unit != expected_unit:
                raise ValueError(f"{path}:{line_number}: expected unit {expected_unit!r}, got {unit!r}")
            entries.append(
                VocabularyEntry(
                    unit=unit,
                    item=str(row["item"]),
                    rank=int(row["rank"]),
                    count=int(row["count"]),
                    cumulative_count=int(row.get("cumulative_count", row["count"])),
                    coverage=float(row.get("coverage", 0.0)),
                )
            )

    entries.sort(key=lambda entry: entry.rank)
    return entries


def _entry_at_rank(entries: List[VocabularyEntry], rank: int) -> VocabularyEntry:
    if rank < 1 or rank > len(entries):
        raise IndexError(f"rank {rank} is outside 1..{len(entries)}")
    return entries[rank - 1]


def adaptive_rank_estimate(
    entries: List[VocabularyEntry],
    answer: AnswerFn,
    max_questions: int = 30,
) -> QuizResult:
    """Estimate the highest known rank with exponential probing plus binary refinement."""
    if not entries:
        return QuizResult("", 0, 0, 0, 0, 0.0)

    unit = entries[0].unit
    asked = 0
    stopped_early = False
    total_entries = len(entries)
    total_appearances = entries[-1].cumulative_count

    low_known = 0
    high_unknown = total_entries + 1
    probe = 1

    while probe <= total_entries and asked < max_questions:
        response = answer(_entry_at_rank(entries, probe))
        asked += 1
        if response is None:
            stopped_early = True
            break
        if response:
            low_known = probe
            probe *= 2
        else:
            high_unknown = probe
            break

    if not stopped_early and high_unknown == total_entries + 1 and asked < max_questions:
        if low_known >= total_entries:
            return QuizResult(unit, total_entries, asked, total_entries, total_appearances, 1.0)
        high_unknown = total_entries + 1

    while not stopped_early and high_unknown - low_known > 1 and asked < max_questions:
        midpoint = (low_known + high_unknown) // 2
        response = answer(_entry_at_rank(entries, midpoint))
        asked += 1
        if response is None:
            stopped_early = True
            break
        if response:
            low_known = midpoint
        else:
            high_unknown = midpoint

    coverage = entries[low_known - 1].coverage if low_known else 0.0
    return QuizResult(unit, low_known, asked, total_entries, total_appearances, coverage, stopped_early)


def _prompt_answer(label: str) -> AnswerFn:
    def ask(entry: VocabularyEntry) -> bool | None:
        while True:
            response = input(
                f"Do you know this {label}? {entry.item} "
                f"(rank {entry.rank}, {entry.count} appearances) [y/n/q]: "
            ).strip().lower()
            if response in {"y", "yes"}:
                return True
            if response in {"n", "no"}:
                return False
            if response in {"q", "quit", "exit"}:
                return None
            print("Please answer y, n, or q.")

    return ask


def _print_result(result: QuizResult, label: str) -> None:
    print()
    if result.stopped_early:
        print(f"Stopped early. Current estimate: you know about {result.known_rank} {label}.")
    else:
        print(f"Estimated known {label}: {result.known_rank}")
    print(f"Questions asked: {result.asked}")
    print(f"Frequency-list size: {result.total_entries}")
    print(f"Known-token coverage estimate: {result.coverage:.2%} of {result.total_appearances} appearances")


def _quiz_one(path: Path, unit: str, label: str, max_questions: int) -> QuizResult:
    entries = load_ranked_entries(path, expected_unit=unit)
    print(f"\n{label.title()} quiz from {path}")
    print(f"Loaded {len(entries)} ranked {label}.")
    result = adaptive_rank_estimate(entries, _prompt_answer(label), max_questions=max_questions)
    _print_result(result, label)
    return result



def learner_profile_payload(
    results: dict[str, QuizResult],
    char_path: Path,
    word_path: Path,
    created_at: str | None = None,
) -> dict:
    created_at = created_at or datetime.now(timezone.utc).astimezone().isoformat()
    estimates = {}
    known_thresholds = {}
    if "char" in results:
        result = results["char"]
        known_thresholds["char_rank"] = result.known_rank
        estimates["characters"] = {
            "estimated_known": result.known_rank,
            "questions_asked": result.asked,
            "frequency_list_size": result.total_entries,
            "known_token_coverage": result.coverage,
            "total_appearances": result.total_appearances,
        }
    if "word" in results:
        result = results["word"]
        known_thresholds["word_rank"] = result.known_rank
        estimates["words"] = {
            "estimated_known": result.known_rank,
            "questions_asked": result.asked,
            "frequency_list_size": result.total_entries,
            "known_token_coverage": result.coverage,
            "total_appearances": result.total_appearances,
        }
    return {
        "created_at": created_at,
        "source": "vocabulary_quiz",
        "language": "zh",
        "known_thresholds": known_thresholds,
        "estimates": estimates,
        "frequency_lists": {
            "characters": str(char_path),
            "words": str(word_path),
        },
    }


def write_learner_profile(
    output_path: Path,
    results: dict[str, QuizResult],
    char_path: Path,
    word_path: Path,
    created_at: str | None = None,
) -> dict:
    payload = learner_profile_payload(results, char_path, word_path, created_at=created_at)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload

def _parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Quiz yourself on ranked Chinese chars and words.")
    parser.add_argument("--chars", default="results/zh-chars.jsonl", help="Ranked character JSONL file")
    parser.add_argument("--words", default="results/zh-words.jsonl", help="Ranked word JSONL file")
    parser.add_argument("--unit", choices=("both", "char", "word"), default="both")
    parser.add_argument("--max-questions", type=int, default=30)
    parser.add_argument("--profile-output", help="Write learner profile JSON after the quiz")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = _parse_args(argv)
    max_questions = max(1, args.max_questions)

    results: dict[str, QuizResult] = {}
    if args.unit in {"both", "char"}:
        results["char"] = _quiz_one(Path(args.chars), "char", "characters", max_questions)
    if args.unit in {"both", "word"}:
        results["word"] = _quiz_one(Path(args.words), "word", "words", max_questions)
    if args.profile_output:
        write_learner_profile(Path(args.profile_output), results, Path(args.chars), Path(args.words))
        print(f"Wrote learner profile to {args.profile_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
