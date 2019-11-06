'''
Create benchmark based on epubs
'''

import json
import os
import corpus_analysis

DATA = {}
DATA['books'] = []

with open('benchmarks.json', 'w') as outfile:
    for dirpath, __, files in os.walk('test/books/'):
        for ebook in files:
            print "Reading book"
            my_book = corpus_analysis.Book(dirpath + '/' + ebook, 10)
            print "Book read"
            DATA['books'].append(my_book.__dict__)
            outfile.write('\n')

with open('benchmarks.json', 'w') as outfile:
    json.dump(DATA, outfile, indent=2)
