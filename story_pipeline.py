"""Story-first Chinese learning pipeline.

Builds staged Chinese reading stories from an EPUB corpus with constraints on
lexical coverage and repetition. The output is designed for zero-cognate
learners and prioritizes listening-first workflows (TTS commands included).
"""

from __future__ import annotations

import argparse
import html
import json
import random
import re
import shutil
import warnings
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Counter as TypingCounter
from typing import Dict, Iterable, List, Sequence, Tuple

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from lxml import etree

try:
    from readability_metric import (
        detect_language_code,
        is_chinese_language,
        tokenize_words,
    )
except Exception:  # pragma: no cover - lightweight fallback when dependencies are missing.
    CJK_RE = re.compile(r"[\u4e00-\u9fff]")
    WORD_RE = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*", re.UNICODE)

    def is_chinese_language(language_code):
        return bool(language_code) and language_code.lower().replace("_", "-").startswith("zh")

    def detect_language_code(text):
        return "zh" if CJK_RE.search(text or "") else "unknown"

    def tokenize_words(text, language_code=None):
        if is_chinese_language(language_code):
            return CJK_RE.findall(text or "")
        return WORD_RE.findall((text or "").casefold())

try:  # pragma: no cover - optional dependency.
    import jieba
    import jieba.posseg as jieba_posseg
except Exception:  # pragma: no cover - fallback mode without jieba.
    jieba = None
    jieba_posseg = None


DEFAULT_SUPPORT_WORDS = (
    "小明",
    "今天",
    "有",
    "在",
    "和",
    "看",
)


def _coarse_pos(raw_pos: str) -> str:
    if not raw_pos:
        return "other"
    if raw_pos.startswith("n"):
        return "noun"
    if raw_pos.startswith("v"):
        return "verb"
    if raw_pos.startswith("a"):
        return "adjective"
    if raw_pos.startswith("d"):
        return "adverb"
    if raw_pos in {"r", "rr", "rz", "rg"}:
        return "pronoun"
    if raw_pos in {"m", "q", "p"}:
        return "determiner"
    if raw_pos in {"u", "w", "c"}:
        return "function"
    return "other"


def tokenize_chinese_text(text: str) -> Tuple[List[str], TypingCounter[str]]:
    """Tokenize Chinese text and return tokens plus coarse POS counts."""

    if not text:
        return [], Counter()

    if jieba is None or jieba_posseg is None:
        return tokenize_words(text, "zh"), Counter()

    tokens: List[str] = []
    pos_counts: TypingCounter[str] = Counter()
    for word, raw_pos in jieba_posseg.cut(text):
        stripped = (word or "").strip()
        if not stripped:
            continue
        tokens.append(stripped)
        pos_counts[_coarse_pos(raw_pos)] += 1

    if tokens:
        return tokens, pos_counts

    tokens = tokenize_words(text, "zh")
    return tokens, Counter()


def _iter_epub_paths(corpus_root: Path) -> Iterable[Path]:
    for path in sorted(corpus_root.rglob("*.epub")):
        if path.is_file():
            yield path


def _read_rootfile(archive: zipfile.ZipFile) -> str | None:
    """Read the OPF rootfile path from an EPUB container."""

    try:
        with archive.open("META-INF/container.xml") as container_file:
            container = etree.parse(container_file)
            return container.findtext(
                ".//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile/@full-path"
            )
    except (KeyError, OSError, etree.XMLSyntaxError):
        return None



def _first_local_text(root, local_name):
    for element in root.iter():
        if etree.QName(element).localname == local_name:
            value = element.text
            if value:
                value = value.strip()
                if value:
                    return value
    return ""


def _find_first_child_with_local_name(parent, local_name):
    root = parent.getroot() if hasattr(parent, "getroot") else parent
    for element in root:
        if etree.QName(element).localname == local_name:
            return element
    return None


def read_epub_metadata(epub_path: Path) -> Dict[str, str]:
    """Extract minimal EPUB metadata."""

    with zipfile.ZipFile(epub_path) as archive:
        rootfile = _read_rootfile(archive)
        if not rootfile:
            candidates = [name for name in archive.namelist() if name.lower().endswith(".opf")]
            if not candidates:
                return {}
            rootfile = candidates[0]

        try:
            with archive.open(str(rootfile)) as opf_file:
                opf = etree.parse(opf_file, etree.XMLParser(recover=True))
        except (KeyError, OSError, etree.XMLSyntaxError):
            return {"_rootfile": str(rootfile)}

        return {
            "_rootfile": str(rootfile),
            "title": _first_local_text(opf, "title"),
            "language": _first_local_text(opf, "language"),
            "creator": _first_local_text(opf, "creator"),
        }


