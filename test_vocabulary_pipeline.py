"""Unit tests for vocabulary extraction pipeline."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import vocabulary_pipeline as vp


def _build_fake_epub(path: Path, title: str, language: str, text: str) -> None:
    container_xml = """<?xml version='1.0' encoding='utf-8'?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/book.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""
    opf_xml = f"""<?xml version='1.0' encoding='utf-8'?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="uid">
  <metadata>
    <dc:title xmlns:dc="http://purl.org/dc/elements/1.1/">{title}</dc:title>
    <dc:creator xmlns:dc="http://purl.org/dc/elements/1.1/">作者</dc:creator>
    <dc:language xmlns:dc="http://purl.org/dc/elements/1.1/">{language}</dc:language>
  </metadata>
  <manifest>
    <item id="chapter1" href="chapter1.xhtml" media-type="application/xhtml+xml" />
  </manifest>
  <spine>
    <itemref idref="chapter1" />
  </spine>
</package>"""
    chapter_xml = f"<html><body><p>{text}</p></body></html>"

    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("META-INF/container.xml", container_xml)
        archive.writestr("OEBPS/book.opf", opf_xml)
        archive.writestr("OEBPS/chapter1.xhtml", chapter_xml)


class VocabularyPipelineTest(unittest.TestCase):
    def test_build_chinese_profile_builds_ranked_lists(self):
        with TemporaryDirectory() as tempdir:
            corpus_root = Path(tempdir) / "corpus"
            corpus_root.mkdir()
            _build_fake_epub(corpus_root / "a.epub", "测试", "zh", "小猫小猫看电视")
            _build_fake_epub(corpus_root / "b.epub", "测试", "zh", "小猫喜欢看电视")

            profiles = vp.build_chinese_frequency_profiles(
                corpus_root,
                min_count=1,
                include_chars=True,
                include_words=True,
            )

        self.assertEqual(profiles["chars"][0]["count"], 2)
        self.assertGreaterEqual(profiles["chars"][1]["count"], profiles["chars"][2]["count"])
        self.assertTrue(all(item["unit"] == "char" for item in profiles["chars"]))
        self.assertTrue(profiles["words"])

    def test_build_chinese_profile_with_pos(self):
        with TemporaryDirectory() as tempdir:
            corpus_root = Path(tempdir) / "corpus"
            corpus_root.mkdir()
            _build_fake_epub(corpus_root / "book.epub", "测试", "zh", "小猫喜欢看电视")

            with patch(
                "vocabulary_pipeline._word_tokens_with_pos",
                return_value=[("小猫", "n"), ("喜欢", "v"), ("看", "v"), ("电视", "n")],
            ), patch("readability_metric.detect_language_code", return_value="zh"):
                profiles = vp.build_chinese_frequency_profiles(corpus_root, with_pos=True, min_count=1)

        by_word = {entry["item"]: entry for entry in profiles["words"]}
        self.assertEqual(by_word["小猫"]["pos_primary"], "noun")
        self.assertEqual(by_word["喜欢"]["pos_primary"], "verb")
        self.assertEqual(by_word["喜欢"]["pos_distribution"][0]["pos"], "verb")

    def test_write_jsonl_outputs_profile(self):
        with TemporaryDirectory() as tempdir:
            corpus_root = Path(tempdir) / "corpus"
            output = Path(tempdir) / "output"
            corpus_root.mkdir()
            _build_fake_epub(corpus_root / "book.epub", "测试", "zh", "小猫小猫吃饭")

            output_chars = output / "chars.jsonl"
            output_words = output / "words.jsonl"

            with patch(
                "vocabulary_pipeline._word_tokens",
                return_value=["小猫", "小猫", "吃饭"],
            ):
                result = vp.main(
                    [
                        "--corpus-dir",
                        str(corpus_root),
                        "--output-chars",
                        str(output_chars),
                        "--output-words",
                        str(output_words),
                        "--min-count",
                        "1",
                    ]
                )

            self.assertEqual(result, 0)
            char_rows = [json.loads(line) for line in output_chars.read_text(encoding="utf-8").splitlines()]
            word_rows = [json.loads(line) for line in output_words.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(char_rows[0]["unit"], "char")
            self.assertEqual(word_rows[0]["item"], "小猫")
            self.assertEqual(word_rows[0]["count"], 2)


if __name__ == "__main__":
    unittest.main()
