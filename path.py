
# -*- coding=UTF-8 -*-
"""Path handling.  """
from __future__ import print_function, unicode_literals
import locale


def get_unicode(input_str, codecs=('UTF-8', 'GBK')):
    """Return unicode by try decode @input_str with @codecs.  """

    if isinstance(input_str, unicode):
        return input_str

    for i in tuple(codecs) + tuple(locale.getdefaultlocale()[1]):
        try:
            return unicode(input_str, i)
        except (UnicodeDecodeError, LookupError):
            continue
    raise UnicodeError(repr(input_str))


def get_encoded(input_str, encoding=None):
    """Return unicode by try decode @input_str with @encodeing.  """
    if encoding is None:
        encoding = locale.getdefaultlocale()[1]

    return get_unicode(input_str).encode(encoding)
