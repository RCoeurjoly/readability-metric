# -*- coding: utf-8 -*-
'''
corpus-analysis.py: readability metric for epub ebooks.
Version 1.0
Copyright (C) 2019  Roland Coeurjoly <rolandcoeurjoly@gmail.com>
'''
# Imports
import lxml
import unicodedata
import icu
import sys
import os
import math
import subprocess
import ebooklib
import pymongo
from ebooklib import epub
from bs4 import BeautifulSoup
from scipy.optimize import curve_fit
from scipy import log as log
import numpy as np
import mysql.connector
from polyglot.text import Text
from nltk import FreqDist
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
## Curve fitting functions
def lexical_sweep_map(start, stop, step, text):
    return map(lambda x: [x, len(set(text[0:x]))], xrange(start,
                                                          stop,
                                                          step))

def lexical_sweep_list_comprehension(start, stop, step, text):
     return [[x, len(set(text[0:x]))] for x in xrange(start,
                                                      stop,
                                                      step)]

def lexical_sweep_for_loop(start, stop, step, text):
    return map(lambda x: [x, len(set(text[0:x]))], xrange(start,
                                                          stop,
                                                          step))

def lexical_sweep(text, slicing_function=lexical_sweep_map, samples=10):
    '''
    Lexical sweep.
    '''
    try:
        log_behaviour_start = 5000
        sweep_values = []
        log_behaviour_range = len(text) - log_behaviour_start
        log_step = log_behaviour_range/(samples - 1)
        if len(text) > 10000 and samples >= 2:
            sweep_values = slicing_function(log_behaviour_start,
                                            len(text) + 1,
                                            log_step,
                                            text)
            return sweep_values
        return False
    except AttributeError as ex:
        print ex
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
# Classes
## Book Class
class Book(object):
    '''
    Book class
    '''
    # pylint: disable=too-many-instance-attributes
    # There is a lot of metadata but it is repetitive and non problematic.
    def __init__(self, epub_filename, slicing_function=lexical_sweep_map, samples=0):
        '''
        Init.
        '''
        # pylint: disable=too-many-statements
        # There is a lot of metadata but it is repetitive and non problematic.
        try:
            print "Extracting metadata"
            self.extract_metadata(epub_filename)
            if samples:
                print "Extracting text"
                self.extract_text()
                print "Detecting language"
                self.detect_language()
                print "Tokenization"
                self.tokenize()
                print "Calculating word sweep values"
                sweep_values = lexical_sweep(self.tokens, slicing_function, samples)
                self.fit = []
                print "Word fit"
                self.extract_fit_parameters("words", sweep_values)
                if self.language == "zh" or self.language == "zh_Hant":
                    print "Calculating character sweep values"
                    sweep_values = lexical_sweep(self.zh_characters, slicing_function, samples)
                    print "Character fit"
                    self.extract_fit_parameters("characters", sweep_values)
                self.delete_heavy_attributes()
        except AttributeError:
            pass
    def extract_metadata(self, epub_filename):
        '''
        Extraction of metadata
        '''
        # pylint: disable=too-many-statements
        # There is a lot of metadata but it is repetitive and non problematic.
        self.filepath = epub_filename
        epub_file = epub.read_epub(self.filepath)
        try:
            self.author = epub_file.get_metadata('DC', 'creator')[0][0].encode('utf-8')
        except (IndexError, AttributeError):
            pass
        try:
            self.title = epub_file.get_metadata('DC', 'title')[0][0].encode('utf-8')
        except (IndexError, AttributeError):
            pass
        try:
            self.epub_type = epub_file.get_metadata('DC', 'type')[0][0].encode('utf-8')
        except (IndexError, AttributeError):
            pass
        try:
            self.subject = epub_file.get_metadata('DC', 'subject')[0][0].encode('utf-8')
        except (IndexError, AttributeError):
            pass
        try:
            self.source = epub_file.get_metadata('DC', 'source')[0][0].encode('utf-8')
        except (IndexError, AttributeError):
            pass
        try:
            self.rights = epub_file.get_metadata('DC', 'rights')[0][0].encode('utf-8')
        except (IndexError, AttributeError):
            pass
        try:
            self.relation = epub_file.get_metadata('DC', 'relation')[0][0].encode('utf-8')
        except (IndexError, AttributeError):
            pass
        try:
            self.publisher = epub_file.get_metadata('DC', 'publisher')[0][0].encode('utf-8')
        except (IndexError, AttributeError):
            pass
        #try:
        #    self.language = epub_file.get_metadata('DC', 'language')[0][0].encode('utf-8')
        #except (IndexError, AttributeError):
        #    pass
        try:
            self.identifier = epub_file.get_metadata('DC', 'identifier')[0][0].encode('utf-8')
        except (IndexError, AttributeError):
            pass
        try:
            self.epub_format = epub_file.get_metadata('DC', 'format')[0][0].encode('utf-8')
        except (IndexError, AttributeError):
            pass
        try:
            self.description = epub_file.get_metadata('DC', 'description')[0][0].encode('utf-8')
        except (IndexError, AttributeError):
            pass
        try:
            self.coverage = epub_file.get_metadata('DC', 'coverage')[0][0].encode('utf-8')
        except (IndexError, AttributeError):
            pass
        try:
            self.contributor = epub_file.get_metadata('DC', 'contributor')[0][0].encode('utf-8')
        except (IndexError, AttributeError):
            pass
        try:
            self.date = epub_file.get_metadata('DC', 'date')[0][0].encode('utf-8')
        except (IndexError, AttributeError):
            pass
    def tokenize(self):
        '''
        Tokenization.
        '''
        try:
            if self.language == 'zh' or self.language == 'zh_Hant':
                self.zh_characters = ''.join(character for character in self.text
                                             if u'\u4e00' <= character <= u'\u9fff')
                self.character_count = len(self.zh_characters)
                self.unique_characters = len(set(self.zh_characters))
            self.tokens = Text(self.text).words
            #self.tokens.remove('.')
            self.word_count = len(self.tokens)
            self.unique_words = len(set(self.tokens))
        except ValueError as ex:
            print ex
            self.tokens = []
    def get_freq_dist(self):
        '''
        Frequency distribution for both .
        '''
        if not self.tokens:
            self.tokenize()
        if self.language == 'zh' or self.language == 'zh_Hant':
            self.zh_char_freq_dist = dict(FreqDist(self.zh_characters))
            try:
                del self.zh_char_freq_dist['.']
            except KeyError as ex:
                print ex
        self.freq_dist = dict(FreqDist(self.tokens))
        try:
            del self.freq_dist['.']
        except KeyError as ex:
            print ex
    def extract_text(self):
        '''
        Extract all text from the book.
        '''
        book = epub.read_epub(self.filepath)
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
        if not hasattr(self, 'text'):
            self.extract_text()
        self.language = Text(self.text).language.code
    
    
    
    def extract_fit_parameters(self, analysis_type, sweep_values):
        '''
        Curve fit.
        '''
        if analysis_type == "words":
            log_x = True
            log_y = True
            function = linear_func
        elif analysis_type == "characters":
            log_x = True
            log_y = False
            function = linear_func
        if sweep_values:
            array = list(zip(*sweep_values))
            if log_x:
                xarr = log(array[0])
            else:
                xarr = array[0]
            if log_y:
                yarr = log(array[1])
            else:
                yarr = array[1]
            initial_a = 0
            initial_b = 0
            popt, pcov = curve_fit(function, xarr, yarr, (initial_a, initial_b))
            slope = popt[0]
            intercept = popt[1]
            perr = np.sqrt(np.diag(pcov))
            std_error_slope = perr[0]
            std_error_intercept = perr[1]
            self.fit.append({'type': analysis_type,
                             'samples': len(sweep_values),
                             'intercept': intercept,
                             'slope': slope,
                             'std_error_intercept': std_error_intercept,
                             'std_error_slope': std_error_slope})
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
    def delete_heavy_attributes(self):
        '''
        Delete heavy attributes.
        '''
        del self.text
        del self.tokens
        try:
            del self.zh_characters
        except AttributeError:
            pass
