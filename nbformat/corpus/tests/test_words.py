"""Tests for nbformat corpus"""

# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

import pytest
import random

from .. import words

def test_acceptable_nouns_set():
    assert len(words.acceptable_nouns()) > 1000
    for word in words.acceptable_nouns():
        assert len(word) > 3, word
        assert word == word.strip()


def test_acceptable_adjectives_set():
    assert len(words.acceptable_adjectives()) > 1000
    for word in words.acceptable_adjectives():
        assert len(word) > 3, word
        assert word == word.strip()


def test_generate_corpus_id():
    assert len(words.generate_corpus_id()) > 7
    # 1 in 5073324 (3714 x 1366) times this will fail
    assert words.generate_corpus_id() !=  words.generate_corpus_id()
