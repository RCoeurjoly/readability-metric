"""Unit tests for subtitle watch ladder reports."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import subtitle_ladder as sl


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


class SubtitleLadderTest(unittest.TestCase):
    def test_build_subtitle_ladder_groups_series_and_modes(self):
        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            words = root / "words.jsonl"
            chars = root / "chars.jsonl"
            _write_jsonl(
                words,
                [
                    {"unit": "word", "item": "猫", "count": 100, "rank": 1, "cumulative_count": 100, "coverage": 0.5},
                    {"unit": "word", "item": "狗", "count": 80, "rank": 2, "cumulative_count": 180, "coverage": 0.9},
                    {"unit": "word", "item": "龙", "count": 20, "rank": 9000, "cumulative_count": 200, "coverage": 1.0},
                ],
            )
            _write_jsonl(chars, [{"unit": "char", "item": "猫", "count": 1, "rank": 1, "cumulative_count": 1, "coverage": 1.0}])
            profile = root / "learner.json"
            profile.write_text(
                json.dumps(
                    {
                        "known_thresholds": {"word_rank": 100, "character_rank": 10},
                        "frequency_lists": {"words": str(words), "characters": str(chars)},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            easy1 = root / "easy1"
            easy2 = root / "easy2"
            hard1 = root / "hard1"
            for path in (easy1, easy2, hard1):
                path.mkdir()
                _write_jsonl(path / "chars.jsonl", [{"unit": "char", "item": "猫", "count": 1, "rank": 1, "cumulative_count": 1, "coverage": 1.0}])
            _write_jsonl(easy1 / "words.jsonl", [{"unit": "word", "item": "猫", "count": 98, "rank": 1, "cumulative_count": 98, "coverage": 0.98}, {"unit": "word", "item": "龙", "count": 2, "rank": 2, "cumulative_count": 100, "coverage": 1.0}])
            _write_jsonl(easy2 / "words.jsonl", [{"unit": "word", "item": "猫", "count": 95, "rank": 1, "cumulative_count": 95, "coverage": 0.95}, {"unit": "word", "item": "龙", "count": 5, "rank": 2, "cumulative_count": 100, "coverage": 1.0}])
            _write_jsonl(hard1 / "words.jsonl", [{"unit": "word", "item": "猫", "count": 89, "rank": 1, "cumulative_count": 89, "coverage": 0.89}, {"unit": "word", "item": "龙", "count": 11, "rank": 2, "cumulative_count": 100, "coverage": 1.0}])
            manifest = root / "manifest.jsonl"
            _write_jsonl(
                manifest,
                [
                    {"included": True, "media_type": "subtitle", "book_id": "easy1", "title": "Easy - Episode 01", "book_dir": str(easy1), "collection": "Dubbed Anime", "series": "Easy", "episode_number": 1},
                    {"included": True, "media_type": "subtitle", "book_id": "easy2", "title": "Easy - Episode 02", "book_dir": str(easy2), "collection": "Dubbed Anime", "series": "Easy", "episode_number": 2},
                    {"included": True, "media_type": "subtitle", "book_id": "hard1", "title": "Hard - Episode 01", "book_dir": str(hard1), "collection": "Donghua", "series": "Hard", "episode_number": 1},
                ],
            )

            episodes, series = sl.build_subtitle_ladder(
                manifest,
                profile,
                root / "episodes.jsonl",
                root / "series.jsonl",
                min_coverage=0.95,
                target_coverage=0.98,
                top_unknown=2,
            )

            self.assertEqual(episodes[0]["book_id"], "easy1")
            self.assertEqual(episodes[0]["watch_mode"], "extensive")
            self.assertEqual(episodes[1]["watch_mode"], "ci")
            easy_series = next(row for row in series if row["series"] == "Easy")
            self.assertEqual(easy_series["contiguous_watchable_from_start"], 2)
            self.assertEqual(easy_series["contiguous_extensive_from_start"], 1)
            self.assertEqual(easy_series["recommended_start"], "Easy - Episode 01")
            hard_series = next(row for row in series if row["series"] == "Hard")
            self.assertEqual(hard_series["recommended_start"], None)
            self.assertTrue((root / "episodes.jsonl").exists())
            self.assertTrue((root / "series.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