# Functions
def clean_non_printable(text):
    '''
    Remove all non printable characters from string.
    '''
    return ''.join(character for character in text
                   if unicodedata.category(character) in PRINTABLE)
def clean_dots(dictionary):
    '''
    Remove dot form dictionary.
    '''
    del dictionary['.']
## Database functions
### SQL
MY_DB = mysql.connector.connect(
    host="localhost",
    user="root",
    passwd="root",
    charset='utf8'
)

#def insert_book_db(book, db="library"):
#    '''
#    Insert data into db
#    '''
#    mycursor = MY_DB.cursor()
#    mycursor.execute("use " + db + ";")
#    sql = """INSERT IGNORE corpus (title,
#    author,
#    slope,
#    intercept,
#    std_error_slope,
#    std_error_intercept,
#    word_count,
#    unique_words,
#    zhslope,
#    zhintercept,
#    zhstd_error_slope,
#    zhstd_error_intercept,
#    character_count,
#    unique_characters,
#    language,
#    epub_type,
#    subject,
#    source,
#    rights,
#    relation,
#    publisher,
#    identifier,
#    epub_format,
#    description,
#    contributor,
#    date
#    ) VALUES (%s,
#    %s,
#    %s,
#    %s,
#    %s,
#    %s,
#    %s,
#    %s,
#    %s,
#    %s,
#    %s,
#    %s,
#    %s,
#    %s,
#    %s,
#    %s,
#    %s,
#    %s,
#    %s,
#    %s,
#    %s,
#    %s,
#    %s,
#    %s,
#    %s,
#    %s)"""
#    val = (book.title,
#           book.author,
#           book.fitword_curve_fit['slope']),
#           float(word_curve_fit['intercept']),
#           float(word_curve_fit['std_error_slope']),
#           float(word_curve_fit['std_error_intercept']),
#           float(book.word_count),
#           float(book.unique_words),
#           float(zh_character_curve_fit['slope']),
#           float(zh_character_curve_fit['intercept']),
#           float(zh_character_curve_fit['std_error_slope']),
#           float(zh_character_curve_fit['std_error_intercept']),
#           float(book.character_count),
#           float(book.unique_characters),
#           book.language,
#           book.epub_type,
#           book.subject,
#           book.source,
#           book.rights,
#           book.relation,
#           book.publisher,
#           book.identifier,
#           book.epub_format,
#           book.description,
#           book.contributor,
#           book.date)
#    mycursor.execute(sql, val)
#    MY_DB.commit()
#    print("1 record inserted, ID:", mycursor.lastrowid)
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
### MongoDB
def mongo_connection(database, client="mongodb://localhost:27017/", collection="corpus"):
    myclient = pymongo.MongoClient(client)
    mydb = myclient[database]
    mycol = mydb[collection]
    return myclient, mydb, mycol
