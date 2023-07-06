
# -*- coding=UTF-8 -*-
"""Coding decoding tools.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import locale
import sys

import six


def get_unicode(input_bytes, codecs=('UTF-8', 'GBK')):
    """Return unicode string by try decode @input_bytes with @codecs.  """

    if isinstance(input_bytes, int):
        return six.text_type(input_bytes)

    if isinstance(input_bytes, six.text_type):
        return input_bytes

    try:
        input_bytes = six.binary_type(input_bytes)
    except (TypeError, ValueError):
        return six.text_type(input_bytes)

    try:
        return input_bytes.decode()
    except UnicodeDecodeError:
        for i in tuple(codecs) + (sys.getfilesystemencoding(), locale.getdefaultlocale()[1]):
            try:
                return six.text_type(input_bytes, i)
            except UnicodeDecodeError:
                continue
        raise


def get_encoded(input_str, encoding=None):
    """Return unicode by try decode @string with @encodeing.  """

    return get_unicode(input_str).encode(encoding or sys.getfilesystemencoding())
