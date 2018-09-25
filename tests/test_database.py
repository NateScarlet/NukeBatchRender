# -*- coding=UTF-8 -*-
"""Testing database.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import random

import pytest

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
    assert sorted(result) == sorted(frames)


def test_output(session):
    case = [
        'test.%d.exr',
        'test%d.exr',
        'test1%d.exr',
        'test%04d.exr',
        '测试1%d.exr',
        '001/test%04d.exr',
    ]
    for i in case:
        files = [database.Output(path=database.output.format_sequence(
            i, j), frame=j) for j in range(-100, 100)]
        session.add_all(files)
        session.commit()
        assert database.output.get_sequence_pattern(files) == [i], i
        _ = [session.delete(i) for i in files]
        session.commit()
