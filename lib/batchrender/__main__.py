#! /usr/bin/env python2
# -*- coding=UTF-8 -*-
"""GUI batchrender for nuke.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import atexit
import logging
import sys
from subprocess import call

from Qt import QtCore
from Qt.QtWidgets import QApplication

from . import filetools, mimetool, singleton
from .__about__ import __version__
from .codectools import get_encoded
from .log import _set_logger
from .view import MainWindow

LOGGER = logging.getLogger()


def _set_default_encoding(encoding='utf-8'):
    if sys.getdefaultencoding() != encoding:
        reload(sys)
        sys.setdefaultencoding(encoding)


def install_translator(app):
    """Install translator on app.  """

    translator = QtCore.QTranslator(app)
    translator.load(QtCore.QLocale.system(), "i18n/",
                    directory=filetools.__dirpath__)
    app.installTranslator(translator)


def main():
    setattr(sys.modules[__name__], '__SINGLETON', singleton.SingleInstance())
    _set_default_encoding()
    _set_logger()
    mimetool.setup()

    atexit.register(lambda: LOGGER.debug('Python exit.'))
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    install_translator(app)

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
