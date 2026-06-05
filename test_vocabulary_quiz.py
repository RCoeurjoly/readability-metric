"""Unit tests for adaptive vocabulary quiz."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import vocabulary_quiz as vq


def _entries(count: int, unit: str = "char") -> list[vq.VocabularyEntry]:
    return [
        vq.VocabularyEntry(
            unit=unit,
            item=f"item-{rank}",
            rank=rank,
            count=count - rank + 1,
            cumulative_count=rank,
            coverage=rank / count,
        )
        for rank in range(1, count + 1)
    ]


class VocabularyQuizTest(unittest.TestCase):
    def test_adaptive_rank_estimate_refines_threshold(self):
        entries = _entries(100)
        asked_ranks: list[int] = []

        def answer(entry: vq.VocabularyEntry) -> bool:
            asked_ranks.append(entry.rank)
            return entry.rank <= 37

        result = vq.adaptive_rank_estimate(entries, answer, max_questions=30)

        self.assertEqual(result.known_rank, 37)
        self.assertLessEqual(result.asked, 14)
        self.assertIn(64, asked_ranks)
        self.assertEqual(result.coverage, 0.37)

    def test_adaptive_rank_estimate_handles_no_first_item(self):
        entries = _entries(100)

        result = vq.adaptive_rank_estimate(entries, lambda entry: False, max_questions=30)

        self.assertEqual(result.known_rank, 0)
        self.assertEqual(result.coverage, 0.0)

    def test_adaptive_rank_estimate_handles_quit(self):
        entries = _entries(100)
        answers = iter([True, True, None])

        result = vq.adaptive_rank_estimate(entries, lambda entry: next(answers), max_questions=30)

        self.assertTrue(result.stopped_early)
        self.assertEqual(result.known_rank, 2)

    def test_load_ranked_entries_validates_unit(self):
        with TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "chars.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "unit": "char",
                        "item": "你",
                        "rank": 1,
                        "count": 10,
                        "cumulative_count": 10,
                        "coverage": 1.0,
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            rows = vq.load_ranked_entries(path, expected_unit="char")

        self.assertEqual(rows[0].item, "你")
        self.assertEqual(rows[0].rank, 1)


    def test_write_learner_profile_outputs_latest_results(self):
        with TemporaryDirectory() as tempdir:
            output = Path(tempdir) / "profile.json"
            results = {
                "char": vq.QuizResult("char", 12, 5, 100, 1000, 0.5),
                "word": vq.QuizResult("word", 34, 6, 200, 2000, 0.25),
            }

            payload = vq.write_learner_profile(
                output,
                results,
                Path("chars.jsonl"),
                Path("words.jsonl"),
                created_at="2026-06-03T00:00:00+00:00",
            )

            saved = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload, saved)
            self.assertEqual(saved["known_thresholds"]["char_rank"], 12)
            self.assertEqual(saved["known_thresholds"]["word_rank"], 34)
            self.assertEqual(saved["estimates"]["words"]["known_token_coverage"], 0.25)


if __name__ == "__main__":
    unittest.main()
