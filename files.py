#! /usr/bin/env python2
# -*- coding=UTF-8 -*-
"""Task rendering.  """

from __future__ import print_function, unicode_literals

import datetime
import logging
import os
import re
import shutil
import subprocess
import sys

from path import get_encoded, get_unicode, version_filter

LOGGER = logging.getLogger('render')


class Files(list):
    """(Single instance)Files that need to be render.  """
    instance = None

    def __new__(cls):
        if not cls.instance:
            cls.instance = super(Files, cls).__new__(cls)
        return cls.instance

    def __init__(self):
        super(Files, self).__init__()
        self.update()

    def update(self):
        """Update self from renderable files in dir.  """

        del self[:]
        _files = sorted([get_unicode(i) for i in os.listdir(os.getcwd())
                         if get_unicode(i).endswith(('.nk', '.nk.lock'))],
                        key=os.path.getmtime,
                        reverse=False)
        self.extend(_files)
        self.all_locked = self and all(bool(i.endswith('.lock')) for i in self)

    @staticmethod
    def archive(f, dest='文件备份'):
        """Archive file in a folder with time struture.  """
        LOGGER.debug('Archiving file: %s -> %s', f, dest)
        now = datetime.datetime.now()
        dest = os.path.join(
            dest,
            get_unicode(now.strftime(
                get_encoded('%y-%m-%d_%A/%H时%M分/'))))

        copy(f, dest)

    def old_version_files(self):
        """Files that already has higher version.  """

        newest = version_filter(self)
        ret = [i for i in self if i not in newest]
        return ret

    @classmethod
    def remove(cls, f):
        """Archive file then remove it.  """

        cls.archive(f)
        if not os.path.isabs(f):
            os.remove(get_encoded(f))

    @staticmethod
    def split_version(f):
        """Return nuke style _v# (shot, version number) pair.

        >>> Files.split_version('sc_001_v20.nk')
        (u'sc_001', 20)
        >>> Files.split_version('hello world')
        (u'hello world', None)
        >>> Files.split_version('sc_001_v-1.nk')
        (u'sc_001_v-1', None)
        >>> Files.split_version('sc001V1.jpg')
        (u'sc001', 1)
        >>> Files.split_version('sc001V1_no_bg.jpg')
        (u'sc001', 1)
        >>> Files.split_version('suv2005_v2_m.jpg')
        (u'suv2005', 2)
        """

        f = os.path.splitext(f)[0]
        match = re.match(r'(.+)v(\d+)', f, flags=re.I)
        if not match:
            return (f, None)
        shot, version = match.groups()
        return (shot.rstrip('_'), int(version))


FILES = Files()


def copy(src, dst):
    """Copy src to dst."""
    src, dst = get_unicode(src), get_unicode(dst)
    LOGGER.info('\n复制:\n\t%s\n->\t%s', src, dst)
    if not os.path.exists(src):
        return
    dst_dir = os.path.dirname(dst)
    if not os.path.exists(dst_dir):
        LOGGER.debug('创建目录: %s', dst_dir)
        os.makedirs(dst_dir)
    try:
        shutil.copy2(src, dst)
    except OSError:
        if sys.platform == 'win32':
            subprocess.call('XCOPY /V /Y "{}" "{}"'.format(src, dst))
        else:
            raise
    if os.path.isdir(dst):
        ret = os.path.join(dst, os.path.basename(src))
    else:
        ret = dst
    return ret
