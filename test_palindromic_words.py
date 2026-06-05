from io import StringIO

import palindromic_words


def test_find_palindromes_ignores_case_by_default():
    words = ["Level", "book", "Radar", "python", "noon"]

    assert list(palindromic_words.find_palindromes(words)) == ["Level", "Radar", "noon"]


def test_find_palindromes_filters_two_character_repeats():
    words = ["看看", "是不是", "太太", "上海自来水来自海上"]

    assert list(palindromic_words.find_palindromes(words)) == ["是不是", "上海自来水来自海上"]


def test_find_palindromes_can_filter_unique_words():
    words = ["Level", "level", "noon", "Noon"]

    assert list(palindromic_words.find_palindromes(words, unique=True)) == ["Level", "noon"]


def test_find_palindromes_honors_case_sensitive_mode():
    words = ["Level", "level", "noon"]

    assert list(palindromic_words.find_palindromes(words, case_sensitive=True)) == [
        "level",
        "noon",
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
