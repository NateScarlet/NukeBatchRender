# -*- coding=UTF-8 -*-
"""Testing database.  """

from unittest import TestCase
from threading import Thread
import tempfile
from pprint import pprint
from random import gauss
from multiprocessing.dummy import Pool
from contextlib import contextmanager

from database import Database


def show_database(database):
    """Get all content from a database.  """

    assert isinstance(database, Database)

    with database.connection() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        available_table = (c.fetchall())
        for i in available_table:
            c.execute("SELECT * FROM {}".format(i[0]))
            pprint(c.fetchall())


def _test_in_thread(func, exc_dict):
    try:
        func()
    except Exception as ex:
        exc_dict[func.__name__] = ex
        raise


class DataBaseTestCase(TestCase):
    @contextmanager
    def _database(self):
        # TODO: clean up after test.
        temp_file = tempfile.mkstemp()[1]
        yield Database(temp_file)

    def test_reuse(self):
        temp_file = tempfile.mkstemp()[1]
        database = Database(temp_file)
        filename, frames, cost = 'test', 10, 123
        database.set_task(filename, frames, cost)
        self.assertEqual(database.get_task_frames(filename), frames)
        self.assertEqual(database.get_task_cost(filename), cost)
        database = Database(temp_file)
        self.assertEqual(database.get_task_frames(filename), frames)
        self.assertEqual(database.get_task_cost(filename), cost)

    def test_normal(self):

        times = 10
        with self._database() as database:
            assert isinstance(database, Database)
            case = []
            for _ in xrange(times):
                case.append(gauss(20, 20))
            filename = tempfile.mktemp()
            total = reduce(float.__add__, case)
            avg = total / times
            self.assertIsInstance(database.averge_task_cost, float)

            for i in case:
                database.set_frame_time(filename, 1, i)
                self.assertEqual(database.get_frame_time(filename, 1), i)
            self.assertEqual(database.get_averge_time(filename), avg)

            database.set_task(filename, times, total)
            self.assertEqual(database.averge_task_cost, total)

    def test_error(self):
        with self._database() as database:
            self.assertIsNone(database.get_frame_time('test1.nk', 2))

    def test_threading(self):
        exceptions = {}

        thread = Thread(target=lambda: _test_in_thread(
            self.test_normal, exceptions))
        thread.start()
        thread.join()

        thread = Thread(target=lambda: _test_in_thread(
            self.test_error, exceptions))
        thread.start()
        thread.join()

        self.assertFalse(exceptions)

    def test_pool(self):
        times = 50
        with self._database() as database:
            case = []
            for _ in xrange(times):
                case.append(gauss(20, 20))
            filename = tempfile.mktemp()
            avg = reduce(float.__add__, case) / times

            def _run(i):
                database.set_frame_time(filename, 1, i)

            pool = Pool()
            pool.map(_run, case)
            pool.close()
            pool.join()
            self.assertAlmostEqual(database.get_averge_time(filename), avg)
