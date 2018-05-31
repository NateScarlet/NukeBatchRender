# -*- coding=UTF-8 -*-
"""Task rendering.  """

import logging
from abc import abstractmethod

import six
from Qt.QtCore import QObject, Signal

from ..texttools import stylize
LOGGER = logging.getLogger(__name__)


class RenderObject(QObject):
    """Base render object.  """

    is_stopping = False
    _remains = None

    # Signals.
    changed = Signal()
    started = Signal()
    stopped = Signal()
    finished = Signal()
    time_out = Signal()
    progressed = Signal(int)
    stdout = Signal(six.text_type)
    stderr = Signal(six.text_type)
    remains_changed = Signal(float)

    def __init__(self, parent=None):
        super(RenderObject, self).__init__(parent)

        # Singals.
        self.finished.connect(self.stopped)
        self.changed.connect(self.on_changed)
        self.progressed.connect(self.on_progressed)
        self.time_out.connect(self.on_time_out)
        self.started.connect(lambda: self.progressed.emit(0))
        self.started.connect(self.on_started)
        self.stopped.connect(self.on_stopped)
        self.finished.connect(self.on_finished)
        self.stdout.connect(self.on_stdout)
        self.stderr.connect(self.on_stderr)

    def info(self, text):
        """Send info to stdout.  """

        LOGGER.info('%s: %s', self, text)
        self.stdout.emit(stylize(text, 'info'))

    def error(self, text):
        """Send error to stderr.  """

        LOGGER.error('%s: %s', self, text)
        self.stderr.emit(stylize(text, 'error'))

    @property
    def remains(self):
        """Time remains of this.  """

        return self._remains

    @remains.setter
    def remains(self, value):
        if value == self._remains:
            return

        self._remains = value
        self.remains_changed.emit(value)

    @abstractmethod
    def on_changed(self):
        pass

    @abstractmethod
    def on_started(self):
        pass

    @abstractmethod
    def on_stopped(self):
        pass

    @abstractmethod
    def on_finished(self):
        pass

    @abstractmethod
    def on_time_out(self):
        pass

    @abstractmethod
    def on_progressed(self, value):
        pass

    @abstractmethod
    def on_stdout(self, msg):
        pass

    @abstractmethod
    def on_stderr(self, msg):
        pass
