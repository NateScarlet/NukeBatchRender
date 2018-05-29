# -*- coding=UTF-8 -*-
"""GUI mainwindow.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import logging
import logging.handlers
import os
import sys

from Qt.QtCore import Qt, QTimer
from Qt.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QLineEdit,
                          QSpinBox)

from .. import render
from ..__about__ import __version__
from ..config import CONFIG

LOGGER = logging.getLogger()


class Title(object):
    """Window title.  """
    default_title = 'Nuke批渲染'
    prefix = ''
    title_index = 0

    def __init__(self, parent):
        self.title_index = 0
        from .mainwindow import MainWindow
        assert isinstance(
            parent, MainWindow), 'Need a Mainwindow as parent.'
        self.parent = parent

        self._timer = QTimer()
        self._timer.setInterval(300)
        self._timer.timeout.connect(self.update)
        setattr(self.parent, '_title', self)

        self.parent.control.queue.changed.connect(self.update_prefix)
        self.parent.progressBar.valueChanged.connect(self.update_prefix)

        self.parent.control.slave.started.connect(self._timer.start)
        self.parent.control.slave.finished.connect(self._timer.stop)

        self.update()

    def update_prefix(self):
        """Update title prefix with progress.  """

        prefix = ''
        queue_length = len(list(self.parent.queue.enabled_tasks()))

        if queue_length:
            prefix = '[{}]{}'.format(queue_length, prefix)
        if self.parent.slave.rendering:
            prefix = '{}%{}'.format(
                self.parent.progressBar.value(), prefix)

        if prefix != self.prefix:
            self.prefix = prefix
            self.update()

    def update(self):
        """Update title, rotate when rendering.  """

        slave = self.parent.control.slave
        if slave.rendering:
            task = slave.task
            assert isinstance(task, render.Task)
            title = task.filename.partition('.nk')[0] or self.default_title
            self.title_index += 1
            index = self.title_index % len(title)
        else:
            title = self.default_title
            self.title_index = 0
            index = 0

        title = '{}{} {}'.format(
            self.prefix, title[index:], title[:index])

        self.parent.setWindowTitle(title)
