"""Docstring test.  """
from __future__ import absolute_import

from unittest import TestCase
from tempfile import mktemp

import sys
from Qt.QtCore import QCoreApplication
import render


class QueueTestCase(TestCase):
    def test_normal(self):
        dummy_app = QCoreApplication(sys.argv)
        test_size = 100
        queue = render.Queue()
        for _ in xrange(test_size):
            queue.put(mktemp())

        self.assertTrue(queue, queue)
        self.assertEqual(len(queue), test_size)

        # Set tasks finished.
        for i in tuple(queue):
            self.assertIsInstance(i, render.Task)
            assert isinstance(i, render.Task)
            i.state |= render.FINISHED
        self.assertFalse(queue, queue)
        self.assertEqual(len(queue), test_size)
