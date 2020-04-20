'''
Create benchmark based on epubs
'''

import json
import os
import corpus_analysis
from corpus_analysis import correct_dirpath
DATA = {}
DATA['books'] = []

with open('benchmarks.json', 'w') as outfile:
    for dirpath, __, files in os.walk('assets/'):
        for ebook in files:
            ebook_path = correct_dirpath(dirpath) + ebook
            print("Reading book")
            my_book = corpus_analysis.Book(ebook_path, samples=10)
            print("Book read")
            DATA['books'].append(my_book.__dict__)
            outfile.write('\n')

with open('benchmarks.json', 'w') as outfile:
    json.dump(DATA, outfile, indent=2)
