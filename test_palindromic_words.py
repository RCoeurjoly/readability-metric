from io import StringIO

import palindromic_words


def test_find_mirror_pairs_detects_reversed_words_once():
    words = ["家人", "book", "人家", "看看", "人家"]

    assert list(palindromic_words.find_mirror_pairs(words)) == [("家人", "人家")]


def test_find_mirror_pairs_can_filter_by_max_length():
    words = ["家人", "人家", "上海", "海上", "不得不"]

    assert list(palindromic_words.find_mirror_pairs(words, max_length=2)) == [
        ("家人", "人家"),
        ("上海", "海上"),
    ]


def test_find_mirror_pairs_honors_case_sensitive_mode():
    words = ["Ab", "ba", "aB"]

    assert list(palindromic_words.find_mirror_pairs(words, case_sensitive=True)) == [
        ("ba", "aB")
    ]


def test_read_words_splits_whitespace():
    stream = StringIO("level book\nradar\tcivic")

    assert list(palindromic_words.read_words(stream)) == ["level", "book", "radar", "civic"]


def test_read_words_extracts_items_from_jsonl():
    stream = StringIO('{"item": "上海自来水来自海上", "count": 3}\n{"item": "book"}\n')

    assert list(palindromic_words.read_words(stream)) == ["上海自来水来自海上", "book"]


def test_read_words_can_use_custom_jsonl_field():
    stream = StringIO('{"word": "radar"}\n')

    assert list(palindromic_words.read_words(stream, jsonl_field="word")) == ["radar"]
