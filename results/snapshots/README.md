# Corpus Word Frequency Snapshots

This directory stores compact, committed snapshots of corpus-wide ranked word
frequency results.

The original generated files live under `results/*.jsonl` and are ignored by
git because they are large. Snapshots use gzip-compressed CSV with these fields:

```text
rank,item,count,cumulative_count,coverage
```

Restore a JSONL file with:

```sh
python3 scripts/word_result_snapshot.py import results/snapshots/fr-words.csv.gz results/fr-words.jsonl
python3 scripts/word_result_snapshot.py import results/snapshots/zh-words.csv.gz results/zh-words.jsonl
```
