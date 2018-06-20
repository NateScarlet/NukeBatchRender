# -*- coding=UTF-8 -*-
"""External actions.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import logging
import sys
from subprocess import CREATE_NEW_CONSOLE, PIPE, Popen, call

from Qt.QtWidgets import QMessageBox

from . import filetools
from .codectools import get_unicode, get_encoded as e

LOGGER = logging.getLogger('actions')


def hiber():
    """Hibernate this computer.  """

    LOGGER.info('休眠')
    proc = Popen('SHUTDOWN /H', stderr=PIPE)
    stderr = get_unicode(proc.communicate()[1])
    LOGGER.error(stderr)
    if '没有启用休眠' in stderr:
        LOGGER.info('没有启用休眠, 转为使用关机')
        shutdown()


def shutdown():
    """Shutdown this computer.  """

    LOGGER.info('关机')
    if sys.platform == 'win32':
        call('SHUTDOWN /S')
        QMessageBox.information(None, '关机', '即将关机, 按OK以取消关机')
        LOGGER.info('用户取消关机')
        call('SHUTDOWN /A')
    else:
        call('shutdown')


def convert_to_mov(src, dst, start_number):
    """Convert sequence to mov, use ffmpeg.  """

    try:
        filetools.popen(['ffmpeg', '-version'])
    except OSError:
        raise RuntimeError('FFmpeg is not installed.')
    command = ['ffmpeg', '-y',
               '-gamma', '2.2',
               '-pix_fmt', 'yuv420p',
               '-start_number', start_number,
               '-i', src,
               '-vcodec', 'prores', '-profile:3',
               '-o', dst]
    kwargs = {}
    if sys.platform == 'win32':
        kwargs['creationflags'] = CREATE_NEW_CONSOLE
        command = ['cmd', '/c'] + command + ['||', 'PAUSE']
    command = [e(i) for i in command]
    filetools.popen(command, **kwargs)
