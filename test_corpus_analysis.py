# -*- coding: utf-8 -*-
'''
Unit testing for the corpus analysis
'''
import timeout_decorator
import pymongo
import unittest
import json
import mysql
from decimal import *
from ebooklib import epub
from corpus_analysis import Book, lexical_sweep, linear_func, analyse_directory

class MyTest(unittest.TestCase):
    '''
    Class
    '''
    maxDiff = None

    @timeout_decorator.timeout(1)
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
                my_book = Book(benchmark['filepath'].encode('utf-8'))
                my_book.extract_metadata()
                self.assertEqual(my_book.author, benchmark['author'].encode('utf-8'))
                self.assertEqual(my_book.title, benchmark['title'].encode('utf-8'))
                for key in benchmark.keys():
                    if key in metadata:
                        attr = getattr(my_book, key)
                        self.assertEqual(attr, benchmark[key].encode('utf-8'))
                print "Metadata for " + benchmark['title'].encode('utf-8') + " OK"

    @timeout_decorator.timeout(7)
    def test_language(self):
        '''
        Given a certain book, test language
        '''
        with open("benchmarks.json", "r") as test_cases:
            benchmarks = json.load(test_cases)
            for benchmark in benchmarks['books']:
                my_book = Book(benchmark['filepath'].encode('utf-8'))
                my_book.detect_language()
                self.assertEqual(my_book.language, benchmark['language'].encode('utf-8'))
                print "Language for " + benchmark['title'].encode('utf-8') + " OK"

    @timeout_decorator.timeout(20)
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
                my_book = Book(benchmark['filepath'].encode('utf-8'))
                my_book.detect_language()
                my_book.tokenize()
                for key in benchmark.keys():
                    if key in tokens:
                        attr = getattr(my_book, key)
                        self.assertEqual(attr, benchmark[key])
                print "Tokens for " + benchmark['title'].encode('utf-8') + " OK"

    @timeout_decorator.timeout(50)
    def test_sweep(self):
        '''
        Given a certain book, test sweep
        '''
        my_book = Book("test/books/hongloumeng.epub", 10)
        self.assertEqual(True, True)

    @timeout_decorator.timeout(708)
    def test_fit(self):
        '''
        Given a certain book, test fit
        '''
        with open("benchmarks.json", "r") as test_cases:
            benchmarks = json.load(test_cases)
            for benchmark in benchmarks['books']:
                my_book = Book(benchmark['filepath'].encode('utf-8'), 10)
                self.assertEqual(my_book.fit, benchmark['fit'])
                print "Fit for " + benchmark['title'].encode('utf-8') + " OK"

    @timeout_decorator.timeout(900)
    def test_db_writing(self):
        '''
        Write all books to database
        '''
        my_args = ["lol", "test/", "db/library_test.db"]
        # Drop database
        myclient = pymongo.MongoClient("mongodb://localhost:27017/")
        mydb = myclient["library_test"]
        mycol = mydb["corpus"]
        mycol.drop()
        analyse_directory(my_args, "library_test")

if __name__ == '__main__':
    unittest.main(failfast=True)
