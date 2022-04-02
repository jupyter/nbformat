"""
Contains base test class for nbformat
"""

# Copyright (c) IPython Development Team.
# Distributed under the terms of the Modified BSD License.

import os
import unittest


class TestsBase(unittest.TestCase):
    """Base tests class."""

    @classmethod
    def fopen(cls, f, mode="r", encoding="utf-8"):
        return open(os.path.join(cls._get_files_path(), f), mode, encoding=encoding)

    @classmethod
    def _get_files_path(cls):
        return os.path.dirname(__file__)
