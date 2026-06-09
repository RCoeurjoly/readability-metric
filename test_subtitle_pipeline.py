"""Tests for subtitle vocabulary extraction."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import book_recommendations as br
import subtitle_pipeline as sp


def _xml(sentences: list[str]) -> bytes:
    body = "".join(f"<s id=\"{index}\">{sentence}</s>" for index, sentence in enumerate(sentences, start=1))
    return f"<?xml version=\"1.0\" encoding=\"utf-8\"?><doc>{body}</doc>".encode("utf-8")


class SubtitlePipelineTest(unittest.TestCase):
    def test_extract_opus_xml_text_cleans_subtitle_artifacts(self):
        data = _xml([
            "1",
            "00:00:01,000 --> 00:00:02,000",
            "<i>小猫</i>{\\an8}喜欢电视",
            "[字幕]",
            "再见\\N朋友",
        ])

        self.assertEqual(sp.extract_opus_xml_text(data), "小猫 喜欢电视\n再见 朋友")

    def test_normalize_chinese_text_uses_opencc(self):
        class FakeOpenCC:
            def __init__(self, mode: str):
                self.mode = mode

            def convert(self, text: str) -> str:
                assert self.mode == "t2s"
                return text.replace("貓", "猫").replace("電視", "电视")

        with patch.dict("sys.modules", {"opencc": type("FakeModule", (), {"OpenCC": FakeOpenCC})}):
            self.assertEqual(sp.normalize_chinese_text("貓看電視"), "猫看电视")

    def test_build_subtitle_profiles_and_recommendations_are_compatible(self):
        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            archive = root / "zh_CN.zip"
            with zipfile.ZipFile(archive, "w") as zip_file:
                zip_file.writestr("movie/easy.xml", _xml(["小猫小猫看电视"]))
                zip_file.writestr("movie/hard.xml", _xml(["小狗研究量子力学"]))

            output_items = root / "items"
            output_chars = root / "subtitle-chars.jsonl"
            output_words = root / "subtitle-words.jsonl"

            with patch("subtitle_pipeline.normalize_chinese_text", side_effect=lambda text, mode="t2s": text), patch(
                "vocabulary_pipeline._word_tokens",
                side_effect=[
                    ["小猫", "小猫", "看", "电视"],
                    ["小狗", "研究", "量子力学"],
                ],
            ):
                included_dirs = sp.build_subtitle_frequency_profiles(
                    archive,
                    output_items,
                    output_chars,
                    output_words,
                    min_count=1,
                    min_cjk_chars=1,
                )

            self.assertEqual(len(included_dirs), 2)
            manifest_rows = [json.loads(line) for line in (output_items / "manifest.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(manifest_rows), 2)
            self.assertTrue(all(row["included"] for row in manifest_rows))
            self.assertTrue(all(row["media_type"] == "subtitle" for row in manifest_rows))
            self.assertTrue((Path(manifest_rows[0]["book_dir"]) / "chars.jsonl").exists())
            self.assertTrue((Path(manifest_rows[0]["book_dir"]) / "words.jsonl").exists())

            profile = root / "learner.json"
            profile.write_text(
                json.dumps(
                    {
                        "known_thresholds": {"word_rank": 2},
                        "frequency_lists": {"words": str(output_words), "characters": str(output_chars)},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            rows = br.build_recommendations(output_items / "manifest.jsonl", profile, root / "recs.jsonl", top_unknown=2)

            self.assertEqual(len(rows), 2)
            self.assertGreaterEqual(rows[0]["known_word_coverage"], rows[1]["known_word_coverage"])
            self.assertEqual(rows[0]["media_type"], "subtitle")

    def test_build_local_subtitle_profiles_from_srt_folder(self):
        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            corpus = root / "archive"
            episode_dir = corpus / "Dubbed Anime" / "Friendly Show"
            episode_dir.mkdir(parents=True)
            (episode_dir / "Friendly Show - 01.srt").write_text(
                "1\n00:00:01,000 --> 00:00:02,000\n繁體貓看電視\n\n"
                "2\n00:00:03,000 --> 00:00:04,000\n朋友再見\n",
                encoding="utf-8",
            )

            output_items = root / "items"
            output_chars = root / "chars.jsonl"
            output_words = root / "words.jsonl"

            with patch("subtitle_pipeline.normalize_chinese_text", side_effect=lambda text, mode="t2s": text.replace("繁體", "繁体").replace("貓", "猫").replace("電視", "电视").replace("見", "见")):
                included_dirs = sp.build_local_subtitle_frequency_profiles(
                    corpus,
                    output_items,
                    output_chars,
                    output_words,
                    min_count=1,
                    min_cjk_chars=1,
                )

            self.assertEqual(len(included_dirs), 1)
            manifest_rows = [json.loads(line) for line in (output_items / "manifest.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(manifest_rows[0]["collection"], "Dubbed Anime")
            self.assertEqual(manifest_rows[0]["series"], "Friendly Show")
            self.assertEqual(manifest_rows[0]["title"], "Friendly Show - Friendly Show - 01")
            self.assertEqual(manifest_rows[0]["media_type"], "subtitle")
            chars = [json.loads(line)["item"] for line in (included_dirs[0] / "chars.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertIn("猫", chars)

    def test_mandarin_archive_filters_non_mandarin_tracks_and_records_metadata(self):
        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            corpus = root / "Mandarin-Subtitles-Archive"
            mainland_dir = corpus / "Dubbed Anime" / "Kaguya-sama" / "Mainland"
            japanese_dir = corpus / "Dubbed Anime" / "Kaguya-sama" / "jpn"
            cantonese_dir = corpus / "Dubbed Anime" / "Kaguya-sama" / "Cantonese"
            mainland_dir.mkdir(parents=True)
            japanese_dir.mkdir(parents=True)
            cantonese_dir.mkdir(parents=True)
            (mainland_dir / "Kaguya-sama.S01E01.CHS.srt").write_text(
                "1\n00:00:01,000 --> 00:00:02,000\n学生会今天开会\n",
                encoding="utf-8",
            )
            (japanese_dir / "Kaguya-sama.S01E01.JPN.srt").write_text(
                "1\n00:00:01,000 --> 00:00:02,000\n生徒会\n",
                encoding="utf-8",
            )
            (cantonese_dir / "Kaguya-sama.S01E01.Cantonese.srt").write_text(
                "1\n00:00:01,000 --> 00:00:02,000\n學生會今日開會\n",
                encoding="utf-8",
            )

            paths = list(sp.iter_mandarin_archive_subtitle_paths(corpus))
            self.assertEqual([path.name for path in paths], ["Kaguya-sama.S01E01.CHS.srt"])

            output_items = root / "items"
            output_chars = root / "chars.jsonl"
            output_words = root / "words.jsonl"

            with patch("subtitle_pipeline.normalize_chinese_text", side_effect=lambda text, mode="t2s": text):
                included_dirs = sp.build_mandarin_archive_frequency_profiles(
                    corpus,
                    output_items,
                    output_chars,
                    output_words,
                    min_count=1,
                    min_cjk_chars=1,
                )

            self.assertEqual(len(included_dirs), 1)
            manifest_rows = [json.loads(line) for line in (output_items / "manifest.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(manifest_rows[0]["source"], "Furretar/Mandarin-Subtitles-Archive")
            self.assertEqual(manifest_rows[0]["collection"], "Dubbed Anime")
            self.assertEqual(manifest_rows[0]["series"], "Kaguya sama")
            self.assertEqual(manifest_rows[0]["season"], None)
            self.assertEqual(manifest_rows[0]["episode_number"], 1)
            self.assertEqual(manifest_rows[0]["subtitle_variant"], "mainland")




if __name__ == "__main__":
    unittest.main()