def read_epub_text(epub_path: Path) -> str:
    """Extract plain text from an EPUB using manifest/spine order."""

    with zipfile.ZipFile(epub_path) as archive:
        metadata = read_epub_metadata(epub_path)
        rootfile = metadata.get("_rootfile")
        if not rootfile:
            return ""

        root_path = Path(rootfile)
        try:
            with archive.open(rootfile) as opf_file:
                opf = etree.parse(opf_file, etree.XMLParser(recover=True))
        except (KeyError, OSError, etree.XMLSyntaxError):
            return ""

        manifest_element = _find_first_child_with_local_name(opf, "manifest")
        spine_element = _find_first_child_with_local_name(opf, "spine")

        if manifest_element is None:
            manifest = {}
        else:
            manifest = {
                item.get("id"): item
                for item in manifest_element
                if etree.QName(item).localname == "item" and item.get("id") is not None
            }

        spine_ids = []
        if spine_element is not None:
            for item in spine_element:
                if etree.QName(item).localname == "itemref" and item.get("idref"):
                    spine_ids.append(item.get("idref"))

        ordered_items = [manifest[item_id] for item_id in spine_ids if item_id in manifest]
        if not ordered_items:
            ordered_items = list(manifest.values())

        chunks: List[str] = []
        for item in ordered_items:
            href = item.get("href")
            media_type = item.get("media-type", "")
            if not href:
                continue
            if media_type not in ("application/xhtml+xml", "text/html") and not href.lower().endswith(
                (".xhtml", ".html", ".htm")
            ):
                continue
            item_path = (root_path.parent / href).as_posix()
            try:
                raw_html = archive.read(item_path)
            except KeyError:
                continue
            if not raw_html:
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
                chunks.append(BeautifulSoup(raw_html, "lxml").get_text(" "))

        return " ".join(chunks)

def build_story_templates(word: str, seed: int) -> List[str]:
    templates = [
        "小明看见{word}，并且很高兴。",
        "今天，小明拿到{word}。",
        "朋友给了小明一个{word}。",
        "小明把{word}放在桌子上。",
        "在公园里，小明看见{word}。",
    ]
    rng = random.Random(seed)
    rng.shuffle(templates)
    return [template.format(word=word) for template in templates[:2]]


@dataclass
class StoryConfig:
    target_known_ratio: float = 0.98
    min_repetitions: int = 5
    stage_word_count: int = 8
    max_sentence_count: int = 30
    support_words: Sequence[str] = DEFAULT_SUPPORT_WORDS
    language: str = "zh"


@dataclass
class StoryDraft:
    stage: int
    title: str
    text: str
    introduced_words: List[str]
    known_ratio: float
    word_count: int
    known_ratio_with_introduced: float
    max_unknown_streak: int
    repetitions_ok: bool
    target_ratio_ok: bool


def _coverage_stats(tokens: Sequence[str], allowed: Sequence[str]) -> Tuple[float, int]:
    if not tokens:
        return 0.0, 0

    allowed_set = set(allowed)
    known = 0
    max_streak = 0
    current = 0
    for token in tokens:
        if token in allowed_set:
            known += 1
            current = 0
        else:
            current += 1
            max_streak = max(max_streak, current)

    return known / len(tokens), max_streak


