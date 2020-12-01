import os
import random

from functools import lru_cache


@lru_cache(1)
def acceptable_nouns():
    with open(os.path.join(os.path.dirname(__file__), 'nouns.txt'), 'r') as nouns_file:
        return set(word.rstrip() for word in nouns_file.readlines())


@lru_cache(1)
def acceptable_adjectives():
    with open(os.path.join(os.path.dirname(__file__), 'adjectives.txt'), 'r') as adjectives_file:
        return set(word.rstrip() for word in adjectives_file.readlines())


def generate_corpus_id():
    return '-'.join((random.sample(acceptable_adjectives(), 1)[0], random.sample(acceptable_nouns(), 1)[0]))
