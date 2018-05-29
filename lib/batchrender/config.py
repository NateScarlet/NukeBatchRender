# -*- coding=UTF-8 -*-
"""Config file on disk.  """
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import json
import logging
import os
import re
import sys

from .path import get_unicode


LOGGER = logging.getLogger('config')
CONSOLE_STYLE = ''

if sys.platform == 'win32':
    import locale
    locale.setlocale(locale.LC_ALL, str('chinese'))

if getattr(sys, 'frozen', False):
    __file__ = os.path.join(getattr(sys, '_MEIPASS', ''), __file__)


def _update_style():
    path = os.path.join(os.path.dirname(__file__), 'console.css')
    with open(path) as f:
        style = '<style>{}</style>'.format(f.read())
    setattr(sys.modules[__name__], 'CONSOLE_STYLE', style)


_update_style()


class Config(dict):
    """A config file can be manipulated that automatic write and read json file on disk."""

    default = {
        'NUKE': r'C:\Program Files\Nuke10.0v4\Nuke10.0.exe',
        'DEADLINE': r'C:\Program Files\Thinkbox\Deadline7\bin\deadlineslave.exe',
        'DIR': os.path.expanduser('~/.nuke/batchrender'),
        'AFTER_FINISH': 0,
        'AFTER_FINISH_CMD': '',
        'AFTER_FINISH_PROGRAM': '',
        'PROXY': 0,
        'LOW_PRIORITY': 2,
        'CONTINUE': 2,
        'HIBER': 0,
        'MEMORY_LIMIT': 10.0,
        'THREADS': 4,
        'TIME_OUT': 600
    }
    path = os.path.expanduser('~/.nuke/.batchrender.json')
    _log_path = None
    instance = None

    def __new__(cls):
        # Singleton
        if not cls.instance:
            cls.instance = super(Config, cls).__new__(cls)
        return cls.instance

    def __init__(self):
        super(Config, self).__init__()
        self.update(dict(self.default))
        self.read()

    def __setitem__(self, key, value):
        LOGGER.debug('%s = %s', key, value)
        dict.__setitem__(self, key, value)
        self.write()

    def write(self):
        """Write config to disk."""

        with open(self.path, 'w') as f:
            json.dump(self, f, indent=4, sort_keys=True)

    def read(self):
        """Read config from disk."""

        if os.path.isfile(self.path):
            with open(self.path) as f:
                self.update(dict(json.load(f)))

    @property
    def log_path(self):
        """Log save path.  """

        if not self._log_path:
            working_dir = self['DIR']
            if not os.path.isdir(working_dir):
                working_dir = os.path.expanduser('~/.nuke/batchrender')
            self._log_path = os.path.join(working_dir, 'Nuke批渲染.log')

        return self._log_path

    def update(self, other):
        """Type checked update.  """
        assert isinstance(other, dict)
        other = dict(other)
        for k in self.keys():
            if other.has_key(k):
                other_type = type(other[k])
                self_type = type(self[k])
                if other_type != self_type:
                    logging.warning('config: Key %s should be %s, got %s. ignored.',
                                    k, self_type, other_type)
                    del other[k]
        dict.update(self, other)


CONFIG = Config()


def l10n(text):
    """Translate error info to chinese."""
    if not isinstance(text, (str, unicode)):
        LOGGER.debug('Try localization non-str: %s', text)
        return text

    ret = get_unicode(text).strip('\r\n')

    with open(os.path.join(os.path.dirname(__file__), 'batchrender.zh_CN.json')) as f:
        translate_dict = json.load(f)
    for k, v in translate_dict.iteritems():
        try:
            ret = re.sub(k, v, ret)
        except TypeError as ex:
            LOGGER.debug('l10n fail: re.sub(%s, %s, %s)\n %s', k, v, ret, ex)
    return ret


def stylize(text, text_type=None):
    """Stylelize text for text edit"""

    if text_type:
        text = '<span class={}>{}</span>'.format(get_unicode(text_type), text)
    return CONSOLE_STYLE + text
