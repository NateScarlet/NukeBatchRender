#! /usr/bin/env python2
# -*- coding=UTF-8 -*-
"""GUI batchrender for nuke.  """

from __future__ import print_function, unicode_literals

import atexit
import os
import sys
import logging
from subprocess import call
from path import get_encoded

import singleton
from mainwindow import QApplication, MainWindow, DEFAULT_DIR, CONFIG
from log import _set_logger
from __version__ import __version__

LOGGER = logging.getLogger()
if __name__ == '__main__':
    __SINGLETON = singleton.SingleInstance()


def main():
    _set_logger()

    atexit.register(lambda: LOGGER.debug('Python exit.'))
    try:
        os.chdir(CONFIG['DIR'])
        LOGGER.debug('Change dir: %s', os.getcwd())
    except OSError:
        LOGGER.warning('工作目录不可用: %s, 重置为默认位置', CONFIG['DIR'])
        if not os.path.exists(CONFIG['DIR']):
            if not os.path.exists(DEFAULT_DIR):
                os.makedirs(DEFAULT_DIR)
            CONFIG['DIR'] = DEFAULT_DIR
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    if sys.platform == 'win32':
        call(get_encoded('TITLE 批渲染控制台 v{}'.format(__version__)), shell=True)

    frame = MainWindow()
    frame.show()
    sys.exit(app.exec_())
    LOGGER.debug('Exit')


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        pass
    except:
        LOGGER.error('Uncaught exception.', exc_info=True)
        raise
