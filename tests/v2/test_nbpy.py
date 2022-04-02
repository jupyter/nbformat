from unittest import TestCase

from nbformat.v2.nbbase import (
    NotebookNode,
    new_code_cell,
    new_notebook,
    new_text_cell,
    new_worksheet,
)
from nbformat.v2.nbpy import reads, writes

from .nbexamples import nb0, nb0_py


class TestPy(TestCase):
    def test_write(self):
        s = writes(nb0)
        self.assertEqual(s, nb0_py)
