"""Unit tests for canonical book tagging."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import book_tags as bt


class BookTagsTest(unittest.TestCase):
    def test_normalize_handles_basic_simplified_traditional_variants(self):
        self.assertEqual(bt.normalize("《骆驼祥子》"), bt.normalize("駱駝祥子"))
        self.assertEqual(bt.normalize("张爱玲"), bt.normalize("張愛玲"))

    def test_match_books_uses_author_for_duplicate_canonical_titles(self):
        entries = bt.canonical_entries()
        manifest = [
            {
                "book_id": "zhang-xiguo",
                "title": "棋王",
                "creator": "張系國",
                "filename": "qiwang.epub",
                "book_dir": "books/qiwang",
            }
        ]

        matches = bt.match_books(manifest, entries)

        qiwang = [row for row in matches if row["title"] == "棋王"]
        self.assertEqual(len(qiwang), 1)
        self.assertEqual(qiwang[0]["tags"][0]["rank"], 79)
        self.assertEqual(qiwang[0]["tags"][0]["match_type"], "title_creator_exact")

    def test_unique_title_fallback_allows_pen_name_or_metadata_mismatch(self):
        entries = bt.canonical_entries()
        manifest = [
            {
                "book_id": "guanchang",
                "title": "官場現形記",
                "creator": "李寶嘉",
                "filename": "book.epub",
                "book_dir": "books/book",
            }
        ]

        matches = bt.match_books(manifest, entries)

        self.assertEqual(matches[0]["tags"][0]["rank"], 13)
        self.assertEqual(matches[0]["tags"][0]["match_type"], "unique_title_exact")


    def test_load_ranking_json_entries_from_downloaded_shape(self):
        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            (root / "sample.json").write_text(
                json.dumps(
                    {
                        "榜单名称": "测试榜",
                        "URL": "https://example.invalid",
                        "条目": [
                            {"rank_position": None, "书名": "測試書", "作者": "作者", "出版社": "出版社", "出版年": 2024}
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            entries = bt.load_ranking_json_entries(root)

        self.assertEqual(entries[0]["list_id"], "sample")
        self.assertEqual(entries[0]["list_name"], "测试榜")
        self.assertEqual(entries[0]["rank"], 1)
        self.assertEqual(entries[0]["title"], "測試書")


if __name__ == "__main__":
    unittest.main()
