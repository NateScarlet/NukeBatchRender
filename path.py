# -*- coding=UTF-8 -*-
"""pathname manipulations. """

import os
import re
import locale

__version__ = '0.1.0'


def expand_frame(filename, frame):
    '''Return a frame mark expaned version of filename, with given frame.

    >>> expand_frame('test_sequence_###.exr', 1)
    'test_sequence_001.exr'
    >>> expand_frame('test_sequence_369.exr', 1)
    'test_sequence_369.exr'
    >>> expand_frame('test_sequence_%03d.exr', 1234)
    'test_sequence_1234.exr'
    >>> expand_frame('test_sequence_%03d.###.exr', 1234)
    'test_sequence_1234.1234.exr'
    '''
    def _format_repl(matchobj):
        return matchobj.group(0) % frame

    def _hash_repl(matchobj):
        return '%0{}d'.format(len(matchobj.group(0)))
    ret = filename
    ret = re.sub(r'(\#+)', _hash_repl, ret)
    ret = re.sub(r'(%0?\d*d)', _format_repl, ret)
    return ret


def split_version(f):
    """Return nuke style _v# (shot, version number) pair.

    >>> split_version('sc_001_v20.nk')
    ('sc_001', 20)
    >>> split_version('hello world')
    ('hello world', None)
    >>> split_version('sc_001_v-1.nk')
    ('sc_001_v-1', None)
    >>> split_version('sc001V1.jpg')
    ('sc001', 1)
    >>> split_version('sc001V1_no_bg.jpg')
    ('sc001', 1)
    >>> split_version('suv2005_v2_m.jpg')
    ('suv2005', 2)
    """

    match = re.match(r'(.+)v(\d+)', f, flags=re.I)
    if not match:
        return (os.path.splitext(f)[0], None)
    shot, version = match.groups()
    return (shot.strip('_'), int(version))


def remove_version(path):
    """Return filename without version number.

    >>> remove_version('sc_001_v233.jpg')
    'sc_001.jpg'
    """
    shot = split_version(path)[0]
    ext = os.path.splitext(path)[1]
    return '{}{}'.format(shot, ext)


def get_footage_name(path):
    """Return filename without frame number.

    >>> get_footage_name('sc_001_BG.0034.exr')
    'sc_001_BG'
    >>> get_footage_name('sc_001_BG.%04d.exr')
    'sc_001_BG'
    >>> get_footage_name('sc_001_BG.###.exr')
    'sc_001_BG'
    >>> get_footage_name('sc_001._BG.exr')
    'sc_001._BG'
    """
    ret = path
    ret = re.sub(r'\.\d+\b', '', ret)
    ret = re.sub(r'\.#+(?=\.)', '', ret)
    ret = re.sub(r'\.%0?\d*d\b', '', ret)
    ret = os.path.splitext(ret)[0]
    return ret


def get_unicode(input_str, codecs=('UTF-8', 'GBK')):
    """Return unicode by try decode @string with @codecs.  """

    if isinstance(input_str, unicode):
        return input_str

    for i in tuple(codecs) + tuple(locale.getdefaultlocale()[1]):
        try:
            return unicode(input_str, i)
        except UnicodeDecodeError:
            continue


def get_encoded(input_str, encoding=None):
    """Return unicode by try decode @string with @encodeing.  """
    if encoding is None:
        encoding = locale.getdefaultlocale()[1]

    return get_unicode(input_str).encode(encoding)


def is_ascii(text):
    """Return true if @text can be convert to ascii.

    >>> is_ascii('a')
    True
    >>> is_ascii('测试')
    False

    """
    try:
        get_unicode(text).encode('ASCII')
        return True
    except UnicodeEncodeError:
        return False


def escape_batch(text):
    """Return escaped text for windows shell.

    >>> escape_batch('test_text "^%~1"')
    u'test_text \\\\"^^%~1\\\\"'
    >>> escape_batch(u'中文 \"^%1\"')
    u'\\xe4\\xb8\\xad\\xe6\\x96\\x87 \\\\"^^%1\\\\"'
    """

    return text.replace(u'^', u'^^').replace(u'"', u'\\"').replace(u'|', u'^|')
