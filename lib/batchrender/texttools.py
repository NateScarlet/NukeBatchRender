# -*- coding=UTF-8 -*-
"""Console tools.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import logging

from . import filetools
from .codectools import get_unicode as u

LOGGER = logging.getLogger(__name__)


def _read_style():
    with open(filetools.path('console.css')) as f:
        return '<style>{}</style>'.format(f.read())


CONSOLE_STYLE = _read_style()


def stylize(text, css_class=None):
    """Stylelize text for text edit"""

    if css_class:
        text = '<span class={}>{}</span>'.format(
            u(css_class), u(text))
    return CONSOLE_STYLE + text
