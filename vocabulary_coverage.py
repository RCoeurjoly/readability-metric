'''
Random
'''
from collections import Counter

import corpus_analysis


MY_BOOK = corpus_analysis.Book("./assets/pinocchio.epub")
MY_BOOK.tokenize()
MY_FREQDIST = Counter(MY_BOOK.tokens)
print(MY_BOOK.word_count)
percentage = 0
cumulative_word_count = 0
coverage = 1
last_word_frequency = MY_FREQDIST.most_common(coverage)[coverage - 1][1]
coverage += 1
cumulative_word_count += last_word_frequency
percentage = (cumulative_word_count*100/MY_BOOK.word_count)
print(MY_FREQDIST.most_common(coverage)[coverage - 1][1])
print(percentage)
