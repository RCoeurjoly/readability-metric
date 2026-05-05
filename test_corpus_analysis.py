# -*- coding: utf-8 -*-
"""Unit tests for EPUB readability analysis."""

import json
import tempfile
import unittest
from pathlib import Path

from readability_metric import (
    PREDICTION_WORD_COUNT,
    Book,
    add_language_percentiles_to_records,
    analyse_epub_file,
    analyse_paths_to_jsonl,
    lexical_sweep,
    normalize_language_code,
    predicted_unique_words,
)


ASSETS = Path("assets")


class CorpusAnalysisTest(unittest.TestCase):
    maxDiff = None

    def test_metadata_extraction(self):
        my_book = Book(str(ASSETS / "moby.epub"))
        self.assertEqual(my_book.title, "Moby Dick; Or, The Whale")
        self.assertEqual(my_book.creator, "Herman Melville")
        self.assertEqual(my_book.original_language, "en")

    def test_language_and_tokens(self):
        my_book = Book(str(ASSETS / "moby.epub"))
        my_book.detect_language()
        my_book.tokenize()
        self.assertEqual(my_book.language, "en")
        self.assertGreater(my_book.word_count, 10000)
        self.assertGreater(my_book.unique_words, 1000)
        self.assertLessEqual(my_book.unique_words, my_book.word_count)

    def test_fit_parameters_are_json_ready(self):
        my_book = Book(str(ASSETS / "moby.epub"), samples=10)
        self.assertIn("slope", my_book.words_fit)
        expected = predicted_unique_words(my_book.words_fit, PREDICTION_WORD_COUNT)
        self.assertAlmostEqual(my_book.predicted_unique_words_20k, expected)
        json.dumps(my_book.__dict__)

    def test_lexical_sweep_small_text(self):
        self.assertFalse(lexical_sweep(["word"] * 100, samples=10))

    def test_language_code_normalization(self):
        self.assertEqual(normalize_language_code("pt-BR"), "pt")
        self.assertEqual(normalize_language_code("por"), "pt")
        self.assertEqual(normalize_language_code("cat"), "ca")
        self.assertEqual(normalize_language_code("zh_Hant"), "zh")
        self.assertIsNone(normalize_language_code("unknown"))

    def test_single_epub_record(self):
        record = analyse_epub_file(str(ASSETS / "pinocchio.epub"), samples=10)
        self.assertEqual(record["status"], "ok")
        self.assertEqual(record["title"], "The Adventures of Pinocchio")
        self.assertIn("words_fit", record)
        self.assertIn("predicted_unique_words_20k", record)

    def test_jsonl_batch_output(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "books.jsonl"
            summary = analyse_paths_to_jsonl([ASSETS], output, samples=0, resume=False)
            self.assertEqual(summary["errors"], 0)
            records = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(summary["written"], len(records))
            self.assertGreaterEqual(len(records), 8)

    def test_language_percentiles_are_ease_oriented(self):
        records = [
            {"status": "ok", "language": "ca", "predicted_unique_words_20k": 1000},
            {"status": "ok", "language": "ca", "predicted_unique_words_20k": 2000},
            {"status": "ok", "language": "ca", "predicted_unique_words_20k": 3000},
            {"status": "ok", "language": "en", "predicted_unique_words_20k": 5000},
        ]
        add_language_percentiles_to_records(records)
        self.assertEqual(records[0]["lexical_ease_percentile_by_language"], 100.0)
        self.assertEqual(records[1]["lexical_ease_percentile_by_language"], 50.0)
        self.assertEqual(records[2]["lexical_ease_percentile_by_language"], 0.0)
        self.assertEqual(records[3]["lexical_ease_percentile_by_language"], 100.0)
        self.assertEqual(records[0]["lexical_ease_language_sample_size"], 3)


if __name__ == "__main__":
    unittest.main(failfast=True)
