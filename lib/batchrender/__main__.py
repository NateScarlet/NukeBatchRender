#! /usr/bin/env python2
# -*- coding=UTF-8 -*-
"""GUI batchrender for nuke.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import atexit
import logging
import os
import sys
from subprocess import call

from Qt.QtWidgets import QApplication

from . import singleton
from .__about__ import __version__
from .codectools import get_encoded
from .log import _set_logger
from .view import MainWindow

LOGGER = logging.getLogger()


def main():
    setattr(sys.modules[__name__], '__SINGLETON', singleton.SingleInstance())
    _set_logger()

    if sys.getdefaultencoding() != 'UTF-8':
        reload(sys)
        sys.setdefaultencoding('UTF-8')

    if getattr(sys, 'frozen', False):
        os.environ['QT_PREFERRED_BINDING'] = 'PySide'

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
