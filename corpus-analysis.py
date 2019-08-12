# imports
# -*- coding: utf-8 -*-
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
def linear_func(x, a, b):
    return (a + b*x)

def log_func(x, a, b):
    return (a + b*log(x))

def log_log_func(x, a, b):
    return (math.e**(a + b*log(x)))
def fit_values(function, values):
    t =  list(zip(*values))
    xarr = t[0]
    yarr = t[1]

    a = 0
    b = 0
    return curve_fit(function,  xarr, yarr, (a,b))
mydb = mysql.connector.connect(
  host="localhost",
  user="root",
  passwd="root",
  charset='utf8'
)
def runbackup(hostname, mysql_user, mysql_pw):
    try:
        p = subprocess.Popen("mysqldump -h" + hostname + " -u" + mysql_user + " -p'" + mysql_pw + "' --databases library > ~/Metatron/library.sql", shell=True)
        # Wait for completion
        p.communicate()
        print("Backup done for", hostname)
    except:
        # Check for errors
        if(p.returncode != 0):
            raise
        print("Backup failed for", hostname)
for dirpath, dirnames, files in os.walk(str(sys.argv[1])):
    for ebook in files:
        if ebook.endswith(".epub"):
            print ("Reading ebook " + ebook + ", number  " + str(i))
            try:
                book = epub.read_epub(dirpath + "/" + ebook)
            except:
                continue
            print ("Getting epub metadata")
            try:
                epubType = book.get_metadata('DC', 'type')[0][0].encode('utf-8')
            except:
                epubType = ''
            try:
                subject = book.get_metadata('DC', 'subject')[0][0].encode('utf-8')
            except:
                subject = ''
            try:
                source = book.get_metadata('DC', 'source')[0][0].encode('utf-8')
            except:
                source = ''
            try:
                rights = book.get_metadata('DC', 'rights')[0][0].encode('utf-8')
            except:
                rights = ''
            try:
                relation = book.get_metadata('DC', 'relation')[0][0].encode('utf-8')
            except:
                relation = ''
            try:
                publisher = book.get_metadata('DC', 'publisher')[0][0].encode('utf-8')
            except:
                publisher = ''
            #try:
            #    language = book.get_metadata('DC', 'language')[0][0].encode('utf-8')
            #except:
            #    language = 'empty'
            try:
                identifier = book.get_metadata('DC', 'identifier')[0][0].encode('utf-8')
            except:
                identifier = ''
            try:
                epubFormat = book.get_metadata('DC', 'format')[0][0].encode('utf-8')
            except:
                epubFormat = ''
            try:
                description = book.get_metadata('DC', 'description')[0][0].encode('utf-8')
            except:
                description = ''
            try:
                coverage = book.get_metadata('DC', 'coverage')[0][0].encode('utf-8')
            except:
                coverage = ''
            try:
                contributor = book.get_metadata('DC', 'contributor')[0][0].encode('utf-8')
            except:
                contributor = ''
            try:
                author = book.get_metadata('DC', 'creator')[0][0].encode('utf-8')
            except:
                author = ''
            try:
                title = book.get_metadata('DC', 'title')[0][0].encode('utf-8')
            except:
                title = ''
            try:
                date = book.get_metadata('DC', 'date')[0][0].encode('utf-8')
            except:
                date = ''
            print ("Checking if book exists in database")
            mycursor = mydb.cursor()
            
            try:
                mycursor.execute("CREATE DATABASE library")
            except:
                mycursor.execute("USE library;")
            
            try:
                query = 'SELECT * from corpus where title="' + str(title) + '" and author="' + str(author) + '"'
                mycursor.execute(query)
                myresult = mycursor.fetchall()
                if mycursor.rowcount==1:
                    print ("Book " + str(title) + ", by " + str(author) + " already in database. Next.")
                    continue
            except:
                pass
            print ("Extracting text from ebook")
            cleantext = ""
            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_DOCUMENT:
                    raw_html = item.get_content()
                    cleantext += BeautifulSoup(raw_html, "lxml").text
            print ("Detecting language")
            language_detected=Text(cleantext).language.code
            print ("Language detected: " + str(language_detected))
            print ("Performing tokenization")
            character_count = int()
            unique_characters = int()
            if (language_detected == 'zh' or language_detected == 'zh_Hant'):
                zh_characters = ''.join(c for c in cleantext if u'\u4e00' <= c <= u'\u9fff')
                character_count = len(zh_characters)
                unique_characters = len(set(zh_characters))
            tokens = Text(cleantext).words
            word_count = len(tokens)
            unique_words = len(set(tokens))
            print ("Lexical sweep")
            start = 5000
            #Temporary value for speed. Before it was 500
            samples = 10
            
            sweep_values = []
            if word_count > 10000:
                for j in xrange(0, len(tokens) - start, (len(tokens) - start)/samples):
                    sweep_values.append([log(len(tokens[0:start + j])), log(len(set(tokens[0:start + j])))])
                popt, pcov = fit_values(linear_func, sweep_values)
                intercept = popt[0]
                slope = popt[1]
                perr = np.sqrt(np.diag(pcov))
                std_error_intercept=perr[0]
                std_error_slope=perr[1]
            else:
                intercept = int()
                slope = int()
                std_error_intercept = int()
                std_error_slope = int()
            
            zhsweep_values = []
            if ((language_detected == 'zh' or language_detected == 'zh_Hant') and character_count > 10000):
                for j in xrange(0, len(zh_characters) - start, (len(zh_characters) - start)/samples):
                    zhsweep_values.append([len(zh_characters[0:start + j]), log(len(set(zh_characters[0:start + j])))])
                zhpopt, zhpcov = fit_values(linear_func, zhsweep_values)
                zhintercept = zhpopt[0]
                zhslope = zhpopt[1]
                zhperr = np.sqrt(np.diag(zhpcov))
                zhstd_error_intercept=zhperr[0]
                zhstd_error_slope=zhperr[1]
            else:
                zhintercept = int()
                zhslope = int()
                zhstd_error_intercept = int()
                zhstd_error_slope = int()
            #print ("Writing to file")
            #with open("/home/rcl/readability-measure/test/"
            #          + str(language_detected)
            #          + ".tsv", "w") as myfile:
            #    myfile.write(str(wordCount) + "\t"
            #                 + str(uniqueWords) + "\t"
            #                 #+ str(intercept) + "\t"
            #                 #+ str(slope) + "\t"
            #                 + str(language_detected) + "\t"
            #                 + str(author) + "\t"
            #                 + str(title) + "\t"
            #                 + str(epubType) + "\t"
            #                 + str(subject) + "\t"
            #                 + str(source) + "\t"
            #                 + str(rights) + "\t"
            #                 + str(relation) + "\t"
            #                 + str(publisher) + "\t"
            #                 + str(identifier) + "\t"
            #                 + str(epubFormat) + "\t"
            #                 # + str(description) + "\t"
            #                 + str(contributor) + "\t"
            #                 + str(date) + "\n")
            print ("Writing to database")
            mycursor = mydb.cursor()
            
            print ("Gotten cursor")
            
            mycursor.execute("CREATE DATABASE IF NOT EXISTS library;")
            mycursor.execute("use library;")
            
            print ("Gotten library")
            
            mycursor.execute(""" CREATE TABLE IF NOT EXISTS corpus (id INT AUTO_INCREMENT PRIMARY KEY,
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
            
            print ("Check table exists")
            mycursor.execute("ALTER DATABASE library CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
            mycursor.execute("ALTER TABLE corpus CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
            print ("DB and table utf8")
            try:
                mycursor.execute("ALTER TABLE corpus ADD CONSTRAINT unique_book UNIQUE (title,author);")
            except:
                pass
            print ("Add constraint")
            
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
            float(slope),
            float(intercept),
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
            print ("executed insert")
            mydb.commit()
            print("1 record inserted, ID:", mycursor.lastrowid)
            i += 1
            runbackup("localhost", "root", "root");
mydb.close()
