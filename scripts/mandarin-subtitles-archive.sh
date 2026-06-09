#!/usr/bin/env bash
set -euo pipefail

archive_root="${1:-${MANDARIN_SUBTITLES_ARCHIVE:-$HOME/Downloads/Mandarin-Subtitles-Archive}}"
jobs="${JOBS:-4}"

python3 -m subtitle_pipeline \
  --source mandarin-subtitles-archive \
  --corpus-root "$archive_root" \
  --output-items results/zh-mandarin-subtitles-archive \
  --output-chars results/zh-mandarin-subtitles-archive-chars.jsonl \
  --output-words results/zh-mandarin-subtitles-archive-words.jsonl \
  --min-count 1 \
  --min-cjk-chars 20 \
  --jobs "$jobs" \
  --verbose
