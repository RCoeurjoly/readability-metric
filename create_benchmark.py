'''
Create benchmark based on epubs
'''

import json
import os
from corpus_analysis import analyse_book

DATA = {}
DATA['books'] = []

for dirpath, __, files in os.walk('test'):
    for ebook in files:
        try:
            my_book, word_curve_fit, zh_character_curve_fit = analyse_book(dirpath
                                                                           + '/'
                                                                           + ebook)
        except TypeError as ex:
            print ex
            continue
        DATA['books'].append({"path": dirpath + "/" + ebook,
                              "author": my_book.author,
                              "title": my_book.title,
                              "epub_type": my_book.epub_type,
                              "subject": my_book.subject,
                              "rights": my_book.rights,
                              "relation": my_book.relation,
                              "publisher": my_book.publisher,
                              "identifier": my_book.identifier,
                              "epub_format": my_book.epub_format,
                              "description": my_book.description,
                              "contributor": my_book.contributor,
                              "date": my_book.date,
                              "language": my_book.language,
                              "word_count": my_book.word_count,
                              "unique_words": my_book.unique_words,
                              "zh_character_count": my_book.character_count,
                              "unique_zh_characters": my_book.unique_characters,
                              "word_curve_fit_slope":
                              word_curve_fit['slope'],
                              "word_curve_fit_intercept":
                              word_curve_fit['intercept'],
                              "word_curve_fit_std_error_slope":
                              word_curve_fit['std_error_slope'],
                              "word_curve_fit_std_error_intercept":
                              word_curve_fit['std_error_intercept'],
                              "zh_character_curve_fit_slope":
                              zh_character_curve_fit['slope'],
                              "zh_character_curve_fit_intercept":
                              zh_character_curve_fit['intercept'],
                              "zh_character_curve_fit_std_error_slope":
                              zh_character_curve_fit['std_error_slope'],
                              "zh_character_curve_fit_std_error_intercept":
                              zh_character_curve_fit['std_error_intercept']})

with open('benchmarks.json', 'w') as outfile:
    json.dump(DATA, outfile)
