# -*- coding: utf-8 -*-
'''
corpus-analysis.py: readability measure for epub ebooks.
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
# Book Class
class Book(object):
    '''
    Book class
    '''
    # pylint: disable=too-many-instance-attributes
    # There is a lot of metadata but it is repetitive and non problematic.
    def __init__(self, epub_file):
        '''
        Init.
        '''
        # pylint: disable=too-many-statements
        # There is a lot of metadata but it is repetitive and non problematic.
        try:
            self.epub_type = epub_file.get_metadata('DC', 'type')[0][0].encode('utf-8')
        except IndexError:
            self.epub_type = ''
        try:
            self.subject = epub_file.get_metadata('DC', 'subject')[0][0].encode('utf-8')
        except IndexError:
            self.subject = ''
        try:
            self.source = epub_file.get_metadata('DC', 'source')[0][0].encode('utf-8')
        except IndexError:
            self.source = ''
        try:
            self.rights = epub_file.get_metadata('DC', 'rights')[0][0].encode('utf-8')
        except IndexError:
            self.rights = ''
        try:
            self.relation = epub_file.get_metadata('DC', 'relation')[0][0].encode('utf-8')
        except IndexError:
            self.relation = ''
        try:
            self.publisher = epub_file.get_metadata('DC', 'publisher')[0][0].encode('utf-8')
        except IndexError:
            self.publisher = ''
        #try:
        #    self.language = epub_file.get_metadata('DC', 'language')[0][0].encode('utf-8')
        #except IndexError:
        #    self.language = 'empty'
        try:
            self.identifier = epub_file.get_metadata('DC', 'identifier')[0][0].encode('utf-8')
        except IndexError:
            self.identifier = ''
        try:
            self.epub_format = epub_file.get_metadata('DC', 'format')[0][0].encode('utf-8')
        except IndexError:
            self.epub_format = ''
        try:
            self.description = epub_file.get_metadata('DC', 'description')[0][0].encode('utf-8')
        except IndexError:
            self.description = ''
        try:
            self.coverage = epub_file.get_metadata('DC', 'coverage')[0][0].encode('utf-8')
        except IndexError:
            self.coverage = ''
        try:
            self.contributor = epub_file.get_metadata('DC', 'contributor')[0][0].encode('utf-8')
        except IndexError:
            self.contributor = ''
        self.author = epub_file.get_metadata('DC', 'creator')[0][0].encode('utf-8')
        self.title = epub_file.get_metadata('DC', 'title')[0][0].encode('utf-8')
        try:
            self.date = epub_file.get_metadata('DC', 'date')[0][0].encode('utf-8')
        except IndexError:
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
    def extract_text(self, book):
        '''
        Extract all text from the book.
        '''
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
        self.language = Text(self.text).language.code
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

        popt, pcov = curve_fit(function, xarr, yarr)
        intercept = popt[0]
        slope = popt[1]
        perr = np.sqrt(np.diag(pcov))
        std_error_intercept = perr[0]
        std_error_slope = perr[1]
        return {'intercept': intercept,
                'slope': slope,
                'std_error_intercept': std_error_intercept,
                'std_error_slope': std_error_slope}
    return {'intercept': int(),
            'slope': int(),
            'std_error_intercept': int(),
            'std_error_slope': int()}
def lexical_sweep(text, samples=10):
    '''
    Lexical sweep.
    '''
    #Temporary value for speed. Before it was 500
    log_behaviour_start = 5000
    sweep_values = []
    log_behaviour_range = len(text) - log_behaviour_start
    log_step = log_behaviour_range/samples
    if len(text) > 10000:
        for sample_size in xrange(
                log_behaviour_start,
                log_behaviour_range,
                log_step):
            x_sample = log(len(text[0:sample_size]))
            y_sample = log(len(set(text[0:sample_size])))
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
def insert_book_db(book, word_curve_fit, zh_character_curve_fit):
    '''
    Insert data into db
    '''
    mycursor = MY_DB.cursor()
    mycursor.execute("use library;")
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
    epubType,
    subject,
    source,
    rights,
    relation,
    publisher,
    identifier,
    epubFormat,
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
def create_database():
    '''
    Create database if it doesn't exists yet.
    '''
    mycursor = MY_DB.cursor()
    mycursor.execute("CREATE DATABASE IF NOT EXISTS library;")
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
        epubFormat VARCHAR(255),
        description VARCHAR(510),
        contributor VARCHAR(255),
        date VARCHAR(255)) """)
    mycursor.execute(
        "ALTER DATABASE library CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
    mycursor.execute(
        "ALTER TABLE corpus CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
    try:
        mycursor.execute(
            "ALTER TABLE corpus ADD CONSTRAINT unique_book UNIQUE (title,author);")
    except Exception as ex:
        print ex
def is_book_in_db(title, author):
    '''
    Check if book is in database.
    '''
    mycursor = MY_DB.cursor()
    mycursor.execute("CREATE DATABASE IF NOT EXISTS library;")
    mycursor.execute("USE library;")
    query = ('SELECT * from corpus where title="' + str(title)
             + '" and author="' + str(author) + '"')
    mycursor.execute(query)
    mycursor.fetchall()
    if mycursor.rowcount == 1:
        print ("Book " + str(title)
               + ", by " + str(author)
               + " already in database. Next.")
        return True
    return False
def runbackup(hostname,
              mysql_user,
              mysql_password,
              db_loc="/media/root/terabyte/Metatron/library.sql"):
    '''
    Write sql file.
    '''
    try:
        backup = subprocess.Popen("mysqldump -h"
                                  + hostname + " -u"
                                  + mysql_user + " -p'"
                                  + mysql_password + "' --databases library > "
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
def analyze_books(argv):
    '''
    Main function: open and read all epub files in directory.
    Analyze them and populate data in database
    :param argv: command line args.
    '''
    books_analyzed = 1
    for dirpath, __, files in os.walk(str(argv[1])):
        for ebook in files:
            if ebook.endswith(".epub"):
                print "Reading ebook " + ebook + ", number  " + str(books_analyzed)
                try:
                    epub_file = epub.read_epub(dirpath + "/" + ebook)
                except Exception as ex:
                    print ex
                    continue
                print "Getting epub metadata"
                my_book = Book(epub_file)
                print "Checking if book exists in database"
                if is_book_in_db(my_book.title, my_book.author):
                    continue
                print "Extracting text from ebook"
                my_book.extract_text(epub_file)
                print "Detecting language"
                my_book.detect_language()
                print "Language detected: " + str(my_book.language)
                print "Performing tokenization"
                my_book.tokenize()
                print "Lexical sweeps"
                sweep_values = lexical_sweep(my_book.tokens, samples=10)
                word_curve_fit = extract_fit_parameters(log_func, sweep_values)
                sweep_values = lexical_sweep(my_book.zh_characters, samples=10)
                zh_character_curve_fit = extract_fit_parameters(log_log_func, sweep_values)
                sweep_values = []
                print "Writing to database"
                insert_book_db(my_book, word_curve_fit, zh_character_curve_fit)
                books_analyzed += 1
                if len(argv) == 3:
                    runbackup("localhost", "root", "root", str(argv[2]))
                else:
                    runbackup("localhost", "root", "root")
    MY_DB.close()
if __name__ == '__main__':
    analyze_books(sys.argv)