"""Docstring test.  """
from unittest import TestCase
import doctest
import batchrender.texttools


class TestModule(TestCase):
    def test_path(self):
        result = doctest.testmod(batchrender.texttools, verbose=False)
        self.assertFalse(result.failed)