def generate_stage_story(
    stage: int,
    stage_words: Sequence[str],
    config: StoryConfig,
    known_words: Sequence[str],
) -> StoryDraft:
    support = list(config.support_words) + list(known_words)
    repeats: Dict[str, int] = {word: 0 for word in stage_words}
    sentences: List[str] = []

    for word in stage_words:
        for template in build_story_templates(word, hash((stage, word))):
            for _ in range(config.min_repetitions):
                sentences.append(template)
                repeats[word] += 1
            if len(sentences) >= config.max_sentence_count:
                break
        if len(sentences) >= config.max_sentence_count:
            break

    while len(sentences) < config.max_sentence_count and len(sentences) < len(stage_words) * 2:
        filler = support[len(sentences) % len(support)] if support else ""
        if filler:
            sentences.append(f"小明又看了一眼{filler}。")
        else:
            sentences.append("小明又看了一眼。")

    text = "".join(sentences)
    tokens, _ = tokenize_chinese_text(text)

    covered_without_new, max_unknown_streak = _coverage_stats(tokens, set(support))
    covered_with_new, _ = _coverage_stats(tokens, set(support) | set(stage_words))

    repetitions_ok = all(repeats[word] >= config.min_repetitions for word in stage_words)

    return StoryDraft(
        stage=stage,
        title=f"Stage {stage + 1}: {len(stage_words)} new words",
        text=text,
        introduced_words=list(stage_words),
        known_ratio=covered_without_new,
        known_ratio_with_introduced=covered_with_new,
        word_count=len(tokens),
        max_unknown_streak=max_unknown_streak,
        repetitions_ok=repetitions_ok,
        target_ratio_ok=covered_with_new >= config.target_known_ratio,
    )


def build_chinese_profile_from_epubs(corpus_root: Path, min_count: int = 2) -> List[Dict[str, int]]:
    if not corpus_root.exists():
        return []

    aggregate = Counter()

    for path in _iter_epub_paths(corpus_root):
        metadata = read_epub_metadata(path)
        language = metadata.get("language")
        if language and not is_chinese_language(language):
            continue

        text = read_epub_text(path)
        if not text or not detect_language_code(text).startswith("zh"):
            continue

        tokens, _ = tokenize_chinese_text(text)
        aggregate.update(tokens)

    if not aggregate:
        return []

    return [
        {"word": word, "count": int(count), "rank": rank}
        for rank, (word, count) in enumerate(aggregate.most_common(), start=1)
        if count >= min_count and word.strip()
    ]


def build_tts_command(text: str, out_path: Path, voice: str = "zh") -> Tuple[str, Sequence[str]]:
    """Choose a local TTS binary; return command tuple or manual path."""

    if shutil.which("espeak-ng"):
        return "espeak-ng", ("espeak-ng", "-v", voice, "-w", str(out_path), text)
    if shutil.which("espeak"):
        return "espeak", ("espeak", "-v", voice, "-w", str(out_path), text)
    return "manual", ()


@dataclass
class StoryPackage:
    html_path: Path
    text_path: Path
    metadata_path: Path
    tts_path: Path
    audio_path: Path
    draft: StoryDraft


