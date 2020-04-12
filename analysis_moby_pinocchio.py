import sys
from corpus_analysis import Book

moby_dick = Book("test/moby.epub")
pinocchio = Book("test/pinocchio.epub")
# moby_dick.extract_text()
# pinocchio.extract_text()
# moby_dick.tokenize()
# pinocchio.tokenize()
print (moby_dick.word_count,
       moby_dick.unique_words,
       pinocchio.word_count,
       pinocchio.unique_words,
       pinocchio.title)
print('\n'.join(sys.path))


def dummy_function():
    moby_dick = Book("test/moby.epub")
    pinocchio = Book("test/pinocchio.epub")
    moby_dick.extract_text()
    pinocchio.extract_text()
    moby_dick.tokenize()
    pinocchio.tokenize()
    return (moby_dick.word_count,
            moby_dick.unique_words,
            pinocchio.word_count,
            pinocchio.unique_words)


dummy_function()
