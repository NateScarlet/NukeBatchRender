# -*- coding=UTF-8 -*-
"""Frame range object.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import re
from collections import namedtuple
from functools import reduce  # pylint: disable=redefined-builtin

import six
from six.moves import range


class _FrameRangePart(namedtuple('FrameRangePart', ('first', 'last', 'increment'))):
    @property
    def is_single(self):
        """If the part only has one frame.  """
        return self.first == self.last

    @property
    def is_double(self):
        """If the part only has two frame.  """

        return abs(self.last - self.first) == self.increment

    def __add__(self, other):
        return self.concact(other)

    def concact(self, other):
        """Get concated part with other part.  """

        assert isinstance(other, _FrameRangePart), type(other)

        if self.is_single and other.is_single:
            first, last = sorted([self.first, other.first])
            increment = last - first
        elif self.is_single and other.first - other.increment == self.first:
            first = self.first
            last = other.last
            increment = other.increment
        elif self.is_single and other.last + other.increment == self.first:
            first = other.first
            last = self.first
            increment = other.increment
        elif other.is_single and self.last + self.increment == other.first:
            first = self.first
            last = other.first
            increment = self.increment
        elif other.is_single and self.first - self.increment == other.first:
            first = other.first
            last = self.last
            increment = self.increment
        elif self.increment == other.increment and (self.last + self.increment == other.first
                                                    or self.first - self.increment == other.last):
            first = min(self.first, other.first)
            last = max(self.last, other.last)
            increment = self.increment
        elif self.is_double and self.last + other.increment == other.first:
            return [_FrameRangePart(first=self.first,
                                    last=self.first,
                                    increment=1),
                    _FrameRangePart(first=self.last,
                                    last=other.last,
                                    increment=other.increment)]
        elif self.is_double:
            return [_FrameRangePart(first=self.first,
                                    last=self.first,
                                    increment=1),
                    _FrameRangePart(first=self.last,
                                    last=self.last,
                                    increment=1),
                    other]
        else:
            return [self, other]
        return [_FrameRangePart(first=first, last=last, increment=increment)]


@six.python_2_unicode_compatible
class FrameRange(set):
    """Nuke style frame range list.  """

    def __str__(self):
        """Nuke style frame range representation.  """
        return ' '.join(_format_part(i) for i in self._iter_parts())

    def _iter_parts(self):
        frames = sorted(self)
        parts = (_FrameRangePart(first=i, last=i, increment=1) for i in frames)
        if (len(frames) <= 1
                or (len(frames) == 2
                    and frames[1] - frames[0] != 1)):
            return parts
        return reduce(_concat_part, parts)

    def __add__(self, other):
        return self.union(other)

    @classmethod
    def parse(cls, text):
        """Get framerange from text.  """

        def _int(obj):
            if obj is None:
                return obj
            return int(obj)

        ret = []
        for i in text.split(' '):

            match = re.match(r'(-?\d+)(?:-(-?\d+))?(?:x(-?\d+))?', i)
            if not match:
                raise ValueError('Can not parse.', i)
            first, last, increment = [_int(i) for i in match.groups()]
            if last is None:
                ret.append(first)
            else:
                ret.extend(list(range(first, last + 1, increment or 1)))
        return cls(ret)


def _format_part(part):
    assert isinstance(part, _FrameRangePart), type(part)
    if part.is_single:
        ret = six.text_type(part.first)
    else:
        ret = '{}-{}'.format(part.first, part.last)

    if part.increment != 1:
        ret += 'x{}'.format(part.increment)

    return ret


def _concat_part(base, part):
    assert isinstance(part, _FrameRangePart), type(part)
    if isinstance(base, _FrameRangePart):
        return base.concact(part)
    last = base[-1]
    assert isinstance(last, _FrameRangePart), type(last)

    return base[:-1] + last.concact(part)
