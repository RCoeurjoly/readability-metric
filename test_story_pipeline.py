# -*- coding: utf-8 -*-
"""Unit tests for Chinese story pipeline."""

import json
import zipfile
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from unittest.mock import patch

import story_pipeline as sp


class StoryPipelineTest(TestCase):
    def test_tokenize_chinese_text_fallback_without_jieba(self):
        original_jieba = sp.jieba
        original_jieba_posseg = sp.jieba_posseg
        sp.jieba = None
        sp.jieba_posseg = None
        try:
            tokens, pos = sp.tokenize_chinese_text("今天天气很好")
        finally:
            sp.jieba = original_jieba
            sp.jieba_posseg = original_jieba_posseg

        self.assertEqual(pos, Counter())
        self.assertEqual(tokens, ["今", "天", "天", "气", "很", "好"])

    def test_generate_stage_story_repetition_and_metadata(self):
        config = sp.StoryConfig(min_repetitions=2, max_sentence_count=12)
        draft = sp.generate_stage_story(0, ["猫", "狗"], config, known_words=[])

        self.assertEqual(draft.introduced_words, ["猫", "狗"])
        self.assertEqual(draft.stage, 0)
        self.assertTrue(draft.repetitions_ok)
        self.assertGreater(draft.word_count, 0)
        self.assertLessEqual(draft.max_unknown_streak, draft.word_count)

    def test_write_story_package_outputs_artifacts(self):
        story = sp.StoryDraft(
            stage=0,
            title="Stage 1",
            text="小明看见猫。",
            introduced_words=["猫"],
            known_ratio=0.75,
            known_ratio_with_introduced=0.80,
            word_count=4,
            max_unknown_streak=1,
            repetitions_ok=True,
            target_ratio_ok=False,
        )

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            package = sp.write_story_package(story, output_dir, Path("stage_01.html"))

            self.assertTrue(package.html_path.exists())
            self.assertTrue(package.text_path.exists())
            self.assertTrue(package.metadata_path.exists())
            self.assertTrue(package.tts_path.exists())

            html = package.html_path.read_text(encoding="utf-8")
            self.assertIn("Reveal text", html)

            metadata = json.loads(package.metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["title"], "Stage 1")
            self.assertEqual(metadata["audio_file"], package.audio_path.name)

            tts = json.loads(package.tts_path.read_text(encoding="utf-8"))
            self.assertIn("command_source", tts)

    def test_generate_curriculum_creates_manifest_from_epubs(self):
        def build_fake_epub(path: Path, text: str) -> None:
            container_xml = """<?xml version='1.0' encoding='utf-8'?>
<container version=\"1.0\" xmlns=\"urn:oasis:names:tc:opendocument:xmlns:container\">
  <rootfiles>
    <rootfile full-path=\"OEBPS/book.opf\" media-type=\"application/oebps-package+xml\"/>
  </rootfiles>
</container>"""
            opf_xml = """<?xml version='1.0' encoding='utf-8'?>
<package xmlns=\"http://www.idpf.org/2007/opf\" version=\"2.0\" unique-identifier=\"uid\">
  <metadata>
    <dc:title xmlns:dc=\"http://purl.org/dc/elements/1.1/\">测试书</dc:title>
    <dc:creator xmlns:dc=\"http://purl.org/dc/elements/1.1/\">作者</dc:creator>
    <dc:language xmlns:dc=\"http://purl.org/dc/elements/1.1/\">zh</dc:language>
  </metadata>
  <manifest>
    <item id=\"chapter1\" href=\"chapter1.xhtml\" media-type=\"application/xhtml+xml\" />
  </manifest>
  <spine>
    <itemref idref=\"chapter1\" />
  </spine>
</package>"""
            chapter_xml = f"<html><body><p>{text}</p></body></html>"

            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("META-INF/container.xml", container_xml)
                archive.writestr("OEBPS/book.opf", opf_xml)
                archive.writestr("OEBPS/chapter1.xhtml", chapter_xml)

        with TemporaryDirectory() as tmpdir:
            corpus_root = Path(tmpdir) / "corpus"
            output_dir = Path(tmpdir) / "stories"
            corpus_root.mkdir()

            build_fake_epub(corpus_root / "book.epub", "小猫在草地上跑。小猫喜欢草和树。")

            with patch("story_pipeline.tokenize_chinese_text", return_value=(["猫", "狗", "树", "树", "树", "猫", "草", "草"], Counter())):
                with patch("story_pipeline.detect_language_code", return_value="zh"):
                    packages = sp.generate_curriculum(
                        corpus_root,
                        output_dir,
                        stages=1,
                        config=sp.StoryConfig(stage_word_count=2, min_repetitions=1, max_sentence_count=8),
                        min_count=1,
                    )

            self.assertEqual(len(packages), 1)
            manifest = json.loads((output_dir / "curriculum.json").read_text(encoding="utf-8"))
            self.assertEqual(len(manifest), 1)
            self.assertEqual(manifest[0]["stage"], 0)
            self.assertGreater(len(manifest[0]["introduced_words"]), 0)


if __name__ == "__main__":
    main()
