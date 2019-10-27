'''
Create benchmark based on epubs
'''

import json
import os
import corpus_analysis

DATA = {}
DATA['books'] = []

with open('benchmarks.json', 'w') as outfile:
    for dirpath, __, files in os.walk('test'):
        for ebook in files:
            print "Reading book"
            my_book = corpus_analysis.Book(dirpath + '/' + ebook, 10)
            print "Book read"
            json.dump(my_book.__dict__, outfile)
