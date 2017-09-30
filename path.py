
# -*- coding=UTF-8 -*-
"""Path handling.  """
from __future__ import print_function, unicode_literals
OS_ENCODING = __import__('locale').getdefaultlocale()[1]


def get_unicode(string, codecs=('GBK', 'UTF-8', OS_ENCODING)):
    """Return unicode by try decode @string with @codecs.  """

    if isinstance(string, unicode):
        return string

    for i in codecs:
        try:
            return unicode(string, i)
        except UnicodeDecodeError:
            continue
