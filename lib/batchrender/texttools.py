# -*- coding=UTF-8 -*-
"""Console tools.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import json
import logging
import os
import re
import sys

from . import filetools
from .codectools import get_unicode as u

LOGGER = logging.getLogger(__name__)

CONSOLE_STYLE = ''


def _update_style():
    with open(filetools.path('console.css')) as f:
        style = '<style>{}</style>'.format(f.read())
    setattr(sys.modules[__name__], 'CONSOLE_STYLE', style)


_update_style()


def l10n(text):
    """Translate error info to chinese."""
    if not isinstance(text, (str, unicode)):
        LOGGER.debug('Try localization non-str: %s', text)
        return text

    ret = u(text).strip('\r\n')

    with open(os.path.join(os.path.dirname(__file__), 'batchrender.zh_CN.json')) as f:
        translate_dict = json.load(f)
    for k, v in translate_dict.iteritems():
        try:
            ret = re.sub(k, v, ret)
        except TypeError as ex:
            LOGGER.debug('l10n fail: re.sub(%s, %s, %s)\n %s', k, v, ret, ex)
    return ret


def stylize(text, css_class=None):
    """Stylelize text for text edit"""

    if css_class:
        text = '<span class={}>{}</span>'.format(
            u(css_class), u(text))
    return CONSOLE_STYLE + text


def timef(seconds, digits=None):
    """Return a nice representation fo given seconds.

    >>> print(timef(10.123))
    10.123秒
    >>> print(timef(100))
    1分40秒
    >>> print(timef(100000))
    27小时46分40秒
    >>> print(timef(1.23456789, 3))
    1.235秒
    """

    hour = seconds // 3600
    minute = seconds % 3600 // 60
    seconds = seconds % 60
    if digits is not None:
        seconds = round(seconds, digits)
    if int(seconds) == seconds:
        seconds = int(seconds)

    ret = ''
    if hour:
        ret += '{:.0f}小时'.format(hour)
    if minute:
        ret += '{:.0f}分'.format(minute)
    ret += '{}秒'.format(seconds)
    return ret
