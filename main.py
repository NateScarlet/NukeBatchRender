#! /usr/bin/env python2
# -*- coding=UTF-8 -*-
"""GUI batchrender for nuke.  """

from __future__ import absolute_import, print_function, unicode_literals

import atexit
import logging
import sys
import os
from subprocess import call

import singleton
from log import _set_logger
from path import get_encoded

LOGGER = logging.getLogger()
if __name__ == '__main__':
    __SINGLETON = singleton.SingleInstance()


def main():
    _set_logger()

    if getattr(sys, 'frozen', False):
        os.environ['QT_PREFERRED_BINDING'] = 'PySide'

    from __version__ import __version__
    from mainwindow import QApplication, MainWindow

    atexit.register(lambda: LOGGER.debug('Python exit.'))
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    if sys.platform == 'win32':
        call(get_encoded('TITLE 批渲染.console v{}'.format(__version__)), shell=True)

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
