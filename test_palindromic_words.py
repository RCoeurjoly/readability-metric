from io import StringIO

import palindromic_words


def test_find_palindromes_ignores_case_by_default():
    words = ["Level", "book", "Radar", "python", "noon"]

    assert list(palindromic_words.find_palindromes(words)) == ["Level", "Radar", "noon"]


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
