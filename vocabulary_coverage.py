'''
Random
'''
from nltk import FreqDist
import corpus_analysis


MY_BOOK = corpus_analysis.Book("./test/pinocchio.epub")
MY_BOOK.tokenize()
MY_FREQDIST = FreqDist(MY_BOOK.tokens)
print(MY_BOOK.word_count)
percentage = 0
cumulative_word_count = 0
coverage = 1
print(MY_FREQDIST.most_common(coverage)[coverage - 1][1])
margin_unknowable_list = MY_FREQDIST.most_common(MY_BOOK.word_count - 1) - MY_FREQDIST.most_common(int(round((MY_BOOK.word_count - 1)*0.98)))
last_word_frequency = MY_FREQDIST.most_common(coverage)[coverage - 1][1]
coverage += 1
cumulative_word_count += last_word_frequency
percentage = (cumulative_word_count*100/MY_BOOK.word_count)
print(margin_unknowable_list)
