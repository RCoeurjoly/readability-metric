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
import re
import lxml
import ebooklib
import pymongo
from ebooklib import epub
from bs4 import BeautifulSoup
from scipy.optimize import curve_fit
import numpy as np
from numpy.lib.scimath import log as log
from polyglot.text import Text
from nltk import FreqDist
# Constants
PRINTABLE = {
    # 'Cc',
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
# Curve fitting functions


def lexical_sweep_map(start, stop, step, text):
    return list(map(lambda x: [x, len(set(text[0:x]))], range(int(start),
                                                         int(stop),
                                                         int(step))))


def lexical_sweep_list_comprehension(start, stop, step, text):
    return [[x, len(set(text[0:x]))] for x in range(int(start),
                                                    int(stop),
                                                    int(step))]


def lexical_sweep_for_loop(start, stop, step, text):
    return list(map(lambda x: [x, len(set(text[0:x]))], range(int(start),
                                                         int(stop),
                                                         int(step))))


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
        print(ex)
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
# Book Class


class Book(object):
    '''
    Book class
    '''
    def __init__(self, epub_filename, slicing_function=lexical_sweep_map, samples=0):
        '''
        Init.
        '''
        # pylint: disable=too-many-statements
        # There is a lot of metadata but it is repetitive and non problematic.
        try:
            print("Extracting metadata")
            self.extract_metadata(epub_filename)
            if samples:
                print("Extracting text")
                self.extract_text()
                print("Detecting language")
                self.detect_language()
                print("Tokenization")
                self.tokenize()
                print("Calculating word sweep values")
                sweep_values = lexical_sweep(self.tokens, slicing_function, samples)
                self.fit = []
                print("Word fit")
                self.extract_fit_parameters("words", sweep_values)
                if self.language == "zh" or self.language == "zh_Hant":
                    print("Calculating character sweep values")
                    sweep_values = lexical_sweep(self.zh_characters, slicing_function, samples)
                    print("Character fit")
                    self.extract_fit_parameters("characters", sweep_values)
                self.delete_heavy_attributes()
        except AttributeError:
            pass

    def extract_metadata(self, epub_filename):
        '''
        Extraction of metadata
        '''
        self.filepath = epub_filename
        epub_file = epub.read_epub(self.filepath)
        metadata_fields = ['creator',
                           'title',
                           'subject',
                           'source',
                           'rights',
                           'relation',
                           'publisher',
                           'identifier',
                           'description',
                           'coverage',
                           'contributor',
                           'date']
        for metadata_field in metadata_fields:
            try:
                setattr(self,
                        metadata_field,
                        epub_file.get_metadata('DC', metadata_field)[0][0])
            except (IndexError, AttributeError):
                pass
        metadata_to_attribute = [['original_language', 'language'],
                                 ['epub_type', 'type'],
                                 ['epub_format', 'format']]
        for attribute, metadata_field in metadata_to_attribute:
            try:
                setattr(self,
                        attribute,
                        epub_file.get_metadata('DC', metadata_field)[0][0])
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
            self.word_count = len(self.tokens)
            self.unique_words = len(set(self.tokens))
        except ValueError as ex:
            print(ex)
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
                print(ex)
        self.freq_dist = dict(FreqDist(self.tokens))
        try:
            del self.freq_dist['.']
        except KeyError as ex:
            print(ex)

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
            #print("My sweep values:")
            #for i in sweep_values:
            #    print(str(i) + ", " + str(sweep_values[i]))
            self.fit.append({'type': analysis_type,
                             'samples': len(sweep_values),
                             'intercept': intercept,
                             'slope': slope,
                             'std_error_intercept': std_error_intercept,
                             'std_error_slope': std_error_slope})

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
# Database functions
# MongoDB


def mongo_connection(database, client="mongodb://localhost:27017/", collection="corpus"):
    myclient = pymongo.MongoClient(client)
    mydb = myclient[database]
    mycol = mydb[collection]
    return myclient, mydb, mycol


def insert_book_mongo(book, collection):
    collection.insert_one(book.__dict__)


def is_book_in_mongodb(book, collection):
    try:
        myquery = {"creator": book.creator, "title": book.title}
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
        print(db)
        backup = subprocess.Popen(["mongodump", "--host", "localhost", "--db",
                                   db])
        # Wait for completion
        backup.communicate()
        if backup.returncode != 0:
            sys.exit(1)
        else:
            print("Backup done for " + db)
    except OSError as ex:
        # Check for errors
        print(ex)
        print("Backup failed for " + db)
# Main function


def correct_dirpath(dirpath):
    if dirpath.endswith('/'):
        return dirpath
    return dirpath + '/'


def get_size(filepath, unit='M'):
    if unit == 'K':
        return os.path.getsize(filepath) >> 10
    if unit == 'M':
        return os.path.getsize(filepath) >> 20
    if unit == 'G':
        return os.path.getsize(filepath) >> 30


def analyse_file(ebookpath, my_col):
    """
    Analyse single book
    """
    if ebookpath.endswith(".epub"):
        try:
            ebook = re.search(r'.*(/.*$)', ebookpath).group(1)
            print("Checking if book " + ebook + " is in database")
            my_book = Book(ebookpath)
            if is_book_in_mongodb(my_book, my_col):
                return False
            if get_size(ebookpath) < 10:
                print("Reading ebook " + ebook)
                my_book = Book(ebookpath, samples=10)
            else:
                print("Book " + ebook + " too big. Only metadata is read")
            print("Writing to database")
            my_col.insert_one(my_book.__dict__, my_col)
            return True
        except (KeyError,
                TypeError,
                lxml.etree.XMLSyntaxError,
                ebooklib.epub.EpubException) as ex:
            print(ex)
            return False
        print("Only epubs can be analysed")
        return False


def analyse_directory(argv):
    '''
    Main function: open and read all epub files in directory.
    Analyze them and populate data in database
    :param argv: command line args.
    '''
    corpus_path = str(argv[1])
    db = str(argv[2])
    books_analyzed = 1
    my_client, __, my_col = mongo_connection(db)
    for dirpath, __, files in os.walk(corpus_path):
        for ebook in files:
            result = analyse_file(correct_dirpath(dirpath) + ebook, my_col)
            if result:
                print("Books analysed: " + str(books_analyzed + 1))
                books_analyzed += 1
            if books_analyzed % 25 == 0:
                print("Performing backup")
                backup_mongo(db)
    print("Performing final backup")
    backup_mongo(db)
    print("Closing db")
    my_client.close()


def main(argv):
    if str(argv[1]).endswith(".epub"):
        db = str(argv[2])
        __, __, my_col = mongo_connection(db)
        return analyse_file(str(argv[1]), my_col)
    else:
        analyse_directory(argv)


if __name__ == '__main__':
    main(sys.argv)
