"""Unit tests for book recommendation scoring."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import book_recommendations as br


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


class BookRecommendationsTest(unittest.TestCase):
    def test_profile_coverage_counts_unknown_tokens_and_items(self):
        with TemporaryDirectory() as tempdir:
            profile = Path(tempdir) / "words.jsonl"
            _write_jsonl(
                profile,
                [
                    {"unit": "word", "item": "猫", "count": 8, "rank": 1, "cumulative_count": 8, "coverage": 0.8},
                    {"unit": "word", "item": "狗", "count": 2, "rank": 2, "cumulative_count": 10, "coverage": 1.0},
                ],
            )

            stats = br.profile_coverage(profile, {"猫": 1, "狗": 9000}, known_rank=100, top_unknown=5)

        self.assertEqual(stats["total_tokens"], 10)
        self.assertEqual(stats["known_tokens"], 8)
        self.assertEqual(stats["unknown_tokens"], 2)
        self.assertEqual(stats["distinct_unknown"], 1)
        self.assertEqual(stats["top_unknown"][0]["item"], "狗")

    def test_build_recommendations_orders_by_word_coverage(self):
        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            chars = root / "chars.jsonl"
            words = root / "words.jsonl"
            _write_jsonl(chars, [{"unit": "char", "item": "猫", "count": 10, "rank": 1, "cumulative_count": 10, "coverage": 1.0}])
            _write_jsonl(
                words,
                [
                    {"unit": "word", "item": "小猫", "count": 10, "rank": 1, "cumulative_count": 10, "coverage": 0.5},
                    {"unit": "word", "item": "小狗", "count": 10, "rank": 9000, "cumulative_count": 20, "coverage": 1.0},
                ],
            )
            profile = root / "learner.json"
            profile.write_text(
                json.dumps(
                    {
                        "known_thresholds": {"char_rank": 10, "word_rank": 100},
                        "frequency_lists": {"characters": str(chars), "words": str(words)},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            easy = root / "easy"
            hard = root / "hard"
            _write_jsonl(easy / "chars.jsonl", [{"unit": "char", "item": "猫", "count": 1, "rank": 1, "cumulative_count": 1, "coverage": 1.0}])
            _write_jsonl(easy / "words.jsonl", [{"unit": "word", "item": "小猫", "count": 9, "rank": 1, "cumulative_count": 9, "coverage": 1.0}])
            _write_jsonl(hard / "chars.jsonl", [{"unit": "char", "item": "猫", "count": 1, "rank": 1, "cumulative_count": 1, "coverage": 1.0}])
            _write_jsonl(
                hard / "words.jsonl",
                [
                    {"unit": "word", "item": "小猫", "count": 1, "rank": 1, "cumulative_count": 1, "coverage": 0.1},
                    {"unit": "word", "item": "小狗", "count": 9, "rank": 2, "cumulative_count": 10, "coverage": 1.0},
                ],
            )
            manifest = root / "manifest.jsonl"
            _write_jsonl(
                manifest,
                [
                    {"included": True, "book_id": "hard", "title": "Hard", "book_dir": str(hard)},
                    {"included": True, "book_id": "easy", "title": "Easy", "book_dir": str(easy)},
                ],
            )
            output = root / "recommendations.jsonl"

            rows = br.build_recommendations(manifest, profile, output, top_unknown=3)

            self.assertEqual(rows[0]["book_id"], "easy")
            self.assertEqual(rows[0]["known_word_coverage"], 1.0)
            self.assertEqual(rows[1]["unknown_word_tokens"], 9)
            self.assertTrue(output.exists())

    def test_build_recommendations_can_filter_ranked_word_only_books(self):
        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            words = root / "words.jsonl"
            _write_jsonl(
                words,
                [
                    {"unit": "word", "item": "chat", "count": 10, "rank": 1, "cumulative_count": 10, "coverage": 0.5},
                    {"unit": "word", "item": "chien", "count": 10, "rank": 9000, "cumulative_count": 20, "coverage": 1.0},
                ],
            )
            profile = root / "learner.json"
            profile.write_text(
                json.dumps(
                    {
                        "known_thresholds": {"word_rank": 100},
                        "frequency_lists": {"words": str(words)},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            ranked = root / "ranked"
            unranked = root / "unranked"
            _write_jsonl(ranked / "words.jsonl", [{"unit": "word", "item": "chat", "count": 9, "rank": 1, "cumulative_count": 9, "coverage": 1.0}])
            _write_jsonl(unranked / "words.jsonl", [{"unit": "word", "item": "chien", "count": 9, "rank": 1, "cumulative_count": 9, "coverage": 1.0}])
            manifest = root / "manifest.jsonl"
            _write_jsonl(
                manifest,
                [
                    {"included": True, "book_id": "ranked", "title": "Ranked", "book_dir": str(ranked)},
                    {"included": True, "book_id": "unranked", "title": "Unranked", "book_dir": str(unranked)},
                ],
            )
            tags = root / "tags.jsonl"
            _write_jsonl(tags, [{"book_id": "ranked", "tags": [{"list_id": "canon", "rank": 1}]}])

            rows = br.build_recommendations(
                manifest,
                profile,
                root / "recommendations.jsonl",
                tags_path=tags,
                ranked_only=True,
            )

            self.assertEqual([row["book_id"] for row in rows], ["ranked"])
            self.assertEqual(rows[0]["known_char_coverage"], None)
            self.assertEqual(rows[0]["known_word_coverage"], 1.0)
            self.assertEqual(rows[0]["tags"][0]["list_id"], "canon")



if __name__ == "__main__":
    unittest.main()
