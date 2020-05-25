# -*- coding: utf-8 -*-
'''
Unit testing for the corpus analysis
'''
import pymongo
import unittest
import json
from ebooklib import epub
from corpus_analysis import Book, lexical_sweep, linear_func, analyse_directory

class MyTest(unittest.TestCase):
    '''
    Class
    '''
    maxDiff = None

    def test_metadata(self):
        '''
        Given a certain book, test metadata
        '''
        metadata = ['epub_type',
                    'subject',
                    'source',
                    'rights',
                    'relation',
                    'publisher',
                    'identifier',
                    'epub_format',
                    'description',
                    'coverage',
                    'contributor',
                    'date']

        with open("benchmarks.json", "r") as test_cases:
            benchmarks = json.load(test_cases)
            for benchmark in benchmarks['books']:
                my_book = Book(benchmark['filepath'])
                self.assertEqual(my_book.creator, benchmark['creator'])
                self.assertEqual(my_book.title, benchmark['title'])
                for key in benchmark.keys():
                    if key in metadata:
                        attr = getattr(my_book, key)
                        self.assertEqual(attr, benchmark[key])
                print("Metadata for " + benchmark['title'] + " OK")

    def test_language(self):
        '''
        Given a certain book, test language
        '''
        with open("benchmarks.json", "r") as test_cases:
            benchmarks = json.load(test_cases)
            for benchmark in benchmarks['books']:
                my_book = Book(benchmark['filepath'])
                my_book.detect_language()
                self.assertEqual(my_book.language, benchmark['language'])
                print("Language for " + benchmark['title'] + " OK")

    def test_tokens(self):
        '''
        Given a certain book, test tokens
        '''
        tokens = ['word_count',
                  'unique_words',
                  'character_count',
                  'unique_characters']

        with open("benchmarks.json", "r") as test_cases:
            benchmarks = json.load(test_cases)
            for benchmark in benchmarks['books']:
                my_book = Book(benchmark['filepath'])
                my_book.detect_language()
                my_book.tokenize()
                for key in benchmark.keys():
                    if key in tokens:
                        attr = getattr(my_book, key)
                        self.assertEqual(attr, benchmark[key])
                print("Tokens for " + benchmark['title'] + " OK")

    def test_fit(self):
        '''
        Given a certain book, test fit
        '''
        with open("benchmarks.json", "r") as test_cases:
            benchmarks = json.load(test_cases)
            for benchmark in benchmarks['books']:
                my_book = Book(benchmark['filepath'], samples=10)
                self.assertEqual(my_book.words_fit, benchmark['words_fit'])
                print("Fit for " + benchmark['title'] + " OK")

    def test_db_writing(self):
        '''
        Write all books to database
        '''
        my_args = ["assets/", "library_test", "dump/my_json.json"]
        # Drop database
        myclient = pymongo.MongoClient("mongodb://localhost:27017/")
        mydb = myclient["library_test"]
        mycol = mydb["corpus"]
        mycol.drop()
        analyse_directory(my_args[0], my_args[1], my_args[2])
        with open("benchmarks.json", "r") as test_cases:
            benchmarks = json.load(test_cases)
            for benchmark in benchmarks['books']:
                for result in mycol.find({}, {"_id":False}):
                    if benchmark['title'] == result['title']:
                        self.assertEqual(result, benchmark)
                        print("Database write for " + benchmark['title'] + " OK")

if __name__ == '__main__':
    unittest.main(failfast=True)
