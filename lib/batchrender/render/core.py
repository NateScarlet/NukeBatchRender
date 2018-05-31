# -*- coding=UTF-8 -*-
"""Task rendering.  """

import logging
import threading
from abc import abstractmethod
from functools import wraps

import six
from Qt.QtCore import QObject, Signal

from ..config import stylize

LOGGER = logging.getLogger(__name__)


class RenderObject(QObject):
    """Base render object.  """

    stopping = False
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

    def __init__(self):
        super(RenderObject, self).__init__()

        # Singals.
        self.changed.connect(self.on_changed)
        self.progressed.connect(self.on_progressed)
        self.time_out.connect(self.on_time_out)
        self.started.connect(lambda: self.progressed.emit(0))
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

    @abstractmethod
    def on_changed(self):
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


def run_async(func):
    """Run func in thread.  """

    @wraps(func)
    def _func(*args, **kwargs):
        thread = threading.Thread(target=func, args=args, kwargs=kwargs)
        thread.start()
        return thread
    return _func


def timef(seconds):
    """Return a nice representation fo given seconds.

    >>> print(timef(10.123))
    10.123秒
    >>> print(timef(100))
    1分40秒
    >>> print(timef(100000))
    27小时46分40秒
    >>> print(timef(1.23456789))
    1.235秒
    """

    ret = ''
    hour = seconds // 3600
    minute = seconds % 3600 // 60
    seconds = round((seconds % 60 * 1000)) / 1000
    if int(seconds) == seconds:
        seconds = int(seconds)
    if hour:
        ret += '{:.0f}小时'.format(hour)
    if minute:
        ret += '{:.0f}分'.format(minute)
    ret += '{}秒'.format(seconds)
    return ret
