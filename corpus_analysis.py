# -*- coding: utf-8 -*-
'''
corpus-analysis.py: readability measure for epub ebooks.
Version 1.0
Copyright (C) 2019  Roland Coeurjoly <rolandcoeurjoly@gmail.com>
'''
# imports
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
# main function
i = 1
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
def fit_values(function, values):
    '''
    Fit values to a given model.
    '''
    array = list(zip(*values))
    xarr = array[0]
    yarr = array[1]

    return curve_fit(function, xarr, yarr)
MY_DB = mysql.connector.connect(
    host="localhost",
    user="root",
    passwd="root",
    charset='utf8'
)
def runbackup(hostname, mysql_user, mysql_pw):
    '''
    Write sql file.
    '''
    try:
        backup = subprocess.Popen("mysqldump -h"
                                  + hostname + " -u"
                                  + mysql_user + " -p'"
                                  + mysql_pw + "' --databases library > "
                                  + "/media/root/terabyte/Metatron/library.sql", shell=True)
        # Wait for completion
        backup.communicate()
        print("Backup done for", hostname)
    except Exception as ex:
        # Check for errors
        print ex
        if backup.returncode != 0:
            print("Backup failed for", hostname)
        raise
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
    'Zs'
}
def filter_non_printable(text):
    '''
    Remove all non printable characters from string.
    '''
    return ''.join(character for character in text if unicodedata.category(character) in PRINTABLE)
