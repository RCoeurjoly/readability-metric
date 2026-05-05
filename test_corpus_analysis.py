# -*- coding: utf-8 -*-
"""Unit tests for EPUB readability analysis."""

import json
import tempfile
import unittest
from pathlib import Path

from readability_metric import Book, analyse_epub_file, analyse_paths_to_jsonl, lexical_sweep


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
        json.dumps(my_book.__dict__)

    def test_lexical_sweep_small_text(self):
        self.assertFalse(lexical_sweep(["word"] * 100, samples=10))

    def test_single_epub_record(self):
        record = analyse_epub_file(str(ASSETS / "pinocchio.epub"), samples=10)
        self.assertEqual(record["status"], "ok")
        self.assertEqual(record["title"], "The Adventures of Pinocchio")
        self.assertIn("words_fit", record)

    def test_jsonl_batch_output(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "books.jsonl"
            summary = analyse_paths_to_jsonl([ASSETS], output, samples=0, resume=False)
            self.assertEqual(summary["errors"], 0)
            records = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(summary["written"], len(records))
            self.assertGreaterEqual(len(records), 8)


if __name__ == "__main__":
    unittest.main(failfast=True)
