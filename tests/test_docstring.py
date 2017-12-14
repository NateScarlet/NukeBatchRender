"""Docstring test.  """
from unittest import TestCase
import doctest


class TestModule(TestCase):
    def test_path(self):
        import path
        result = doctest.testmod(path, verbose=False)
        self.assertFalse(result.failed)
