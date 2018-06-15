# -*- coding=UTF-8 -*-
"""Testing database.  """


import pytest
import random

from batchrender import database


@pytest.fixture(name='session')
def _session():
    database.core.setup('sqlite:///:memory:')
    return database.core.Session()


def test_has_sequence(session):

    file_obj = database.File(hash='abc')
    session.add(file_obj)

    assert not file_obj.has_sequence()

    output_obj = database.Output(path='test1', frame=1, files=[file_obj])
    session.add(output_obj)
    assert not file_obj.has_sequence()

    output_obj = database.Output(path='test2', frame=2, files=[file_obj])
    session.add(output_obj)
    assert file_obj.has_sequence()

    output_obj.frame = 1
    assert not file_obj.has_sequence()
    output_obj.frame = 2
    assert file_obj.has_sequence()


def test_rendered_frams(session):
    frames = set(random.randint(0, 100) for _ in xrange(100))
    file_obj = database.File(hash='abc')
    session.add(file_obj)

    for i in frames:
        output_obj = database.Output(
            path='test{}'.format(i), frame=i, files=[file_obj])
        session.add(output_obj)

    result = file_obj.rendered_frames()
    assert result == sorted(frames)