def insert_book_mongo(book, collection):
    collection.insert_one(book.__dict__)
def is_book_in_mongodb(book, collection):
    try:
        myquery = { "author": book.author, "title": book.title}
        mydoc = collection.find_one(myquery)
        if mydoc:
            return True
        return False
    except AttributeError:
        return True
def backup_mongo(db):
    '''
    Write mongo file as json.
    '''
    try:
        print db
        backup = subprocess.Popen(["mongodump", "--host", "localhost", "--db",
                                   db])
        # Wait for completion
        backup.communicate()
        if backup.returncode != 0:
            sys.exit(1)
        else:
            print "Backup done for " + db
    except OSError as ex:
        # Check for errors
        print ex
        print "Backup failed for " + db
# Main function
def correct_dirpath(dirpath):
    if dirpath.endswith('/'):
        return dirpath
    return dirpath + '/'

def get_size(filepath, unit='M'):
    if unit == 'K':
        return (os.path.getsize(filepath) >> 10)
    if unit == 'M':
        return (os.path.getsize(filepath) >> 20)
    if unit == 'G':
        return (os.path.getsize(filepath) >> 30)

def analyse_directory(argv):
    '''
    Main function: open and read all epub files in directory.
    Analyze them and populate data in database
    :param argv: command line args.
    '''
    corpus_path = str(argv[1])
    db = str(argv[2])
    books_analyzed = 0
    myclient, __, mycol = mongo_connection(db)
    for dirpath, __, files in os.walk(corpus_path):
        for ebook in files:
            if ebook.endswith(".epub"):
                try:
                    ebookpath = correct_dirpath(dirpath) + ebook
                    print "Checking if book " + ebook + " is in database"
                    try:
                        my_book = Book(ebookpath)
                    except lxml.etree.XMLSyntaxError:
                        continue
                    if is_book_in_mongodb(my_book, mycol):
                        continue
                    if get_size(ebookpath) < 10:
                        print "Reading ebook " + ebook + ", number  " + str(books_analyzed + 1)
                        my_book = Book(ebookpath, samples=10)
                    else:
                        print "Book " + ebook + " too big. Only metadata is read"
                    print "Writing to database"
                    mycol.insert_one(my_book.__dict__, mycol)
                    if books_analyzed%10 == 0:
                        print "Performing backup"
                        backup_mongo(db)
                    books_analyzed += 1
                except (KeyError, TypeError) as ex:
                    print ex
                    continue
    print "Performing final backup"
    backup_mongo(db)
    print "Closing db"
    myclient.close()

if __name__ == '__main__':
    analyse_directory(sys.argv)