for dirpath, dirnames, files in os.walk(str(sys.argv[1])):
    for ebook in files:
        if ebook.endswith(".epub"):
            print "Reading ebook " + ebook + ", number  " + str(i)
            try:
                book = epub.read_epub(dirpath + "/" + ebook)
            except Exception as ex:
                print ex
                raise
            print "Getting epub metadata"
            try:
                epubType = book.get_metadata('DC', 'type')[0][0].encode('utf-8')
            except IndexError:
                epubType = ''
            try:
                subject = book.get_metadata('DC', 'subject')[0][0].encode('utf-8')
            except IndexError:
                subject = ''
            try:
                source = book.get_metadata('DC', 'source')[0][0].encode('utf-8')
            except IndexError:
                source = ''
            try:
                rights = book.get_metadata('DC', 'rights')[0][0].encode('utf-8')
            except IndexError:
                rights = ''
            try:
                relation = book.get_metadata('DC', 'relation')[0][0].encode('utf-8')
            except IndexError:
                relation = ''
            try:
                publisher = book.get_metadata('DC', 'publisher')[0][0].encode('utf-8')
            except IndexError:
                publisher = ''
            #try:
            #    language = book.get_metadata('DC', 'language')[0][0].encode('utf-8')
            #except IndexError:
            #    language = 'empty'
            try:
                identifier = book.get_metadata('DC', 'identifier')[0][0].encode('utf-8')
            except IndexError:
                identifier = ''
            try:
                epubFormat = book.get_metadata('DC', 'format')[0][0].encode('utf-8')
            except IndexError:
                epubFormat = ''
            try:
                description = book.get_metadata('DC', 'description')[0][0].encode('utf-8')
            except IndexError:
                description = ''
            try:
                coverage = book.get_metadata('DC', 'coverage')[0][0].encode('utf-8')
            except IndexError:
                coverage = ''
            try:
                contributor = book.get_metadata('DC', 'contributor')[0][0].encode('utf-8')
            except IndexError:
                contributor = ''
            try:
                author = book.get_metadata('DC', 'creator')[0][0].encode('utf-8')
            except IndexError:
                author = ''
            try:
                title = book.get_metadata('DC', 'title')[0][0].encode('utf-8')
            except IndexError:
                title = ''
            try:
                date = book.get_metadata('DC', 'date')[0][0].encode('utf-8')
            except IndexError:
                date = ''
            print "Checking if book exists in database"
            mycursor = MY_DB.cursor()
            try:
                mycursor.execute("CREATE DATABASE library")
            except Exception as ex:
                print ex
                mycursor.execute("USE library;")
                raise
            try:
                query = ('SELECT * from corpus where title="' + str(title)
                         + '" and author="' + str(author) + '"')
                mycursor.execute(query)
                myresult = mycursor.fetchall()
                if mycursor.rowcount == 1:
                    print ("Book " + str(title)
                           + ", by " + str(author)
                           + " already in database. Next.")
                    continue
            except Exception as ex:
                print ex
                raise
            print "Extracting text from ebook"
            cleantext = ""
            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_DOCUMENT:
                    raw_html = item.get_content()
                    cleantext += BeautifulSoup(raw_html, "lxml").text
            print "Detecting language"
            cleantext = filter_non_printable(cleantext)
            language_detected = Text(cleantext).language.code
            print "Language detected: " + str(language_detected)
            print "Performing tokenization"
            character_count = int()
            unique_characters = int()
            if language_detected == 'zh' or language_detected == 'zh_Hant':
                zh_characters = ''.join(c for c in cleantext if u'\u4e00' <= c <= u'\u9fff')
                character_count = len(zh_characters)
                unique_characters = len(set(zh_characters))
            tokens = Text(cleantext).words
            word_count = len(tokens)
            unique_words = len(set(tokens))
            print "Lexical sweep"
            #Temporary value for speed. Before it was 500
            samples = 10
            log_behaviour_start = 5000
            sweep_values = []
            zhsweep_values = []
            log_behaviour_range = len(tokens) - log_behaviour_start
            log_step = log_behaviour_range/samples
            zhlog_behaviour_range = len(zh_characters) - log_behaviour_start
            zhlog_step = zhlog_behaviour_range/samples
            if word_count > 10000:
                for sample_size in xrange(
                        log_behaviour_start,
                        log_behaviour_range,
                        log_step):
                    x_sample = log(len(tokens[0:sample_size]))
                    y_sample = log(len(set(tokens[0:sample_size])))
                    sweep_values.append([x_sample, y_sample])
                popt, pcov = fit_values(linear_func, sweep_values)
                book_intercept = popt[0]
                book_slope = popt[1]
                perr = np.sqrt(np.diag(pcov))
                std_error_intercept = perr[0]
                std_error_slope = perr[1]
                if language_detected == 'zh' or language_detected == 'zh_Hant':
                    for sample_size in xrange(
                            log_behaviour_start,
                            zhlog_behaviour_range,
                            zhlog_step):
                        x_sample = len(zh_characters[0:sample_size])
                        y_sample = log(len(set(zh_characters[0:sample_size])))
                        zhsweep_values.append([x_sample, y_sample])
                    zhpopt, zhpcov = fit_values(linear_func, zhsweep_values)
                    zhintercept = zhpopt[0]
                    zhslope = zhpopt[1]
                    zhperr = np.sqrt(np.diag(zhpcov))
                    zhstd_error_intercept = zhperr[0]
                    zhstd_error_slope = zhperr[1]
                else:
                    zhintercept = int()
                    zhslope = int()
                    zhstd_error_intercept = int()
                    zhstd_error_slope = int()
            else:
                book_intercept = int()
                book_slope = int()
                std_error_intercept = int()
                std_error_slope = int()
            print "Writing to database"
            mycursor = MY_DB.cursor()
            print "Gotten cursor"
            mycursor.execute("CREATE DATABASE IF NOT EXISTS library;")
            mycursor.execute("use library;")
            print "Gotten library"
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
                epubType VARCHAR(255),
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
            print "Check table exists"
            mycursor.execute(
                "ALTER DATABASE library CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
            mycursor.execute(
                "ALTER TABLE corpus CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
            print "DB and table utf8"
            try:
                mycursor.execute(
                    "ALTER TABLE corpus ADD CONSTRAINT unique_book UNIQUE (title,author);")
            except Exception as ex:
                print ex
                raise
            print "Add constraint"
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
            val = (title,
                   author,
                   float(book_slope),
                   float(book_intercept),
                   float(std_error_slope),
                   float(std_error_intercept),
                   float(word_count),
                   float(unique_words),
                   float(zhslope),
                   float(zhintercept),
                   float(zhstd_error_slope),
                   float(zhstd_error_intercept),
                   float(character_count),
                   float(unique_characters),
                   language_detected,
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
                   date)
            mycursor.execute(sql, val)
            print "executed insert"
            MY_DB.commit()
            print("1 record inserted, ID:", mycursor.lastrowid)
            i += 1
            runbackup("localhost", "root", "root")
MY_DB.close()
