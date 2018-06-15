# -*- coding=UTF-8 -*-
"""Frame range test.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import six

from batchrender import framerange


def test_framerange():
    cases = [
        ([0], '0'),
        ([1, 2, 3, 4], '1-4'),
        ([1, 2, 3, 5, 6], '1-3 5-6'),
        ([1, 3, 5, 7, 9], '1-9x2'),
        ([1, 3, 5, 7, 9, 10, 11], '1-9x2 10-11'),
        ([-1, 0, 1, 3, 5, 7, 9, 10, 11], '-1-1 3-9x2 10-11'),
    ]
    for frames, range_text in cases:
        frange = framerange.FrameRange(frames)
        assert six.text_type(frange) == range_text
        assert framerange.FrameRange.parse(range_text) == frange
