# -*- coding: utf-8 -*-
'''
corpus-analysis.py: readability metric for epub ebooks.
Version 1.0
Copyright (C) 2019  Roland Coeurjoly <rolandcoeurjoly@gmail.com>
'''
# Imports
import unicodedata
import sys
import os
import math
import subprocess
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
from scipy.optimize import curve_fit
from scipy import log as log
import numpy as np
import mysql.connector
from polyglot.text import Text
# Constants
PRINTABLE = {
    #'Cc',
    'Cf',
    'Cn',
    'Co',
    'Cs',
    'LC',
    'Ll',
    'Lm',
    'Lo',
    'Lt',
    'Lu',
    'Mc',
    'Me',
    'Mn',
    'Nd',
    'Nl',
    'No',
    'Pc',
    'Pd',
    'Pe',
    'Pf',
    'Pi',
    'Po',
    'Ps',
    'Sc',
    'Sk',
    'Sm',
    'So',
    'Zl',
    'Zp',
    'Zs'}
# Classes
## Book Class
class Book(object):
    '''
    Book class
    '''
    # pylint: disable=too-many-instance-attributes
    # There is a lot of metadata but it is repetitive and non problematic.
    def __init__(self, epub_filename):
        '''
        Init.
        '''
        # pylint: disable=too-many-statements
        # There is a lot of metadata but it is repetitive and non problematic.
        self.filename = epub_filename
        epub_file = epub.read_epub(epub_filename)
        try:
            self.epub_type = epub_file.get_metadata('DC', 'type')[0][0].encode('utf-8')
        except (IndexError, AttributeError):
            self.epub_type = ''
        try:
            self.subject = epub_file.get_metadata('DC', 'subject')[0][0].encode('utf-8')
        except (IndexError, AttributeError):
            self.subject = ''
        try:
            self.source = epub_file.get_metadata('DC', 'source')[0][0].encode('utf-8')
        except (IndexError, AttributeError):
            self.source = ''
        try:
            self.rights = epub_file.get_metadata('DC', 'rights')[0][0].encode('utf-8')
        except (IndexError, AttributeError):
            self.rights = ''
        try:
            self.relation = epub_file.get_metadata('DC', 'relation')[0][0].encode('utf-8')
        except (IndexError, AttributeError):
            self.relation = ''
        try:
            self.publisher = epub_file.get_metadata('DC', 'publisher')[0][0].encode('utf-8')
        except (IndexError, AttributeError):
            self.publisher = ''
        #try:
        #    self.language = epub_file.get_metadata('DC', 'language')[0][0].encode('utf-8')
        #except (IndexError, AttributeError):
        #    self.language = 'empty'
        try:
            self.identifier = epub_file.get_metadata('DC', 'identifier')[0][0].encode('utf-8')
        except (IndexError, AttributeError):
            self.identifier = ''
        try:
            self.epub_format = epub_file.get_metadata('DC', 'format')[0][0].encode('utf-8')
        except (IndexError, AttributeError):
            self.epub_format = ''
        try:
            self.description = epub_file.get_metadata('DC', 'description')[0][0].encode('utf-8')
        except (IndexError, AttributeError):
            self.description = ''
        try:
            self.coverage = epub_file.get_metadata('DC', 'coverage')[0][0].encode('utf-8')
        except (IndexError, AttributeError):
            self.coverage = ''
        try:
            self.contributor = epub_file.get_metadata('DC', 'contributor')[0][0].encode('utf-8')
        except (IndexError, AttributeError):
            self.contributor = ''
        self.author = epub_file.get_metadata('DC', 'creator')[0][0].encode('utf-8')
        self.title = epub_file.get_metadata('DC', 'title')[0][0].encode('utf-8')
        try:
            self.date = epub_file.get_metadata('DC', 'date')[0][0].encode('utf-8')
        except (IndexError, AttributeError):
            self.date = ''
        self.language = str()
        self.zh_characters = str()
        self.character_count = int()
        self.unique_characters = int()
        self.tokens = str()
        self.word_count = int()
        self.unique_words = int()
        self.text = str()
    def tokenize(self):
        '''
        Tokenization.
        '''
        if not self.tokens:
            self.extract_text()
        if self.language == 'zh' or self.language == 'zh_Hant':
            self.zh_characters = ''.join(character for character in self.text
                                         if u'\u4e00' <= character <= u'\u9fff')
            self.character_count = len(self.zh_characters)
            self.unique_characters = len(set(self.zh_characters))
        else:
            self.zh_characters = str()
            self.character_count = int()
            self.unique_characters = int()
        self.tokens = Text(self.text).words
        self.word_count = len(self.tokens)
        self.unique_words = len(set(self.tokens))
    def extract_text(self):
        '''
        Extract all text from the book.
        '''
        book = epub.read_epub(self.filename)
        cleantext = ""
        html_filtered = ""
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                raw_html = item.get_content()
                html_filtered += BeautifulSoup(raw_html, "lxml").text
        cleantext = clean_non_printable(html_filtered)
        self.text = cleantext
    def detect_language(self):
        '''
        We don't trust the epub metadata regarding language tags
        so we do our own language detection
        '''
        if not self.tokens:
            self.extract_text()
        self.language = Text(self.text).language.code
    def release_text(self):
        '''
        Release text.
        '''
        self.text = str()
    def release_zh_characters(self):
        '''
        Release Chinese characters.
        '''
        self.zh_characters = str()
    def release_tokens(self):
        '''
        Release tokens.
        '''
        self.tokens = str()
