# -*- coding=UTF-8 -*-
"""GUI mainwindow.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import logging

from PySide2.QtCore import QObject, QTimer

from ..__about__ import __version__
from ..control import Controller
from ..mixin import UnicodeTrMixin

LOGGER = logging.getLogger(__name__)


class Title(UnicodeTrMixin, QObject):
    """Window title.  """

    def __init__(self, control, parent):
        assert isinstance(control, Controller), type(control)
        super(Title, self).__init__(parent)

        self.parent = parent
        self.control = control

        self.prefix = ''
        self.title_index = 0
        self.progress = 0

        self._timer = QTimer()
        self._timer.setInterval(300)
        self._timer.timeout.connect(self.rotate_text)

        self.control.queue.changed.connect(self.update_prefix)
        self.control.slave.progressed.connect(self.on_progressed)
        self.control.slave.started.connect(self.on_started)
        self.control.slave.stopped.connect(self.on_stopped)

    def on_started(self):
        self._timer.start()
        self.update_prefix()

    def on_stopped(self):
        self._timer.stop()
        self.update_prefix()

    def on_progressed(self, value):
        self.progress = value
        self.update_prefix()

    @property
    def text(self):
        """Title text.  """

        task = self.control.slave.task
        if task:
            return task.label
        self.title_index = 0
        return self.tr('NukeBatchRender')

    def rotate_text(self):
        """Rotate title text.  """

        self.title_index += 1
        self.update()

    def update_prefix(self):
        """Update title prefix with progress.  """

        control = self.control
        queue_length = len(list(control.model.iter_checked()))

        def _format_length(length):
            return '[{}]'.format(queue_length) if length else ''

        if control.slave.is_rendering:
            result = '{}%{}'.format(self.progress,
                                    _format_length(queue_length-1))
        elif queue_length:
            result = _format_length(queue_length)
        else:
            result = ''

        if result != self.prefix:
            self.prefix = result
            self.update()

    def update(self):
        """Update title, rotate when rendering.  """

        text = self.text
        index = self.title_index % len(text)
        text = '{}{} {}'.format(self.prefix, text[index:], text[:index])

        self.parent.setWindowTitle(text)
