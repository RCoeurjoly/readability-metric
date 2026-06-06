"""Tests for subtitle title metadata hydration."""

from __future__ import annotations

import csv
import gzip
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import subtitle_metadata as sm


def _write_gzip_tsv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with gzip.open(path, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class SubtitleMetadataTest(unittest.TestCase):
    def test_parse_bare_opus_path_as_imdb_title_id(self):
        info = sm.parse_opus_subtitle_path("OpenSubtitles/xml/zh_CN/1906/566/1952983785.xml")

        self.assertEqual(info.year_dir, "1906")
        self.assertEqual(info.title_tconst, "tt0000566")
        self.assertIsNone(info.parent_tconst)
        self.assertEqual(info.subtitle_file_id, "1952983785")

    def test_parse_series_episode_opus_path(self):
        info = sm.parse_opus_subtitle_path("OpenSubtitles/xml/zh_CN/2023/29347204_9529546_3_1/abc.xml")

        self.assertEqual(info.title_tconst, "tt29347204")
        self.assertEqual(info.parent_tconst, "tt9529546")
        self.assertEqual(info.season, 3)
        self.assertEqual(info.episode, 1)

    def test_hydrate_manifest_and_recommendations(self):
        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            manifest = root / "manifest.jsonl"
            manifest.write_text(
                json.dumps(
                    {
                        "book_id": "movie",
                        "filepath": "OpenSubtitles/xml/zh_CN/1906/566/1952983785.xml",
                        "title": "1952983785",
                    },
                    ensure_ascii=False,
                )
                + "\n"
                + json.dumps(
                    {
                        "book_id": "episode",
                        "filepath": "OpenSubtitles/xml/zh_CN/2023/29347204_9529546_3_1/abc.xml",
                        "title": "abc",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            basics = root / "title.basics.tsv.gz"
            episodes = root / "title.episode.tsv.gz"
            akas = root / "title.akas.tsv.gz"
            _write_gzip_tsv(
                basics,
                [
                    {
                        "tconst": "tt0000566",
                        "titleType": "movie",
                        "primaryTitle": "The Story of the Kelly Gang",
                        "originalTitle": "The Story of the Kelly Gang",
                        "isAdult": "0",
                        "startYear": "1906",
                        "endYear": r"\N",
                        "runtimeMinutes": "70",
                        "genres": "Biography,Crime,Drama",
                    },
                    {
                        "tconst": "tt9529546",
                        "titleType": "tvSeries",
                        "primaryTitle": "The Show",
                        "originalTitle": "The Show",
                        "isAdult": "0",
                        "startYear": "2020",
                        "endYear": r"\N",
                        "runtimeMinutes": r"\N",
                        "genres": "Drama",
                    },
                    {
                        "tconst": "tt1234567",
                        "titleType": "tvEpisode",
                        "primaryTitle": "Pilot",
                        "originalTitle": "Pilot",
                        "isAdult": "0",
                        "startYear": "2023",
                        "endYear": r"\N",
                        "runtimeMinutes": "42",
                        "genres": "Drama",
                    },
                ],
                ["tconst", "titleType", "primaryTitle", "originalTitle", "isAdult", "startYear", "endYear", "runtimeMinutes", "genres"],
            )
            _write_gzip_tsv(
                episodes,
                [
                    {
                        "tconst": "tt1234567",
                        "parentTconst": "tt9529546",
                        "seasonNumber": "3",
                        "episodeNumber": "1",
                    }
                ],
                ["tconst", "parentTconst", "seasonNumber", "episodeNumber"],
            )
            _write_gzip_tsv(
                akas,
                [
                    {
                        "titleId": "tt0000566",
                        "ordering": "1",
                        "title": "The Story of the Kelly Gang",
                        "region": "AU",
                        "language": r"\N",
                        "types": "original",
                        "attributes": r"\N",
                        "isOriginalTitle": "1",
                    },
                    {
                        "titleId": "tt9529546",
                        "ordering": "1",
                        "title": "The Show",
                        "region": "CN",
                        "language": r"\N",
                        "types": "imdbDisplay",
                        "attributes": r"\N",
                        "isOriginalTitle": "1",
                    },
                ],
                ["titleId", "ordering", "title", "region", "language", "types", "attributes", "isOriginalTitle"],
            )
            output_manifest = root / "manifest.hydrated.jsonl"

            total, matched = sm.hydrate_manifest_rows(manifest, output_manifest, basics, episodes, akas)

            self.assertEqual((total, matched), (2, 2))
            rows = [json.loads(line) for line in output_manifest.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(rows[0]["title"], "The Story of the Kelly Gang (1906)")
            self.assertEqual(rows[1]["title"], "The Show (2020) S03E01 - Pilot")
            self.assertEqual(rows[1]["imdb_episode_tconst"], "tt1234567")
            self.assertFalse(rows[0]["chinese_audio_likely"])
            self.assertTrue(rows[1]["chinese_audio_likely"])
            self.assertEqual(rows[1]["imdb_aka_regions"], ["CN"])

            recs = root / "recommendations.jsonl"
            recs.write_text(json.dumps({"book_id": "episode", "title": "abc"}) + "\n", encoding="utf-8")
            output_recs = root / "recommendations.hydrated.jsonl"
            rec_total, rec_matched = sm.hydrate_recommendations(output_manifest, recs, output_recs)

            self.assertEqual((rec_total, rec_matched), (1, 1))
            rec_row = json.loads(output_recs.read_text(encoding="utf-8"))
            self.assertEqual(rec_row["title"], "The Show (2020) S03E01 - Pilot")
            self.assertTrue(rec_row["chinese_audio_likely"])

            audio_output = root / "audio.jsonl"
            total_audio, kept_audio = sm.filter_chinese_audio_likely(output_recs, audio_output)
            self.assertEqual((total_audio, kept_audio), (1, 1))


if __name__ == "__main__":
    unittest.main()
