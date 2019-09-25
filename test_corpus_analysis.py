# -*- coding: utf-8 -*-
'''
Unit testing for the corpus analysis
'''
import unittest
import json
from ebooklib import epub
from corpus_analysis import Book, lexical_sweep, extract_fit_parameters, linear_func

class MyTest(unittest.TestCase):
    '''
    Class
    '''
    def test_metadata(self):
        '''
        Given a certain book, test metadata
        '''
        with open("benchmarks.json", "r") as test_cases:
            benchmarks = json.load(test_cases)
            for benchmark in benchmarks['books']:
                epub_file = epub.read_epub(benchmark['path'].encode('utf-8'))
                my_book = Book(epub_file)
                self.assertEqual(my_book.author, benchmark['author'].encode('utf-8'))
                self.assertEqual(my_book.title, benchmark['title'].encode('utf-8'))
                self.assertEqual(my_book.epub_type, benchmark['epub_type'].encode('utf-8'))
                self.assertEqual(my_book.subject, benchmark['subject'].encode('utf-8'))
                self.assertEqual(my_book.rights, benchmark['rights'].encode('utf-8'))
                self.assertEqual(my_book.relation, benchmark['relation'].encode('utf-8'))
                self.assertEqual(my_book.publisher, benchmark['publisher'].encode('utf-8'))
                self.assertEqual(my_book.identifier, benchmark['identifier'].encode('utf-8'))
                self.assertEqual(my_book.epub_format, benchmark['epub_format'].encode('utf-8'))
                self.assertEqual(my_book.description, benchmark['description'].encode('utf-8'))
                self.assertEqual(my_book.contributor, benchmark['contributor'].encode('utf-8'))
                self.assertEqual(my_book.date, benchmark['date'].encode('utf-8'))
                print "Metadata for " + benchmark['title'].encode('utf-8') + " OK"

    def test_language(self):
        '''
        Given a certain book, test language
        '''
        with open("benchmarks.json", "r") as test_cases:
            benchmarks = json.load(test_cases)
            for benchmark in benchmarks['books']:
                epub_file = epub.read_epub(benchmark['path'].encode('utf-8'))
                my_book = Book(epub_file)
                my_book.extract_text(epub_file)
                my_book.detect_language()
                self.assertEqual(my_book.language, benchmark['language'].encode('utf-8'))
                print "Language for " + benchmark['title'].encode('utf-8') + " OK"

    def test_tokens(self):
        '''
        Given a certain book, test language
        '''
        with open("benchmarks.json", "r") as test_cases:
            benchmarks = json.load(test_cases)
            for benchmark in benchmarks['books']:
                epub_file = epub.read_epub(benchmark['path'].encode('utf-8'))
                my_book = Book(epub_file)
                my_book.extract_text(epub_file)
                my_book.detect_language()
                my_book.tokenize()
                self.assertEqual(my_book.word_count, benchmark['word_count'])
                self.assertEqual(my_book.unique_words, benchmark['unique_words'])
                self.assertEqual(my_book.character_count, benchmark['zh_character_count'])
                self.assertEqual(my_book.unique_characters, benchmark['unique_zh_characters'])
                print "Tokens for " + benchmark['title'].encode('utf-8') + " OK"

    def test_fit(self):
        '''
        Given a certain book, test language
        '''
        with open("benchmarks.json", "r") as test_cases:
            benchmarks = json.load(test_cases)
            for benchmark in benchmarks['books']:
                epub_file = epub.read_epub(benchmark['path'].encode('utf-8'))
                my_book = Book(epub_file)
                my_book.extract_text(epub_file)
                my_book.detect_language()
                my_book.tokenize()
                sweep_values = lexical_sweep(my_book.tokens, samples=10, log_x=True, log_y=True)
                word_curve_fit = extract_fit_parameters(linear_func, sweep_values)
                sweep_values = lexical_sweep(my_book.zh_characters, samples=10, log_x=True)
                zh_character_curve_fit = extract_fit_parameters(linear_func, sweep_values)
                self.assertEqual(float(word_curve_fit['slope']),
                                 benchmark['word_curve_fit_slope'])
                self.assertEqual(float(word_curve_fit['intercept']),
                                 benchmark['word_curve_fit_intercept'])
                self.assertEqual(float(word_curve_fit['std_error_slope']),
                                 benchmark['word_curve_fit_std_error_slope'])
                self.assertEqual(float(word_curve_fit['std_error_intercept']),
                                 benchmark['word_curve_fit_std_error_intercept'])
                self.assertEqual(float(zh_character_curve_fit['slope']),
                                 benchmark['zh_character_curve_fit_slope'])
                self.assertEqual(float(zh_character_curve_fit['intercept']),
                                 benchmark['zh_character_curve_fit_intercept'])
                self.assertEqual(float(zh_character_curve_fit['std_error_slope']),
                                 benchmark['zh_character_curve_fit_std_error_slope'])
                self.assertEqual(float(zh_character_curve_fit['std_error_intercept']),
                                 benchmark['zh_character_curve_fit_std_error_intercept'])
                print "Fit for " + benchmark['title'].encode('utf-8') + " OK"
def main():
    '''
    Main
    '''
    unittest.main()

if __name__ == "__main__":
    main()
