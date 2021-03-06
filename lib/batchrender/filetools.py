# -*- coding=UTF-8 -*-
"""File tools.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import hashlib
import logging
import os
import re
import shutil
import subprocess
import sys

import six

from .codectools import get_encoded as e
from .codectools import get_unicode as u

LOGGER = logging.getLogger(__name__)
CHUNK_SIZE = 2 * 2 ** 10  # 2MB

if getattr(sys, 'frozen', False):
    __file__ = os.path.join(getattr(sys, '_MEIPASS', ''), __file__)

__dirpath__ = os.path.abspath(os.path.dirname(__file__))


def path(*other):
    """Get path relative to this file.

    Returns:
        str -- Absolute path under file directory.
    """

    return os.path.abspath(os.path.join(__dirpath__, *other))


def filehash(filepath):
    """Get hash from a file.

    Args:
        filepath (str): File path.

    Returns:
        Hash object
    """

    filepath = bytes(filepath, 'utf-8')
    ret = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(CHUNK_SIZE), b''):
            ret.update(chunk)
    return ret


def filehash_hex(filepath):
    """Shortcut function for file hexdigest.

    Args:
        filepath (str): File path.

    Returns:
        str: File hash hexdigest.
    """

    return filehash(filepath).hexdigest()


def copy(src, dst):
    """Copy src to dst."""

    src, dst = u(src), u(dst)
    src_e, dst_e = e(src), e(dst)
    LOGGER.info('\n复制:\n\t%s\n->\t%s', src, dst)
    if not os.path.exists(src_e):
        return None
    dst_dir = os.path.dirname(dst)
    dst_dir_e = e(dst_dir)
    if not os.path.exists(dst_dir_e):
        LOGGER.debug('创建目录: %s', dst_dir)
        os.makedirs(dst_dir_e)
    try:
        shutil.copy2(src_e, dst_e)
    except shutil.Error as ex:
        try:
            if u(ex.args[0]).endswith('are the same file'):
                LOGGER.debug('Same file, skip copy.')
            else:
                raise
        except:
            raise ex
    except OSError:
        if sys.platform == 'win32':
            subprocess.call(e('XCOPY /V /Y "{}" "{}"'.format(src, dst)))
        else:
            raise
    if os.path.isdir(dst_e):
        ret = os.path.join(dst, os.path.basename(src))
    else:
        ret = dst
    return ret


def version_filter(iterable):
    """Keep only newest version for each shot, try compare mtime when version is same.

    >>> version_filter(('sc_001_v1', 'sc_001_v2', 'sc002_v3', 'thumbs.db'))
    [u'sc002_v3', u'sc_001_v2', u'thumbs.db']
    """
    def _num(version):
        return version or -1

    shots = {}
    iterable = sorted(
        iterable, key=lambda x: _num(split_version(x)[1]), reverse=True)
    for i in iterable:
        shot, version = split_version(i)
        version = _num(version)
        shot = shot.lower()
        shots.setdefault(shot, {})
        shots[shot].setdefault('path_list', [])
        max_version = _num(shots[shot].get('version'))
        if version > max_version:
            shots[shot]['path_list'] = [i]
            shots[shot]['version'] = version
        elif version == max_version:
            shots[shot]['path_list'].append(i)

    for shot in shots:
        shots[shot] = sorted(
            shots[shot]['path_list'],
            key=lambda shot:
            os.path.getmtime(shot) if os.path.exists(shot) else None,
            reverse=True)[0]
    return sorted(shots.values())


def split_version(f):
    """Return nuke style _v# (shot, version number) pair.

    >>> split_version('sc_001_v20.nk')
    (u'sc_001', 20)
    >>> split_version('hello world')
    (u'hello world', None)
    >>> split_version('sc_001_v-1.nk')
    (u'sc_001_v-1', None)
    >>> split_version('sc001V1.jpg')
    (u'sc001', 1)
    >>> split_version('sc001V1_no_bg.jpg')
    (u'sc001', 1)
    >>> split_version('suv2005_v2_m.jpg')
    (u'suv2005', 2)
    """

    match = re.match(r'(.+)v(\d+)', f, flags=re.I)
    if not match:
        return (os.path.splitext(f)[0], None)
    shot, version = match.groups()
    return (shot.strip('_'), int(version))


def ensure_parent_directory(filepath):
    """Ensure parents direcotry exsits.  """

    filepath = u(filepath)
    try:
        os.makedirs(e(os.path.dirname(filepath)))
    except OSError:
        pass


def popen(*args, **kwargs):
    """`Subprocess.Popen` with local bin folder injected.  """

    def _inject_bin_folder(env):
        env_path = u(env.get('path', ''))
        env['path'] = u(path('bin') + os.pathsep + env_path)

    kwargs.setdefault('env', os.environ)
    _inject_bin_folder(kwargs['env'])

    return subprocess.Popen(*args, **kwargs)
