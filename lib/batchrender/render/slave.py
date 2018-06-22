# -*- coding=UTF-8 -*-
"""NukeTask rendering.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import logging

from Qt.QtCore import QTimer

from . import core
from ..config import CONFIG
from .task import NukeTask

LOGGER = logging.getLogger(__name__)


class Slave(core.RenderObject):
    """Render slave.  """

    _task = None

    def __init__(self, queue):
        super(Slave, self).__init__()
        self.is_rendering = False
        self.queue = queue

        # Time out timer.
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(self.time_out)
        self._time_out_timer = timer
        self._task_signals = [
            ('progressed', self.progressed),
            ('frame_finished', self.on_frame_finished),
            ('finished', self._start_next),
            ('stdout', self.stdout),
            ('stderr', self.stderr),
            ('aborted', self.aborted),
            ('remains_changed', self.queue.update_remains),
        ]

    @property
    def task(self):
        """Current render task.  """

        return self._task

    @task.setter
    def task(self, value):
        assert value is None or isinstance(value, NukeTask), value

        def _apply_on_signals(task, method):
            if not isinstance(task, NukeTask):
                return
            for i in self._task_signals:
                signal, slot = i
                getattr(getattr(task, signal), method)(slot)

        old = self._task
        _apply_on_signals(value, 'connect')
        self._task = value
        _apply_on_signals(old, 'disconnect')

    def _start_next(self):
        try:
            task = self.queue.get()
            assert isinstance(task, NukeTask)
            self.task = task
            task.run()
        except StopIteration:
            self.task = None
            self.finished.emit()
            self.is_rendering = False

    def start(self):
        """Overridde.  """

        if self.is_rendering:
            return

        self.is_rendering = True
        self._start_next()
        self.started.emit()

    def stop(self):
        """Stop rendering.  """

        self.is_stopping = True
        task = self.task
        if isinstance(task, NukeTask):
            task.stop()

    def on_started(self):
        LOGGER.debug('Render start')
        self._start_timeout_timer()

    def on_aborted(self):
        LOGGER.debug('Render aborted.')
        self.task = None

    def on_stopped(self):
        LOGGER.debug('Render stopped.')
        self.is_rendering = False
        self.is_stopping = False
        self._stop_timeout_timer()

    def on_finished(self):
        LOGGER.debug('Render finished.')

    def on_time_out(self):
        task = self.task
        if isinstance(task, NukeTask):
            task.priority -= 1
            task.stop()

    def on_frame_finished(self, payload):
        # Restart timeout timer.

        frame = payload['frame']
        total = payload['total']

        self._stop_timeout_timer()
        if frame != total:
            self._start_timeout_timer()

    def _start_timeout_timer(self):
        time_out = CONFIG['TIME_OUT']
        if time_out > 0:
            self._time_out_timer.start(time_out * 1000)

    def _stop_timeout_timer(self):
        timer = self._time_out_timer
        if timer.isActive():
            timer.stop()
