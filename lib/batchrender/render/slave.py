# -*- coding=UTF-8 -*-
"""Task rendering.  """

import logging

from Qt.QtCore import QTimer

from . import core
from ..config import CONFIG
from .task import Task
from.. import database

LOGGER = logging.getLogger(__name__)


class Slave(core.RenderObject):
    """Render slave.  """

    _task = None

    def __init__(self):
        super(Slave, self).__init__()
        self.rendering = False

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
        with database.core.session_scope() as sess:
            while not self.stopping:
                task = queue.get(sess)
                if not task:
                    break
                assert isinstance(task, Task)
                LOGGER.debug('Rendering queue:\n%s', queue)
                try:
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
