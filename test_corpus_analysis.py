# -*- coding: utf-8 -*-
'''
Unit testing for the corpus analysis
'''
import timeout_decorator
import unittest
import json
import mysql
from decimal import *
from ebooklib import epub
from corpus_analysis import Book, lexical_sweep, extract_fit_parameters, linear_func, analyse_directory

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
        with open("benchmarks.json", "r") as test_cases:
            benchmarks = json.load(test_cases)
            for benchmark in benchmarks['books']:
                my_book = Book(benchmark['path'].encode('utf-8'))
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

    @timeout_decorator.timeout(13)
    def test_language(self):
        '''
        Given a certain book, test language
        '''
        with open("benchmarks.json", "r") as test_cases:
            benchmarks = json.load(test_cases)
            for benchmark in benchmarks['books']:
                my_book = Book(benchmark['path'].encode('utf-8'))
                my_book.extract_text()
                my_book.detect_language()
                self.assertEqual(my_book.language, benchmark['language'].encode('utf-8'))
                print "Language for " + benchmark['title'].encode('utf-8') + " OK"

    @timeout_decorator.timeout(25)
    def test_tokens(self):
        '''
        Given a certain book, test tokens
        '''
        with open("benchmarks.json", "r") as test_cases:
            benchmarks = json.load(test_cases)
            for benchmark in benchmarks['books']:
                my_book = Book(benchmark['path'].encode('utf-8'))
                my_book.tokenize()
                self.assertEqual(my_book.word_count, benchmark['word_count'])
                self.assertEqual(my_book.unique_words, benchmark['unique_words'])
                self.assertEqual(my_book.character_count, benchmark['zh_character_count'])
                self.assertEqual(my_book.unique_characters, benchmark['unique_zh_characters'])
                print "Tokens for " + benchmark['title'].encode('utf-8') + " OK"

    @timeout_decorator.timeout(50)
    def test_sweep(self):
        '''
        Given a certain book, test sweep
        '''
        my_book = Book("test/books/hongloumeng.epub")
        my_book.tokenize()
        sweep_values = lexical_sweep(my_book.tokens)
        zh_sweep_values = lexical_sweep(my_book.zh_characters)
        print sweep_values
        print zh_sweep_values
        self.assertEqual(True, True)

    @timeout_decorator.timeout(88)
    def test_fit(self):
        '''
        Given a certain book, test fit
        '''
        with open("benchmarks.json", "r") as test_cases:
            benchmarks = json.load(test_cases)
            for benchmark in benchmarks['books']:
                my_book = Book(benchmark['path'].encode('utf-8'))
                my_book.tokenize()
                sweep_values = lexical_sweep(my_book.tokens, samples=10)
                word_curve_fit = extract_fit_parameters(linear_func, sweep_values, log_x=True, log_y=True)
                sweep_values = lexical_sweep(my_book.zh_characters, samples=10)
                zh_character_curve_fit = extract_fit_parameters(linear_func, sweep_values, log_x=True)
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

    @timeout_decorator.timeout(900)
    def test_db_writing(self):
        '''
        Write all books to database
        '''
        query_pattern = """Select title,
        author,
        slope,
        intercept,
        std_error_slope,
        std_error_intercept,
        word_count,
        unique_words,
        zhslope,
        zhintercept,
        zhstd_error_slope,
        zhstd_error_intercept,
        character_count,
        unique_characters,
        language,
        epub_type,
        subject,
        source,
        rights,
        relation,
        publisher,
        identifier,
        epub_format,
        description,
        contributor,
        date from corpus
        """
        expected_result_Xueqin = [(u'\u7d05\u6a13\u5922', u'Xueqin Cao',
                                   Decimal('0.49438'), Decimal('3.36368'),
                                   Decimal('0.01678'), Decimal('0.20654'),
                                   Decimal('662992.0'), Decimal('21113.0'),
                                   Decimal('636.13906'), Decimal('-4277.28846'),
                                   Decimal('5.36047'), Decimal('66.41762'),
                                   Decimal('724567.0'), Decimal('4263.0'),
                                   u'zh_Hant', u'',
                                   u'China -- History -- Qing dynasty, 1644-1912 -- Fiction',
                                   u'http://www.gutenberg.orgfiles/24264/24264-0.txt',
                                   u'Public domain in the USA.', u'', u'',
                                   u'http://www.gutenberg.org/ebooks/24264', u'', u'', u'',
                                   u'2008-01-12')]

        expected_result_Collodi = [(u'The Adventures of Pinocchio',
                                    u'Carlo Collodi', Decimal('0.56476'),
                                    Decimal('2.29671'), Decimal('0.01358'),
                                    Decimal('0.13704'), Decimal('52544.0'),
                                    Decimal('4945.0'), Decimal('0.00000'),
                                    Decimal('0.00000'), Decimal('0.00000'),
                                    Decimal('0.00000'), Decimal('0.0'), Decimal('0.0'),
                                    u'en', u'', u'Fairy tales',
                                    u'http://www.gutenberg.org/files/500/500-h/500-h.htm',
                                    u'Public domain in the USA.', u'', u'',
                                    u'http://www.gutenberg.org/ebooks/500', u'', u'',
                                    u'Carol Della Chiesa', u'2006-01-12')]

        expected_result_Goethe = [(u'Faust: Eine Trag\xf6die', u'Johann Wolfgang von Goethe',
                                   Decimal('0.76069'), Decimal('1.12047'), Decimal('0.00841'),
                                   Decimal('0.08245'), Decimal('36751.0'), Decimal('9293.0'),
                                   Decimal('0.00000'), Decimal('0.00000'), Decimal('0.00000'),
                                   Decimal('0.00000'), Decimal('0.0'), Decimal('0.0'), u'de',
                                   u'', u'German poetry',
                                   u'http://www.gutenberg.org/files/21000/21000-h/21000-h.htm',
                                   u'Public domain in the USA.', u'', u'',
                                   u'http://www.gutenberg.org/ebooks/21000', u'', u'', u'',
                                   u'2007-04-06')]

        expected_result_Melville = [(u'Moby Dick; Or, The Whale', u'Herman Melville',
                                     Decimal('0.62059'), Decimal('2.24768'), Decimal('0.00923'),
                                     Decimal('0.10468'), Decimal('260447.0'), Decimal('20825.0'),
                                     Decimal('0.00000'), Decimal('0.00000'), Decimal('0.00000'),
                                     Decimal('0.00000'), Decimal('0.0'), Decimal('0.0'), u'en',
                                     u'', u'Whaling -- Fiction',
                                     u'http://www.gutenberg.org/files/2701/2701-h/2701-h.htm',
                                     u'Public domain in the USA.', u'', u'',
                                     u'http://www.gutenberg.org/ebooks/2701', u'', u'', u'',
                                     u'2001-07-01')]

        expected_result_Defoe = [(u'The Life and Adventures of Robinson Crusoe',
                                  u'Daniel Defoe', Decimal('0.54545'), Decimal('2.44881'),
                                  Decimal('0.00879'), Decimal('0.09605'), Decimal('141776.0'),
                                  Decimal('7643.0'), Decimal('0.00000'), Decimal('0.00000'),
                                  Decimal('0.00000'), Decimal('0.00000'), Decimal('0.0'),
                                  Decimal('0.0'), u'en', u'', u'Shipwreck survival -- Fiction',
                                  u'http://www.gutenberg.org/files/521/521-h/521-h.htm',
                                  u'Public domain in the USA.', u'', u'',
                                  u'http://www.gutenberg.org/ebooks/521', u'', u'', u'',
                                  u'1996-05-01')]

        expected_result_Baudelaire = [(u'Les Fleurs du Mal', u'Charles Baudelaire', Decimal('0.74097'),
                                       Decimal('1.32195'), Decimal('0.00444'), Decimal('0.04306'),
                                       Decimal('31525.0'), Decimal('8177.0'), Decimal('0.00000'),
                                       Decimal('0.00000'),
                                       Decimal('0.00000'), Decimal('0.00000'), Decimal('0.0'), Decimal('0.0'),
                                       u'fr', u'', u'Poetry',
                                       u'http://www.gutenberg.org/files/6099/6099-h/6099-h.htm',
                                       u'Public domain in the USA.', u'', u'',
                                       u'http://www.gutenberg.org/ebooks/6099', u'', u'', u'',
                                       u'2004-07-01')]

        expected_result_Saavedra = [(u'Don Quijote', u'Miguel de Cervantes Saavedra', Decimal('0.64185'),
                                     Decimal('1.85563'), Decimal('0.01072'), Decimal('0.12811'),
                                     Decimal('449755.0'), Decimal('27284.0'), Decimal('0.00000'),
                                     Decimal('0.00000'), Decimal('0.00000'), Decimal('0.00000'),
                                     Decimal('0.0'), Decimal('0.0'), u'es', u'',
                                     u'Spain -- Social life and customs -- 16th century -- Fiction',
                                     u'http://www.gutenberg.org/files/2000/2000-h/2000-h.htm',
                                     u'Public domain in the USA.', u'', u'',
                                     u'http://www.gutenberg.org/ebooks/2000', u'', u'', u'',
                                     u'1999-12-01')]

        expected_result_Descartes = [(u'Meditationes de prima philosophia', u'Ren\xe9 Descartes',
                                      Decimal('0.57913'), Decimal('2.70417'), Decimal('0.02310'),
                                      Decimal('0.22193'), Decimal('28207.0'), Decimal('6085.0'),
                                      Decimal('0.00000'), Decimal('0.00000'), Decimal('0.00000'),
                                      Decimal('0.00000'), Decimal('0.0'), Decimal('0.0'), u'la', u'',
                                      u'First philosophy',
                                      u'http://www.gutenberg.org/files/23306/23306-h/23306-h.htm',
                                      u'Public domain in the USA.', u'', u'',
                                      u'http://www.gutenberg.org/ebooks/23306', u'', u'', u'',
                                      u'2007-11-03')]

        MY_DB = mysql.connector.connect(
            host="localhost",
            user="root",
            passwd="root",
            charset='utf8'
        )
        mycursor = MY_DB.cursor()
        mycursor.execute("DROP DATABASE IF EXISTS library_test;")
        my_args = ["lol", "test/", "db/library_test.db"]
        analyse_directory(my_args, "library_test")
        mycursor = MY_DB.cursor()
        mycursor.execute("USE library_test;")
        query_Xueqin = (query_pattern + ' where author="Xueqin Cao";')
        mycursor.execute(query_Xueqin)
        self.assertEqual(mycursor.fetchall(), expected_result_Xueqin)
        query_Collodi = (query_pattern + ' where author="Carlo Collodi";')
        mycursor.execute(query_Collodi)
        self.assertEqual(mycursor.fetchall(), expected_result_Collodi)
        query_Goethe = (query_pattern + ' where author="Johann Wolfgang von Goethe";')
        mycursor.execute(query_Goethe)
        self.assertEqual(mycursor.fetchall(), expected_result_Goethe)
        query_Melville = (query_pattern + ' where author="Herman Melville";')
        mycursor.execute(query_Melville)
        self.assertEqual(mycursor.fetchall(), expected_result_Melville)
        query_Defoe = (query_pattern + ' where author="Daniel Defoe";')
        mycursor.execute(query_Defoe)
        self.assertEqual(mycursor.fetchall(), expected_result_Defoe)
        query_Baudelaire = (query_pattern + ' where author="Charles Baudelaire";')
        mycursor.execute(query_Baudelaire)
        self.assertEqual(mycursor.fetchall(), expected_result_Baudelaire)
        query_Saavedra = (query_pattern + ' where author="Miguel de Cervantes Saavedra";')
        mycursor.execute(query_Saavedra)
        self.assertEqual(mycursor.fetchall(), expected_result_Saavedra)
        query_Descartes = (query_pattern + ' where author="René Descartes";')
        mycursor.execute(query_Descartes)
        self.assertEqual(mycursor.fetchall(), expected_result_Descartes)
        mycursor = MY_DB.cursor()
        mycursor.execute("drop database library_test;")

if __name__ == '__main__':
    unittest.main(failfast=True)
