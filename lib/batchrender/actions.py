# -*- coding=UTF-8 -*-
"""After render actions.  """
from __future__ import print_function, unicode_literals

import sys
import logging
from subprocess import PIPE, Popen, call
from path import get_unicode

from Qt.QtWidgets import QMessageBox

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