# Functions
def clean_non_printable(text):
    '''
    Remove all non printable characters from string.
    '''
    return ''.join(character for character in text if unicodedata.category(character) in PRINTABLE)
## Curve fitting functions
def extract_fit_parameters(function, sweep_values):
    '''
    Curve fit.
    '''
    if sweep_values:
        array = list(zip(*sweep_values))
        xarr = array[0]
        yarr = array[1]
        initial_a = 0
        initial_b = 0
        popt, pcov = curve_fit(function, xarr, yarr, (initial_a, initial_b))
        slope = popt[0]
        intercept = popt[1]
        perr = np.sqrt(np.diag(pcov))
        std_error_slope = perr[0]
        std_error_intercept = perr[1]
        return {'intercept': intercept,
                'slope': slope,
                'std_error_intercept': std_error_intercept,
                'std_error_slope': std_error_slope}
    return {'intercept': int(),
            'slope': int(),
            'std_error_intercept': int(),
            'std_error_slope': int()}
def lexical_sweep(text, samples=10, log_x=False, log_y=False):
    '''
    Lexical sweep.
    '''
    log_behaviour_start = 5000
    sweep_values = []
    log_behaviour_range = len(text) - log_behaviour_start
    log_step = log_behaviour_range/(samples - 1)
    if len(text) > 10000 and samples >= 2:
        for sample_size in xrange(
                log_behaviour_start,
                len(text) - 1,
                log_step):
            if log_x:
                x_sample = log(sample_size)
            else:
                x_sample = sample_size
            if log_y:
                y_sample = log(len(set(text[0:sample_size])))
            else:
                y_sample = len(set(text[0:sample_size]))
            sweep_values.append([x_sample, y_sample])
        return sweep_values
    return False
def linear_func(variable, slope, y_intercept):
    '''
    Linear model.
    '''
    return slope*variable + y_intercept

def log_func(variable, coefficient, x_intercept):
    '''
    Logarithmic model.
    '''
    return coefficient*log(variable) + x_intercept

def log_log_func(variable, coefficient, intercept):
    '''
    Log-log model.
    '''
    return math.e**(coefficient*log(variable) + intercept)
## Database functions
MY_DB = mysql.connector.connect(
    host="localhost",
    user="root",
    passwd="root",
    charset='utf8'
)
def insert_book_db(book, word_curve_fit, zh_character_curve_fit, db="library"):
    '''
    Insert data into db
    '''
    mycursor = MY_DB.cursor()
    mycursor.execute("use " + db + ";")
    sql = """INSERT IGNORE corpus (title,
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
    date
    ) VALUES (%s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s)"""
    val = (book.title,
           book.author,
           float(word_curve_fit['slope']),
           float(word_curve_fit['intercept']),
           float(word_curve_fit['std_error_slope']),
           float(word_curve_fit['std_error_intercept']),
           float(book.word_count),
           float(book.unique_words),
           float(zh_character_curve_fit['slope']),
           float(zh_character_curve_fit['intercept']),
           float(zh_character_curve_fit['std_error_slope']),
           float(zh_character_curve_fit['std_error_intercept']),
           float(book.character_count),
           float(book.unique_characters),
           book.language,
           book.epub_type,
           book.subject,
           book.source,
           book.rights,
           book.relation,
           book.publisher,
           book.identifier,
           book.epub_format,
           book.description,
           book.contributor,
           book.date)
    mycursor.execute(sql, val)
    MY_DB.commit()
    print("1 record inserted, ID:", mycursor.lastrowid)
