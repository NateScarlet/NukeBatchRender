# -*- coding=UTF-8 -*-
"""Database output table.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import logging
import re

import six
from sqlalchemy import Column, Integer
from sqlalchemy.orm import relationship

from . import core
from ..codectools import get_unicode as u

LOGGER = logging.getLogger(__name__)


class Output(core.Base, core.SerializableMixin):
    """Output table.  """

    __tablename__ = 'Output'
    path = Column(core.Path, primary_key=True)
    timestamp = Column(core.TimeStamp)
    frame = Column(Integer, nullable=False)
    files = relationship('File', secondary=core.FILE_OUTPUT)

    def file_pattern(self):
        """File naming pattern for this output file.  """

        return get_filename_pattern(self.as_posix(), self.frame)

    def as_posix(self):
        """FilePath as posix.  """

        return u(self.path.as_posix())


def group_by_pattern(outputs):
    """Group outputs by file naming patten.  """

    output_groups = {}
    for i in outputs:
        assert isinstance(i, Output)
        key = i.file_pattern()
        output_groups.setdefault(key, [])
        output_groups[key].append(i)
    # Combine edge pattern with common pattern.
    for k, v in list(dict(output_groups).items()):
        for i in dict(output_groups):
            if i == k:
                continue
            if all(format_sequence(i, j.frame) == j.as_posix() for j in v):
                output_groups[i].extend(output_groups.pop(k))
                break
    return output_groups


def get_sequence_pattern(outputs):
    """Get output sequence file naming pattern.  """

    def _test(pattern, outputs):
        return all(format_sequence(pattern, i.frame) == i.as_posix() for i in outputs)

    output_groups = group_by_pattern(outputs)
    # Exclude None and pattern of single file .
    patterns = set(i for i in output_groups
                   if i and len(output_groups[i]) > 1)

    ret = set()
    for i in list(patterns):
        patterns.remove(i)
        # Test to exclude duplicated pattern.
        if not any(_test(j, output_groups[i]) for j in patterns):
            ret.add(i)
    return sorted(ret)


def get_filename_pattern(path, frame):
    """Get filename pattern from path with frame.  """

    def _repl(matchobj):
        value = matchobj.group(0)
        if value == six.text_type(frame):
            return '%d'
        return '%0{}d'.format(len(value))

    ret = u(path)
    ret = re.sub(r'(0*{})'.format(frame), _repl, ret)
    return ret


def format_sequence(pattern, frame):
    """Format sequence pattern with frame.  """

    def _format_repl(matchobj):
        return matchobj.group(0) % frame

    def _hash_repl(matchobj):
        return '%0{}d'.format(len(matchobj.group(0)))

    ret = u(pattern)
    ret = re.sub(r'(\#+)', _hash_repl, ret)
    ret = re.sub(r'(%0?\d*d)', _format_repl, ret)
    return ret