def write_story_package(story: StoryDraft, output_dir: Path, filename: Path) -> StoryPackage:
    output_dir.mkdir(parents=True, exist_ok=True)

    html_path = output_dir / filename
    text_path = html_path.with_suffix(".txt")
    metadata_path = html_path.with_suffix(".json")
    tts_path = html_path.with_suffix(".tts.json")
    audio_path = html_path.with_suffix(".wav")

    title = html.escape(story.title)
    text = html.escape(story.text)

    text_path.write_text(story.text, encoding="utf-8")
    html_path.write_text(
        f'''<!doctype html>
<html lang="zh">
<head>
  <meta charset="utf-8" />
  <title>{title}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 760px; margin: 2rem auto; line-height: 1.6; }}
    .story {{ font-size: 1.35rem; margin-top: 1rem; }}
    .meta {{ color: #666; font-size: 0.9rem; }}
    #story-text {{ display: none; }}
    button {{ margin: 0.5rem 0; }}
  </style>
  <script>
    function toggleStory() {{
      var story = document.getElementById('story-text');
      story.style.display = story.style.display === 'none' || story.style.display === '' ? 'block' : 'none';
      var btn = document.getElementById('toggle-btn');
      btn.textContent = (btn.textContent === 'Reveal text') ? 'Hide text' : 'Reveal text';
    }}
  </script>
</head>
<body>
  <h1>{title}</h1>
  <p class="meta">Coverage (prior known): {story.known_ratio:.2%}</p>
  <p class="meta">Coverage (including new words): {story.known_ratio_with_introduced:.2%}</p>
  <p class="meta">Introduced words: {"、".join(html.escape(w) for w in story.introduced_words)}</p>
  <p class="meta">Repetition rule satisfied: {story.repetitions_ok}</p>
  <p class="meta">Target ratio reached: {story.target_ratio_ok}</p>
  <audio controls>
    <source src="{audio_path.name}" type="audio/wav" />
    Audio not embedded automatically. Use the generated command JSON.
  </audio>
  <div>
    <button id="toggle-btn" onclick="toggleStory()">Reveal text</button>
  </div>
  <div id="story-text" class="story">{text}</div>
</body>
</html>
''',
        encoding="utf-8",
    )

    command_label, command = build_tts_command(story.text, audio_path)
    tts_path.write_text(
        json.dumps(
            {
                "story": story.title,
                "command_source": command_label,
                "command": list(command),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    metadata_path.write_text(
        json.dumps(
            {
                "stage": story.stage,
                "title": story.title,
                "introduced_words": story.introduced_words,
                "known_ratio": story.known_ratio,
                "known_ratio_with_introduced": story.known_ratio_with_introduced,
                "word_count": story.word_count,
                "max_unknown_streak": story.max_unknown_streak,
                "repetitions_ok": story.repetitions_ok,
                "target_ratio_ok": story.target_ratio_ok,
                "audio_file": audio_path.name,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return StoryPackage(
        html_path=html_path,
        text_path=text_path,
        metadata_path=metadata_path,
        tts_path=tts_path,
        audio_path=audio_path,
        draft=story,
    )


def generate_curriculum(
    corpus_root: Path,
    output_dir: Path,
    stages: int = 4,
    config: StoryConfig | None = None,
    min_count: int = 2,
) -> List[StoryPackage]:
    if config is None:
        config = StoryConfig()

    output_dir.mkdir(parents=True, exist_ok=True)
    profile = build_chinese_profile_from_epubs(corpus_root, min_count=min_count)
    words = [entry.get("word") for entry in profile if entry.get("word")]
    if not words:
        return []

    known_words: List[str] = list(config.support_words)
    cursor = 0
    packages: List[StoryPackage] = []

    for stage in range(stages):
        stage_words = words[cursor : cursor + config.stage_word_count]
        if not stage_words:
            break

        draft = generate_stage_story(stage, stage_words, config, known_words)
        package = write_story_package(draft, output_dir, Path(f"stage_{stage + 1:02d}.html"))
        packages.append(package)

        known_words.extend(stage_words)
        cursor += len(stage_words)

        if not draft.target_ratio_ok:
            config = StoryConfig(
                target_known_ratio=config.target_known_ratio,
                min_repetitions=config.min_repetitions,
                stage_word_count=max(1, config.stage_word_count - 2),
                max_sentence_count=config.max_sentence_count,
                support_words=config.support_words,
                language=config.language,
            )

    manifest = [
        {
            "stage": package.draft.stage,
            "title": package.draft.title,
            "introduced_words": package.draft.introduced_words,
            "word_count": package.draft.word_count,
            "known_ratio": package.draft.known_ratio,
            "known_ratio_with_introduced": package.draft.known_ratio_with_introduced,
            "max_unknown_streak": package.draft.max_unknown_streak,
            "repetitions_ok": package.draft.repetitions_ok,
            "target_ratio_ok": package.draft.target_ratio_ok,
            "html_path": str(package.html_path),
            "text_path": str(package.text_path),
            "metadata_path": str(package.metadata_path),
            "tts_path": str(package.tts_path),
            "audio_path": str(package.audio_path),
        }
        for package in packages
    ]
    (output_dir / "curriculum.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return packages


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Generate staged Chinese stories from an EPUB corpus.")
    parser.add_argument("--corpus-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--stages", type=int, default=4)
    parser.add_argument("--stage-word-count", type=int, default=8)
    parser.add_argument("--min-repetitions", type=int, default=5)
    parser.add_argument("--target-ratio", type=float, default=0.98)
    parser.add_argument("--max-sentence-count", type=int, default=30)
    parser.add_argument("--min-word-count", type=int, default=2)
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    packages = generate_curriculum(
        Path(args.corpus_dir),
        Path(args.output_dir),
        stages=max(1, args.stages),
        config=StoryConfig(
            stage_word_count=max(1, args.stage_word_count),
            min_repetitions=max(1, args.min_repetitions),
            target_known_ratio=max(0.0, min(1.0, args.target_ratio)),
            max_sentence_count=max(1, args.max_sentence_count),
        ),
        min_count=max(1, args.min_word_count),
    )
    print(f"Generated {len(packages)} staged stories")
    return 0 if packages else 1


if __name__ == "__main__":
    raise SystemExit(main())
