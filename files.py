#! /usr/bin/env python2
# -*- coding=UTF-8 -*-
"""Task rendering.  """

from __future__ import absolute_import, print_function, unicode_literals

import datetime
import logging
import os
from os.path import basename, isabs, join
import shutil
import subprocess
import sys

from path import get_encoded, get_unicode, version_filter
from config import CONFIG
LOGGER = logging.getLogger('render')


class Files(list):
    """(Single instance)Files that need to be render.

    attribute:
        path_method: should be a function return a vaild filepath.
    """
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
        path = get_unicode(CONFIG['DIR'])
        _files = sorted([join(path, get_unicode(i)) for i in os.listdir(get_encoded(path))
                         if get_unicode(i).endswith('.nk')],
                        key=os.path.getmtime,
                        reverse=False)
        self.extend(_files)

    def archive(self, f, dest='文件备份'):
        """Archive file in a folder with time struture.  """

        LOGGER.debug('Archiving file: %s -> %s', f, dest)
        now = datetime.datetime.now()
        dest = join(CONFIG['DIR'], dest, get_unicode(now.strftime(
            get_encoded('%y-%m-%d_%A/%H时%M分/'))))

        copy(f, dest)

    def old_version_files(self):
        """Files that already has higher version.  """

        ret = [i for i in self if i not in version_filter(self)]
        return ret

    def remove(self, f):
        """Archive file then remove it.  """

        self.archive(f)
        if not isabs(f):
            os.remove(get_encoded(self[f]))


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