def create_database(db="library"):
    '''
    Create database if it doesn't exists yet.
    '''
    mycursor = MY_DB.cursor()
    mycursor.execute("CREATE DATABASE IF NOT EXISTS " + db + ";")
    mycursor.execute(
        "ALTER DATABASE " + db + " CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
    mycursor.execute("USE " + db + ";")
    mycursor.execute(
        """ CREATE TABLE IF NOT EXISTS corpus (id INT AUTO_INCREMENT PRIMARY KEY,
        title VARCHAR(255),
        author VARCHAR(255),
        slope DECIMAL(10,5),
        intercept DECIMAL(10,5),
        std_error_slope DECIMAL(10,5),
        std_error_intercept DECIMAL(10,5),
        word_count DECIMAL(20,1),
        unique_words DECIMAL(20,1),
        zhslope DECIMAL(10,5),
        zhintercept DECIMAL(10,5),
        zhstd_error_slope DECIMAL(10,5),
        zhstd_error_intercept DECIMAL(10,5),
        character_count DECIMAL(15,1),
        unique_characters DECIMAL(15,1),
        language VARCHAR(255),
        epub_type VARCHAR(255),
        subject VARCHAR(255),
        source VARCHAR(255),
        rights VARCHAR(255),
        relation VARCHAR(255),
        publisher VARCHAR(255),
        identifier VARCHAR(255),
        epub_format VARCHAR(255),
        description VARCHAR(510),
        contributor VARCHAR(255),
        date VARCHAR(255)) """)
    mycursor.execute(
        "ALTER TABLE corpus CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
    try:
        mycursor.execute(
            "ALTER TABLE corpus ADD CONSTRAINT unique_book UNIQUE (title,author);")
    except Exception as ex:
        print ex
def is_book_in_db(my_book, db):
    '''
    Check if book is in database.
    '''
    mycursor = MY_DB.cursor()
    mycursor.execute("USE " + db + ";")
    query = ('SELECT * from corpus where title="' + str(my_book.title)
             + '" and author="' + str(my_book.author) + '"')
    mycursor.execute(query)
    mycursor.fetchall()
    if mycursor.rowcount == 1:
        print ("Book " + str(my_book.title)
               + ", by " + str(my_book.author)
               + " already in database. Next.")
        return True
    return False
def runbackup(hostname,
              mysql_user,
              mysql_password,
              db,
              db_loc="test/db/library_test.db"):
    '''
    Write sql file.
    '''
    try:
        backup = subprocess.Popen("mysqldump -h"
                                  + hostname + " -u"
                                  + mysql_user + " -p'"
                                  + mysql_password + "' --databases "
                                  + db + " > "
                                  + db_loc, shell=True)
        # Wait for completion
        backup.communicate()
        if backup.returncode != 0:
            sys.exit(1)
        else:
            print("Backup done for", hostname)
    except Exception as ex:
        # Check for errors
        print ex
        print("Backup failed for", hostname)
# Main function
def analyse_book(ebook, samples=10):
    '''
    Analyse individual book.
    You can insert into db or into json afterwards
    '''
    try:
        my_book = Book(ebook)
        my_book.extract_text()
        my_book.detect_language()
        my_book.tokenize()
        sweep_values = lexical_sweep(my_book.tokens,
                                     samples,
                                     log_x=True,
                                     log_y=True)
        word_curve_fit = extract_fit_parameters(linear_func, sweep_values)
        sweep_values = lexical_sweep(my_book.zh_characters,
                                     samples,
                                     log_x=True,
                                     log_y=False)
        zh_character_curve_fit = extract_fit_parameters(linear_func, sweep_values)

        return my_book, word_curve_fit, zh_character_curve_fit
    except TypeError as ex:
        print ex
        return False

def analyse_directory(argv, db):
    '''
    Main function: open and read all epub files in directory.
    Analyze them and populate data in database
    :param argv: command line args.
    '''
    if db == "library":
        db_file = "/media/root/terabyte/Metatron/library.sql"
    else:
        db_file = "test/db/library.db"
    create_database(db)
    books_analyzed = 0
    corpus_path = str(argv[1])
    for dirpath, __, files in os.walk(corpus_path):
        for ebook in files:
            if ebook.endswith(".epub"):
                try:
                    my_book = Book(dirpath + '/' + ebook)
                    print "Checking if book exists in database"
                    if is_book_in_db(my_book, db):
                        continue
                    print "Reading ebook " + ebook + ", number  " + str(books_analyzed)
                    result = analyse_book(dirpath + '/' + ebook)
                    if not result:
                        continue
                    my_book, word_curve_fit, zh_char_curve_fit = result[0], result[1], result[2]
                    print "Writing to database"
                    insert_book_db(my_book, word_curve_fit, zh_char_curve_fit, db)
                    books_analyzed += 1
                    runbackup("localhost", "root", "root", db, db_file)
                except (KeyError, TypeError) as ex:
                    print ex
                    continue
    MY_DB.close()

if __name__ == '__main__':
    analyse_directory(sys.argv, "library")
