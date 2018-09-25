# -*- coding=UTF-8 -*-
"""NukeTask rendering.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import logging

from Qt.QtCore import QTimer, Signal

from . import core
from .. import model
from ..config import CONFIG
from ..exceptions import AlreadyRendering
from .task import NukeTask

LOGGER = logging.getLogger(__name__)


class Slave(core.RenderObject):
    """Render slave.  """

    _task = None
    task_stopped = Signal()

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
            ('stopped', self.task_stopped),
            ('remains_changed', self.queue.update_remains),
        ]

        self.task_stopped.connect(self.on_task_stopped)

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

        if value == self._task:
            return
        old = self._task
        _apply_on_signals(value, 'connect')
        self._task = value
        _apply_on_signals(old, 'disconnect')

    def _start_next(self):
        try:
            task = self.queue.get()
            assert isinstance(task, NukeTask)
            self.task = task
            try:
                task.start()
            except AlreadyRendering:
                task.state |= model.core.DISABLED
                self.on_task_stopped()
                self.info('任务可能正由其他进程渲染, 自动跳过')
                self.info('如果想强制渲染请手动再次勾选此任务')
                self._start_next()
        except StopIteration:
            self.task = None
            self.finished.emit()

    def start(self):
        """Overridde.  """

        if self.is_rendering:
            return

        self.started.emit()
        self._start_next()

    def abort(self):
        """Abort rendering.  """

        self.is_aborting = True
        task = self.task
        if isinstance(task, NukeTask):
            task.abort()

    def on_task_stopped(self):
        self._stop_timeout_timer()

    def on_started(self):
        LOGGER.debug('Render start')
        self.is_rendering = True
        self._start_timeout_timer()

    def on_aborted(self):
        LOGGER.debug('Render aborted.')

    def on_stopped(self):
        LOGGER.debug('Render stopped.')
        self.is_rendering = False
        self.is_aborting = False
        self.task = None

    def on_finished(self):
        LOGGER.debug('Render finished.')

    def on_time_out(self):
        task = self.task
        if isinstance(task, NukeTask):
            task.priority -= 1
            task.abort()

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
