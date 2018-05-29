# -*- coding=UTF-8 -*-
"""Task rendering.  """

import logging

from Qt.QtCore import QTimer

from . import core
from ..config import CONFIG
from .task import Task

LOGGER = logging.getLogger(__name__)


class Slave(core.RenderObject):
    """Render slave.  """

    _task = None
    rendering = False

    def __init__(self):
        super(Slave, self).__init__()

        # Time out timer.
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(self.time_out)
        self._time_out_timer = timer

    @property
    def task(self):
        """Current render task.  """

        return self._task

    @task.setter
    def task(self, value):
        assert value is None or isinstance(value, Task), value

        old = self._task
        if isinstance(old, Task):
            old.progressed.disconnect(self.progressed)
        if isinstance(value, Task):
            value.progressed.connect(self.progressed)
        self._task = value

    @core.run_async
    def start(self, queue):
        """Overridde.  """

        if self.rendering or self.stopping:
            return

        self.rendering = True

        LOGGER.debug('Render start')
        self.started.emit()

        while queue and not self.stopping:
            LOGGER.debug('Rendering queue:\n%s', queue)
            try:
                task = queue.get()
                assert isinstance(task, Task)
                self.task = task
                task.run()
            except Exception:
                LOGGER.error('Exception during render.', exc_info=True)
                raise

        if not self.stopping:
            self.finished.emit()
        self.stopped.emit()

    def stop(self):
        """Stop rendering.  """

        self.stopping = True
        task = self.task
        if isinstance(task, Task):
            task.stop()

    def on_stopped(self):
        LOGGER.debug('Render stopped.')
        self._time_out_timer.stop()
        self.rendering = False
        self.stopping = False
        self.task = None

    def on_finished(self):
        LOGGER.debug('Render finished.')

    def on_time_out(self):
        task = self.task
        self.error(u'{}: 渲染超时'.format(task))
        if isinstance(task, Task):
            task.priority -= 1
            task.stop()

    def on_progressed(self, value):
        timer = self._time_out_timer
        timer.stop()

        if CONFIG['LOW_PRIORITY']:
            # Restart timeout timer.
            time_out = CONFIG['TIME_OUT'] * 1000

            if time_out > 0 and value < 100:
                timer.start(time_out)


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
