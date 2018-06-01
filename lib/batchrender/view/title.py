# -*- coding=UTF-8 -*-
"""GUI mainwindow.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import logging

from Qt.QtCore import QTimer

from ..__about__ import __version__
from ..control import Controller
LOGGER = logging.getLogger(__name__)


class Title(object):
    """Window title.  """

    default_title = 'Nuke批渲染'

    def __init__(self, control, parent):
        assert isinstance(control, Controller), type(control)

        self.parent = parent
        self.control = control

        self.prefix = ''
        self.title_index = 0
        self.progress = 0

        self._timer = QTimer()
        self._timer.setInterval(300)
        self._timer.timeout.connect(self.update)

        self.control.queue.changed.connect(self.update_prefix)
        self.control.slave.progressed.connect(self.on_progressed)
        self.control.slave.started.connect(self.on_started)
        self.control.slave.finished.connect(self.on_stopped)

    def on_started(self):
        self._timer.start()
        self.update_prefix()

    def on_stopped(self):
        self._timer.stop()
        self.update_prefix()

    def on_progressed(self, value):
        self.progress = value
        self.update_prefix()

    def update_prefix(self):
        """Update title prefix with progress.  """

        result = ''
        control = self.control
        queue_length = len(list(control.model.iter_checked()))

        if queue_length:
            result = '[{}]'.format(queue_length)
        if control.slave.is_rendering:
            result = '{}%{}'.format(self.progress, result)

        if result != self.prefix:
            self.prefix = result
            self.update()

    def update(self):
        """Update title, rotate when rendering.  """

        task = self.control.slave.task
        if task:
            title = task.label or self.default_title
            self.title_index += 1
            index = self.title_index % len(title)
        else:
            title = self.default_title
            self.title_index = 0
            index = 0

        title = '{}{} {}'.format(
            self.prefix, title[index:], title[:index])

        self.parent.setWindowTitle(title)
